import sqlite3
import os
from datetime import datetime, timedelta
import random
import math

from config import DATABASE_PATH

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()

    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        username TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'viewer',
        organization TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active BOOLEAN DEFAULT 1
    )''')

    # Aquifers table
    c.execute('''CREATE TABLE IF NOT EXISTS aquifers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        region TEXT NOT NULL,
        state TEXT NOT NULL,
        lat REAL NOT NULL,
        lng REAL NOT NULL,
        area_km2 REAL,
        depth_m REAL,
        stress_level REAL DEFAULT 0.5,
        water_level_m REAL,
        recharge_rate REAL,
        extraction_rate REAL,
        status TEXT DEFAULT 'normal',
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Wells table
    c.execute('''CREATE TABLE IF NOT EXISTS wells (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        site_no TEXT UNIQUE,
        name TEXT NOT NULL,
        aquifer_id INTEGER,
        lat REAL NOT NULL,
        lng REAL NOT NULL,
        depth_m REAL,
        water_level_m REAL,
        water_level_change REAL DEFAULT 0,
        status TEXT DEFAULT 'active',
        well_type TEXT DEFAULT 'monitoring',
        last_reading TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (aquifer_id) REFERENCES aquifers(id)
    )''')

    # Well readings (time series)
    c.execute('''CREATE TABLE IF NOT EXISTS well_readings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        well_id INTEGER NOT NULL,
        water_level_m REAL NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        source TEXT DEFAULT 'sensor',
        FOREIGN KEY (well_id) REFERENCES wells(id)
    )''')

    # Alerts table
    c.execute('''CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aquifer_id INTEGER,
        well_id INTEGER,
        alert_type TEXT NOT NULL,
        severity TEXT NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        region TEXT,
        is_active BOOLEAN DEFAULT 1,
        is_acknowledged BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        acknowledged_at TIMESTAMP,
        FOREIGN KEY (aquifer_id) REFERENCES aquifers(id),
        FOREIGN KEY (well_id) REFERENCES wells(id)
    )''')

    # Forecasts table
    c.execute('''CREATE TABLE IF NOT EXISTS forecasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aquifer_id INTEGER NOT NULL,
        forecast_date DATE NOT NULL,
        predicted_level_m REAL NOT NULL,
        predicted_demand_mm3 REAL,
        confidence REAL DEFAULT 0.85,
        model_version TEXT DEFAULT 'v1.0',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (aquifer_id) REFERENCES aquifers(id)
    )''')

    # Regulatory reports
    c.execute('''CREATE TABLE IF NOT EXISTS regulatory_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        region TEXT NOT NULL,
        report_type TEXT NOT NULL,
        status TEXT DEFAULT 'draft',
        content TEXT,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        submitted_at TIMESTAMP,
        FOREIGN KEY (created_by) REFERENCES users(id)
    )''')

    # Performance Indexes
    c.execute('CREATE INDEX IF NOT EXISTS idx_wells_status ON wells(status)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_wells_water_change ON wells(water_level_change)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_wells_aquifer_id ON wells(aquifer_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_wells_last_reading ON wells(last_reading DESC)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_well_readings_well_id_time ON well_readings(well_id, timestamp DESC)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_alerts_is_active ON alerts(is_active)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_grace_aquifer_date ON grace_anomalies(aquifer_id, measurement_date DESC)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_climate_aquifer_date ON climate_data(aquifer_id, data_date DESC)')

    conn.commit()
    _seed_data(conn)
    conn.close()
    print("[OK] Database initialized successfully")

