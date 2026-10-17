"""Phase0 follow-up 2: crossings v2 seeded from NCDOT structures + NBI bridges on named waterways; OSM-only crossings kept as a flagged secondary set."""
import json, re, numpy as np, pandas as pd, geopandas as gpd, xarray as xr
P = "data/phase0/"; U = 32617
s = gpd.read_parquet(P + "ncdot_structures_pilot.parquet").to_crs(U); n = gpd.read_parquet(P + "nbi_pilot.parquet").to_crs(U)
rch = gpd.read_parquet(P + "nwm_flowlines_bbox.parquet").to_crs(U); rch["feature_id"] = rch.feature_id.astype("int64")
X1 = gpd.read_parquet(P + "crossings.parquet").to_crs(U)
# waterway-name test: v1 regex extended by hand after reading the 106 rejected names (TRIBUTARY/TRIBITARY, CRK, ICW/INTRACOASTAL, W/W, CUT, HOLE, SAUCE PAN, CAPE FEAR R)
WATER = re.compile(r"creek|river|branch|swamp|canal|ditch|run\b|bay|sound|inlet|brook|stream|slough|pond|lake|waterway|\bcr\b|\bbr\b|channel|marsh|gut|bayou|drain|trib|\bcrk|\bicw\b|intracoastal|w/w|\bcut\b|\bhole\b|sauce pan|cape fear r\b", re.I)
NOT = re.compile(r"wildlife|wet ?lands|\bR/?R\b|railroad|rail road|parking", re.I)  # wildlife crossings / wetlands / railroads are not stream crossings
def wlike(x):
    x = str(x)
    return bool(WATER.search(x)) and not NOT.search(x)
s = s[s.BRDG_TYP_NM.isin(["BRIDGE", "CULVERT", "PIPE"])].copy(); s = s[s.FTR_INTRSC.map(wlike)]
n = n[n.FEATURES_DESC_006A.map(wlike)].copy()
rows = []
for i, r in s.iterrows():
    b = n[n.ncdot_link == r.BRDG_NBR]; b = b.iloc[0] if len(b) else None
    g = lambda c: None if b is None else b[c]
    rows.append(dict(src="ncdot" + ("+nbi" if b is not None else ""), ncdot_brdg_nbr=r.BRDG_NBR, nbi_structure_no=None if b is None else b.STRUCTURE_NUMBER_008.strip(), structure_type=r.BRDG_TYP_NM,
                     feature_name=str(r.FTR_INTRSC).strip(), road_carried=str(r.F_CARRIED).strip(), county=r.COUNTY, geometry=r.geometry, year_built=g("YEAR_BUILT_027"),
                     nbi_structure_len_m=g("STRUCTURE_LEN_MT_049"), nbi_waterway_eval=g("WATERWAY_EVAL_071"), nbi_channel_cond=g("CHANNEL_COND_061"), nbi_scour_critical=g("SCOUR_CRITICAL_113")))
for i, b in n[~n.ncdot_link.isin(set(s.BRDG_NBR))].iterrows():
    rows.append(dict(src="nbi_only", ncdot_brdg_nbr=None, nbi_structure_no=b.STRUCTURE_NUMBER_008.strip(), structure_type="BRIDGE(NBI)", feature_name=str(b.FEATURES_DESC_006A).strip(),
                     road_carried=str(b.FACILITY_CARRIED_007).strip(), county=b.COUNTY_CODE_003, geometry=b.geometry, year_built=b.YEAR_BUILT_027, nbi_structure_len_m=b.STRUCTURE_LEN_MT_049,
                     nbi_waterway_eval=b.WATERWAY_EVAL_071, nbi_channel_cond=b.CHANNEL_COND_061, nbi_scour_critical=b.SCOUR_CRITICAL_113))
