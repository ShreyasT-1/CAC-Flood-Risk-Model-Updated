"""Phase 2 / T12: USGS STN Florence high-water marks vs lidar road crest at seed crossings, and the hindcast hazard output at those crossings.
All definitions are fixed in docs/validation_protocol.md, Amendment 2 (written before this script ran). Run once.
Usage (repo root): python src/validation/40_t12_hwm_crest.py"""
import os, json, time, requests, numpy as np, pandas as pd, geopandas as gpd, rasterio, sys
sys.path.insert(0, "src/live"); from nwm_retro import fetch
O = "data/phase2/t12/"; U = 32119; CFS = 35.3146667; FT = 0.3048; rng = np.random.default_rng(20261011); NB = 10000
# ---- HWMs ----
H = pd.DataFrame(json.load(open(O + "stn_hwms_florence_nc.json")))
n0 = len(H); H = H[(H.verticalDatumName == "NAVD88") & H.elev_ft.notna() & ~H.hwmQualityName.isin(["VP: > 0.40 ft", "Unknown/Historical"])].copy()
H["hwm_m"] = H.elev_ft * FT; H = gpd.GeoDataFrame(H, geometry=gpd.points_from_xy(H.longitude_dd, H.latitude_dd), crs=4326).to_crs(U)
print("HWMs", n0, "-> qualifying", len(H), H.hwm_environment.value_counts().to_dict())
# ---- crossings + NBI length ----
S = gpd.read_parquet("data/phase2/t10/structures_nc.parquet").to_crs(U)
n = pd.read_csv("data/phase0/raw/NBI_NC25.txt", dtype=str, quotechar="'", encoding="latin1", low_memory=False)
def dms(v, lon):
    v = str(v).strip()
    if not v.isdigit(): return np.nan
    d, rest = (int(v[:3]), v[3:]) if lon else (int(v[:2]), v[2:]); return d + int(rest[:2]) / 60 + int(rest[2:]) / 100 / 3600
n["lat"] = n.LAT_016.map(lambda v: dms(v, False)); n["lon"] = -n.LONG_017.map(lambda v: dms(v, True)); n = n.dropna(subset=["lat", "lon"])
n = gpd.GeoDataFrame({"nbi_len": pd.to_numeric(n.STRUCTURE_LEN_MT_049, errors="coerce").values}, geometry=gpd.points_from_xy(n.lon, n.lat), crs=4326).to_crs(U)
j = gpd.sjoin_nearest(S[["crossing_id", "geometry"]], n, how="left", max_distance=50); j = j[~j.index.duplicated()]
S["len_m"] = np.where(S.src == "nbi_only", S.nbi_len_m, j.nbi_len.reindex(S.index).values)
S["is_bridge"] = S.structure_type.str.contains("BRIDGE"); S["length_class"] = np.where(~S.is_bridge, "culvert/pipe", np.where(S.len_m.isna(), "bridge_len_unknown", np.where(S.len_m >= 35, "bridge_long_ge35m", "bridge_short_lt35m")))
# ---- pairing (nearest qualifying HWM within 1 km; primary uses <= 300 m) ----
P = gpd.sjoin_nearest(S, H[["hwm_id", "hwm_m", "hwm_environment", "hwmQualityName", "hwmTypeName", "countyName", "geometry"]], how="inner", max_distance=1000, distance_col="hwm_dist_m"); P = P[~P.index.duplicated()].copy()
print("crossings with a qualifying HWM <= 1 km:", len(P), "| <= 300 m:", int((P.hwm_dist_m <= 300).sum()), P.length_class.value_counts().to_dict())
# ---- crest from 3DEP 1 m ----
R = gpd.read_parquet("data/phase2/t10/osm_roads_nc.parquet").to_crs(U)
TNM = "https://tnmaccess.nationalmap.gov/api/v1/products"
def tiles(pt_ll):
    for k in range(6):
        try:
            d = requests.get(TNM, params=dict(datasets="Digital Elevation Model (DEM) 1 meter", bbox=f"{pt_ll.x},{pt_ll.y},{pt_ll.x},{pt_ll.y}", prodFormats="GeoTIFF", outputFormat="JSON"), timeout=120).json()
            return sorted(d.get("items", []), key=lambda i: i.get("publicationDate", ""), reverse=True)
        except Exception: time.sleep(10)
    return []
