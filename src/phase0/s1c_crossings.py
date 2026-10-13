"""Phase0 S1c: build crossings table + match to NWM reaches + RouteLink attrs + flags. Outputs data/phase0/crossings.parquet, unmatched GeoJSON, s1_stats.json."""
import json, numpy as np, pandas as pd, geopandas as gpd, xarray as xr
from shapely.ops import unary_union
P = "data/phase0/"; U = 32617
cs = gpd.read_file(P + "counties.geojson").to_crs(U)
roads = gpd.read_parquet(P + "osm_roads.parquet").to_crs(U)
ww = gpd.read_parquet(P + "osm_waterways.parquet").to_crs(U)
rch = gpd.read_parquet(P + "nwm_flowlines_bbox.parquet").to_crs(U); rch["feature_id"] = rch.feature_id.astype("int64")  # service returns str
cty = cs.dissolve().geometry.iloc[0]

def pts(a, b, label):
    j = gpd.sjoin(a, b, how="inner", predicate="intersects", lsuffix="r", rsuffix="s")
    rows = []
    for i, r in j.iterrows():
        x = r.geometry.intersection(b.geometry.loc[r.index_s]) if hasattr(r, "index_s") else None
    return rows
def inter(a, b, tag):
    """all intersection points of road a-rows with line b-rows (explode multipoints; shared line overlaps -> midpoint)."""
    bs = b.geometry.values; tree = b.sindex; out = []
    for i, g in zip(a.index, a.geometry.values):
        for k in tree.query(g, predicate="intersects"):
            x = g.intersection(bs[k])
            if x.is_empty: continue
            for p in (x.geoms if hasattr(x, "geoms") else [x]):
                out.append((i, b.index[k], p.centroid if p.geom_type != "Point" else p))
    return pd.DataFrame(out, columns=["road_i", "src_i", "geometry"]).pipe(lambda d: gpd.GeoDataFrame(d, geometry="geometry", crs=U))

A = inter(roads, ww, "osm_waterway"); A["source"] = "osm_waterway"
B = inter(roads, rch, "nwm_reach"); B["source"] = "nwm_reach"
for d in (A, B): d["in_county"] = d.geometry.within(cty)
A, B = A[A.in_county], B[B.in_county]
# dedupe: A first (cluster pts within 15 m per road way), then B points >30 m from any A point
def cluster(d):
    d = d.copy(); d["g"] = d.geometry.buffer(15); u = d.dissolve(by="road_i")  # per road way
    res = []
    for i, r in u.iterrows():
        for p in (r.g.geoms if hasattr(r.g, "geoms") else [r.g]):
            m = d[(d.road_i == i) & d.geometry.within(p)]
            res.append(dict(road_i=i, src_i=m.src_i.iloc[0], source=m.source.iloc[0], geometry=m.geometry.union_all().centroid))
    return gpd.GeoDataFrame(res, geometry="geometry", crs=U)