def _seed_data(conn):
    c = conn.cursor()

    # Check if already seeded
    c.execute("SELECT COUNT(*) FROM aquifers")
    if c.fetchone()[0] > 0:
        return

    print("[INFO] Seeding database...")

    # Seed aquifers
    aquifers = [
        ("Ogallala Aquifer", "High Plains", "Kansas", 38.5, -99.0, 450000, 90, 0.82, 28.5, 0.8, 15.2, "critical"),
        ("Central Valley Aquifer", "Central Valley", "California", 36.7, -119.7, 52000, 120, 0.75, 45.2, 1.2, 18.5, "high"),
        ("Edwards Aquifer", "Hill Country", "Texas", 29.7, -98.5, 3600, 60, 0.65, 180.0, 3.5, 8.2, "moderate"),
        ("Floridan Aquifer", "Southeast", "Florida", 27.9, -82.5, 100000, 300, 0.45, 15.8, 8.5, 6.3, "normal"),
        ("Columbia Plateau Aquifer", "Pacific Northwest", "Washington", 46.7, -119.5, 174000, 150, 0.38, 55.3, 12.0, 5.1, "normal"),
        ("Snake River Plain Aquifer", "Southern Idaho", "Idaho", 43.5, -114.0, 25000, 200, 0.55, 70.2, 6.8, 9.4, "moderate"),
        ("Mississippi Embayment Aquifer", "Mississippi Valley", "Mississippi", 32.3, -90.2, 100000, 500, 0.42, 22.1, 10.2, 4.8, "normal"),
        ("Denver Basin Aquifer", "Front Range", "Colorado", 39.7, -104.9, 6500, 250, 0.70, 35.6, 0.5, 11.3, "high"),
        ("Atlantic Coastal Plain Aquifer", "East Coast", "Virginia", 37.4, -77.4, 50000, 400, 0.35, 18.9, 15.0, 3.2, "normal"),
        ("Willamette Valley Aquifer", "Pacific Northwest", "Oregon", 44.9, -123.0, 5000, 80, 0.30, 12.4, 20.0, 2.1, "normal"),
    ]

    c.executemany('''INSERT INTO aquifers 
        (name, region, state, lat, lng, area_km2, depth_m, stress_level, water_level_m, 
         recharge_rate, extraction_rate, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''', aquifers)

    # Seed wells
    wells_data = []
    for i in range(1, 11):
        aq = aquifers[i-1]
        for j in range(1, 6):
            lat = aq[3] + random.uniform(-1.5, 1.5)
            lng = aq[4] + random.uniform(-1.5, 1.5)
            depth = aq[6] * random.uniform(0.6, 1.2)
            wl = aq[8] * random.uniform(0.85, 1.15)
            change = random.uniform(-2.5, 0.5)
            status = "active" if random.random() > 0.1 else "inactive"
            wells_data.append((
                f"USGS-{i:02d}{j:03d}", f"Well {i}-{j}", i, lat, lng,
                round(depth, 1), round(wl, 2), round(change, 2), status, "monitoring"
            ))

    c.executemany('''INSERT INTO wells 
        (site_no, name, aquifer_id, lat, lng, depth_m, water_level_m, 
         water_level_change, status, well_type) VALUES (?,?,?,?,?,?,?,?,?,?)''', wells_data)

    # Seed well readings (last 90 days)
    c.execute("SELECT id, water_level_m FROM wells")
    wells_list = c.fetchall()
    readings = []
    for well in wells_list:
        base_level = well[1]
        for day in range(90, 0, -1):
            ts = datetime.now() - timedelta(days=day)
            noise = random.uniform(-0.5, 0.3)
            trend = -day * 0.01
            level = base_level + noise + trend
            readings.append((well[0], round(level, 2), ts.isoformat(), "sensor"))
    c.executemany("INSERT INTO well_readings (well_id, water_level_m, timestamp, source) VALUES (?,?,?,?)", readings)

    # Seed alerts
    alerts_data = [
        (1, None, "stress_critical", "critical", "Critical Stress: Ogallala Aquifer",
         "Ogallala Aquifer stress level at 82%. Immediate action required. Water levels declining at 2.5m/year.", "High Plains"),
        (2, None, "depletion_warning", "high", "High Depletion Rate: Central Valley",
         "Central Valley extraction exceeds recharge by 15x. Subsidence risk increasing.", "Central Valley"),
        (3, None, "level_drop", "high", "Significant Level Drop: Denver Basin",
         "Denver Basin water level dropped 3.2m in last 30 days. Monitor closely.", "Front Range"),
        (4, None, "recharge_low", "moderate", "Low Recharge: Edwards Aquifer",
         "Edwards Aquifer recharge rate 40% below seasonal average due to drought conditions.", "Hill Country"),
        (6, None, "contamination_risk", "moderate", "Contamination Risk: Snake River Plain",
         "Agricultural runoff detected near Snake River Plain monitoring wells.", "Southern Idaho"),
        (8, None, "stress_elevated", "moderate", "Elevated Stress: Denver Basin",
         "Denver Basin stress levels elevated due to urban demand increase.", "Front Range"),
        (1, None, "emergency", "critical", "Emergency: Ogallala Depletion Accelerating",
         "Latest satellite data shows Ogallala depletion rate increased 35% this quarter.", "High Plains"),
    ]
    c.executemany('''INSERT INTO alerts 
        (aquifer_id, well_id, alert_type, severity, title, message, region) VALUES (?,?,?,?,?,?,?)''', alerts_data)

    # Seed forecasts (next 180 days)
    c.execute("SELECT id, water_level_m, extraction_rate, recharge_rate FROM aquifers")
    aq_list = c.fetchall()
    forecasts = []
    for aq in aq_list:
        base_level = aq[1]
        extraction = aq[2]
        recharge = aq[3]
        net_change = (recharge - extraction) * 0.01
        for day in range(1, 181):
            fd = (datetime.now() + timedelta(days=day)).date()
            seasonal = math.sin(day * 0.034) * 2
            predicted = base_level + (net_change * day) + seasonal + random.uniform(-0.3, 0.3)
            demand = extraction * (1 + 0.002 * day + random.uniform(-0.05, 0.05))
            confidence = max(0.6, 0.95 - day * 0.001)
            forecasts.append((aq[0], fd.isoformat(), round(predicted, 2), round(demand, 3), round(confidence, 3)))
    c.executemany('''INSERT INTO forecasts 
        (aquifer_id, forecast_date, predicted_level_m, predicted_demand_mm3, confidence) 
        VALUES (?,?,?,?,?)''', forecasts)

    # Seed default admin user
    import hashlib
    pw_hash = hashlib.sha256("admin123".encode()).hexdigest()
    c.execute('''INSERT OR IGNORE INTO users (email, username, password_hash, role, organization) 
        VALUES (?,?,?,?,?)''',
        ("admin@aquifer.io", "Admin", pw_hash, "admin", "Aquifer Intelligence"))
    c.execute('''INSERT OR IGNORE INTO users (email, username, password_hash, role, organization) 
        VALUES (?,?,?,?,?)''',
        ("analyst@aquifer.io", "Analyst", pw_hash, "analyst", "USGS"))

    conn.commit()
    print("[OK] Seed data inserted")
