"""Phase1 step 3c: snap crossings to graph segments (<=50 m; prefer a bridge-tagged segment within range, else nearest), origins and facilities to nearest graph node."""
import json, numpy as np, pandas as pd, geopandas as gpd
O = "data/phase1/"; U = 32617
S = gpd.read_parquet(O + "graph_segments.parquet"); N = gpd.read_parquet(O + "graph_nodes.parquet")
X = gpd.read_parquet("data/phase0/crossings_v2.parquet").to_crs(U)
c = gpd.sjoin(X[["crossing_id", "src", "data_quality", "hazard_threshold_ok", "feature_id", "geometry"]].assign(g=X.geometry.buffer(50)).set_geometry("g").drop(columns="geometry"),
              S[["seg_id", "bridge", "highway", "name", "geometry"]], how="left", predicate="intersects").dropna(subset=["seg_id"])
c["seg_id"] = c.seg_id.astype(int); c["d"] = [X.geometry.loc[i].distance(S.geometry.iloc[s]) for i, s in zip(c.index, c.seg_id)]
c["bridge_tag"] = c.bridge != ""
c = c.sort_values(["bridge_tag", "d"], ascending=[False, True]).groupby(level=0).first()
# a bridge-tagged segment that is 49 m away beats a nearer non-bridge one: accept only if within 50 m (already) -- document in report
X = X.join(c[["seg_id", "d", "bridge_tag", "highway", "name"]].rename(columns={"seg_id": "snap_seg", "d": "snap_dist_m", "highway": "snap_highway", "name": "snap_road_name"}))
X[["crossing_id", "src", "data_quality", "feature_id", "hazard_threshold_ok", "crest_elev_reliable", "snap_seg", "snap_dist_m", "bridge_tag", "snap_highway", "snap_road_name"]].to_parquet(O + "crossing_snap.parquet")
sd = X[X.src != "osm_secondary"]
print("crossings", len(X), "snapped", int(X.snap_seg.notna().sum()), "| seed", len(sd), "snapped", int(sd.snap_seg.notna().sum()), "to bridge-tagged seg", int(sd.bridge_tag.fillna(False).sum()), "| median snap dist", round(float(X.snap_dist_m.median()), 1))
print("segments with >=1 seed crossing", sd.snap_seg.nunique(), "| with hazard-ok seed", sd[sd.hazard_threshold_ok].snap_seg.nunique(), "| secondary matched+hazard_ok segs", X[(X.src == "osm_secondary") & X.hazard_threshold_ok].snap_seg.nunique())
# origins + facilities -> nearest node
def to_node(df, lon="lon", lat="lat"):
    g = gpd.GeoDataFrame(df.copy(), geometry=gpd.points_from_xy(df[lon], df[lat]), crs=4326).to_crs(U)
    j = gpd.sjoin_nearest(g, N[["node", "geometry"]], how="left", distance_col="snap_m"); return j[~j.index.duplicated()]
B = gpd.read_parquet(O + "origins_blocks.parquet"); B = B[B.pop20 > 0].reset_index(drop=True)
Bn = to_node(B[["geoid20", "pop20", "county", "lon", "lat"]]); Bn.drop(columns="geometry").to_parquet(O + "origins_snapped.parquet")
print("origins (populated blocks)", len(Bn), "pop", int(Bn.pop20.sum()), "snap>500 m:", int((Bn.snap_m > 500).sum()), "snap>1500 m:", int((Bn.snap_m > 1500).sum()), "median snap m", round(float(Bn.snap_m.median())))
H = pd.read_csv(O + "hospitals_geocoded.csv", dtype={"facility_id": str}); H = H[H.lat.notna() & (H.emergency == "Yes")]
Hn = to_node(H); inside = gpd.GeoSeries(Hn.geometry, crs=U).within(gpd.read_file("data/phase0/counties.geojson").to_crs(U).union_all().buffer(10000))
Hn = Hn[inside.values & (Hn.snap_m < 300)]; Hn.drop(columns="geometry").to_parquet(O + "hospitals_snapped.parquet"); print("hospitals w/ ED inside 10 km buffer", len(Hn), Hn[["name", "county", "snap_m"]].round(0).to_string())
F = pd.read_csv(O + "fire_stations_osm.csv"); Fn = to_node(F); Fn = Fn[Fn.snap_m < 300]
Fn = Fn[gpd.GeoSeries(Fn.geometry, crs=U).within(gpd.read_file("data/phase0/counties.geojson").to_crs(U).union_all().buffer(10000)).values]; Fn.drop(columns="geometry").to_parquet(O + "firestations_snapped.parquet"); print("fire stations inside buffer", len(Fn))
