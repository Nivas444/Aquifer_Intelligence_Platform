from fastapi import APIRouter, Depends, HTTPException, Query
import sqlite3
from database import get_db
from typing import Optional

router = APIRouter()

@router.get("/")
def get_aquifers(
    status: Optional[str] = None,
    state: Optional[str] = None,
    db: sqlite3.Connection = Depends(get_db)
):
    query = "SELECT * FROM aquifers WHERE 1=1"
    params = []
    if status:
        query += " AND status=?"
        params.append(status)
    if state:
        query += " AND state=?"
        params.append(state)
    query += " ORDER BY stress_level DESC"
    rows = db.execute(query, params).fetchall()
    return [dict(r) for r in rows]

@router.get("/map")
def get_aquifer_map(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute('''
        SELECT a.*, 
               COUNT(w.id) as well_count,
               AVG(w.water_level_m) as avg_water_level
        FROM aquifers a
        LEFT JOIN wells w ON w.aquifer_id = a.id AND w.status='active'
        GROUP BY a.id
        ORDER BY a.stress_level DESC
    ''').fetchall()
    return [dict(r) for r in rows]

@router.get("/geojson")
def get_aquifer_geojson(db: sqlite3.Connection = Depends(get_db)):
    """Return a GeoJSON FeatureCollection representing aquifer stress as a grid.

    The grid covers each aquifer's bounding box (from config.AQUIFER_BBOX) with
    square cells of fixed degree size.  Each cell inherits the stress level of
    its aquifer.  This mimics the tiled appearance of the NASA/GRACE map.
    """
    import math
    from services.nasa_grace import AQUIFER_BBOX

    # pull current stress levels from database
    rows = db.execute("SELECT id, stress_level, status, name, region, state FROM aquifers").fetchall()
    stress_map = {r[0]: {'stress': r[1], 'status': r[2], 'name': r[3], 'region': r[4], 'state': r[5]} for r in rows}

    features = []
    cell_deg = 0.5  # grid resolution in degrees (~55 km at mid lat)

    # helper to convert average water_level_change to 0‑1 stress
    def change_to_stress(change, default):
        if change is None:
            return default
        # more negative -> higher stress; map -5m or lower to 1.0
        val = -change / 5.0
        return max(0.0, min(1.0, val))

    for aq_id, bbox in AQUIFER_BBOX.items():
        south, west, north, east = bbox
        stinfo = stress_map.get(aq_id, {})
        aquifer_default = stinfo.get('stress', 0) or 0
        status = stinfo.get('status', '')
        name = stinfo.get('name', '')
        region = stinfo.get('region', '')

        # PRE-FETCH: Move these outside the lat/lng loops as they are per-aquifer
        # NOAA adjustment: recent recharge factor <1 increases stress
        recharge_adj = 0
        dr = db.execute(
            "SELECT recharge_factor FROM climate_data WHERE aquifer_id=? ORDER BY data_date DESC LIMIT 1",
            (aq_id,)
        ).fetchone()
        if dr and dr['recharge_factor'] is not None:
            recharge_adj = (1 - dr['recharge_factor'])

        # GRACE adjustment: negative anomaly increases stress
        grace_adj = 0
        ga = db.execute(
            "SELECT anomaly_cm FROM grace_anomalies WHERE aquifer_id=? ORDER BY measurement_date DESC LIMIT 1",
            (aq_id,)
        ).fetchone()
        if ga and ga['anomaly_cm'] is not None:
            grace_adj = (-ga['anomaly_cm'] / 40.0)

        # Pre-fetch wells for this aquifer to filter in memory (spatial join optimization)
        aq_wells = db.execute(
            "SELECT lat, lng, water_level_change FROM wells WHERE aquifer_id=?", 
            (aq_id,)
        ).fetchall()

        lat = south
        while lat < north:
            lng = west
            while lng < east:
                lat2 = min(lat + cell_deg, north)
                lng2 = min(lng + cell_deg, east)

                # Filter pre-fetched wells in memory for this cell
                cell_well_changes = [
                    w['water_level_change'] for w in aq_wells 
                    if lat <= w['lat'] < lat2 and lng <= w['lng'] < lng2
                ]
                
                avg_change = sum(cell_well_changes) / len(cell_well_changes) if cell_well_changes else None
                stress_val = change_to_stress(avg_change, aquifer_default)

                # Apply pre-fetched adjustments
                stress_val = max(0.0, min(1.0, stress_val + recharge_adj + grace_adj))

                coords = [[lng, lat], [lng2, lat], [lng2, lat2], [lng, lat2], [lng, lat]]
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [coords]},
                    "properties": {
                        "aquifer_id": aq_id,
                        "name": name,
                        "region": region,
                        "state": stinfo.get('state',''),
                        "stress_level": stress_val,
                        "status": status,
                        "avg_change": avg_change
                    }
                })
                lng += cell_deg
            lat += cell_deg

    return {"type": "FeatureCollection", "features": features}

@router.get("/stats")
def get_aquifer_stats(db: sqlite3.Connection = Depends(get_db)):
    total = db.execute("SELECT COUNT(*) as cnt FROM aquifers").fetchone()["cnt"]
    critical = db.execute("SELECT COUNT(*) as cnt FROM aquifers WHERE status='critical'").fetchone()["cnt"]
    high = db.execute("SELECT COUNT(*) as cnt FROM aquifers WHERE status='high'").fetchone()["cnt"]
    normal = db.execute("SELECT COUNT(*) as cnt FROM aquifers WHERE status='normal'").fetchone()["cnt"]
    avg_stress = db.execute("SELECT AVG(stress_level) as avg FROM aquifers").fetchone()["avg"]
    return {
        "total": total,
        "critical": critical,
        "high": high,
        "normal": normal,
        "avg_stress": round(avg_stress * 100, 1) if avg_stress else 0
    }

@router.get("/{aquifer_id}")
def get_aquifer(aquifer_id: int, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute("SELECT * FROM aquifers WHERE id=?", (aquifer_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Aquifer not found")
    return dict(row)

@router.get("/{aquifer_id}/wells")
def get_aquifer_wells(aquifer_id: int, db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(
        "SELECT * FROM wells WHERE aquifer_id=? ORDER BY last_reading DESC",
        (aquifer_id,)
    ).fetchall()
    return [dict(r) for r in rows]

@router.get("/{aquifer_id}/history")
def get_aquifer_history(aquifer_id: int, days: int = 90, db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute('''
        SELECT DATE(wr.timestamp) as date, 
               AVG(wr.water_level_m) as avg_level,
               MIN(wr.water_level_m) as min_level,
               MAX(wr.water_level_m) as max_level,
               COUNT(*) as reading_count
        FROM well_readings wr
        JOIN wells w ON w.id = wr.well_id
        WHERE w.aquifer_id=? 
          AND wr.timestamp >= datetime('now', ? || ' days')
        GROUP BY DATE(wr.timestamp)
        ORDER BY date ASC
    ''', (aquifer_id, f'-{days}')).fetchall()
    return [dict(r) for r in rows]
