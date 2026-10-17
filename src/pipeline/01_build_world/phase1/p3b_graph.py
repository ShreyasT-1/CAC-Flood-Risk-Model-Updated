"""Phase1 step 3b: drivable road graph (OSM, Geofabrik NC extract on disk) for the 3 counties + 10 km buffer (bbox of the buffered polygon); junction-to-junction segments, directed arcs, snap crossings/origins/facilities."""
import json, numpy as np, pandas as pd, geopandas as gpd, osmium
from shapely.geometry import LineString
from collections import Counter
O = "data/phase1/"; U = 32617
cs = gpd.read_file("data/phase0/counties.geojson").to_crs(U); x0, y0, x1, y1 = gpd.GeoSeries([cs.union_all().buffer(10000)], crs=U).to_crs(4326).total_bounds
print("graph bbox", x0, y0, x1, y1)
DRIVE = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "living_street", "service", "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link"}
SPEED = {"motorway": 100, "motorway_link": 60, "trunk": 80, "trunk_link": 50, "primary": 65, "primary_link": 45, "secondary": 55, "secondary_link": 40, "tertiary": 50, "tertiary_link": 35, "unclassified": 40, "residential": 35, "living_street": 15, "service": 20}  # km/h, my defaults (no maxspeed parsing)
ways = []
for o in osmium.FileProcessor("data/raw/nc.osm.pbf").with_locations().with_filter(osmium.filter.KeyFilter("highway")):
    if not o.is_way(): continue
    t = o.tags; h = t.get("highway")
    if h not in DRIVE: continue
    if h == "service" and t.get("service") in ("parking_aisle", "driveway", "drive-through", "emergency_access"): continue
    if t.get("access") in ("no", "private") or t.get("motor_vehicle") in ("no", "private"): continue
    try: pts = [(n.ref, n.lon, n.lat) for n in o.nodes]
    except Exception: continue
    if len(pts) < 2 or not any(x0 < p[1] < x1 and y0 < p[2] < y1 for p in pts[:1] + pts[-1:] + pts[len(pts) // 2:len(pts) // 2 + 1]): continue
    ow = t.get("oneway"); ow = "fwd" if (ow in ("yes", "true", "1") or t.get("junction") == "roundabout" or (h in ("motorway", "motorway_link") and ow != "no")) else ("rev" if ow == "-1" else "both")
    ways.append((o.id, h, t.get("name"), t.get("ref"), ow, t.get("bridge") or t.get("tunnel") or "", pts))
print("ways", len(ways))
use = Counter(); [use.update(set(n for n, _, _ in w[6])) for w in ways]
xy = {}; [xy.update({n: (lo, la) for n, lo, la in w[6]}) for w in ways]
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
N = gpd.GeoDataFrame(N, geometry=gpd.points_from_xy(N.lon, N.lat), crs=4326).to_crs(U)
S.to_parquet(O + "graph_segments.parquet"); N.to_parquet(O + "graph_nodes.parquet")
print("segments", len(S), "nodes", len(N), "km", round(S.length_m.sum() / 1000), "bridge-tagged segs", int((S.bridge != "").sum()), S.highway.value_counts().to_dict())
