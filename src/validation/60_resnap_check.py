"""Origin re-snap check (2026-10-12): 30 random blocks unreachable under the phase-1 snap and reachable under the phase-2 re-snap, plus all blocks dropped by the re-snap (new snap > 1,500 m).
Per block: snap distance, class/name of the roads at the snapped node, whether the straight line block -> snapped node crosses OSM river/canal/tidal water (>= river-sized; streams/ditches/drains excluded), ramp/service flags.
Usage (repo root): python src/60_resnap_check.py"""
import os, importlib.util, numpy as np, pandas as pd, geopandas as gpd
from shapely.geometry import LineString
os.environ["P2_RESNAP"] = "1"; U = 5070; O = "data/phase2/resnap_check/"; os.makedirs(O, exist_ok=True)
sp = importlib.util.spec_from_file_location("eng", "src/22_engine_p2.py"); eng = importlib.util.module_from_spec(sp); sp.loader.exec_module(eng)
raw = pd.read_parquet("data/phase1b/origins_snapped.parquet"); old = raw[raw.snap_m < 1500].reset_index(drop=True)   # phase-1 snap, as the phase-1 engine used it
new_all = eng.resnap(raw)                                                                                         # phase-2 re-snap of all 6,977 blocks
b = pd.read_parquet("data/phase2/engine/replay_hindcast_base_baseline.parquet"); b = b[b.facility_type == "hospital_ED_acute"]; unreach_old = set(b[~b.baseline_reachable].geoid20)
r = pd.read_parquet("data/phase2/engine/replay_hindcast_resnap_baseline.parquet"); r = r[r.facility_type == "hospital_ED_acute"]; reach_new = set(r[r.baseline_reachable].geoid20)
n = new_all.set_index("geoid20"); o = raw.set_index("geoid20")
dropped = sorted(set(old.geoid20) - set(new_all[new_all.snap_m < 1500].geoid20)); cand = sorted(unreach_old & reach_new)
print("old unreachable blocks", len(unreach_old), "people", int(b[~b.baseline_reachable].pop20.sum()), "| reachable now", len(cand), "| dropped by re-snap", len(dropped), "| old-unreachable AND dropped", len(set(dropped) & unreach_old))
pick = list(np.random.default_rng(20261012).choice(cand, 30, replace=False))
S = gpd.read_parquet("data/phase1b/graph_segments.parquet"); N = pd.read_parquet("data/phase1b/graph_nodes.parquet").set_index("node")
inc = {}
for u, v, h, nm, rf, br in zip(S.u, S.v, S.highway, S.name, S.ref, S.bridge):
    for x in (u, v): inc.setdefault(int(x), []).append((h, nm if isinstance(nm, str) else (rf if isinstance(rf, str) else "")))
RANK = ["motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "service", "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link", "living_street"]
W = gpd.read_parquet("data/phase0/osm_waterways.parquet"); W = W[W.waterway.isin(["river", "canal", "tidal_channel"]) & (W.tunnel.fillna("").astype(str).isin(["", "no", "None"]))].to_crs(U); tree = W.sindex
def desc(node):
    c = inc.get(int(node), []); cls = sorted({h for h, _ in c}, key=lambda h: RANK.index(h) if h in RANK else 99); nms = sorted({m for _, m in c if m})
    return ", ".join(cls), ", ".join(nms[:3]), (len(c) > 0 and all(h.endswith("_link") or h == "service" for h, _ in c)), any(h.endswith("_link") for h, _ in c)
def crosses(lon, lat, node):
    p = gpd.GeoSeries(gpd.points_from_xy([lon, N.lon[node]], [lat, N.lat[node]]), crs=4326).to_crs(U); ln = LineString(list(zip(p.x, p.y))); ix = tree.query(ln, predicate="intersects")
    return (", ".join(sorted(set(W.waterway.values[ix]))) or ""), bool(len(ix))
rows = []
for grp, ids in (("sample_30_now_reachable", pick), ("dropped_21", dropped)):
    for g in ids:
        a = n.loc[g]; ob = o.loc[g]; cls, nm, only_svc, link = desc(a.node); w, cw = crosses(a.lon, a.lat, int(a.node)); cls0, nm0, svc0, link0 = desc(ob.node); w0, cw0 = crosses(ob.lon, ob.lat, int(ob.node))
        rows.append(dict(group=grp, geoid20=g, county=a.county, pop20=int(a.pop20), old_snap_m=round(float(ob.snap_m)), new_snap_m=round(float(a.snap_m)), new_node_road_classes=cls, new_node_road_names=nm, new_only_ramp_or_service=only_svc, new_has_ramp=link,
                         new_line_crosses_water=cw, new_water_type=w, old_node_road_classes=cls0, old_node_road_names=nm0, old_line_crosses_water=cw0, old_was_unreachable=g in unreach_old))
D = pd.DataFrame(rows); D["flag_wrong"] = D.new_only_ramp_or_service | D.new_has_ramp | D.new_line_crosses_water | (D.new_snap_m > 500)
D.to_csv(O + "resnap_check.csv", index=False); pd.set_option("display.width", 260, "display.max_columns", 30, "display.max_rows", 100, "display.max_colwidth", 40)
s = D[D.group == "sample_30_now_reachable"]; print(s[["geoid20", "county", "pop20", "old_snap_m", "new_snap_m", "new_node_road_classes", "new_node_road_names", "new_only_ramp_or_service", "new_has_ramp", "new_line_crosses_water", "new_water_type", "flag_wrong"]].to_string(index=False))
print("\nDROPPED"); print(D[D.group == "dropped_21"][["geoid20", "county", "pop20", "old_snap_m", "new_snap_m", "new_node_road_classes", "new_node_road_names", "new_line_crosses_water", "old_was_unreachable"]].to_string(index=False))
print("\nsample flagged:", int(s.flag_wrong.sum()), "of 30 | crosses water", int(s.new_line_crosses_water.sum()), "| ramp/service-only", int(s.new_only_ramp_or_service.sum()), "| has ramp", int(s.new_has_ramp.sum()), "| new snap > 500 m", int((s.new_snap_m > 500).sum()), "| old line crossed water", int(s.old_line_crosses_water.sum()))
print("median snap m: old", s.old_snap_m.median(), "new", s.new_snap_m.median())
