"""Phase 2 / T15 Step 2: crossing sets and labels for the chosen events (Amendment 3 + 4). Statewide NWM flowlines + OWP q2/q10 pulled once (tiled bbox queries), statewide seed structures (data/phase2/t10/structures_nc.parquet)
matched to the nearest reach <= 100 m (assessed: q2 >= 1 cfs), per event: counties with >= 1 flood-related CLOSED record, positives = crossing within 100 m (250 m sensitivity) of a closure record started in the window (point or line geometry).
Usage (repo root): python src/52_t15_crossings.py"""
import os, re, json, time, requests, numpy as np, pandas as pd, geopandas as gpd, xarray as xr
from shapely.geometry import Point, LineString, shape
O = "data/phase2/t15/"; U = 32119
FS = "https://maps.water.noaa.gov/server/rest/services/reference/static_nwm_flowlines/FeatureServer/0/query"
# ---- statewide reaches ----
if not os.path.exists(O + "nc_reaches.parquet"):
    rows = []
    for x in np.arange(-84.4, -75.3, 0.5):
        for y in np.arange(33.7, 36.7, 0.5):
            off = 0
            while True:
                for k in range(8):
                    try: j = requests.get(FS, params=dict(where="1=1", geometry=f"{x},{y},{x + .5},{y + .5}", geometryType="esriGeometryEnvelope", inSR=4326, spatialRel="esriSpatialRelIntersects", outFields="feature_id,strm_order,name,rf_50_0_17c,rf_10_0_17c,rf_2_0_17c", outSR=4326, f="geojson", resultOffset=off, resultRecordCount=2000), timeout=180).json(); break
                    except Exception: time.sleep(10)
                f = j.get("features", []); rows += f; off += len(f)
                if len(f) < 2000 and not j.get("properties", {}).get("exceededTransferLimit", False): break
        print("tile col", x, "reaches so far", len(rows), flush=True)
    g = gpd.GeoDataFrame.from_features(rows, crs=4326).drop_duplicates("feature_id"); g["feature_id"] = g.feature_id.astype("int64"); g.to_parquet(O + "nc_reaches.parquet")
RCH = gpd.read_parquet(O + "nc_reaches.parquet").to_crs(U); print("reaches", len(RCH))
# ---- structures + reach match ----
cs = gpd.read_file("zip://data/raw/counties.zip"); cs = cs[cs.STATEFP == "37"]; code2name = dict(zip(cs.COUNTYFP, cs.NAME.str.upper()))
S = gpd.read_parquet("data/phase2/t10/structures_nc.parquet").to_crs(U); S["cty"] = [c.upper() if not str(c).isdigit() else code2name.get(str(c).zfill(3)) for c in S.county]
m = gpd.sjoin_nearest(S[["crossing_id", "geometry"]], RCH[["feature_id", "strm_order", "name", "rf_2_0_17c", "rf_10_0_17c", "geometry"]], how="left", max_distance=100, distance_col="reach_dist_m"); m = m[~m.index.duplicated()]
S = S.join(m[["feature_id", "strm_order", "name", "rf_2_0_17c", "rf_10_0_17c", "reach_dist_m"]].rename(columns={"rf_2_0_17c": "q2_cfs", "rf_10_0_17c": "q10_cfs", "name": "reach_name"}))
S["assessed"] = S.feature_id.notna() & (S.q2_cfs >= 1) & (S.q10_cfs >= S.q2_cfs)   # q10 >= q2 sanity (monotone thresholds); non-monotone rows are not assessed
rl = xr.open_dataset("data/phase0/raw/RouteLink_CONUS_v3.1.6.nc"); RL = pd.DataFrame({"feature_id": rl["link"].values.astype("int64"), "rl_slope": rl["So"].values}).drop_duplicates("feature_id")
S = S.merge(RL, on="feature_id", how="left") if False else S.assign(rl_slope=S.feature_id.map(RL.set_index("feature_id").rl_slope))
S["tidal"] = ((S.rl_slope < 2e-4) & (S.strm_order >= 3)) | S.feature_name.fillna("").str.contains(r"intracoastal|\bicw\b|tidal|sound|inlet|\bbay\b|discharge|cape fear r", case=False, regex=True)
S["order_class"] = pd.cut(S.strm_order, [0, 1, 2, 99], labels=["1", "2", ">=3"]).astype(str)
n = pd.read_csv("data/phase0/raw/NBI_NC25.txt", dtype=str, quotechar="'", encoding="latin1", low_memory=False)
def dms(v, lon):
    v = str(v).strip()
    if not v.isdigit(): return np.nan
    d, rest = (int(v[:3]), v[3:]) if lon else (int(v[:2]), v[2:]); return d + int(rest[:2]) / 60 + int(rest[2:]) / 100 / 3600
