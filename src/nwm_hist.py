"""Historical pull of operational short-range cycles (GCS NetCDF; BigQuery not available - no project ID yet).
usage: python nwm_hist.py START END [cycles]   e.g. 2018-09-17 2018-11-13   (cycles default 00,03,...,21)
Prints file count / expected GB first (the GCS analogue of a dry run). Resumable: existing cycle parquet is skipped."""
import sys
from datetime import datetime, timedelta, timezone
from nwm_fc import *

a, b = [datetime.strptime(x, "%Y-%m-%d").replace(tzinfo=timezone.utc) for x in sys.argv[1:3]]
hours = [int(h) for h in (sys.argv[3] if len(sys.argv) > 3 else "0,3,6,9,12,15,18,21").split(",")]
cycles = [a + timedelta(days=d, hours=h) for d in range((b - a).days + 1) for h in hours]
todo = [c for c in cycles if not cycle_path(c).exists()]
print(f"{len(cycles)} cycles, {len(todo)} to pull = {len(todo) * 18} files, ~{len(todo) * 18 * 10.5 / 1000:.1f} GB read (reach subset kept)", flush=True)
for i, c in enumerate(todo):
    st = archive_cycle(c)
    print(i + 1, len(todo), c.strftime("%Y-%m-%dT%HZ"), st, flush=True)