cache = O + "crest_cache.parquet"; C = pd.read_parquet(cache) if os.path.exists(cache) else pd.DataFrame(columns=["crossing_id"])
rows = []
for i, r in P[~P.crossing_id.isin(C.crossing_id)].iterrows():
    rec = dict(crossing_id=r.crossing_id, crest_m=np.nan, crest_note="")
    rd = R.iloc[R.sindex.query(r.geometry.buffer(30), predicate="intersects")]
    if rd.empty: rec["crest_note"] = "no_named_osm_road_within_30m"; rows.append(rec); continue
    road = rd.geometry.iloc[int(np.argmin(rd.distance(r.geometry).values))]; s0 = road.project(r.geometry)
    pts = gpd.GeoSeries([road.interpolate(x) for x in np.arange(max(0, s0 - 40), min(road.length, s0 + 40) + 1e-6, 5)], crs=U)
    ll = gpd.GeoSeries([r.geometry], crs=U).to_crs(4326).iloc[0]; its = tiles(ll)
    if not its: rec["crest_note"] = "no_1m_tile"; rows.append(rec); continue
    for it in its:
        try:
            with rasterio.open("/vsicurl/" + it["downloadURL"]) as ds:
                q = pts.to_crs(ds.crs); v = np.array([x[0] for x in ds.sample([(p.x, p.y) for p in q])], float); v[(v == ds.nodata) | (v < -500)] = np.nan
            if np.isfinite(v).any(): rec.update(crest_m=float(np.nanmax(v)), crest_note="ok", dem_tile=it["title"], dem_pub=it.get("publicationDate"), crest_nodata_frac=float(np.isnan(v).mean())); break
            rec["crest_note"] = "tile_nodata"
        except Exception as e: rec["crest_note"] = f"read_error:{type(e).__name__}"
    rows.append(rec)
if rows: C = pd.concat([C, pd.DataFrame(rows)], ignore_index=True); C.to_parquet(cache)
P = P.merge(C, on="crossing_id", how="left")
# ---- reach + model ----
FS = "https://maps.water.noaa.gov/server/rest/services/reference/static_nwm_flowlines/FeatureServer/0/query"; rr = []
for r in P.itertuples():
    ll = gpd.GeoSeries([r.geometry], crs=U).to_crs(4326).iloc[0]
    for k in range(8):
        try: jj = requests.get(FS, params=dict(where="1=1", geometry=f"{ll.x - .003},{ll.y - .003},{ll.x + .003},{ll.y + .003}", geometryType="esriGeometryEnvelope", inSR=4326, spatialRel="esriSpatialRelIntersects", outFields="feature_id,strm_order,rf_10_0_17c,rf_2_0_17c", outSR=4326, f="geojson"), timeout=120).json(); break
        except Exception: time.sleep(10)
    g = gpd.GeoDataFrame.from_features(jj["features"], crs=4326).to_crs(U) if jj.get("features") else []
    if len(g): d = g.distance(r.geometry); k = int(np.argmin(d.values)); rr.append(dict(crossing_id=r.crossing_id, feature_id=int(g.feature_id.iloc[k]), strm_order=g.strm_order.iloc[k], reach_dist_m=float(d.iloc[k]), q2_cfs=g.rf_2_0_17c.iloc[k], q10_cfs=g.rf_10_0_17c.iloc[k]))
