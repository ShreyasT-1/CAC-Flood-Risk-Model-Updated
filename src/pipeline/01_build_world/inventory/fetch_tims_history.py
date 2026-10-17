"""Download NCDOT_TIMSIncidentsHistory layer 0 (points) fully, paged, to data/raw_new/ncdot_tims_history/. Never overwrites."""
import json, os, time, requests, pandas as pd
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
B = "https://services.arcgis.com/NuWFvHYDMVmmxMeM/ArcGIS/rest/services/NCDOT_TIMSIncidentsHistory/FeatureServer/0/query"
out = "data/raw_new/ncdot_tims_history"; os.makedirs(out, exist_ok=True)
pq = f"{out}/tims_incidents_history_points.parquet"
assert not os.path.exists(pq), "exists; not overwriting"
rows, off = [], 0
while True:
    for k in range(5):
        try:
            j = requests.get(B, params=dict(where="1=1", outFields="*", returnGeometry="false", f="json", resultOffset=off, resultRecordCount=1000, orderByFields="OBJECTID"), timeout=120).json()
            if "error" in j: raise RuntimeError(j["error"])
            break
        except Exception as e:
            print("retry", k, e); time.sleep(10 * (k + 1))
    f = j["features"]; rows += [x["attributes"] for x in f]; off += len(f)
    print(off, flush=True)
    if not f or not j.get("exceededTransferLimit"): break
df = pd.DataFrame(rows)
for c in ["CreationDate", "StartDateTime", "EndDateTime", "LastUpdateDateTime"]:
    df[c] = pd.to_datetime(df[c], unit="ms", utc=True)
df.to_parquet(pq); print("saved", len(df))
