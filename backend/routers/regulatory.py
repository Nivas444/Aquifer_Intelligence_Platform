from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import sqlite3
import logging
from database import get_db
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()

class ReportCreate(BaseModel):
    title: str
    region: str
    report_type: str
    content: Optional[str] = ""

@router.get("/reports")
def get_reports(
    region: Optional[str] = None,
    report_type: Optional[str] = None,
    db: sqlite3.Connection = Depends(get_db)
):
    query = "SELECT * FROM regulatory_reports WHERE 1=1"
    params = []
    if region:
        query += " AND region=?"
        params.append(region)
    if report_type:
        query += " AND report_type=?"
        params.append(report_type)
    query += " ORDER BY created_at DESC"
    rows = db.execute(query, params).fetchall()
    return [dict(r) for r in rows]

@router.post("/reports")
def create_report(req: ReportCreate, db: sqlite3.Connection = Depends(get_db)):
    db.execute(
        "INSERT INTO regulatory_reports (title, region, report_type, content) VALUES (?,?,?,?)",
        (req.title, req.region, req.report_type, req.content)
    )
    db.commit()
    return {"message": "Report created successfully"}

@router.get("/compliance")
def get_compliance(db: sqlite3.Connection = Depends(get_db)):
    try:
        aquifers = db.execute("SELECT * FROM aquifers").fetchall()
        compliance = []
        for aq in aquifers:
            aq = dict(aq)
            ratio = aq["extraction_rate"] / max(aq["recharge_rate"], 0.1)
            compliant = ratio <= 1.5 and aq["stress_level"] < 0.7
            compliance.append({
                "aquifer_id": aq["id"],
                "aquifer_name": aq["name"],
                "region": aq["region"],
                "state": aq["state"],
                "extraction_recharge_ratio": round(ratio, 2),
                "stress_level": aq["stress_level"],
                "compliant": compliant,
                "violations": [] if compliant else (
                    ["Extraction exceeds sustainable yield"] if ratio > 1.5 else [] +
                    ["Stress level exceeds threshold"] if aq["stress_level"] >= 0.7 else []
                ),
                "recommended_action": (
                    "Immediate extraction reduction required" if aq["status"] == "critical" else
                    "Review extraction permits" if aq["status"] == "high" else
                    "Monitor and maintain current practices"
                )
            })
        return compliance
    except Exception as e:
        logger.error(f"Compliance query error: {e}")
        return []

@router.get("/permits")
def get_permit_summary(db: sqlite3.Connection = Depends(get_db)):
    try:
        # Simulated permit data based on aquifer status
        aquifers = db.execute("SELECT id, name, state, status, extraction_rate FROM aquifers").fetchall()
        permits = []
        for aq in aquifers:
            aq = dict(aq)
            permits.append({
                "aquifer_id": aq["id"],
                "aquifer_name": aq["name"],
                "state": aq["state"],
                "permitted_extraction": round(aq["extraction_rate"] * 1.1, 2),
                "actual_extraction": aq["extraction_rate"],
                "permit_status": "suspended" if aq["status"] == "critical" else "active",
                "next_review": "2025-06-01",
                "compliance_score": 95 if aq["status"] == "normal" else 70 if aq["status"] == "moderate" else 40
            })
        return permits
    except Exception as e:
        logger.error(f"Permits query error: {e}")
        return []

@router.get("/recommendations")
def get_recommendations(db: sqlite3.Connection = Depends(get_db)):
    try:
        aquifers = db.execute(
            "SELECT * FROM aquifers WHERE status IN ('critical','high') ORDER BY stress_level DESC"
        ).fetchall()
        recs = []
        for aq in aquifers:
            aq = dict(aq)
            recs.append({
                "aquifer_id": aq["id"],
                "aquifer_name": aq["name"],
                "priority": "urgent" if aq["status"] == "critical" else "high",
                "recommendations": [
                    f"Reduce extraction by {round((1 - aq['recharge_rate']/max(aq['extraction_rate'],0.1))*100)}%",
                    "Implement mandatory water conservation measures",
                    "Consider Managed Aquifer Recharge (MAR) programs",
                    "Restrict new extraction permits until levels recover",
                    "Establish inter-basin water transfer agreements"
                ] if aq["status"] == "critical" else [
                    "Review and cap current extraction permits",
                    "Increase monitoring frequency to weekly",
                    "Promote water recycling and reuse programs",
                    "Evaluate demand-side management options"
                ]
            })
        return recs
    except Exception as e:
        logger.error(f"Recommendations query error: {e}")
        return []
