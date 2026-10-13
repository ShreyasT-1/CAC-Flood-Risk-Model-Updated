"""Phase 2 / T10E: test the hindcast closure rule (NWM v3.0 retro flow > q10 on a crossing's reach) against the documented Florence closures in docs/florence_documented_closures.csv.
Definitions: docs/validation_protocol.md (section E + Amendment 1). Statewide seed structures from data/phase2/t10/structures_nc.parquet (NCDOT + NBI, waterway-like). Hindcast only; no tuning.
Usage (repo root): python src/38_t10_documented_test.py"""
import re, sys, time, json, requests, numpy as np, pandas as pd, geopandas as gpd
from scipy.stats import fisher_exact
sys.path.insert(0, "src"); from nwm_retro import fetch
O = "data/phase2/t10/"; U = 32119; CFS = 35.3146667
DOC = pd.read_csv("docs/florence_documented_closures.csv"); DOC = DOC[DOC.status == "verified"]
cs = gpd.read_file("zip://data/raw/counties.zip"); cs = cs[cs.STATEFP == "37"]; code2name = dict(zip(cs.COUNTYFP, cs.NAME.str.upper()))
S = gpd.read_parquet(O + "structures_nc.parquet"); S["cty"] = [c.upper() if not str(c).isdigit() else code2name.get(str(c).zfill(3)) for c in S.county]
TOK = re.compile(r"\b(I|US|NC)[-\s]?(\d+)")
def toks(s):
    s = str(s).upper().replace("/", " / "); out = set(); last = None
    for part in re.split(r"[;,&]", s):
        for m in TOK.finditer(part): out.add(m.group(1) + m.group(2)); last = m.group(1)
        m2 = re.search(r"\b(US|NC|I)[-\s]?\d+\s*/\s*(\d+)\b", part)   # US-74/76
        if m2: out.add(m2.group(1) + m2.group(2))
    return out
S["rt"] = S.road_carried.map(toks)
# ---- documented (road, county) units ----
units = []
for r in DOC.itertuples():
    for road in toks(r.road):
        for c in str(r.county).split(";"):
            if c.strip().upper() in code2name.values(): units.append(dict(doc_idx=r.Index, road=road, county=c.strip().upper(), kind="snapshot" if str(r.time_precision).startswith("snapshot") else "other", closed_start=r.closed_start, closed_end=r.closed_end, time_precision=r.time_precision))
Un = pd.DataFrame(units).drop_duplicates(["road", "county", "kind"]); print("documented units", len(Un), Un.kind.value_counts().to_dict())
S["has"] = S.apply(lambda r: r.cty is not None, axis=1)
pairs = set(zip(Un.road, Un.county)); counties = set(Un.county)
# candidate structures: documented pairs AND (control) any I/US/NC road in the same counties
cand = S[S.cty.isin(counties) & S.rt.map(len).gt(0)].copy(); cand = cand.explode("rt").rename(columns={"rt": "road"}); cand = cand[cand.road.notna()]; cand["county"] = cand.cty
print("candidate structure-road rows", len(cand), "unique structures", cand.crossing_id.nunique())
# ---- reaches + thresholds ----
FS = "https://maps.water.noaa.gov/server/rest/services/reference/static_nwm_flowlines/FeatureServer/0/query"; cache = O + "e_structure_reaches.parquet"
try: RC = pd.read_parquet(cache)
except Exception: RC = pd.DataFrame(columns=["crossing_id"])
def getj(params):
    for k in range(8):
        try: return requests.get(FS, params=params, timeout=120).json()
        except Exception: time.sleep(10)
    raise RuntimeError("OWP service unreachable")
rows = []; need = cand.drop_duplicates("crossing_id"); need = need[~need.crossing_id.isin(RC.crossing_id)]
for r in need.to_crs(U).itertuples():
    ll = gpd.GeoSeries([r.geometry], crs=U).to_crs(4326).iloc[0]; j = getj(dict(where="1=1", geometry=f"{ll.x - .003},{ll.y - .003},{ll.x + .003},{ll.y + .003}", geometryType="esriGeometryEnvelope", inSR=4326, spatialRel="esriSpatialRelIntersects",
        outFields="feature_id,strm_order,rf_50_0_17c,rf_10_0_17c,rf_2_0_17c", outSR=4326, f="geojson"))
    g = gpd.GeoDataFrame.from_features(j["features"], crs=4326) if j.get("features") else []
    if len(g):
        g = g.to_crs(U); d = g.distance(r.geometry); i = int(np.argmin(d.values)); rows.append(dict(crossing_id=r.crossing_id, feature_id=int(g.feature_id.iloc[i]), strm_order=g.strm_order.iloc[i], reach_dist_m=float(d.iloc[i]), q2_cfs=g.rf_2_0_17c.iloc[i], q10_cfs=g.rf_10_0_17c.iloc[i], q50_cfs=g.rf_50_0_17c.iloc[i]))
    else: rows.append(dict(crossing_id=r.crossing_id))
