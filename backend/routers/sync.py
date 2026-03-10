"""
Data Sync API — exposes sync status and manual trigger endpoints.
"""
from fastapi import APIRouter, Depends, BackgroundTasks
import sqlite3
from database import get_db

router = APIRouter()


@router.get("/status")
def get_sync_status():
    """Get current sync status for all data sources."""
    try:
        from services.scheduler import get_sync_status
        return get_sync_status()
    except Exception as e:
        return {
            'scheduler_running': False,
            'error': str(e),
            'sources': {
                'usgs':  {'status': 'unknown', 'last_run': None},
                'noaa':  {'status': 'unknown', 'last_run': None},
                'grace': {'status': 'unknown', 'last_run': None},
            }
        }


@router.post("/trigger/usgs")
def trigger_usgs_sync(background_tasks: BackgroundTasks):
    """Manually trigger USGS data sync."""
    from services.usgs_sync import sync_usgs_to_db
    background_tasks.add_task(sync_usgs_to_db)
    return {"message": "USGS sync triggered", "status": "running"}


@router.post("/trigger/noaa")
def trigger_noaa_sync(background_tasks: BackgroundTasks):
    """Manually trigger NOAA climate data sync."""
    from services.noaa_climate import sync_noaa_to_db
    background_tasks.add_task(sync_noaa_to_db)
    return {"message": "NOAA sync triggered", "status": "running"}


@router.post("/trigger/grace")
def trigger_grace_sync(background_tasks: BackgroundTasks):
    """Manually trigger NASA GRACE satellite sync."""
    from services.nasa_grace import sync_nasa_grace_to_db
    background_tasks.add_task(sync_nasa_grace_to_db)
    return {"message": "NASA GRACE sync triggered", "status": "running"}


@router.post("/trigger/all")
def trigger_all_syncs(background_tasks: BackgroundTasks):
    """Trigger all data source syncs at once."""
    from services.usgs_sync import sync_usgs_to_db
    from services.noaa_climate import sync_noaa_to_db
    from services.nasa_grace import sync_nasa_grace_to_db
    background_tasks.add_task(sync_usgs_to_db)
    background_tasks.add_task(sync_noaa_to_db)
    background_tasks.add_task(sync_nasa_grace_to_db)
    return {"message": "All syncs triggered", "status": "running"}


@router.get("/log")
def get_sync_log(limit: int = 20, db: sqlite3.Connection = Depends(get_db)):
    """Get the last N sync log entries."""
    try:
        rows = db.execute('''
            SELECT * FROM sync_log
            ORDER BY synced_at DESC LIMIT ?
        ''', (limit,)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


@router.get("/climate/{aquifer_id}")
def get_climate_data(aquifer_id: int, days: int = 30, db: sqlite3.Connection = Depends(get_db)):
    """Get climate data for an aquifer."""
    try:
        rows = db.execute('''
            SELECT * FROM climate_data
            WHERE aquifer_id=?
            ORDER BY data_date DESC LIMIT ?
        ''', (aquifer_id, days)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


@router.get("/grace/{aquifer_id}")
def get_grace_anomalies(aquifer_id: int, db: sqlite3.Connection = Depends(get_db)):
    """Get NASA GRACE anomaly history for an aquifer."""
    try:
        rows = db.execute('''
            SELECT * FROM grace_anomalies
            WHERE aquifer_id=?
            ORDER BY synced_at DESC LIMIT 24
        ''', (aquifer_id,)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
