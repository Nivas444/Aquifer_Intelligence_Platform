"""
Background Scheduler — Automatic Real-Time Data Sync
Uses Python threading (no extra dependencies).

Schedule:
  USGS  → every 15 minutes  (real-time well readings)
  NOAA  → every 1 hour      (climate & drought data)
  GRACE → every 24 hours    (satellite groundwater anomalies)
"""
import threading
import logging
import time
from datetime import datetime
from config import SYNC_INTERVAL, DATABASE_PATH

logger = logging.getLogger(__name__)

_scheduler_running = False
_last_sync = {
    'usgs':  None,
    'noaa':  None,
    'grace': None,
}
_sync_status = {
    'usgs':  {'status': 'pending', 'last_run': None, 'last_result': None},
    'noaa':  {'status': 'pending', 'last_run': None, 'last_result': None},
    'grace': {'status': 'pending', 'last_run': None, 'last_result': None},
}


def _run_usgs_sync():
    """Run USGS sync with error handling."""
    global _sync_status
    try:
        from services.usgs_sync import sync_usgs_to_db
        logger.info("[TIMER] Running USGS sync...")
        _sync_status['usgs']['status'] = 'running'
        result = sync_usgs_to_db(DATABASE_PATH)
        _sync_status['usgs'] = {
            'status':      'success',
            'last_run':    datetime.now().isoformat(),
            'last_result': result,
        }
        logger.info(f"[OK] USGS sync done: {result['readings_added']} readings added")
    except Exception as e:
        logger.error(f"[ERROR] USGS sync failed: {e}")
        _sync_status['usgs']['status'] = 'error'
        _sync_status['usgs']['last_run'] = datetime.now().isoformat()


def _run_noaa_sync():
    """Run NOAA sync with error handling."""
    global _sync_status
    try:
        from services.noaa_climate import sync_noaa_to_db
        logger.info("[TIMER] Running NOAA sync...")
        _sync_status['noaa']['status'] = 'running'
        result = sync_noaa_to_db(DATABASE_PATH)
        _sync_status['noaa'] = {
            'status':      'success',
            'last_run':    datetime.now().isoformat(),
            'last_result': result,
        }
        logger.info(f"[OK] NOAA sync done: {result['updated']} aquifers updated")
    except Exception as e:
        logger.error(f"[ERROR] NOAA sync failed: {e}")
        _sync_status['noaa']['status'] = 'error'
        _sync_status['noaa']['last_run'] = datetime.now().isoformat()


def _run_grace_sync():
    """Run NASA GRACE sync with error handling."""
    global _sync_status
    try:
        from services.nasa_grace import sync_nasa_grace_to_db
        logger.info("[TIMER] Running NASA GRACE sync...")
        _sync_status['grace']['status'] = 'running'
        result = sync_nasa_grace_to_db(DATABASE_PATH)
        _sync_status['grace'] = {
            'status':      'success',
            'last_run':    datetime.now().isoformat(),
            'last_result': result,
        }
        logger.info(f"[OK] GRACE sync done: {result['updated']} aquifers updated")
    except Exception as e:
        logger.error(f"[ERROR] GRACE sync failed: {e}")
        _sync_status['grace']['status'] = 'error'
        _sync_status['grace']['last_run'] = datetime.now().isoformat()


def _scheduler_loop():
    """Main scheduler loop — runs in a background thread."""
    global _scheduler_running, _last_sync

    # Stagger initial syncs to avoid hitting APIs simultaneously
    time.sleep(5)
    _run_usgs_sync()

    time.sleep(10)
    _run_noaa_sync()

    time.sleep(10)
    _run_grace_sync()

    usgs_interval  = SYNC_INTERVAL * 60          # 15 min
    noaa_interval  = 60 * 60                      # 1 hour
    grace_interval = 24 * 60 * 60                 # 24 hours

    last_usgs  = time.time()
    last_noaa  = time.time()
    last_grace = time.time()

    while _scheduler_running:
        now = time.time()

        if now - last_usgs >= usgs_interval:
            threading.Thread(target=_run_usgs_sync, daemon=True).start()
            last_usgs = now

        if now - last_noaa >= noaa_interval:
            threading.Thread(target=_run_noaa_sync, daemon=True).start()
            last_noaa = now

        if now - last_grace >= grace_interval:
            threading.Thread(target=_run_grace_sync, daemon=True).start()
            last_grace = now

        time.sleep(30)  # Check every 30 seconds


def start_scheduler():
    """Start the background sync scheduler."""
    global _scheduler_running
    if _scheduler_running:
        logger.warning("Scheduler already running")
        return

    _scheduler_running = True
    thread = threading.Thread(target=_scheduler_loop, daemon=True, name='sync-scheduler')
    thread.start()
    logger.info("[LAUNCH] Background sync scheduler started")
    logger.info(f"   USGS:  every {SYNC_INTERVAL} minutes")
    logger.info(f"   NOAA:  every 60 minutes")
    logger.info(f"   GRACE: every 24 hours")


def stop_scheduler():
    """Stop the background scheduler gracefully."""
    global _scheduler_running
    _scheduler_running = False
    logger.info("[STOP] Scheduler stopped")


def get_sync_status() -> dict:
    """Return current sync status for all data sources."""
    return {
        'scheduler_running': _scheduler_running,
        'sources': _sync_status,
        'checked_at': datetime.now().isoformat(),
    }
