"""FEMA NFHL (https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer) download by object id. Layers: 28 zones, 1 LOMRs, 16 BFEs, 14 cross-sections.
Method: (1) object ids intersecting each 0.1-deg tile of the area bbox, (2) fetch geometry+attributes by id in chunks, halving a chunk on failure (FEMA returns empty/500 for big polygon pages), (3) keep features intersecting the buffered area.
Usage: python -I src/pipeline/01_build_world/inventory/fetch_nfhl.py A:28,1,16,14 B:1,16,14   (B zones already in data/phase2/fema_nfhl.parquet)"""
import os, sys, time, datetime, requests, numpy as np, geopandas as gpd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common_geo import areas, ROOT
BASE = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/%d"
NAMES = {28: "flood_hazard_zones", 1: "lomrs", 16: "base_flood_elevations", 14: "cross_sections"}
S = requests.Session(); S.headers["User-Agent"] = "FloodLens-research (student project)"
AR = areas(); FAILED = []


def get(u, tries=3, **kw):
    for k in range(tries):
        try:
            time.sleep(0.5); r = S.get(u, timeout=120, **kw); j = r.json(); assert "error" not in j, j; return j
        except Exception as e:
            time.sleep(5 * (k + 1))
    return None


def by_ids(L, ids):
    j = get(BASE % L + "/query", params=dict(objectIds=",".join(map(str, ids)), outFields="*", outSR=4326, geometryPrecision=6, f="geojson"))
    if j is not None and "features" in j: return j["features"]
    if len(ids) == 1: FAILED.append((L, ids[0])); print("FAILED id", L, ids[0], flush=True); return []
    h = len(ids) // 2; return by_ids(L, ids[:h]) + by_ids(L, ids[h:])


out_dir = f"{ROOT}/data/raw_new/fema_nfhl"; os.makedirs(out_dir, exist_ok=True)
for arg in sys.argv[1:]:
    area, layers = arg.split(":"); buf = AR[area][1]; x0, y0, x1, y1 = buf.bounds
    for L in map(int, layers.split(",")):
        p = f"{out_dir}/nfhl_{NAMES[L]}_area{area}_buf.parquet"
        if os.path.exists(p): print("exists", p); continue
        ids = set()
        for x in np.arange(x0, x1, 0.1):
            for y in np.arange(y0, y1, 0.1):
                j = get(BASE % L + "/query", tries=5, params=dict(where="1=1", geometry=f"{x},{y},{min(x+.1,x1)},{min(y+.1,y1)}", geometryType="esriGeometryEnvelope", inSR=4326, spatialRel="esriSpatialRelIntersects", returnIdsOnly="true", f="json"))
                if j is None: FAILED.append((L, f"idquery {x},{y}")); print("ID QUERY FAILED", x, y, flush=True); continue
                ids.update(j.get("objectIds") or [])
        ids = sorted(ids); print(area, L, "ids", len(ids), flush=True)
        feats = []
        for i in range(0, len(ids), 50):
            feats += by_ids(L, ids[i:i + 50])
            if (i // 50) % 20 == 0: print(area, L, i, "/", len(ids), flush=True)
        if not feats: print(area, L, "NO FEATURES"); continue
        g = gpd.GeoDataFrame.from_features(feats, crs=4326); g.columns = [c.lower() if c != "geometry" else c for c in g.columns]
        g = g[g.intersects(buf)].copy()
        g["fetched_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"); g["source"] = BASE % L
        g.to_parquet(p); print("saved", p, len(g), "failed so far", len(FAILED), flush=True)
print("FAILED:", FAILED)
