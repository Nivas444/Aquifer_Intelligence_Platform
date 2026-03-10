from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import sqlite3
from database import get_db
from typing import Optional
from datetime import datetime

router = APIRouter()

class AlertAcknowledge(BaseModel):
    acknowledged_by: Optional[str] = None

@router.get("/")
def get_alerts(
    severity: Optional[str] = None,
    is_active: Optional[bool] = True,
    aquifer_id: Optional[int] = None,
    limit: int = 50,
    db: sqlite3.Connection = Depends(get_db)
):
    query = '''SELECT al.*, a.name as aquifer_name 
               FROM alerts al 
               LEFT JOIN aquifers a ON a.id=al.aquifer_id 
               WHERE 1=1'''
    params = []
    if severity:
        query += " AND al.severity=?"
        params.append(severity)
    if is_active is not None:
        query += " AND al.is_active=?"
        params.append(1 if is_active else 0)
    if aquifer_id:
        query += " AND al.aquifer_id=?"
        params.append(aquifer_id)
    query += f" ORDER BY CASE al.severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'moderate' THEN 3 ELSE 4 END, al.created_at DESC LIMIT {limit}"
    rows = db.execute(query, params).fetchall()
    return [dict(r) for r in rows]

@router.get("/summary")
def get_alerts_summary(db: sqlite3.Connection = Depends(get_db)):
    total = db.execute("SELECT COUNT(*) as cnt FROM alerts WHERE is_active=1").fetchone()["cnt"]
    critical = db.execute("SELECT COUNT(*) as cnt FROM alerts WHERE severity='critical' AND is_active=1").fetchone()["cnt"]
    high = db.execute("SELECT COUNT(*) as cnt FROM alerts WHERE severity='high' AND is_active=1").fetchone()["cnt"]
    moderate = db.execute("SELECT COUNT(*) as cnt FROM alerts WHERE severity='moderate' AND is_active=1").fetchone()["cnt"]
    unacknowledged = db.execute("SELECT COUNT(*) as cnt FROM alerts WHERE is_active=1 AND is_acknowledged=0").fetchone()["cnt"]
    return {
        "total": total,
        "critical": critical,
        "high": high,
        "moderate": moderate,
        "unacknowledged": unacknowledged
    }

@router.put("/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int, req: AlertAcknowledge, db: sqlite3.Connection = Depends(get_db)):
    alert = db.execute("SELECT id FROM alerts WHERE id=?", (alert_id,)).fetchone()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    db.execute(
        "UPDATE alerts SET is_acknowledged=1, acknowledged_at=? WHERE id=?",
        (datetime.now().isoformat(), alert_id)
    )
    db.commit()
    return {"message": "Alert acknowledged"}

@router.put("/{alert_id}/unacknowledge")
def unacknowledge_alert(alert_id: int, req: AlertAcknowledge, db: sqlite3.Connection = Depends(get_db)):
    alert = db.execute("SELECT id FROM alerts WHERE id=?", (alert_id,)).fetchone()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    db.execute(
        "UPDATE alerts SET is_acknowledged=0, acknowledged_at=NULL WHERE id=?",
        (alert_id,)
    )
    db.commit()
    return {"message": "Alert unacknowledged"}

@router.put("/{alert_id}/resolve")
def resolve_alert(alert_id: int, db: sqlite3.Connection = Depends(get_db)):
    db.execute("UPDATE alerts SET is_active=0 WHERE id=?", (alert_id,))
    db.commit()
    return {"message": "Alert resolved"}

@router.get("/recent")
def get_recent_alerts(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute('''
        SELECT al.*, a.name as aquifer_name 
        FROM alerts al 
        LEFT JOIN aquifers a ON a.id=al.aquifer_id 
        WHERE al.is_active=1
        ORDER BY al.created_at DESC LIMIT 5
    ''').fetchall()
    return [dict(r) for r in rows]
