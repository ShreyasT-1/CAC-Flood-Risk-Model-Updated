"""Hourly live archiver: catch up the last 8 hours of short-range cycles (aws -> gcs -> nomads). Idempotent (existing cycle = skipped).
A cycle is written only when all 18 leads exist; cycles still incomplete 6 h after issue are logged to the manifest as failed.
The label for these data is the NWM version stored per row (nwm_version), e.g. current operational model."""
from nwm_fc import *

now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
for h in range(2, 9):  # f018 appears ~1h45 after issue, so start 2 h back
    c = now - timedelta(hours=h)
    st = archive_cycle(c, sources=("aws", "gcs", "nomads"), require_complete=True)
    if st == "incomplete" and h >= 6:
        log(dict(cycle=c.strftime("%Y-%m-%dT%HZ"), status="failed", error="incomplete on all sources after 6h", source="aws,gcs,nomads",
                 fetched_utc=datetime.now(timezone.utc).isoformat(timespec="seconds")))
    print(c.strftime("%Y-%m-%dT%HZ"), st)
