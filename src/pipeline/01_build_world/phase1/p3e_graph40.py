"""Phase1b step 2b/3a: drivable graph for the 3 counties + 40 km buffer (Geofabrik NC + SC extracts, ways de-duplicated by id), snapping, and derived EXIT points.
Exits are derived, not assumed: every graph segment of a major class (motorway/trunk/primary; secondary listed separately) that crosses the outer boundary of the 3-county union polygon gives an exit at its endpoint
OUTSIDE the boundary; exits closer than 500 m with the same road ref/name are merged. The list is written to data/phase1b/exits.csv."""
import os, json, numpy as np, pandas as pd, geopandas as gpd, osmium
from shapely.geometry import LineString
from collections import Counter
O = "data/phase1b/"; U = 32617
cs = gpd.read_file("data/phase0/counties.geojson").to_crs(U); bnd = cs.union_all(); zone = bnd.buffer(40000)
x0, y0, x1, y1 = gpd.GeoSeries([zone], crs=U).to_crs(4326).total_bounds; print("graph bbox", x0, y0, x1, y1)
DRIVE = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "living_street", "service", "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link"}
SPEED = {"motorway": 100, "motorway_link": 60, "trunk": 80, "trunk_link": 50, "primary": 65, "primary_link": 45, "secondary": 55, "secondary_link": 40, "tertiary": 50, "tertiary_link": 35, "unclassified": 40, "residential": 35, "living_street": 15, "service": 20}
ways, seen = [], set()
for pbf in ("data/raw/nc.osm.pbf", O + "raw/south-carolina-latest.osm.pbf"):
    if not os.path.exists(pbf): print("MISSING", pbf); continue
    for o in osmium.FileProcessor(pbf).with_locations().with_filter(osmium.filter.KeyFilter("highway")):
        if not o.is_way() or o.id in seen: continue
        t = o.tags; h = t.get("highway")
        if h not in DRIVE: continue
        if h == "service" and t.get("service") in ("parking_aisle", "driveway", "drive-through", "emergency_access"): continue
        if t.get("access") in ("no", "private") or t.get("motor_vehicle") in ("no", "private"): continue
        try: pts = [(n.ref, n.lon, n.lat) for n in o.nodes]
        except Exception: continue
        m = len(pts) // 2
        if len(pts) < 2 or not any(x0 < p[1] < x1 and y0 < p[2] < y1 for p in (pts[0], pts[m], pts[-1])): continue
        ow = t.get("oneway"); ow = "fwd" if (ow in ("yes", "true", "1") or t.get("junction") == "roundabout" or (h in ("motorway", "motorway_link") and ow != "no")) else ("rev" if ow == "-1" else "both")
        seen.add(o.id); ways.append((o.id, h, t.get("name"), t.get("ref"), ow, t.get("bridge") or t.get("tunnel") or "", pts))
    print(pbf, "ways so far", len(ways), flush=True)
use = Counter(); [use.update(set(n for n, _, _ in w[6])) for w in ways]; xy = {}; [xy.update({n: (lo, la) for n, lo, la in w[6]}) for w in ways]
seg = []
for wid, h, nm, ref, ow, br, pts in ways:
    cut = [0] + [i for i in range(1, len(pts) - 1) if use[pts[i][0]] > 1] + [len(pts) - 1]
    for a, b in zip(cut[:-1], cut[1:]):
        p = pts[a:b + 1]
        if p[0][0] == p[-1][0] and len(p) < 3: continue
        seg.append((wid, h, nm, ref, ow, br, p[0][0], p[-1][0], LineString([(lo, la) for _, lo, la in p])))