n["lat"] = n.LAT_016.map(lambda v: dms(v, False)); n["lon"] = -n.LONG_017.map(lambda v: dms(v, True)); n = n.dropna(subset=["lat", "lon"])
nb = gpd.GeoDataFrame({"nbi_len": pd.to_numeric(n.STRUCTURE_LEN_MT_049, errors="coerce").values}, geometry=gpd.points_from_xy(n.lon, n.lat), crs=4326).to_crs(U)
j = gpd.sjoin_nearest(S[["crossing_id", "geometry"]], nb, how="left", max_distance=50); j = j[~j.index.duplicated()]
S["len_m"] = np.where(S.src == "nbi_only", S.nbi_len_m, j.nbi_len.reindex(S.index).values); S["is_bridge"] = S.structure_type.str.contains("BRIDGE")
S["structure_class"] = np.where(~S.is_bridge, "culvert/pipe", np.where(S.len_m.isna(), "bridge_len_unknown", np.where(S.len_m >= 35, "bridge_long_ge35m", "bridge_short_lt35m")))
S["reliable_analogue"] = (S.structure_class.isin(["culvert/pipe", "bridge_short_lt35m"])) & (S.strm_order <= 3) & ~S.tidal   # seed_reliable analogue (phase-0 cutoffs: length < 35 m, order <= 3, not tidal; crest data not available statewide)
print("structures", len(S), "assessed", int(S.assessed.sum()), "reliable-analogue among assessed", int((S.assessed & S.reliable_analogue).sum()))
# ---- closures ----
Q = pd.read_parquet(O + "t15a4_closure_points.parquet"); L = pd.read_parquet(O + "history_lines.parquet"); ev = pd.read_csv(O + "t15a4_events_chosen.csv", parse_dates=["start", "last_start", "flow_start", "flow_end"])
Q["CountyName"] = Q.CountyName.str.upper(); lg = {}
for i_, gj in zip(L.Id, L._geom):
    try:
        g = json.loads(gj) if isinstance(gj, str) else None; lg[i_] = LineString(max(g["paths"], key=len)) if g and g.get("paths") else None
    except Exception: pass
def geom(gj, lo, la):
    g = json.loads(gj) if isinstance(gj, str) else None
    return Point(g["x"], g["y"]) if g and "x" in g else Point(lo, la)
Q["geometry"] = [geom(a, b, c) for a, b, c in zip(Q._geom, Q.Longitude, Q.Latitude)]; Qg = gpd.GeoDataFrame(Q, geometry="geometry", crs=4326).to_crs(U)
Qg["line"] = [gpd.GeoSeries([lg[i]], crs=4326).to_crs(U).iloc[0] if i in lg and lg[i] is not None else None for i in Qg.Id]
out, summ = [], []
for e in ev.itertuples():
    cl = Qg[(Qg.StartDateTime >= e.start) & (Qg.StartDateTime <= e.last_start)]; ctys = sorted(cl.CountyName.unique()); X = S[S.cty.isin(ctys) & S.assessed].copy()
    pts = gpd.GeoSeries(cl.geometry.values, crs=U); lines = gpd.GeoSeries([l for l in cl.line if l is not None], crs=U)
    for rad, nm in ((100, "pos100"), (250, "pos250")):
        hit = set(); tree_p = X.sindex
        for g in list(pts) + list(lines): hit |= set(X.index[tree_p.query(g.buffer(rad), predicate="intersects")])
        X[nm] = X.index.isin(hit)
    X["event_id"] = e.event_id; out.append(X); summ.append(dict(event_id=e.event_id, start=str(e.start), last_start=str(e.last_start), records=len(cl), counties=len(ctys), crossings_assessed=len(X), pos100=int(X.pos100.sum()), pos250=int(X.pos250.sum()), neg100=int((~X.pos100).sum())))
A = pd.concat(out); keep = ["event_id", "crossing_id", "cty", "feature_id", "strm_order", "order_class", "q2_cfs", "q10_cfs", "structure_class", "reliable_analogue", "tidal", "pos100", "pos250", "src"]; A[keep].to_parquet(O + "t15_crossing_sets.parquet")
pd.DataFrame(summ).to_csv(O + "t15_crossing_sets_summary.csv", index=False); print(pd.DataFrame(summ).to_string(index=False))
