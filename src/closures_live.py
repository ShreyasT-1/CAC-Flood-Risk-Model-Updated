"""T14: hourly snapshot of NCDOT's current TIMS incidents (closures, flooding, crashes, work zones) -> data/closures_live/YYYY-MM-DD/incidents_YYYYMMDDTHHMMZ.geojson. Never overwrites (exclusive create).
Source: NCDOT ArcGIS Online feature service NCDOT_TIMS_Incidents (public, no token; NCDOT metadata says it repackages the TIMS feed every 5 minutes):
https://services.arcgis.com/NuWFvHYDMVmmxMeM/ArcGIS/rest/services/NCDOT_TIMS_Incidents/FeatureServer/0
Not used: the old eapps.ncdot.gov TIMS API (retired 2026-05-27) and the new DriveNC API (needs a developer key = account). NCDOT GIS use limitation: data are not a legal document; NCDOT not liable for errors.
One query per run (paged by 1000 records), one run per hour. Logs to data/closures_live/logs/closures_live.log. Usage: python src/closures_live.py  (pythonw from Task Scheduler)."""
import json, sys, time
from datetime import datetime, timezone
from pathlib import Path
import requests
ROOT = Path(__file__).resolve().parent.parent; OUT = ROOT / "data/closures_live"; LOG = OUT / "logs"; LOG.mkdir(parents=True, exist_ok=True)
if sys.stdout is None: sys.stdout = sys.stderr = open(LOG / "closures_live.log", "a", buffering=1)
URL = "https://services.arcgis.com/NuWFvHYDMVmmxMeM/ArcGIS/rest/services/NCDOT_TIMS_Incidents/FeatureServer/0/query"
UA = {"User-Agent": "FloodLens-student-archiver/1.0 (non-commercial; hourly)"}
def get(params):
    for k in range(5):
        try:
            r = requests.get(URL, params=params, headers=UA, timeout=120); r.raise_for_status(); j = r.json()
            if "error" in j: raise RuntimeError(j["error"])
            return j
        except Exception as e:
            if k == 4: raise
            time.sleep(30 * (k + 1))
def main():
    now = datetime.now(timezone.utc); stamp = now.strftime("%Y%m%dT%H%MZ"); d = OUT / now.strftime("%Y-%m-%d"); d.mkdir(parents=True, exist_ok=True); p = d / f"incidents_{stamp}.geojson"
    feats, off = [], 0
    while True:
        j = get(dict(where="1=1", outFields="*", returnGeometry="true", outSR=4326, f="geojson", resultOffset=off, resultRecordCount=1000, orderByFields="OBJECTID"))
        f = j.get("features", []); feats += f; off += len(f)
        if not f or not j.get("properties", {}).get("exceededTransferLimit", j.get("exceededTransferLimit", False)): break
    doc = dict(type="FeatureCollection", features=feats, fetched_utc=now.isoformat(timespec="seconds"), source=URL)
    try:
        with open(p, "x", encoding="utf-8") as fh: json.dump(doc, fh)   # "x": never overwrite an existing snapshot
    except FileExistsError:
        print(f"[{now.isoformat(timespec='seconds')}] exists, not overwritten: {p.name}"); return
    n_close = sum(1 for x in feats if str(x.get("properties", {}).get("IsFullClosure", "")).lower() in ("true", "yes", "y", "1"))
    print(f"[{now.isoformat(timespec='seconds')}] saved {p.relative_to(ROOT)} incidents={len(feats)} full_closures={n_close}")
if __name__ == "__main__":
    main()