RC = pd.DataFrame(rr, columns=["crossing_id", "feature_id", "strm_order", "reach_dist_m", "q2_cfs", "q10_cfs"]); P = P.merge(RC, on="crossing_id", how="left")
P["assessed"] = (P.reach_dist_m <= 100) & (P.q2_cfs >= 1)
F = fetch(P[P.assessed].feature_id.astype("int64").unique(), pd.Timestamp("2018-09-07 00:00"), pd.Timestamp("2018-10-07 23:00"))
P["peak_cfs"] = [float(F[str(int(f))].max()) * CFS if a else np.nan for f, a in zip(P.feature_id, P.assessed)]
P["peak_q2"] = P.peak_cfs / P.q2_cfs; P["peak_q10"] = P.peak_cfs / P.q10_cfs
P["hwm_minus_crest_m"] = P.hwm_m - P.crest_m; P["hwm_above_crest"] = P.hwm_minus_crest_m > 0; P["hwm_above_crest_1m"] = P.hwm_minus_crest_m > 1
P.drop(columns="geometry").to_csv(O + "t12_pairs.csv", index=False)
# ---- analysis ----
def wilson(k, n, z=1.96):
    if n == 0: return [None, None]
    p = k / n; c = (p + z * z / (2 * n)) / (1 + z * z / n); h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n); return [round(c - h, 3), round(c + h, 3)]
def auc(a, b): a, b = np.asarray(a), np.asarray(b); return float(((a[:, None] > b[None, :]).mean() + .5 * (a[:, None] == b[None, :]).mean())) if len(a) and len(b) else np.nan
def test(D, col, label):
    D = D[D.crest_m.notna()]; out = dict(label=label, n_with_crest=len(D), n_hwm_above=int(D.hwm_above_crest.sum()), share_hwm_above=round(float(D.hwm_above_crest.mean()), 3) if len(D) else None,
                                          share_ci95=wilson(int(D.hwm_above_crest.sum()), len(D)), n_above_crest_plus_1m=int(D.hwm_above_crest_1m.sum()), per_county=D.groupby("countyName").hwm_above_crest.agg(["sum", "count"]).astype(int).to_dict("index"))
    M = D[D.assessed & D[col].notna()]; a = M[M.hwm_above_crest][col].values; b = M[~M.hwm_above_crest][col].values; out.update(model_metric=col, n_model_above=len(a), n_model_below=len(b))
    if min(len(a), len(b)) < 5: out["verdict"] = "too few to test"; return out
    bs = [auc(rng.choice(a, len(a)), rng.choice(b, len(b))) for _ in range(NB)]; out.update(auc=round(auc(a, b), 3), auc_ci95=[round(float(np.percentile(bs, 2.5)), 3), round(float(np.percentile(bs, 97.5)), 3)],
                                                                                    median_ratio_above=round(float(np.median(a)), 2), median_ratio_below=round(float(np.median(b)), 2))
    out["verdict"] = "PASS" if out["auc_ci95"][0] > .5 else "FAIL"; return out
prim = P[(P.hwm_dist_m <= 300) & (P.hwm_environment == "Riverine") & P.length_class.isin(["culvert/pipe", "bridge_short_lt35m"])]
res = [test(prim, "peak_q10", "PRIMARY riverine <=300m, long/unknown-length bridges excluded"), test(prim, "peak_q2", "secondary: same set, peak/q2"),
       test(P[(P.hwm_environment == "Riverine") & P.length_class.isin(["culvert/pipe", "bridge_short_lt35m"])], "peak_q10", "secondary: riverine <=1km"),
       test(P[(P.hwm_dist_m <= 300) & (P.hwm_environment == "Riverine") & (P.length_class != "bridge_long_ge35m")], "peak_q10", "secondary: <=300m incl. unknown-length bridges"),
       test(P[(P.hwm_dist_m <= 1000) & (P.hwm_environment == "Coastal") & (P.length_class != "bridge_long_ge35m")], "peak_q10", "descriptive: coastal HWMs <=1km")]
cnt = dict(pairs_le1km=len(P), pairs_le300m=int((P.hwm_dist_m <= 300).sum()), by_length_class_le300m=P[P.hwm_dist_m <= 300].length_class.value_counts().to_dict(), crest_notes=P.crest_note.value_counts().to_dict(), assessed_reach=int(P.assessed.sum()), primary_set=len(prim))
json.dump(dict(counts=cnt, results=res), open(O + "t12_results.json", "w"), indent=1, default=str); print(json.dumps(cnt, indent=1, default=str)); [print(json.dumps(r, default=str)) for r in res]
