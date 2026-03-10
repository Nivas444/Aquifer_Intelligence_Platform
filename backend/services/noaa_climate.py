"""
NOAA Climate Data Online — Precipitation & Drought Sync
Fixed drought monitor API endpoint.
"""
import urllib.request
import urllib.parse
import json
import sqlite3
import logging
from datetime import datetime, timedelta, date
from config import NOAA_API_KEY, DATABASE_PATH, NOAA_CDO_BASE, NOAA_STATIONS

logger = logging.getLogger(__name__)

# Correct NOAA Drought Monitor endpoint
DROUGHT_API = 'https://droughtmonitor.unl.edu/DmData/GISData.aspx'
DROUGHT_JSON = 'https://droughtmonitor.unl.edu/api/webservice/comprehensivestats/'

def noaa_request(endpoint: str, params: dict) -> dict | None:
    query = urllib.parse.urlencode(params)
    url   = f"{NOAA_CDO_BASE}/{endpoint}?{query}"
    try:
        req = urllib.request.Request(url, headers={
            'token': NOAA_API_KEY,
            'User-Agent': 'AquiferIntelligencePlatform/1.0'
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.warning(f"NOAA CDO [{endpoint}]: {e}")
        return None

def fetch_noaa_precipitation(station_id: str, days: int = 30) -> list:
    end_date   = date.today()
    start_date = end_date - timedelta(days=days)
    data = noaa_request('data', {
        'datasetid':  'GHCND',
        'stationid':  station_id,
        'datatypeid': 'PRCP',
        'startdate':  start_date.isoformat(),
        'enddate':    end_date.isoformat(),
        'limit':      days + 5,
        'units':      'metric',
    })
    if not data or 'results' not in data:
        return []
    return [{'date': r['date'][:10], 'value_mm': round(float(r['value']) / 10, 2)}
            for r in data['results'] if r.get('value') is not None]

def fetch_noaa_temperature(station_id: str, days: int = 30) -> list:
    end_date   = date.today()
    start_date = end_date - timedelta(days=days)
    data = noaa_request('data', {
        'datasetid':  'GHCND',
        'stationid':  station_id,
        'datatypeid': 'TMAX,TMIN',
        'startdate':  start_date.isoformat(),
        'enddate':    end_date.isoformat(),
        'limit':      days * 2 + 10,
        'units':      'metric',
    })
    if not data or 'results' not in data:
        return []
    by_date = {}
    for r in data['results']:
        d = r['date'][:10]
        if d not in by_date:
            by_date[d] = {}
        by_date[d][r['datatype']] = float(r['value']) / 10
    return [{'date': d, 'tmax_c': v.get('TMAX', 25), 'tmin_c': v.get('TMIN', 10)}
            for d, v in sorted(by_date.items())]

def fetch_drought_monitor(state_abbr: str) -> dict | None:
    """Fetch US Drought Monitor — corrected endpoint."""
    end   = date.today()
    start = end - timedelta(days=14)
    # Correct working URL format
    url = (f"https://droughtmonitor.unl.edu/api/webservice/comprehensivestats/"
           f"?aoi={state_abbr}&startdate={start}&enddate={end}&statisticstype=2")
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'AquiferIntelligencePlatform/1.0',
            'Accept': 'application/json'
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if data and isinstance(data, list) and len(data) > 0:
                latest = data[-1]
                return {
                    'd0_pct': float(latest.get('D0', 0)),
                    'd1_pct': float(latest.get('D1', 0)),
                    'd2_pct': float(latest.get('D2', 0)),
                    'd3_pct': float(latest.get('D3', 0)),
                    'd4_pct': float(latest.get('D4', 0)),
                }
    except Exception as e:
        logger.warning(f"Drought monitor ({state_abbr}): {e}")
    return None

def drought_to_recharge_factor(drought_data: dict) -> float:
    if not drought_data:
        return 1.0
    weighted = (
        drought_data.get('d0_pct', 0) * 0.10 +
        drought_data.get('d1_pct', 0) * 0.30 +
        drought_data.get('d2_pct', 0) * 0.50 +
        drought_data.get('d3_pct', 0) * 0.70 +
        drought_data.get('d4_pct', 0) * 0.90
    ) / 100
    return round(max(0.05, 1.0 - weighted), 3)

def estimate_eto(tmax: float, tmin: float) -> float:
    tmean = (tmax + tmin) / 2
    td    = max(0, tmax - tmin)
    eto   = 0.0023 * (tmean + 17.8) * (td ** 0.5) * 4.0
    return round(max(0, eto), 2)

def sync_noaa_to_db(db_path: str = DATABASE_PATH) -> dict:
    """Main NOAA sync."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS sync_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT, synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        wells_updated INTEGER, readings_added INTEGER, errors INTEGER, status TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS climate_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aquifer_id INTEGER NOT NULL,
        data_date DATE NOT NULL,
        precip_mm REAL, tmax_c REAL, tmin_c REAL,
        eto_mm REAL, drought_index REAL DEFAULT 0, recharge_factor REAL DEFAULT 1.0,
        source TEXT DEFAULT 'NOAA',
        synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(aquifer_id, data_date),
        FOREIGN KEY (aquifer_id) REFERENCES aquifers(id)
    )''')

    from config import AQUIFER_STATES
    updated = 0
    errors  = 0
    aquifers = c.execute('SELECT id, name, state, recharge_rate FROM aquifers').fetchall()

    for aq in aquifers:
        aq_id      = aq['id']
        station_id = NOAA_STATIONS.get(aq_id)
        if not station_id:
            continue

        precip_data  = fetch_noaa_precipitation(station_id, days=30)
        temp_data    = fetch_noaa_temperature(station_id, days=30)
        temp_by_date = {t['date']: t for t in temp_data}

        states       = AQUIFER_STATES.get(aq_id, [aq['state']])
        drought      = fetch_drought_monitor(states[0] if states else aq['state'])
        rf_factor    = drought_to_recharge_factor(drought)

        total_precip = sum(p['value_mm'] for p in precip_data)

        for p in precip_data:
            d    = p['date']
            temp = temp_by_date.get(d, {})
            tmax = temp.get('tmax_c', 25)
            tmin = temp.get('tmin_c', 10)
            eto  = estimate_eto(tmax, tmin)
            c.execute('''INSERT OR REPLACE INTO climate_data
                (aquifer_id, data_date, precip_mm, tmax_c, tmin_c, eto_mm, drought_index, recharge_factor)
                VALUES (?,?,?,?,?,?,?,?)''',
                (aq_id, d, p['value_mm'], tmax, tmin, eto, 1-rf_factor, rf_factor))

        new_recharge = round(max(0.1, aq['recharge_rate'] * rf_factor), 3)
        c.execute('UPDATE aquifers SET recharge_rate=?, last_updated=CURRENT_TIMESTAMP WHERE id=?',
                  (new_recharge, aq_id))

        # Auto drought alert if severe
        drought_pct = (drought.get('d3_pct',0) + drought.get('d4_pct',0)) if drought else 0
        if drought_pct > 30:
            existing = c.execute(
                "SELECT id FROM alerts WHERE aquifer_id=? AND alert_type='drought' AND is_active=1",
                (aq_id,)
            ).fetchone()
            if not existing:
                c.execute('''INSERT INTO alerts (aquifer_id, alert_type, severity, title, message, region)
                    SELECT id,'drought','high',
                    'Severe Drought: '||name,
                    'NOAA shows '||?||'% of region in extreme drought. Recharge significantly impacted.',
                    region FROM aquifers WHERE id=?''', (round(drought_pct), aq_id))

        updated += 1
        logger.info(f"NOAA: {aq['name']} precip={total_precip:.1f}mm rf={rf_factor:.2f}")

    c.execute('''INSERT INTO sync_log (source, wells_updated, readings_added, errors, status)
                 VALUES ('NOAA',?,?,?,?)''',
              (updated, len(aquifers)*30, errors, 'success' if errors==0 else 'partial'))
    conn.commit()
    conn.close()

    result = {'source':'NOAA','synced_at':datetime.now().isoformat(),
              'updated':updated,'errors':errors,'status':'success' if errors==0 else 'partial'}
    logger.info(f"NOAA sync complete: {result}")
    return result