A = cluster(A); B = cluster(B)
near = A.geometry.union_all().buffer(30) if len(A) else None
B = B[~B.geometry.within(near)] if near is not None else B
X = pd.concat([A, B], ignore_index=True); X = gpd.GeoDataFrame(X, geometry="geometry", crs=U)
r = roads.loc[X.road_i]
X["osm_road_id"] = r.osm_id.values; X["road_name"] = r.name.values; X["road_ref"] = r.ref.values; X["road_class"] = r.highway.values
X["road_bridge"] = r.bridge.values; X["road_culvert"] = r.culvert.values; X["road_tunnel"] = r.tunnel.values
w = ww.reindex(X.src_i.where(X.source == "osm_waterway"))
X["osm_waterway_name"] = w.name.values; X["osm_waterway_type"] = w.waterway.values
X["county_fp"] = gpd.sjoin(X[["geometry"]], cs[["COUNTYFP", "geometry"]], how="left", predicate="within")["COUNTYFP"].values
# match to nearest NWM reach (cap 500 m just to quantify; 50/100 thresholds applied downstream)
m = gpd.sjoin_nearest(X[["geometry"]], rch[["feature_id", "name", "strm_order", "geometry"]], how="left", max_distance=500, distance_col="match_dist_m")
m = m[~m.index.duplicated(keep="first")]
X["feature_id"] = m.feature_id.reindex(X.index).values; X["match_dist_m"] = m.match_dist_m.reindex(X.index).values
X["nwm_name"] = m["name"].reindex(X.index).values; X["strm_order"] = m.strm_order.reindex(X.index).values
X["match_method"] = np.where(X.feature_id.isna(), "none_within_500m", np.where(X.match_dist_m < 1, "road_x_reach_intersection", "nearest_reach_" + np.where(X.match_dist_m <= 50, "le50m", np.where(X.match_dist_m <= 100, "50_100m", "gt100m"))))
X["stream_name"] = X.osm_waterway_name.fillna(X.nwm_name)
# RouteLink attrs (v3.1.6)
d = xr.open_dataset(P + "raw/RouteLink_CONUS_v3.1.6.nc")
rl = pd.DataFrame({"feature_id": d["link"].values.astype("int64"), "rl_order": d["order"].values, "rl_length_m": d["Length"].values, "rl_slope": d["So"].values, "rl_wbcomid": d["NHDWaterbodyComID"].values, "rl_gage": d["gages"].values}).drop_duplicates("feature_id")
rl["rl_gage"] = rl.rl_gage.map(lambda b: b.decode().strip() if isinstance(b, bytes) else str(b).strip())
X["feature_id"] = X.feature_id.astype("Int64")
X = X.merge(rl, on="feature_id", how="left")
X["in_routelink"] = X.rl_order.notna() | X.feature_id.isna()
# flags (heuristics, documented in report)
X["flag_ditch_like"] = X.osm_waterway_type.isin(["ditch", "drain", "canal"])
X["flag_tidal_like"] = (X.osm_waterway_type == "tidal_channel") | ((X.rl_slope < 2e-4) & (X.strm_order >= 3)) | (X.rl_wbcomid.fillna(0) > 0)
X["flag_headwater_o1"] = X.strm_order == 1
X.insert(0, "crossing_id", [f"X{c}_{i:05d}" for i, c in enumerate(X.county_fp.fillna("000"))])
W = X.to_crs(4326); X["lat"] = W.geometry.y.values; X["lon"] = W.geometry.x.values
out = X.drop(columns=["road_i", "src_i"]).to_crs(4326)
out.to_parquet(P + "crossings.parquet")
um = out[~(out.match_dist_m <= 100)]; um.to_file(P + "crossings_unmatched.geojson", driver="GeoJSON")
st = dict(n=len(out), by_source=out.source.value_counts().to_dict(), by_county=out.county_fp.value_counts().to_dict(),
          m50=float((out.match_dist_m <= 50).mean()), m100=float((out.match_dist_m <= 100).mean()),
          m50_osm=float((out[out.source == "osm_waterway"].match_dist_m <= 50).mean()), m100_osm=float((out[out.source == "osm_waterway"].match_dist_m <= 100).mean()),
          unmatched_n=len(um), per_reach=out.dropna(subset=["feature_id"]).groupby("feature_id").size().describe().to_dict(),
          reaches_with_xing=int(out.feature_id.nunique()), order_counts=out.strm_order.value_counts().sort_index().to_dict(),
          flags={c: int(out[c].sum()) for c in ["flag_ditch_like", "flag_tidal_like", "flag_headwater_o1"]},
          not_in_routelink=int((~out.in_routelink).sum()), reaches_total=len(rch), reaches_in_rl=int(rch.feature_id.isin(rl.feature_id).sum()))
json.dump(st, open(P + "s1_stats.json", "w"), indent=1, default=str); print(json.dumps(st, indent=1, default=str))
