"""IEM Local Storm Reports (NC, per year) + NCEI Storm Events details (per year). Never overwrites. Usage: python -I src/inventory/fetch_storm_reports.py"""
import os, sys, re, json, time, requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common_geo import ROOT
H = {"User-Agent": "FloodLens-student-research/1.0"}
d1 = f"{ROOT}/data/raw_new/iem_lsr_nc"; d2 = f"{ROOT}/data/raw_new/ncei_storm_events"; os.makedirs(d1, exist_ok=True); os.makedirs(d2, exist_ok=True)
for y in range(2005, 2027):
    p = f"{d1}/lsr_NC_{y}.geojson"
    if os.path.exists(p): continue
    r = requests.get("https://mesonet.agron.iastate.edu/geojson/lsr.geojson", params=dict(states="NC", sts=f"{y}-01-01T00:00Z", ets=f"{y+1}-01-01T00:00Z"), headers=H, timeout=180)
    r.raise_for_status(); open(p, "wb").write(r.content); print(y, len(json.loads(r.content)["features"]), flush=True)
idx = requests.get("https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/", headers=H, timeout=60).text
for y in range(2005, 2027):
    m = re.search(rf"StormEvents_details-ftp_v1\.0_d{y}_c\d+\.csv\.gz", idx)
    if not m: print("no ncei file", y); continue
    p = f"{d2}/{m.group(0)}"
    if os.path.exists(p): continue
    r = requests.get("https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/" + m.group(0), headers=H, timeout=180); r.raise_for_status(); open(p, "wb").write(r.content); print(m.group(0), len(r.content), flush=True)
