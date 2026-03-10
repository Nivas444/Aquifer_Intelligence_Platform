"""
USGS Water Services — Real-Time Well Data Sync
Fetches live groundwater level readings from 850,000+ USGS monitoring wells.
API docs: https://waterservices.usgs.gov/rest/IV-Service.html
No API key required.
"""
import urllib.request
import urllib.parse
import json
import sqlite3
import logging
from datetime import datetime, timedelta
from config import USGS_BASE_URL, DATABASE_PATH, AQUIFER_STATES, USGS_PARAMS

logger = logging.getLogger(__name__)

# We used to hard‑code a handful of sites for each aquifer.  For real
# accuracy we now query USGS by state and use whatever wells are returned.
# The AQUIFER_STATES mapping (from config) lists the states within each
# aquifer’s footprint.

USGS_WELL_SITES = None  # deprecated


def fetch_usgs_sites(site_numbers: list[str]) -> list[dict]:
    """Fetch instantaneous values for a list of USGS site numbers."""
    if not site_numbers:
        return []

    sites_str = ','.join(site_numbers[:10])  # Max 10 per request
    params = urllib.parse.urlencode({
        'format': 'json',
        'sites': sites_str,
        'parameterCd': USGS_PARAMS['water_level_depth'],
        'siteType': 'GW',
        'siteStatus': 'active',
    })
    url = f"{USGS_BASE_URL}/iv/?{params}"

    try:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'AquiferIntelligencePlatform/1.0 (research@aquifer.io)',
                'Accept': 'application/json'
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return data.get('value', {}).get('timeSeries', [])
    except Exception as e:
        logger.error(f"USGS fetch error for sites {sites_str}: {e}")
        return []


def fetch_usgs_by_state(state_code: str, limit: int = 20) -> list[dict]:
    """Fetch groundwater wells for an entire state."""
    params = urllib.parse.urlencode({
        'format': 'json',
        'stateCd': state_code.lower(),
        'parameterCd': USGS_PARAMS['water_level_depth'],
        'siteType': 'GW',
        'siteStatus': 'active',
    })
    url = f"{USGS_BASE_URL}/iv/?{params}"

    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'AquiferIntelligencePlatform/1.0'}
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
            series = data.get('value', {}).get('timeSeries', [])
            return series[:limit]
    except Exception as e:
        logger.error(f"USGS state fetch error ({state_code}): {e}")
        return []


def parse_usgs_reading(time_series: dict) -> dict | None:
    """Parse a USGS timeSeries object into a clean reading dict."""
    try:
        source_info = time_series.get('sourceInfo', {})
        site_name   = source_info.get('siteName', 'Unknown Well')
        site_no     = source_info.get('siteCode', [{}])[0].get('value', '')
        geo         = source_info.get('geoLocation', {}).get('geogLocation', {})
        lat         = float(geo.get('latitude', 0))
        lng         = float(geo.get('longitude', 0))

        values = time_series.get('values', [{}])[0].get('value', [])
        if not values:
            return None

        latest      = values[-1]
        raw_value   = latest.get('value', '-999999')
        timestamp   = latest.get('dateTime', datetime.now().isoformat())

        if raw_value in ['-999999', '', None]:
            return None

        # USGS reports depth-to-water in feet — convert to meters
        depth_ft    = float(raw_value)
        depth_m     = round(depth_ft * 0.3048, 2)

        return {
            'site_no':        site_no,
            'name':           site_name[:80],
            'lat':            lat,
            'lng':            lng,
            'water_level_m':  depth_m,
            'timestamp':      timestamp,
            'source':         'USGS-live',
        }
    except Exception as e:
        logger.warning(f"Failed to parse USGS reading: {e}")
        return None


def sync_usgs_to_db(db_path: str = DATABASE_PATH) -> dict:
    """
    Main sync function — pulls live USGS data and writes to SQLite.
    Returns a summary of what was synced.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    synced_wells    = 0
    synced_readings = 0
    errors          = 0

    from config import AQUIFER_STATES
    # iterate aquifers, querying wells from all states in their footprint
    for aquifer_id, states in AQUIFER_STATES.items():
        logger.info(f"Syncing USGS data for aquifer {aquifer_id} (states {states})...")
        time_series_list = []
        # gather up to a few hundred sites per aquifer
        for state in states:
            series = fetch_usgs_by_state(state, limit=100)
            time_series_list.extend(series)

        for ts in time_series_list:
            reading = parse_usgs_reading(ts)
            if not reading:
                continue

            # Upsert well
            existing = c.execute(
                "SELECT id, water_level_m FROM wells WHERE site_no=?",
                (reading['site_no'],)
            ).fetchone()

            if existing:
                well_id   = existing['id']
                old_level = existing['water_level_m'] or reading['water_level_m']
                change    = round(reading['water_level_m'] - old_level, 2)
                c.execute('''
                    UPDATE wells SET
                        water_level_m      = ?,
                        water_level_change = ?,
                        last_reading       = ?,
                        status             = 'active'
                    WHERE id = ?
                ''', (reading['water_level_m'], change, reading['timestamp'], well_id))
            else:
                c.execute('''
                    INSERT INTO wells
                        (site_no, name, aquifer_id, lat, lng,
                         water_level_m, water_level_change, status, well_type, last_reading)
                    VALUES (?,?,?,?,?,?,0,'active','monitoring',?)
                ''', (
                    reading['site_no'], reading['name'], aquifer_id,
                    reading['lat'], reading['lng'],
                    reading['water_level_m'], reading['timestamp']
                ))
                well_id = c.lastrowid
                synced_wells += 1

            # Insert reading
            c.execute('''
                INSERT INTO well_readings (well_id, water_level_m, timestamp, source)
                VALUES (?,?,?,?)
            ''', (well_id, reading['water_level_m'], reading['timestamp'], 'USGS-live'))
            synced_readings += 1

        # Update aquifer average water level from real readings
        avg = c.execute('''
            SELECT AVG(w.water_level_m) as avg_level
            FROM wells w
            WHERE w.aquifer_id=? AND w.status='active'
              AND w.water_level_m IS NOT NULL
        ''', (aquifer_id,)).fetchone()

        if avg and avg['avg_level']:
            c.execute('''
                UPDATE aquifers SET
                    water_level_m = ?,
                    last_updated  = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (round(avg['avg_level'], 2), aquifer_id))

    # Log sync event
    c.execute('''
        CREATE TABLE IF NOT EXISTS sync_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT, synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            wells_updated INTEGER, readings_added INTEGER, errors INTEGER, status TEXT
        )
    ''')
    c.execute('''
        INSERT INTO sync_log (source, wells_updated, readings_added, errors, status)
        VALUES ('USGS', ?, ?, ?, ?)
    ''', (synced_wells, synced_readings, errors, 'success' if errors == 0 else 'partial'))

    conn.commit()
    conn.close()

    result = {
        'source': 'USGS',
        'synced_at': datetime.now().isoformat(),
        'new_wells': synced_wells,
        'readings_added': synced_readings,
        'errors': errors,
        'status': 'success'
    }
    logger.info(f"USGS sync complete: {result}")
    return result
