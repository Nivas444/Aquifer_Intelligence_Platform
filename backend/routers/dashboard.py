from fastapi import APIRouter, Depends
import sqlite3
from database import get_db

router = APIRouter()

@router.get("/overview")
def get_overview(db: sqlite3.Connection = Depends(get_db)):
    # Aquifer stats
    aq_stats = db.execute('''
        SELECT COUNT(*) as total,
               SUM(CASE WHEN status='critical' THEN 1 ELSE 0 END) as critical,
               SUM(CASE WHEN status='high' THEN 1 ELSE 0 END) as high,
               SUM(CASE WHEN status='moderate' THEN 1 ELSE 0 END) as moderate,
               SUM(CASE WHEN status='normal' THEN 1 ELSE 0 END) as normal,
               AVG(stress_level) as avg_stress,
               AVG(extraction_rate) as avg_extraction,
               AVG(recharge_rate) as avg_recharge
        FROM aquifers
    ''').fetchone()

    # Well stats
    well_stats = db.execute('''
        SELECT COUNT(*) as total,
               SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) as active,
               SUM(CASE WHEN water_level_change < -2 THEN 1 ELSE 0 END) as critical_decline,
               AVG(water_level_change) as avg_change
        FROM wells
    ''').fetchone()

    # Alert stats
    alert_stats = db.execute('''
        SELECT COUNT(*) as total,
               SUM(CASE WHEN severity='critical' THEN 1 ELSE 0 END) as critical,
               SUM(CASE WHEN severity='high' THEN 1 ELSE 0 END) as high,
               SUM(CASE WHEN is_acknowledged=0 THEN 1 ELSE 0 END) as unread
        FROM alerts WHERE is_active=1
    ''').fetchone()

    # Top stressed aquifers
    top_stressed = db.execute('''
        SELECT id, name, region, state, stress_level, status, water_level_m 
        FROM aquifers ORDER BY stress_level DESC LIMIT 5
    ''').fetchall()

    # Recent alerts
    recent_alerts = db.execute('''
        SELECT al.id, al.title, al.severity, al.created_at, a.name as aquifer_name
        FROM alerts al
        LEFT JOIN aquifers a ON a.id=al.aquifer_id
        WHERE al.is_active=1
        ORDER BY al.created_at DESC LIMIT 5
    ''').fetchall()

    return {
        "aquifers": dict(aq_stats),
        "wells": dict(well_stats),
        "alerts": dict(alert_stats),
        "top_stressed": [dict(r) for r in top_stressed],
        "recent_alerts": [dict(r) for r in recent_alerts]
    }

@router.get("/trends")
def get_trends(days: int = 30, db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute('''
        SELECT DATE(wr.timestamp) as date,
               AVG(wr.water_level_m) as avg_level,
               COUNT(DISTINCT wr.well_id) as wells_reporting
        FROM well_readings wr
        WHERE wr.timestamp >= datetime('now', ? || ' days')
        GROUP BY DATE(wr.timestamp)
        ORDER BY date ASC
    ''', (f'-{days}',)).fetchall()
    return [dict(r) for r in rows]

@router.get("/stress-distribution")
def get_stress_distribution(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute('''
        SELECT status, COUNT(*) as count, AVG(stress_level) as avg_stress
        FROM aquifers GROUP BY status
    ''').fetchall()
    return [dict(r) for r in rows]

@router.get("/regional-summary")
def get_regional_summary(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute('''
        SELECT state,
               COUNT(*) as aquifer_count,
               AVG(stress_level) as avg_stress,
               SUM(extraction_rate) as total_extraction,
               SUM(recharge_rate) as total_recharge,
               MAX(stress_level) as max_stress
        FROM aquifers
        GROUP BY state
        ORDER BY avg_stress DESC
    ''').fetchall()
    return [dict(r) for r in rows]
