"""New features step A: for every usable gauge fetch (1) NLDI basin polygon and (2) upstream NWIS sites (UT navigation, nwissite source).
Cached to data/raw/nldi_basin/<id>.json and data/raw/nldi_ut/<id>.json. Output: data/derived/upstream_gauges.csv
(one row per gauge x upstream gauge that is itself a usable gauge: great-circle distance, drainage-area ratio, rank by distance).
ponytail: 'nearest' = great-circle distance among upstream (UT) sites, not along-network distance (NLDI returns no distance).
"""
import json, numpy as np, pandas as pd
from concurrent.futures import ThreadPoolExecutor
import requests
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2])); from common import *

NL = "https://api.water.usgs.gov/nldi/linked-data/nwissite/USGS-"
miss = pd.read_csv(DER / "obs_missing.csv", dtype={"usgs_id": str})
uids = miss[~miss.dropped].usgs_id.tolist()
cw = pd.read_csv(DER / "gauge_crosswalk.csv", dtype={"usgs_id": str}).set_index("usgs_id")


def fetch(args):
    u, kind, url, params = args
    f = RAW / kind / f"{u}.json"
    f.parent.mkdir(exist_ok=True)
    if f.exists():
        return u, kind, True
    for i in range(4):
        try:
            r = requests.get(url, params=params, timeout=300)
            if r.status_code == 404:
                f.write_text('{"features":[],"missing":true}'); return u, kind, False
            r.raise_for_status(); f.write_text(r.text); return u, kind, True
        except requests.RequestException:
            import time; time.sleep(3 * (i + 1))
    return u, kind, False


jobs = [(u, "nldi_basin", f"{NL}{u}/basin", {"f": "json", "simplified": "false"}) for u in uids] + \
       [(u, "nldi_ut", f"{NL}{u}/navigation/UT/nwissite", {"f": "json", "distance": 9999}) for u in uids]
with ThreadPoolExecutor(6) as ex:
    res = list(ex.map(fetch, jobs))
bad = [(u, k) for u, k, ok in res if not ok]
print("failed/missing:", bad)

def hav(a, b, c, d):
    a, b, c, d = map(np.radians, (a, b, c, d))
    return 6371 * 2 * np.arcsin(np.sqrt(np.sin((c - a) / 2) ** 2 + np.cos(a) * np.cos(c) * np.sin((d - b) / 2) ** 2))

rows = []
for u in uids:
    j = json.loads((RAW / "nldi_ut" / f"{u}.json").read_text())
    ups = [x["properties"]["identifier"].replace("USGS-", "") for x in j["features"]]
    ups = [x for x in ups if x in cw.index and x != u and x in set(uids)]
    c = cw.loc[u]
    cand = pd.DataFrame({"up_id": ups})
    if len(cand):
        cand["dist_km"] = [hav(c.lat, c.lon, cw.loc[x].lat, cw.loc[x].lon) for x in ups]
        cand["da_ratio"] = [cw.loc[x].drainage_area / c.drainage_area if c.drainage_area > 0 else np.nan for x in ups]
        cand = cand.sort_values("dist_km").head(3)
        for k, r in enumerate(cand.itertuples(), 1):
            rows.append({"usgs_id": u, "rank": k, "up_id": r.up_id, "dist_km": r.dist_km, "da_ratio": r.da_ratio})
out = pd.DataFrame(rows)
out.to_csv(DER / "upstream_gauges.csv", index=False)
print("gauges with >=1 upstream usable gauge:", out.usgs_id.nunique(), "of", len(uids), "| rows", len(out))
