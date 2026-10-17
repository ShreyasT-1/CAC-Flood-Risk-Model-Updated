"""Backfill live cycles from START (ISO hour, UTC) up to now-2h. Idempotent (archive_cycle skips existing). Usage: python nwm_backfill.py 2026-10-10T22"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "live"))   # nwm_fc moved to src/live; this file stays here because Task Scheduler runs it by name from src/
from nwm_fc import *
if sys.stdout is None or os.environ.get('FLOODLENS_LOG'):   # pythonw / scheduled task: no console -> append to the log file
    sys.stdout = sys.stderr = open(Path(__file__).resolve().parent.parent / 'data/forecasts/logs/live_task.log', 'a', buffering=1); print('[%s] start (pythonw)' % datetime.now().isoformat(timespec='seconds'))
a = sys.argv[1]  # ISO hour, or integer = hours back from now
c = (datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=int(a))) if a.isdigit() else datetime.fromisoformat(a).replace(tzinfo=timezone.utc)
end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=2)
while c <= end:
    print(c.strftime("%Y-%m-%dT%HZ"), archive_cycle(c, sources=("aws", "gcs", "nomads"), require_complete=True), flush=True)
    c += timedelta(hours=1)
print('[%s] exit ok' % datetime.now().isoformat(timespec='seconds'))