if rows: RC = pd.concat([RC, pd.DataFrame(rows)], ignore_index=True); RC.to_parquet(cache)
RC["assessed"] = (RC.reach_dist_m <= 100) & (RC.q2_cfs >= 1); RC = RC.drop_duplicates("crossing_id"); cand = cand.merge(RC, on="crossing_id", how="left"); cand["assessed"] = cand.assessed.fillna(False).astype(bool)
A = cand[cand.assessed].copy(); print("assessed structure-road rows", len(A), "unique reaches", A.feature_id.nunique())
# ---- Florence flows ----
T0, T1 = pd.Timestamp("2018-08-27 00:00"), pd.Timestamp("2018-10-31 23:00"); F = fetch(A.feature_id.astype("int64").unique(), T0, T1); F.columns = F.columns.astype(str)
def closed(df, lvl):
    q = df[lvl].values / CFS; v = F[df.feature_id.astype("int64").astype(str).values].values; return pd.DataFrame(v > q[None, :], index=F.index, columns=df.crossing_id.values)
def first_last(m):   # m: bool DataFrame (hours x crossings of one unit); any-closed series
    s = m.any(axis=1); h = s[s].index; return (h[0], h[-1], int(s.sum())) if len(h) else (None, None, 0)
res = {}
for lvl in ("q10_cfs", "q2_cfs", "q50_cfs"):
    Cl = closed(A, lvl); Cl = Cl.loc[:, ~Cl.columns.duplicated()]; snap_t = pd.Timestamp("2018-09-19 19:00"); out = []
    for (road, cty), g in A.groupby(["road", "county"]):
        ids = g.crossing_id.unique(); m = Cl[ids]; f, l, n = first_last(m); listed = (road, cty) in pairs and ((Un.road == road) & (Un.county == cty) & (Un.kind == "snapshot")).any()
        out.append(dict(road=road, county=cty, n_crossings=len(ids), listed_snapshot=bool(listed), closed_at_snapshot=bool(m.loc[snap_t].any()), first_closed=f, last_closed=l, hours_closed=n, ever_09_14_to_09_30=bool(m.loc["2018-09-14":"2018-09-30"].any().any()),
                        closed_share_pre_period_0827_0909=float(m.loc["2018-08-27":"2018-09-09"].any(axis=1).mean())))
    P = pd.DataFrame(out); P.to_csv(O + f"t10e_pair_results_{lvl[:3]}.csv", index=False); L = P[P.listed_snapshot]; N = P[~P.listed_snapshot]
    tab = [[int(L.closed_at_snapshot.sum()), int((~L.closed_at_snapshot).sum())], [int(N.closed_at_snapshot.sum()), int((~N.closed_at_snapshot).sum())]]
    e1 = dict(level=lvl, listed_testable=len(L), listed_hit=int(L.closed_at_snapshot.sum()), listed_hit_share=round(float(L.closed_at_snapshot.mean()), 3) if len(L) else None, unlisted_n=len(N), unlisted_hit=int(N.closed_at_snapshot.sum()),
              unlisted_hit_share=round(float(N.closed_at_snapshot.mean()), 3) if len(N) else None, fisher_p_one_sided=round(float(fisher_exact(tab, alternative="greater")[1]), 4) if len(L) and len(N) else None)
    e1["pass_E1"] = bool(len(L) and e1["listed_hit_share"] >= .6 and e1["fisher_p_one_sided"] is not None and e1["fisher_p_one_sided"] < .05)
    # E2 dated closures
    D2 = {"I40": (["DUPLIN", "PENDER", "NEW HANOVER"], "2018-09-15", "2018-09-24 23:00"), "I95": (["ROBESON", "CUMBERLAND", "HARNETT"], "2018-09-16", "2018-09-23 23:00"), "US17": (["BRUNSWICK"], "2018-09-14", "2018-09-25"), "NC87": (["BRUNSWICK"], "2018-09-14", "2018-09-25")}
    e2 = []
    for road, (ctys, d0, d1) in D2.items():
        for c in ctys:
            g = A[(A.road == road) & (A.county == c)]
            if g.empty: e2.append(dict(road=road, county=c, testable=False)); continue
            m = Cl[g.crossing_id.unique()]; t0 = pd.Timestamp(d0); w = m.loc[t0:pd.Timestamp(d1)]; hit = bool(w.any().any()); f, l, n = first_last(m.loc[t0 - pd.Timedelta("7D"):pd.Timestamp(d1)])
            tw = (f is not None) and (t0 - pd.Timedelta("24h") <= f <= t0 + pd.Timedelta("48h"))   # day [d0, d0+24h] +- 24 h
            e2.append(dict(road=road, county=c, testable=True, n_crossings=g.crossing_id.nunique(), hit=hit, first_model_closed=str(f), timing_hit=bool(tw), hours_closed_in_window=int(w.any(axis=1).sum()), window=f"{d0}..{d1}"))
    E2 = pd.DataFrame(e2); E2.to_csv(O + f"t10e_dated_{lvl[:3]}.csv", index=False); t = E2[E2.testable.eq(True)]
    e1.update(E2_testable_units=len(t), E2_hit_share=round(float(t.hit.mean()), 3) if len(t) else None, E2_timing_hit_share=round(float(t.timing_hit.mean()), 3) if len(t) else None, E2_units_total=len(E2))
    e1["pass_E2"] = bool(len(t) and e1["E2_hit_share"] >= .6 and e1["E2_timing_hit_share"] >= .4); res[lvl] = e1
json.dump(res, open(O + "t10e_results.json", "w"), indent=1, default=str); print(json.dumps(res, indent=1, default=str)); print(pd.read_csv(O + "t10e_dated_q10.csv").to_string(index=False))