S = gpd.GeoDataFrame(rows, geometry="geometry", crs=U).reset_index(drop=True)
# secondary set: v1 crossings with no seed structure within 100 m
X1s = X1[~X1.geometry.within(S.geometry.union_all().buffer(100))][["geometry", "road_name", "road_class", "osm_waterway_name", "osm_waterway_type", "source"]].rename(columns={"source": "v1_source", "osm_waterway_name": "feature_name", "road_name": "road_carried"})
X1s["src"] = "osm_secondary"
A = gpd.GeoDataFrame(pd.concat([S, X1s], ignore_index=True), geometry="geometry", crs=U)
m = gpd.sjoin_nearest(A[["geometry"]], rch[["feature_id", "name", "strm_order", "geometry"]], how="left", max_distance=500, distance_col="match_dist_m"); m = m[~m.index.duplicated()]
A["feature_id"] = m.feature_id.reindex(A.index).astype("Int64"); A["match_dist_m"] = m.match_dist_m.reindex(A.index).values
A["nwm_name"] = m["name"].reindex(A.index).values; A["strm_order"] = m.strm_order.reindex(A.index).values
A["n_reaches_100m"] = [int((rch.distance(g) <= 100).sum()) for g in A.geometry]
A["match_method"] = np.where(A.match_dist_m.isna(), "none_within_500m", np.where(A.match_dist_m <= 50, "nearest_reach_le50m", np.where(A.match_dist_m <= 100, "nearest_reach_50_100m", "nearest_reach_gt100m")))
far = A.match_dist_m > 100
A.loc[far, "feature_id"] = pd.NA; A.loc[far, ["nwm_name", "strm_order"]] = np.nan  # beyond 100 m is NOT a match: distance kept, reach fields blanked (not filled)
d = xr.open_dataset(P + "raw/RouteLink_CONUS_v3.1.6.nc")
rl = pd.DataFrame({"feature_id": d["link"].values.astype("int64"), "rl_slope": d["So"].values, "rl_length_m": d["Length"].values}).drop_duplicates("feature_id")
A["feature_id"] = A.feature_id.astype("Int64"); A = A.merge(rl.astype({"feature_id": "Int64"}), on="feature_id", how="left")
tok = lambda x: set(re.findall(r"[a-z]{3,}", str(x).lower())) - {"creek", "river", "branch", "swamp", "canal", "ditch", "none", "nan", "the", "tributary", "trib", "crk"}
A["name_agrees"] = [bool(tok(a) & tok(b)) if (pd.notna(a) and pd.notna(b)) else np.nan for a, b in zip(A.feature_name, A.nwm_name)]
A["flag_headwater_o1"] = A.strm_order == 1
A["flag_tidal_like"] = ((A.rl_slope < 2e-4) & (A.strm_order >= 3)) | A.feature_name.fillna("").str.contains(r"intracoastal|\bicw\b|tidal|sound|inlet|\bbay\b|discharge|cape fear r", case=False, regex=True)
A["flag_ditch_like"] = A.osm_waterway_type.isin(["ditch", "drain", "canal"]) | A.feature_name.fillna("").str.contains(r"ditch|drain|canal", case=False, regex=True)
matched = A.feature_id.notna(); seed = A.src != "osm_secondary"
good = seed & matched & (A.match_dist_m <= 50) & (A.strm_order >= 2) & ~A.flag_tidal_like & (A.name_agrees.fillna(False).astype(bool) | A.src.str.contains("nbi"))
poor = ~matched | (~seed & ((A.strm_order == 1) | A.flag_ditch_like))
A["data_quality"] = np.where(good, "good", np.where(poor, "poor", "fair"))
A.insert(0, "crossing_id", [f"V2_{i:04d}" for i in range(len(A))])
W = A.to_crs(4326); A["lat"] = W.geometry.y.values; A["lon"] = W.geometry.x.values
A.to_crs(4326).to_parquet(P + "crossings_v2.parquet"); A.to_crs(4326).to_file(P + "crossings_v2.geojson", driver="GeoJSON")
def rep(d):
    mm = d.feature_id.notna()
    return dict(n=len(d), matched_100=int(mm.sum()), match_rate_100=round(float(mm.mean()), 3), match_rate_50=round(float((d.match_dist_m <= 50).mean()), 3),
                order_dist={int(k): int(v) for k, v in d[mm].strm_order.value_counts().sort_index().items()}, on_order1=int((d.strm_order[mm] == 1).sum()),
                order1_share_of_matched=round(float((d.strm_order[mm] == 1).mean()), 3) if mm.any() else None, quality=d.data_quality.value_counts().to_dict(),
                tidal_like=int(d.flag_tidal_like.sum()), multi_reach_ambiguous=int((d.n_reaches_100m > 1).sum()), unique_reaches=int(d.feature_id.nunique()))
st = dict(seed=rep(A[seed]), seed_by_src=A[seed].src.value_counts().to_dict(), seed_by_type=A[seed].structure_type.value_counts().to_dict(), secondary=rep(A[~seed]), all=rep(A),
          seed_name_agree_among_matched=round(float(A[seed & matched].name_agrees.astype(float).mean()), 3),
          seed_unmatched_examples=A[seed & ~matched][["crossing_id", "feature_name", "road_carried", "match_dist_m"]].head(5).to_dict("records"))
json.dump(st, open(P + "s6_stats.json", "w"), indent=1, default=str); print(json.dumps(st, indent=1, default=str))
