"""T4: download FEMA NFHL flood hazard zones (S_FLD_HAZ_AR) for the pilot bbox (New Hanover, Brunswick, Pender + 0.05 deg) from FEMA's public ArcGIS REST service, save data/phase2/fema_nfhl.parquet.
Endpoint verified 2026-10-12: https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28 (layer name "Flood Hazard Zones", ArcGIS Server 11.1). The older path /gis/nfhl/rest/services/... returns 'Not Found'.
Polygons are kept as served (no generalisation). FEMA zones are a COMPARISON layer, not ground truth and not a model input. Usage (repo root): python src/61_fema_nfhl.py"""
import json, time, requests, numpy as np, pandas as pd, geopandas as gpd
URL = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"; OUT = "data/phase2/fema_nfhl.parquet"
FIELDS = "OBJECTID,DFIRM_ID,FLD_AR_ID,FLD_ZONE,ZONE_SUBTY,SFHA_TF,STATIC_BFE,V_DATUM"
S = requests.Session(); S.headers["User-Agent"] = "FloodLens-research (student project)"
def get(u, **kw):
    for k in range(8):
        try: time.sleep(1.0); return S.get(u, timeout=180, **kw)
        except Exception as e: print("retry", k, repr(e)[:120], flush=True); time.sleep(20 * (k + 1))
    raise RuntimeError(u)
meta = get(URL.replace("/query", "") + "?f=json").json(); print("layer", meta["name"], "| maxRecordCount", meta.get("maxRecordCount"), "| fields", [f["name"] for f in meta["fields"]][:25])
cs = gpd.read_file("data/phase0/counties.geojson").to_crs(4326); x0, y0, x1, y1 = cs.total_bounds; x0, y0, x1, y1 = x0 - .05, y0 - .05, x1 + .05, y1 + .05; print("bbox", round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3), "counties", list(cs.columns)[:8])
feats = {}; PAGE = 200
for x in np.arange(x0, x1, 0.2):
    for y in np.arange(y0, y1, 0.2):
        off = 0
        while True:
            for k in range(6):
                try:
                    r = get(URL, params=dict(where="1=1", geometry=f"{x},{y},{min(x + .2, x1)},{min(y + .2, y1)}", geometryType="esriGeometryEnvelope", inSR=4326, spatialRel="esriSpatialRelIntersects", outFields=FIELDS, outSR=4326, geometryPrecision=6, f="geojson", resultOffset=off, resultRecordCount=PAGE, orderByFields="OBJECTID"))
                    j = r.json(); assert "features" in j or "error" not in j, j; break
                except Exception as e: print("retry", k, "tile", round(x, 3), round(y, 3), "off", off, "page", PAGE, repr(e)[:100], getattr(r, "status_code", None), flush=True); PAGE = max(25, PAGE // 2); time.sleep(10 * (k + 1)); j = None
            assert j is not None, f"tile {x},{y} failed after retries"
            f = j.get("features", [])
            for q in f: feats[q["properties"]["OBJECTID"]] = q
            off += len(f)
            if len(f) < PAGE and not j.get("properties", {}).get("exceededTransferLimit", False): break
    print("column", round(x, 2), "features so far", len(feats), flush=True)
g = gpd.GeoDataFrame.from_features(list(feats.values()), crs=4326); g.columns = [c.lower() if c != "geometry" else c for c in g.columns]
g["fetched_utc"] = pd.Timestamp.now("UTC").isoformat(timespec="seconds"); g["source"] = URL.replace("/query", ""); g.to_parquet(OUT)
print("saved", OUT, len(g), "polygons"); print(g.groupby(["fld_zone", "zone_subty"], dropna=False).size().sort_values(ascending=False).head(25).to_string())
