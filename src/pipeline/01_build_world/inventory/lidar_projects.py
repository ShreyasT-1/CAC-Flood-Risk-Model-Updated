"""3DEP project index (layer 24 'Lidar Point Cloud' workunits) intersecting Area A+10km and Area B+40km -> data/raw_new/dem_3dep/lidar_workunits_<A|B>.csv. Usage: python -I src/inventory/lidar_projects.py"""
import os, sys, json, requests, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common_geo import areas, ROOT
U = "https://index.nationalmap.gov/arcgis/rest/services/3DEPElevationIndex/MapServer/24/query"
F = "workunit,project,collect_start,collect_end,ql,spec,dem_gsd_meters,horiz_crs,vert_crs,geoid,lpc_pub_date,lpc_category,onemeter_category,onemeter_reason,seamless_category,sourcedem_category,sourcedem_reason,lpc_link,sourcedem_link,metadata_link"
for k, (_, buf) in areas().items():
    r = requests.get(U, params=dict(where="1=1", geometry=buf.wkt, geometryType="esriGeometryPolygon", inSR=4326, spatialRel="esriSpatialRelIntersects", outFields=F, returnGeometry="false", f="json"), timeout=120)
    if r.status_code != 200 or "features" not in r.json():  # long WKT -> use POST
        r = requests.post(U, data=dict(where="1=1", geometry=json.dumps({"rings": [list(map(list, buf.exterior.coords))], "spatialReference": {"wkid": 4326}}), geometryType="esriGeometryPolygon", inSR=4326, spatialRel="esriSpatialRelIntersects", outFields=F, returnGeometry="false", f="json"), timeout=120)
    df = pd.DataFrame([x["attributes"] for x in r.json()["features"]])
    for c in ("collect_start", "collect_end", "lpc_pub_date"):
        if c in df: df[c] = pd.to_datetime(df[c], unit="ms", errors="coerce").dt.date
    df.to_csv(f"{ROOT}/data/raw_new/dem_3dep/lidar_workunits_{k}.csv", index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30); pd.set_option("display.max_colwidth", 60)
    print(k); print(df.drop(columns=["lpc_link", "sourcedem_link", "metadata_link", "horiz_crs"]).to_string())
