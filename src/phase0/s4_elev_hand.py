"""Phase0 S4: (a) 3DEP 1 m tile coverage of the 3 counties (TNM Access API listing, bbox-approximate); (b) 20 random crossings: road elevation + HAND-proxy from remote 1 m DEM windows.
Official NOAA OWP HAND (s3://noaa-nws-owp-fim) is requester-pays/credentialed -> not used; HAND-proxy = road crest elevation - min channel elevation along the matched NWM reach (+-100 m). NOT true HAND (no flow routing)."""
import json, numpy as np, pandas as pd, geopandas as gpd, rasterio
from rasterio.windows import from_bounds
from shapely.geometry import box, Point, LineString
from shapely.ops import substring
P = "data/phase0/"; U = 32617
cs = gpd.read_file(P + "counties.geojson"); T = pd.read_parquet(P + "tnm_1m_products.parquet")
T["geometry"] = [box(b["minX"], b["minY"], b["maxX"], b["maxY"]) for b in T.boundingBox]; T = gpd.GeoDataFrame(T, crs=4326)
land = cs.to_crs(U); tiles = T.to_crs(U)
cov = {n: float(land[land.NAME == n].geometry.iloc[0].intersection(tiles.geometry.union_all()).area / land[land.NAME == n].geometry.iloc[0].area) for n in land.NAME}
print("bbox-coverage by county (incl. water):", cov)
X = gpd.read_parquet(P + "crossings.parquet").to_crs(U); rch = gpd.read_parquet(P + "nwm_flowlines_bbox.parquet").to_crs(U); rch["feature_id"] = rch.feature_id.astype("int64")
R = gpd.read_parquet(P + "osm_roads.parquet").to_crs(U).set_index("osm_id")
S = X.sample(20, random_state=7).copy(); rows = []
def samp(ds, pts):
    v = np.array([x[0] for x in ds.sample([(p.x, p.y) for p in pts])], dtype=float)
    nd = ds.nodata; v[(v == nd) | (v < -500) | ~np.isfinite(v)] = np.nan; return v
def along(line, c, half, step):
    s = line.project(c); a, b = max(0, s - half), min(line.length, s + half)
    return [line.interpolate(d) for d in np.arange(a, b + 1e-6, step)] if b > a else []
for _, r in S.iterrows():
    rec = dict(crossing_id=r.crossing_id, road_class=r.road_class, source=r.source, feature_id=r.feature_id, match_dist_m=r.match_dist_m, fail="")
    t = tiles[tiles.contains(r.geometry)]
    if t.empty: rec["fail"] = "no_1m_tile"; rows.append(rec); continue
    rec["tile"] = t.iloc[0].title; url = "/vsicurl/" + t.iloc[0].downloadURL
    try:
        with rasterio.open(url) as ds:
            rec["dem_crs"] = str(ds.crs)
            pt = gpd.GeoSeries([r.geometry], crs=U).to_crs(ds.crs).iloc[0]; toDEM = lambda g: gpd.GeoSeries([g], crs=U).to_crs(ds.crs).iloc[0]
            road = R.geometry.loc[r.osm_road_id]; road = road.iloc[0] if hasattr(road, "iloc") else road
            rp = along(road, r.geometry, 40, 5); rec["road_elev_pt"] = float(samp(ds, [toDEM(r.geometry)])[0])
            rv = samp(ds, [toDEM(p) for p in rp]) if rp else np.array([np.nan]); rec["road_elev_crest"] = float(np.nanmax(rv)) if np.isfinite(rv).any() else np.nan; rec["road_nodata_frac"] = float(np.isnan(rv).mean())
            if pd.notna(r.feature_id) and r.match_dist_m <= 100:
                rl = rch[rch.feature_id == r.feature_id].geometry.iloc[0]; rl = rl if rl.geom_type == "LineString" else max(rl.geoms, key=lambda g: g.length)
                cp = rl.interpolate(rl.project(r.geometry)); cpts = along(rl, cp, 100, 5); cv = samp(ds, [toDEM(p) for p in cpts])
                rec["chan_elev_min"] = float(np.nanmin(cv)) if np.isfinite(cv).any() else np.nan; rec["chan_nodata_frac"] = float(np.isnan(cv).mean())
                rec["hand_proxy_m"] = rec["road_elev_crest"] - rec["chan_elev_min"]
            else: rec["fail"] = "no_reach_within_100m"
    except Exception as e: rec["fail"] = f"read_error:{type(e).__name__}:{str(e)[:80]}"
    rows.append(rec)
D = pd.DataFrame(rows)
D["plausible"] = D.hand_proxy_m.between(-0.5, 30) & D.road_elev_crest.notna() & D.chan_elev_min.notna() if "hand_proxy_m" in D else False
D["road_elev_ok"] = D.road_elev_crest.between(-5, 60) if "road_elev_crest" in D else False
D.to_parquet(P + "s4_sample.parquet"); D.to_csv(P + "s4_sample.csv", index=False)
st = dict(coverage_bbox=cov, tiles=len(T), projects=T.title.str.extract(r"x\d+y\d+ (.*)$")[0].value_counts().to_dict(), n=len(D), road_elev_ok=int(D.road_elev_ok.sum()), with_reach=int(D.hand_proxy_m.notna().sum()), hand_plausible=int(D.plausible.sum()), fail_counts=D.fail.value_counts().to_dict())
json.dump(st, open(P + "s4_stats.json", "w"), indent=1, default=str); print(json.dumps(st, indent=1, default=str)); print(D.drop(columns=["tile", "dem_crs"], errors="ignore").round(2).to_string())
