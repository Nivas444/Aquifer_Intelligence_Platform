from fastapi import APIRouter, Depends, HTTPException, Query
import sqlite3
from database import get_db
from typing import Optional

router = APIRouter()

@router.get("/")
def get_wells(
    aquifer_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 100,
    db: sqlite3.Connection = Depends(get_db)
):
    query = "SELECT w.*, a.name as aquifer_name FROM wells w LEFT JOIN aquifers a ON a.id=w.aquifer_id WHERE 1=1"
    params = []
    if aquifer_id:
        query += " AND w.aquifer_id=?"
        params.append(aquifer_id)
    if status:
        query += " AND w.status=?"
        params.append(status)
    query += f" ORDER BY w.last_reading DESC LIMIT {limit}"
    rows = db.execute(query, params).fetchall()
    return [dict(r) for r in rows]

@router.get("/map")
def get_wells_map(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute('''
        SELECT w.id, w.site_no, w.name, w.lat, w.lng, w.water_level_m, 
               w.water_level_change, w.status, w.depth_m,
               a.name as aquifer_name, a.status as aquifer_status,
               a.stress_level
        FROM wells w
        LEFT JOIN aquifers a ON a.id = w.aquifer_id
        WHERE w.status = 'active'
        ORDER BY w.water_level_change ASC
    ''').fetchall()
    return [dict(r) for r in rows]

@router.get("/stats")
def get_well_stats(db: sqlite3.Connection = Depends(get_db)):
    row = db.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) as active,
            SUM(CASE WHEN water_level_change < -1 THEN 1 ELSE 0 END) as declining,
            SUM(CASE WHEN water_level_change < -2 THEN 1 ELSE 0 END) as critical
        FROM wells
    ''').fetchone()
    return {
        "total": row["total"] or 0, 
        "active": row["active"] or 0, 
        "declining": row["declining"] or 0, 
        "critical": row["critical"] or 0
    }

@router.get("/{well_id}")
def get_well(well_id: int, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute('''
        SELECT w.*, a.name as aquifer_name, a.stress_level, a.status as aquifer_status
        FROM wells w LEFT JOIN aquifers a ON a.id=w.aquifer_id
        WHERE w.id=?
    ''', (well_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Well not found")
    return dict(row)

@router.get("/{well_id}/readings")
def get_well_readings(well_id: int, days: int = 30, db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute('''
        SELECT * FROM well_readings 
        WHERE well_id=? AND timestamp >= datetime('now', ? || ' days')
        ORDER BY timestamp ASC
    ''', (well_id, f'-{days}')).fetchall()
    return [dict(r) for r in rows]
