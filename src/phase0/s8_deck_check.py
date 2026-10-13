"""Phase0 follow-up 4: does 1 m lidar (road crest) agree with independent surveyed heights near NBI bridges? Independent heights = NGS datasheet marks (NAVD88 ortho height, m)
set in bridge abutments / footings / massive structures / pavement within 60 m of a seed bridge. NGS has NO deck elevation; marks are structure/ground references, so this tests DEM bias and datum, not deck height directly."""
import json, numpy as np, pandas as pd, geopandas as gpd, rasterio
P = "data/phase0/"; U = 32617
M = pd.read_parquet(P + "ngs_marks_ortho.parquet"); M = M[M.VERT_DATUM.str.strip() == "NAVD 88"].copy(); M["ORTHO_HT"] = M.ORTHO_HT.astype(float)
M["code"] = M.SETTING.str.extract(r"^(\d+)")[0]; M = M[M.code.isin(["31", "32", "34", "36", "37", "38"])]
M = gpd.GeoDataFrame(M, geometry=gpd.points_from_xy(M.lon, M.lat), crs=4326).to_crs(U)
X = gpd.read_parquet(P + "crossings_v2.parquet").to_crs(U); S = X[(X.src != "osm_secondary") & X.structure_type.fillna("").str.contains("BRIDGE")]
j = gpd.sjoin_nearest(M, S[["crossing_id", "nbi_structure_no", "feature_name", "road_carried", "geometry"]], max_distance=60, distance_col="d", how="inner").sort_values("d")
j = j.drop_duplicates("crossing_id").head(14)   # nearest mark per bridge, 14 tried so >=10 survive nodata/tile gaps
R = gpd.read_parquet(P + "osm_roads.parquet").to_crs(U); T = pd.read_parquet(P + "tnm_1m_products.parquet")
T["geometry"] = [__import__("shapely.geometry", fromlist=["box"]).box(b["minX"], b["minY"], b["maxX"], b["maxY"]) for b in T.boundingBox]; T = gpd.GeoDataFrame(T, crs=4326).to_crs(U)
rows = []
for _, r in j.iterrows():
    rec = dict(crossing_id=r.crossing_id, nbi=r.nbi_structure_no, stream=r.feature_name, road=r.road_carried, ngs_pid=r.PID, ngs_setting=r.SETTING, ngs_class=r.VERT_CLASS, ngs_order=r.VERT_ORDER, ngs_ortho_m=r.ORTHO_HT, d_mark_to_bridge_m=r.d)
    t = T[T.contains(r.geometry)]
    if t.empty: rec["note"] = "no_1m_tile"; rows.append(rec); continue
    try:
        with rasterio.open("/vsicurl/" + t.iloc[0].downloadURL) as ds:
            tr = lambda g: gpd.GeoSeries([g], crs=U).to_crs(ds.crs).iloc[0]
            val = lambda g: (lambda v: np.nan if (v == ds.nodata or v < -500) else float(v))(next(ds.sample([(tr(g).x, tr(g).y)]))[0])
            rec["dem_at_mark_m"] = val(r.geometry)
            br = S[S.crossing_id == r.crossing_id].geometry.iloc[0]; rd = R[R.distance(br) < 30]
            if len(rd):
                road = rd.loc[rd.distance(br).idxmin()].geometry; s0 = road.project(br); pts = [road.interpolate(x) for x in np.arange(max(0, s0 - 40), min(road.length, s0 + 40) + 1e-6, 5)]
                v = np.array([val(p) for p in pts]); rec["crest_max_m"] = float(np.nanmax(v)) if np.isfinite(v).any() else np.nan; rec["crest_median_m"] = float(np.nanmedian(v)) if np.isfinite(v).any() else np.nan
                rec["bridge_pt_dem_m"] = val(br); rec["road_nodata_frac"] = float(np.isnan(v).mean())
            else: rec["note"] = "no_osm_road_within_30m"
    except Exception as e: rec["note"] = f"read_error:{type(e).__name__}"
    rows.append(rec)
D = pd.DataFrame(rows)
if "note" not in D: D["note"] = ""
D["mark_minus_dem"] = D.ngs_ortho_m - D.dem_at_mark_m; D["crest_minus_mark"] = D.crest_max_m - D.ngs_ortho_m
D.to_csv(P + "s8_deck_check.csv", index=False); pd.set_option("display.width", 250, "display.max_columns", 30)
print(D[["crossing_id", "stream", "road", "ngs_setting", "ngs_ortho_m", "dem_at_mark_m", "crest_max_m", "bridge_pt_dem_m", "mark_minus_dem", "crest_minus_mark", "d_mark_to_bridge_m", "note"]].round(2).to_string())
ok = D.dropna(subset=["dem_at_mark_m"]); print("n with DEM at mark", len(ok), "| DEM-at-mark minus mark: median %.2f, mean abs %.2f, p90 abs %.2f" % ((-ok.mark_minus_dem).median(), ok.mark_minus_dem.abs().mean(), ok.mark_minus_dem.abs().quantile(.9)))
ok2 = D.dropna(subset=["crest_max_m"]); print("n with crest", len(ok2), "| crest minus mark: median %.2f, mean abs %.2f" % (ok2.crest_minus_mark.median(), ok2.crest_minus_mark.abs().mean()))
