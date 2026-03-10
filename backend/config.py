"""
Central config — reads from .env file automatically.
All services import from here.
"""
import os

def _load_env():
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, val = line.partition('=')
                os.environ.setdefault(key.strip(), val.strip())

_load_env()

# ── API Keys ──
NASA_EARTHDATA_TOKEN = os.environ.get('NASA_EARTHDATA_TOKEN', '')
NOAA_API_KEY         = os.environ.get('NOAA_API_KEY', '')
USGS_BASE_URL        = os.environ.get('USGS_BASE_URL', 'https://waterservices.usgs.gov/nwis')

# ── App ──
APP_SECRET_KEY  = os.environ.get('APP_SECRET_KEY', 'aquifer_secret_key_2024')
DATABASE_PATH   = os.environ.get('DATABASE_PATH', 'aquifer.db')
SYNC_INTERVAL   = int(os.environ.get('SYNC_INTERVAL_MINUTES', '15'))

# ── NASA GRACE endpoints ──
NASA_GRACE_BASE  = 'https://opendap.earthdata.nasa.gov'
NASA_CMR_SEARCH  = 'https://cmr.earthdata.nasa.gov/search'
NASA_PODAAC_BASE = 'https://podaac-tools.jpl.nasa.gov/drive/files/allData/tellus'

# ── NOAA endpoints ──
NOAA_CDO_BASE    = 'https://www.ncdc.noaa.gov/cdo-web/api/v2'
NOAA_DROUGHT_API = 'https://droughtmonitor.unl.edu/api'

# ── USGS parameter codes ──
USGS_PARAMS = {
    'water_level_depth':  '72019',   # Depth to water level (ft below land surface)
    'water_level_elev':   '72020',   # Water level elevation (ft NAVD88)
    'discharge':          '00060',   # Stream discharge
    'groundwater_level':  '63680',   # Turbidity (proxy)
}

# ── US States covered by each aquifer ──
AQUIFER_STATES = {
    1:  ['KS', 'NE', 'CO', 'OK', 'TX', 'SD', 'WY', 'NM'],  # Ogallala
    2:  ['CA'],                                               # Central Valley
    3:  ['TX'],                                               # Edwards
    4:  ['FL', 'GA', 'AL', 'SC'],                            # Floridan
    5:  ['WA', 'OR', 'ID'],                                   # Columbia Plateau
    6:  ['ID'],                                               # Snake River Plain
    7:  ['MS', 'AR', 'TN', 'MO'],                            # Mississippi Embayment
    8:  ['CO'],                                               # Denver Basin
    9:  ['VA', 'MD', 'NC', 'NJ'],                            # Atlantic Coastal Plain
    10: ['OR'],                                               # Willamette Valley
}

# ── NOAA station IDs for each aquifer region ──
NOAA_STATIONS = {
    1:  'GHCND:USW00013967',   # Dodge City KS (Ogallala)
    2:  'GHCND:USW00023232',   # Fresno CA (Central Valley)
    3:  'GHCND:USW00012921',   # San Antonio TX (Edwards)
    4:  'GHCND:USW00012844',   # Tampa FL (Floridan)
    5:  'GHCND:USW00024157',   # Spokane WA (Columbia Plateau)
    6:  'GHCND:USW00024131',   # Boise ID (Snake River Plain)
    7:  'GHCND:USW00013893',   # Jackson MS (Mississippi)
    8:  'GHCND:USW00003017',   # Denver CO (Denver Basin)
    9:  'GHCND:USW00013741',   # Richmond VA (Atlantic Coastal)
    10: 'GHCND:USW00024232',   # Salem OR (Willamette)
}
