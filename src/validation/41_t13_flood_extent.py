"""Phase 2 / T13: observed flood extent (TNC / Schaffer-Smith et al. 2020, Sentinel-1 composite 2018-09-18..09-28/30, ~20 m, CC-BY 4.0) vs the hindcast hazard output at the 250 hazard-ready seed crossings.
Definitions fixed in docs/validation_protocol.md, Amendment 2. Raster pulled from the public NC OneMap ImageServer (exportImage, native 65.6167 ft cells, EPSG:2264); flooded = 1, NoData = 0 (not flooded OR outside the mapped area;
the mosaic footprint polygon is used to tell those apart). Run once. Usage (repo root): python src/validation/41_t13_flood_extent.py"""
import os, json, requests, numpy as np, pandas as pd, geopandas as gpd, rasterio
from shapely.geometry import Polygon
O = "data/phase2/t13/"; os.makedirs(O, exist_ok=True); IS = "https://services.nconemap.gov/secure/rest/services/Florence_Flood_Extent/ImageServer"; PX = 65.61666666666667; CFS = 35.3146667; NB = 10000; rng = np.random.default_rng(20261011)
# footprint of the mosaic (data area)
fp = requests.get(IS + "/query", params=dict(where="1=1", returnGeometry="true", outSR=2264, f="json"), timeout=120).json()["features"][0]["geometry"]["rings"]
FP = gpd.GeoSeries([Polygon(fp[0], fp[1:])], crs=2264); FP.to_file(O + "tnc_footprint.geojson", driver="GeoJSON")
# raster for the pilot bbox (+2 km), tiled exportImage requests, native cell size
cs = gpd.read_file("data/phase0/counties.geojson").to_crs(2264); x0, y0, x1, y1 = cs.total_bounds; x0 -= 6562; y0 -= 6562; x1 += 6562; y1 += 6562
W = int(np.ceil((x1 - x0) / PX)); Hh = int(np.ceil((y1 - y0) / PX)); x1 = x0 + W * PX; y1 = y0 + Hh * PX; arr = np.zeros((Hh, W), np.uint8); TW, TH = 4000, 4000
if not os.path.exists(O + "tnc_florence_flood_pilot.tif"):
    for r0 in range(0, Hh, TH):
        for c0 in range(0, W, TW):
            w, h = min(TW, W - c0), min(TH, Hh - r0); bx = (x0 + c0 * PX, y1 - (r0 + h) * PX, x0 + (c0 + w) * PX, y1 - r0 * PX)
            r = requests.get(IS + "/exportImage", params=dict(bbox=",".join(map(str, bx)), bboxSR=2264, imageSR=2264, size=f"{w},{h}", format="tiff", pixelType="U8", noData=0, interpolation="RSP_NearestNeighbor", f="image"), timeout=600)
            r.raise_for_status(); p = O + "_tile.tif"; open(p, "wb").write(r.content)
            with rasterio.open(p) as ds: arr[r0:r0 + h, c0:c0 + w] = np.nan_to_num(ds.read(1), nan=0)[:h, :w]
            os.remove(p)
    tr = rasterio.transform.from_origin(x0, y1, PX, PX)
    with rasterio.open(O + "tnc_florence_flood_pilot.tif", "w", driver="GTiff", height=Hh, width=W, count=1, dtype="uint8", crs="EPSG:2264", transform=tr, compress="deflate") as ds: ds.write(arr, 1)
