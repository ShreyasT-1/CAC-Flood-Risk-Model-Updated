"""Phase0 S1a: pull NWM flowlines (feature_id, name, strm_order, nwm_vers) for the pilot bbox from NOAA OWP static_nwm_flowlines FeatureServer; counties from data/raw/counties.zip (read-only)."""
import requests, geopandas as gpd, pandas as pd
from pathlib import Path
OUT = Path("data/phase0"); OUT.mkdir(parents=True, exist_ok=True)
cs = gpd.read_file("zip://data/raw/counties.zip")
print(cs.columns.tolist(), cs.crs)
cs = cs[cs["COUNTYFP"].isin(["019", "129", "141"]) & (cs["STATEFP"] == "37")].to_crs(4326)
cs.to_file(OUT / "counties.geojson", driver="GeoJSON")
x0, y0, x1, y1 = cs.total_bounds; x0 -= .02; y0 -= .02; x1 += .02; y1 += .02
U = "https://maps.water.noaa.gov/server/rest/services/reference/static_nwm_flowlines/FeatureServer/0/query"
rows, off = [], 0
while True:
    r = requests.get(U, params=dict(where="1=1", geometry=f"{x0},{y0},{x1},{y1}", geometryType="esriGeometryEnvelope", inSR=4326, spatialRel="esriSpatialRelIntersects",
                     outFields="feature_id,name,strm_order,nwm_vers,huc6", outSR=4326, f="geojson", resultOffset=off, resultRecordCount=2000), timeout=120).json()
    f = r.get("features", []); rows += f; print(off, len(f), flush=True)
    if len(f) == 0 or not r.get("properties", {}).get("exceededTransferLimit", r.get("exceededTransferLimit", len(f) >= 2000)): break
    off += len(f)
g = gpd.GeoDataFrame.from_features(rows, crs=4326).drop_duplicates("feature_id")
g.to_parquet(OUT / "nwm_flowlines_bbox.parquet"); print(len(g), g.nwm_vers.value_counts().to_dict(), g.strm_order.value_counts().sort_index().to_dict())
