"""Measure issue->availability delay per live source: Last-Modified of f001 and f018 minus issue time, last 12 cycles.
-> data/forecasts/live_delay.csv (+ printed medians)."""
from email.utils import parsedate_to_datetime
from nwm_fc import *
from nwm_fc import _S

now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
rows = []
for h in range(2, 14):
    c = now - timedelta(hours=h)
    for s in SOURCES:
        for f in (1, 18):
            try:
                r = _S.head(url(s, c, f), timeout=30)
                lm = parsedate_to_datetime(r.headers["Last-Modified"]) if r.status_code == 200 else None
                rows.append(dict(cycle=c, source=s, lead=f, status=r.status_code, delay_min=(lm - c).total_seconds() / 60 if lm else None))
            except Exception as e:
                rows.append(dict(cycle=c, source=s, lead=f, status=type(e).__name__))
d = pd.DataFrame(rows); d.to_csv(OUT / "live_delay.csv", index=False)
print(d.groupby(["source", "lead"]).agg(n_ok=("delay_min", "count"), n=("status", "size"), median_min=("delay_min", "median"), max_min=("delay_min", "max")))
