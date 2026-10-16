"""Query TNM Access API for 1 m DEM + 1/3 arc-sec NED + LPC (count only) over Area A (+10 km); write manifest CSV. Usage: python -I src/inventory/tnm_manifest.py"""
import os, sys, requests, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common_geo import areas, ROOT
from shapely.geometry import box
API = "https://tnmaccess.nationalmap.gov/api/v1/products"
AB = areas()["A"][1]; bb = ",".join(f"{v:.4f}" for v in AB.bounds)
out = []
for key, ds in (("dem1m", "Digital Elevation Model (DEM) 1 meter"), ("ned13", "National Elevation Dataset (NED) 1/3 arc-second Current")):
    off = 0
    while True:
        r = requests.get(API, params=dict(datasets=ds, bbox=bb, max=200, offset=off, outputFormat="JSON"), headers={"User-Agent": "FloodLens-student"}, timeout=120).json()
        its = r.get("items", [])
        for i in its:
            b = i["boundingBox"]; g = box(b["minX"], b["minY"], b["maxX"], b["maxY"])
            if g.intersects(AB):
                out.append(dict(kind=key, title=i["title"], project=i["title"].split(" ")[-1] if key == "dem1m" else "", pub=i["publicationDate"], updated=i.get("lastUpdated"), size=i["sizeInBytes"], fmt=i["format"], url=i["downloadURL"], **{k: b[k] for k in b}))
        off += 200
        if len(its) < 200: break
df = pd.DataFrame(out); os.makedirs(os.path.join(ROOT, "data/raw_new/dem_3dep"), exist_ok=True)
df.to_csv(os.path.join(ROOT, "data/raw_new/dem_3dep/tile_manifest.csv"), index=False)
print(df.groupby(["kind", "project"]).agg(n=("url", "size"), GB=("size", lambda s: s.sum() / 1e9)), df.groupby("kind")["pub"].agg(["min", "max"]))
# coverage of Area A+10km by 1 m tiles (tile bboxes; 1 m tiles are not exactly rectangular in WGS84 so approximate)
from shapely.ops import unary_union
t = df[df.kind == "dem1m"]
if len(t):
    u = unary_union([box(r.minX, r.minY, r.maxX, r.maxY) for r in t.itertuples()])
    print("1 m tile bbox coverage of A+10km: %.1f%%" % (100 * u.intersection(AB).area / AB.area))