with rasterio.open(O + "tnc_florence_flood_pilot.tif") as ds: A = ds.read(1); tr = ds.transform
print("raster", A.shape, "flooded cells", int((A == 1).sum()), "share", round(float((A == 1).mean()), 4))
# crossings: 250 hazard-ready seed crossings
S = pd.read_parquet("data/phase1b/recurrence_hindcast_nwm_v30_retro.parquet"); S = S[S.in_seed]
X = gpd.read_parquet("data/phase0/crossings_v2.parquet")[["crossing_id", "q2_cfs", "q10_cfs", "geometry"]]; S = X.merge(S[["crossing_id", "county", "feature_id", "in_seed_reliable", "strm_order"]], on="crossing_id"); S = gpd.GeoDataFrame(S, crs=4326).to_crs(2264)
S["in_footprint"] = S.within(FP.iloc[0])
def flooded_within(pt, rad_ft):
    c, r = ~tr * (pt.x, pt.y); c, r = int(c), int(r); k = int(np.ceil(rad_ft / PX)) + 1; sub = A[max(0, r - k):r + k + 1, max(0, c - k):c + k + 1]
    rr, cc = np.mgrid[max(0, r - k):r + k + 1, max(0, c - k):c + k + 1]; xs, ys = tr * (cc + .5, rr + .5); d = np.hypot(xs - pt.x, ys - pt.y)
    return bool(((sub == 1) & (d <= rad_ft + PX / 2)).any()) if rad_ft > 0 else bool(A[r, c] == 1)
for nm, rad in (("inside_30m", 30 / .3048), ("inside_point", 0), ("inside_100m", 100 / .3048)): S[nm] = [flooded_within(p, rad) for p in S.geometry]
F = pd.read_parquet("data/phase1b/flows_hindcast.parquet") * CFS; F.columns = F.columns.astype(str); w = F.loc["2018-09-18 00:00":"2018-09-29 00:00"]
S["max_q10"] = [float(w[str(int(f))].max()) / q for f, q in zip(S.feature_id, S.q10_cfs)]; S["max_q2"] = [float(w[str(int(f))].max()) / q for f, q in zip(S.feature_id, S.q2_cfs)]
S.drop(columns="geometry").to_csv(O + "t13_crossings.csv", index=False)
def auc(a, b): a, b = np.asarray(a), np.asarray(b); return float(((a[:, None] > b[None, :]).mean() + .5 * (a[:, None] == b[None, :]).mean())) if len(a) and len(b) else np.nan
def test(D, inside, col, label):
    D = D[D.in_footprint & D[col].notna()]; a = D[D[inside]][col].values; b = D[~D[inside]][col].values
    out = dict(label=label, n=len(D), n_inside=len(a), n_outside=len(b), share_inside=round(len(a) / max(1, len(D)), 3), per_county=D.groupby("county")[inside].agg(["sum", "count"]).astype(int).to_dict("index"))
    if min(len(a), len(b)) < 5: out["verdict"] = "too few to test"; return out
    bs = [auc(rng.choice(a, len(a)), rng.choice(b, len(b))) for _ in range(NB)]
    out.update(auc=round(auc(a, b), 3), auc_ci95=[round(float(np.percentile(bs, 2.5)), 3), round(float(np.percentile(bs, 97.5)), 3)], median_inside=round(float(np.median(a)), 2), median_outside=round(float(np.median(b)), 2),
               share_gt1_inside=round(float((a > 1).mean()), 3), share_gt1_outside=round(float((b > 1).mean()), 3)); out["verdict"] = "PASS" if out["auc_ci95"][0] > .5 else "FAIL"; return out
res = [test(S, "inside_30m", "max_q10", "PRIMARY: inside = flooded cell within 30 m; max flow/q10 over 09-18..09-29"), test(S, "inside_30m", "max_q2", "secondary: max flow/q2"),
       test(S, "inside_point", "max_q10", "secondary: cell at point"), test(S, "inside_100m", "max_q10", "secondary: within 100 m"), test(S[S.in_seed_reliable], "inside_30m", "max_q10", "secondary: seed_reliable only")]
cnt = dict(crossings=len(S), in_footprint=int(S.in_footprint.sum()), raster_flooded_share_bbox=round(float((A == 1).mean()), 4))
json.dump(dict(counts=cnt, results=res), open(O + "t13_results.json", "w"), indent=1, default=str); print(json.dumps(cnt)); [print(json.dumps(r, default=str)) for r in res]
