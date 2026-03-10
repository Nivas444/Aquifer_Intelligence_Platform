from fastapi import APIRouter, Depends, HTTPException
import sqlite3
from database import get_db
from typing import Optional
import math, random
from datetime import datetime, timedelta

router = APIRouter()

def ai_forecast_model(base_level, extraction, recharge, days_ahead, seasonal_factor=1.0):
    """
    Simple AI forecasting model using linear regression + seasonal adjustment.
    In production, replace with trained ML model (scikit-learn/Prophet).
    """
    net_change_per_day = (recharge - extraction) * 0.005
    results = []
    for day in range(1, days_ahead + 1):
        # Seasonal sine wave (annual cycle)
        seasonal = math.sin((day / 365) * 2 * math.pi) * 1.5 * seasonal_factor
        # Trend component
        trend = net_change_per_day * day
        # Uncertainty grows with time
        uncertainty = 0.1 * math.sqrt(day)
        predicted = base_level + trend + seasonal
        confidence = max(0.5, 0.95 - day * 0.0008)
        results.append({
            "day": day,
            "predicted_level_m": round(predicted, 2),
            "lower_bound": round(predicted - uncertainty, 2),
            "upper_bound": round(predicted + uncertainty, 2),
            "confidence": round(confidence, 3)
        })
    return results

@router.get("/aquifer/{aquifer_id}")
def forecast_aquifer(
    aquifer_id: int,
    days: int = 90,
    db: sqlite3.Connection = Depends(get_db)
):
    aq = db.execute("SELECT * FROM aquifers WHERE id=?", (aquifer_id,)).fetchone()
    if not aq:
        raise HTTPException(status_code=404, detail="Aquifer not found")
    aq = dict(aq)

    forecast = ai_forecast_model(
        aq["water_level_m"], aq["extraction_rate"], aq["recharge_rate"], days
    )

    # Add date labels
    for i, f in enumerate(forecast):
        f["date"] = (datetime.now() + timedelta(days=i+1)).strftime("%Y-%m-%d")

    return {
        "aquifer": {"id": aq["id"], "name": aq["name"], "status": aq["status"]},
        "current_level_m": aq["water_level_m"],
        "forecast_days": days,
        "model": "Aquifer-AI v1.0",
        "forecast": forecast
    }

@router.get("/demand/{aquifer_id}")
def forecast_demand(aquifer_id: int, days: int = 90, db: sqlite3.Connection = Depends(get_db)):
    aq = db.execute("SELECT * FROM aquifers WHERE id=?", (aquifer_id,)).fetchone()
    if not aq:
        raise HTTPException(status_code=404, detail="Aquifer not found")
    aq = dict(aq)

    base_demand = aq["extraction_rate"]
    results = []
    for day in range(1, days + 1):
        date = (datetime.now() + timedelta(days=day)).strftime("%Y-%m-%d")
        # Agricultural + urban demand with seasonal peak in summer
        seasonal_multiplier = 1.0 + 0.3 * math.sin((day / 365 - 0.25) * 2 * math.pi)
        growth_trend = 1 + (0.002 * day / 365)  # 0.2% monthly growth
        demand = base_demand * seasonal_multiplier * growth_trend
        agricultural = demand * 0.72
        urban = demand * 0.18
        industrial = demand * 0.10
        results.append({
            "date": date,
            "total_demand_mm3": round(demand, 3),
            "agricultural_mm3": round(agricultural, 3),
            "urban_mm3": round(urban, 3),
            "industrial_mm3": round(industrial, 3),
            "demand_index": round(demand / base_demand, 3)
        })
    return {
        "aquifer": {"id": aq["id"], "name": aq["name"]},
        "base_demand": base_demand,
        "forecast": results
    }

@router.get("/summary")
def get_forecast_summary(db: sqlite3.Connection = Depends(get_db)):
    aquifers = db.execute("SELECT * FROM aquifers ORDER BY stress_level DESC LIMIT 5").fetchall()
    summaries = []
    for aq in aquifers:
        aq = dict(aq)
        forecast_30 = ai_forecast_model(
            aq["water_level_m"], aq["extraction_rate"], aq["recharge_rate"], 30
        )
        forecast_90 = ai_forecast_model(
            aq["water_level_m"], aq["extraction_rate"], aq["recharge_rate"], 90
        )
        level_30d = forecast_30[-1]["predicted_level_m"]
        level_90d = forecast_90[-1]["predicted_level_m"]
        summaries.append({
            "aquifer_id": aq["id"],
            "aquifer_name": aq["name"],
            "current_level": aq["water_level_m"],
            "predicted_30d": level_30d,
            "predicted_90d": level_90d,
            "change_30d": round(level_30d - aq["water_level_m"], 2),
            "change_90d": round(level_90d - aq["water_level_m"], 2),
            "risk_level": aq["status"]
        })
    return summaries

@router.get("/scarcity-risk")
def get_scarcity_risk(db: sqlite3.Connection = Depends(get_db)):
    aquifers = db.execute("SELECT * FROM aquifers").fetchall()
    risks = []
    for aq in aquifers:
        aq = dict(aq)
        # Simple risk score: stress_level * extraction/recharge ratio
        ratio = aq["extraction_rate"] / max(aq["recharge_rate"], 0.1)
        risk_score = (aq["stress_level"] * 0.6 + min(ratio / 20, 1.0) * 0.4) * 100
        risks.append({
            "aquifer_id": aq["id"],
            "aquifer_name": aq["name"],
            "region": aq["region"],
            "state": aq["state"],
            "stress_level": aq["stress_level"],
            "extraction_recharge_ratio": round(ratio, 2),
            "risk_score": round(risk_score, 1),
            "risk_category": "critical" if risk_score > 75 else "high" if risk_score > 50 else "moderate" if risk_score > 25 else "low"
        })
    risks.sort(key=lambda x: x["risk_score"], reverse=True)
    return risks
