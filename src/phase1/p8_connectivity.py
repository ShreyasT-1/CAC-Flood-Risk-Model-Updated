"""Phase1b step 3: (A) outside-connectivity: when origins lose ALL paths to the derived exit points; (B) origin->ED-hospital access for Brunswick, Pender, northern New Hanover and Wilmington/south New Hanover separately.
Subgroups: county; New Hanover split at latitude 34.28 (north = >= 34.28, my arbitrary line just north of Wilmington's urban core; written here, not derived). All numbers are SCENARIOS from the replay named on the command line;
the crossing set is named in every row. 'loss' = unreachable AND reachable in the no-closure baseline (baseline-unreachable origins are excluded from numerators and denominators).
Usage: python p8_connectivity.py <label e.g. hindcast_nwm_v30_retro>"""
import sys, json, numpy as np, pandas as pd, geopandas as gpd
O = "data/phase1b/"; lab = sys.argv[1]; NH_SPLIT = 34.28
A = pd.read_parquet(O + f"replay_{lab}_origin_state.parquet"); H = pd.read_parquet(O + f"replay_{lab}_hour_state.parquet"); B = pd.read_parquet(O + f"replay_{lab}_baseline.parquet")
X = gpd.read_parquet("data/phase0/crossings_v2.parquet").set_index("crossing_id"); ex = pd.read_csv(O + "exits.csv")
def grp(df):
    g = df.county.copy(); nh = df.county == "New Hanover"; g[nh & (df.lat >= NH_SPLIT)] = "New Hanover north (lat>=34.28)"; g[nh & (df.lat < NH_SPLIT)] = "New Hanover Wilmington/south (lat<34.28)"; return g
B["group"] = grp(B); lat = B.drop_duplicates("geoid20").set_index("geoid20").lat; A["lat"] = A.geoid20.map(lat); A["group"] = grp(A)
rows, crit = [], []
for ft in ("hospital_ED_acute", "exit_major", "exit_major_plus_secondary"):
    b = B[(B.facility_type == ft) & B.baseline_reachable]; den = b.groupby("group").pop20.sum(); a_all = A[(A.facility_type == ft) & (~A.reachable)]
    for (cs_, sc), hh in H[H.facility_type == ft].groupby(["crossing_set", "scenario"]):
        a = a_all[(a_all.crossing_set == cs_) & (a_all.scenario == sc)]; pop_state = a.groupby(["state_id", "group"]).pop20.sum().unstack(fill_value=0)
        for g, d in den.items():
            ps = pop_state[g] if g in pop_state else pd.Series(0, index=hh.state_id.unique()); s = hh.sort_values("hour").assign(pop_lost=lambda x: x.state_id.map(ps).fillna(0)); s["share"] = s.pop_lost / d
            def span(th):
                m = s.share >= th; return (str(s.hour[m].iloc[0]), str(s.hour[m].iloc[-1]), int(m.sum())) if m.any() else (None, None, 0)
            pk = s.loc[s.share.idxmax()]; rows.append(dict(facility_type=ft, crossing_set=cs_, scenario=sc, group=g, pop_base=int(d), peak_share_lost=round(float(pk.share), 4), peak_pop_lost=int(pk.pop_lost), peak_hour=str(pk.hour) if pk.pop_lost > 0 else None,
                                                           first_ge1pct=span(.01)[0], last_ge1pct=span(.01)[1], hours_ge1pct=span(.01)[2], first_ge10pct=span(.10)[0], hours_ge10pct=span(.10)[2], hours_ge50pct=span(.50)[2]))
            if pk.pop_lost > 0 and sc in ("RL10", "RL50", "REF_3.64xHWT", "RL2"):
                aa = a[(a.state_id == pk.state_id) & (a.group == g)]; c = aa.groupby("critical_crossing_baseline_path").pop20.sum().sort_values(ascending=False).head(3)
                for i, p in c.items():
                    r = X.loc[i] if i in X.index else None
                    crit.append(dict(facility_type=ft, crossing_set=cs_, scenario=sc, group=g, peak_hour=str(pk.hour), crossing_id=i, pop_cut_off=int(p), stream=None if r is None else r.feature_name, road=None if r is None else r.road_carried, crossing_src=None if r is None else r.src,
                                     lat=None if r is None else round(float(r.lat), 4), lon=None if r is None else round(float(r.lon), 4)))
R = pd.DataFrame(rows); C = pd.DataFrame(crit); R.to_csv(O + f"p8_{lab}_loss_summary.csv", index=False); C.to_csv(O + f"p8_{lab}_critical_crossings.csv", index=False)
pd.set_option("display.width", 260, "display.max_columns", 30, "display.max_colwidth", 40)
cols = ["crossing_set", "scenario", "group", "pop_base", "peak_share_lost", "peak_pop_lost", "peak_hour", "first_ge1pct", "last_ge1pct", "hours_ge1pct", "hours_ge50pct"]
for ft in ("exit_major", "hospital_ED_acute"):
    print("\n#####", ft, lab); d = R[(R.facility_type == ft) & R.scenario.isin(["RL2", "RL10", "RL50", "REF_3.64xHWT"])]; print(d[cols].to_string(index=False))
print("\nbaseline: pop-weighted mean minutes to nearest facility, baseline-unreachable pop")
for ft in ("hospital_ED_acute", "exit_major"):
    for g, d in B[B.facility_type == ft].groupby("group"):
        r = d[d.baseline_reachable]; print(ft, g, round(float(np.average(r.baseline_tt_min, weights=r.pop20)), 1), int(d[~d.baseline_reachable].pop20.sum()), "of", int(d.pop20.sum()))
print(C[(C.facility_type == "exit_major") & (C.scenario.isin(["RL10", "REF_3.64xHWT"]))].to_string(index=False))
