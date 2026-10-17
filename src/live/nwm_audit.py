"""List GCS short_range channel_rt files for every hourly cycle in a date range; record cycles with missing leads (all 24 cycles/day,
not just the 3-hourly ones we pull). usage: python nwm_audit.py START END -> data/forecasts/gaps_audit.csv + manifest rows (source=gcs_listing)"""
import re, sys
from nwm_fc import *
from nwm_fc import _S

B = "https://storage.googleapis.com/storage/v1/b/national-water-model/o"
a, b = [datetime.strptime(x, "%Y-%m-%d") for x in sys.argv[1:3]]
rows = []
for k in range((b - a).days + 1):
    day = a + timedelta(days=k)
    have, tok = {}, None
    while True:
        p = {"prefix": f"nwm.{day:%Y%m%d}/short_range/", "fields": "items(name),nextPageToken", "maxResults": 1000}
        if tok: p["pageToken"] = tok
        r = _S.get(B, params=p, timeout=60).json()
        for i in r.get("items", []):
            m = re.search(r"\.t(\d\d)z\.short_range\.channel_rt\.f(\d{3})\.conus\.nc$", i["name"])
            if m: have.setdefault(int(m[1]), set()).add(int(m[2]))
        tok = r.get("nextPageToken")
        if not tok: break
    for h in range(24):
        miss = [f for f in LEADS if f not in have.get(h, set())]
        if miss: rows.append(dict(cycle=f"{day:%Y-%m-%d}T{h:02d}Z", n_leads_present=18 - len(miss), missing_leads=",".join(map(str, miss)), pulled_3hourly=h % 3 == 0))
g = pd.DataFrame(rows); OUT.mkdir(parents=True, exist_ok=True)
g.to_csv(OUT / "gaps_audit.csv", index=False); print(g.to_string())
for r in rows:
    log(dict(cycle=r["cycle"], status="missing_upstream", error="not in GCS listing", source="gcs_listing", missing_leads=r["missing_leads"]))