S = gpd.GeoDataFrame(seg, columns=["way_id", "highway", "name", "ref", "oneway", "bridge", "u_osm", "v_osm", "geometry"], crs=4326).to_crs(U)
S["length_m"] = S.length; S["speed_kmh"] = S.highway.map(SPEED); S["time_s"] = S.length_m / (S.speed_kmh / 3.6); S["seg_id"] = np.arange(len(S))
nid = {n: i for i, n in enumerate(pd.unique(np.r_[S.u_osm.values, S.v_osm.values]))}; S["u"] = S.u_osm.map(nid); S["v"] = S.v_osm.map(nid)
N = pd.DataFrame({"node": list(nid.values()), "osm_id": list(nid.keys())}); N["lon"] = [xy[n][0] for n in N.osm_id]; N["lat"] = [xy[n][1] for n in N.osm_id]
N = gpd.GeoDataFrame(N, geometry=gpd.points_from_xy(N.lon, N.lat), crs=4326).to_crs(U); S.to_parquet(O + "graph_segments.parquet"); N.to_parquet(O + "graph_nodes.parquet")
print("segments", len(S), "nodes", len(N), "km", round(S.length_m.sum() / 1000))
# ---- snap crossings (<=50 m; prefer bridge-tagged segment), origins, facilities
X = gpd.read_parquet("data/phase0/crossings_v2.parquet").to_crs(U)
c = gpd.sjoin(X[["crossing_id", "geometry"]].assign(g=X.geometry.buffer(50)).set_geometry("g").drop(columns="geometry"), S[["seg_id", "bridge", "geometry"]], how="left", predicate="intersects").dropna(subset=["seg_id"])
c["seg_id"] = c.seg_id.astype(int); c["d"] = [X.geometry.loc[i].distance(S.geometry.iloc[s]) for i, s in zip(c.index, c.seg_id)]; c["bt"] = c.bridge != ""
c = c.sort_values(["bt", "d"], ascending=[False, True]).groupby(level=0).first(); X = X.join(c[["seg_id", "d"]].rename(columns={"seg_id": "snap_seg", "d": "snap_dist_m"}))
X[["crossing_id", "src", "data_quality", "feature_id", "hazard_threshold_ok", "crest_elev_reliable", "snap_seg", "snap_dist_m"]].to_parquet(O + "crossing_snap.parquet")
print("crossings snapped", int(X.snap_seg.notna().sum()), "of", len(X))
def to_node(df):
    g = gpd.GeoDataFrame(df.copy(), geometry=gpd.points_from_xy(df.lon, df.lat), crs=4326).to_crs(U); j = gpd.sjoin_nearest(g, N[["node", "geometry"]], how="left", distance_col="snap_m"); return j[~j.index.duplicated()]
B = gpd.read_parquet("data/phase1/origins_blocks.parquet"); B = B[B.pop20 > 0].reset_index(drop=True); Bn = to_node(B[["geoid20", "pop20", "county", "lon", "lat"]]); Bn.drop(columns="geometry").to_parquet(O + "origins_snapped.parquet")
print("origins", len(Bn), "snap>500 m", int((Bn.snap_m > 500).sum()), "snap>1500 m", int((Bn.snap_m > 1500).sum()))
H = pd.read_csv(O + "hospitals_40km.csv", dtype={"facility_id": str}); Hn = to_node(H); Hn = Hn[Hn.snap_m < 500]; Hn.drop(columns="geometry").to_parquet(O + "hospitals_snapped.parquet"); print("hospitals snapped", len(Hn), "of", len(H))
F = pd.read_csv(O + "fire_stations_40km.csv"); Fn = to_node(F); Fn = Fn[Fn.snap_m < 500]; Fn.drop(columns="geometry").to_parquet(O + "firestations_snapped.parquet"); print("fire stations snapped", len(Fn), "of", len(F))
# ---- exits: segments crossing the outer boundary
line = bnd.boundary; ex = []; N_i = N.set_index("node")
for _, s in S[S.highway.isin(["motorway", "trunk", "primary", "secondary"]) & S.intersects(line)].iterrows():
    for nd in (s.u, s.v):
        if not N_i.geometry.loc[nd].within(bnd): ex.append(dict(node=int(nd), highway=s.highway, ref=s.ref, name=s["name"], seg_id=int(s.seg_id), x=N_i.geometry.loc[nd].x, y=N_i.geometry.loc[nd].y))
E = pd.DataFrame(ex).drop_duplicates("node")
E["key"] = E.ref.fillna(E.name).fillna("unnamed"); E = E.sort_values("highway", key=lambda s: s.map({"motorway": 0, "trunk": 1, "primary": 2, "secondary": 3}))
keep = []
for _, r in E.iterrows():
    if any((r.key == k.key) and np.hypot(r.x - k.x, r.y - k.y) < 500 for k in keep): continue
    keep.append(r)
E = pd.DataFrame(keep); Eg = gpd.GeoDataFrame(E, geometry=gpd.points_from_xy(E.x, E.y), crs=U).to_crs(4326); E["lon"] = Eg.geometry.x.values; E["lat"] = Eg.geometry.y.values
E["major"] = E.highway.isin(["motorway", "trunk", "primary"]); E.drop(columns=["x", "y"]).to_csv(O + "exits.csv", index=False)
print("EXITS (major = motorway/trunk/primary):", int(E.major.sum()), "| plus secondary:", int((~E.major).sum())); print(E[E.major][["highway", "ref", "name", "lat", "lon"]].round(4).to_string())
