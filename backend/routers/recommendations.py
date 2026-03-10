from fastapi import APIRouter, Depends, Query, HTTPException
import sqlite3
from database import get_db

router = APIRouter()

@router.get("/")
def get_recommendations(
    site_type: str = Query(..., description="Type of facility to build: farm, industry, or data_center"),
    limit: int = Query(5, description="Number of recommendations to return"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    Get top recommended aquifers for building a specific facility type.
    Uses real synced data (USGS, NOAA, NASA GRACE) to calculate suitability.
    """
    valid_types = ['farm', 'industry', 'data_center']
    if site_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid site_type. Must be one of {valid_types}")

    # Fetch aquifers and join with their latest synced data
    query = """
    SELECT 
        a.id, a.name, a.region, a.state, a.area_km2, a.depth_m as base_depth_m,
        
        -- NASA GRACE (Satellite Anomaly)
        (SELECT anomaly_cm FROM grace_anomalies ga WHERE ga.aquifer_id = a.id ORDER BY synced_at DESC LIMIT 1) as grace_anomaly_cm,
        
        -- NOAA (Climate)
        (SELECT drought_index FROM climate_data cd WHERE cd.aquifer_id = a.id ORDER BY synced_at DESC LIMIT 1) as noaa_drought_index,
        (SELECT precip_mm FROM climate_data cd WHERE cd.aquifer_id = a.id ORDER BY synced_at DESC LIMIT 1) as noaa_precip_mm,
        (SELECT recharge_factor FROM climate_data cd WHERE cd.aquifer_id = a.id ORDER BY synced_at DESC LIMIT 1) as noaa_recharge_factor,
        
        -- USGS (Active Wells Water Level Avg)
        (SELECT AVG(water_level_m) FROM wells w WHERE w.aquifer_id = a.id AND w.status = 'active') as usgs_avg_water_level_m
        
    FROM aquifers a
    """
    
    try:
        rows = db.execute(query).fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")

    results = []
    
    for r in rows:
        data = dict(r)
        
        # Use fallback values if sync data is missing (e.g. hasn't synced yet)
        anomaly = data['grace_anomaly_cm'] if data['grace_anomaly_cm'] is not None else 0
        drought = data['noaa_drought_index'] if data['noaa_drought_index'] is not None else 0.5
        precip = data['noaa_precip_mm'] if data['noaa_precip_mm'] is not None else 50
        recharge = data['noaa_recharge_factor'] if data['noaa_recharge_factor'] is not None else 1.0
        water_level = data['usgs_avg_water_level_m'] if data['usgs_avg_water_level_m'] is not None else data['base_depth_m']
        
        score = 0
        
        # Scoring Logic based on Site Type
        if site_type == 'farm':
            # Farm: Needs high precip, good recharge, and shallow water for cheap pumping
            # Base 50 points
            score = 50
            # Up to +20 points for precipitation (> 100mm is ideal)
            score += min(20, (precip / 100) * 20)
            # Up to +20 points for good recharge
            score += recharge * 20
            # Up to +10 points for shallow water (< 30m is ideal)
            score += max(0, 10 - (water_level / 3))
            
            # Penalize heavily for drought
            score -= drought * 30
            
        elif site_type == 'industry':
            # Industry: Needs stable storage (low depletion anomaly) and can handle deeper pumping
            # Base 50 points
            score = 50
            # Up to +30 points for positive or slightly negative GRACE anomaly (stable storage)
            # A highly negative anomaly (e.g. -20cm) means severe depletion.
            anomaly_score = max(0, 30 + anomaly) # -30 or worse = 0 points
            score += min(30, anomaly_score)
            
            # Up to +20 points for area size (larger aquifer = more resistant)
            area_score = min(20, (data['area_km2'] / 100000) * 20) if data['area_km2'] else 10
            score += area_score
            
            # Moderate penalty for deep pumping costs
            score -= (water_level / 10)
            
        elif site_type == 'data_center':
            # Data Center: Prioritizes absolute lowest disaster risk and stress (extreme stability)
            # Base 60 points
            score = 60
            
            # Must avoid extreme drought
            score -= drought * 40
            
            # Must avoid severe depletion (heavy penalty for negative GRACE anomaly)
            if anomaly < -10:
                score -= 30
            elif anomaly < -5:
                score -= 10
            else:
                score += 20  # highly stable
                
            # Prefer larger bodies of water for thermal mass/cooling reliability
            area_score = min(20, (data['area_km2'] / 50000) * 20) if data['area_km2'] else 10
            score += area_score
            
        # Bound score between 0 and 100
        final_score = max(0, min(100, round(score)))
        
        # Prepare response object
        data['suitability_score'] = final_score
        data['site_type_evaluated'] = site_type
        
        # Add a reason based on score components for frontend display
        if site_type == 'farm':
            data['key_factor'] = f"Precipitation: {precip}mm, Average Well Depth: {round(water_level, 1)}m"
        elif site_type == 'industry':
            data['key_factor'] = f"Storage Anomaly: {round(anomaly, 1)}cm, Area: {data['area_km2']} km²"
        elif site_type == 'data_center':
            data['key_factor'] = f"Drought Index: {round(drought, 2)}, Storage Anomaly: {round(anomaly, 1)}cm"
            
        results.append(data)
        
    # Sort by score descending and return limit
    results.sort(key=lambda x: x['suitability_score'], reverse=True)
    return {"recommendations": results[:limit]}
