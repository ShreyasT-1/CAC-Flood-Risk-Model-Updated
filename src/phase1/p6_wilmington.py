"""Phase1 step 6: New Hanover (Wilmington) hospital access in the replay. SCENARIO results, hindcast/forecast-labelled. Not validation."""
import sys, json, numpy as np, pandas as pd, geopandas as gpd
O = "data/phase1/"; tag = sys.argv[1]; label = sys.argv[2]
S = pd.read_parquet(O + f"replay_{tag}_state_summary.parquet"); H = pd.read_parquet(O + f"replay_{tag}_hour_state.parquet"); A = pd.read_parquet(O + f"replay_{tag}_origin_state.parquet")
base = pd.read_parquet(O + f"replay_{tag}_baseline.parquet"); X = gpd.read_parquet("data/phase0/crossings_v2.parquet").set_index("crossing_id")
key = ["facility_type", "crossing_set", "scenario_ratio", "state_id"]
nh = S[(S.county == "New Hanover") & (S.facility_type == "hospital")]
ts = H.merge(nh[key + ["pop_unreachable", "share_unreachable", "pop_detour_gt10min", "pop_base"]], on=key)
ts = ts[ts.facility_type == "hospital"].sort_values("hour"); out = []
for (cs_, sc), g in ts.groupby(["crossing_set", "scenario_ratio"]):
    g = g.sort_values("hour"); u = g.share_unreachable
    def span(th):
        m = u > th
        return (None, None, 0) if not m.any() else (str(g.hour[m].iloc[0]), str(g.hour[m].iloc[-1]), int(m.sum()))
    out.append(dict(crossing_set=cs_, scenario_ratio=sc, peak_share_unreachable=round(float(u.max()), 4), peak_pop_unreachable=int(g.pop_unreachable.max()), pop_base=int(g.pop_base.iloc[0]), peak_hour=str(g.hour[u.idxmax()]),
                    first_any_loss=span(0)[0], last_any_loss=span(0)[1], hours_any_loss=span(0)[2], first_gt10pct=span(.1)[0], hours_gt10pct=span(.1)[2], hours_gt50pct=span(.5)[2], peak_pop_detour_gt10=int(g.pop_detour_gt10min.max())))
R = pd.DataFrame(out); R.to_csv(O + f"p6_{tag}_newhanover_hospital_access.csv", index=False); pd.set_option("display.width", 250, "display.max_columns", 30); print(R.round(3).to_string())
# critical crossing at each (set, scenario) peak hour, per county
res = {}
for cty in ("New Hanover", "Brunswick", "Pender"):
    for cs_ in ("seed", "seed_reliable", "seed_plus_osm_secondary"):
        for sc in (0.5, 1.0, 3.64, 10.0, 30.0):
            n_ = S[(S.county == cty) & (S.facility_type == "hospital") & (S.crossing_set == cs_) & (S.scenario_ratio == sc)]
            g = H[(H.facility_type == "hospital") & (H.crossing_set == cs_) & (H.scenario_ratio == sc)].merge(n_[key + ["pop_unreachable", "share_unreachable", "pop_base"]], on=key)
            if g.empty or g.pop_unreachable.max() == 0: res[f"{cty}|{cs_}|{sc}"] = dict(peak_pop_unreachable=0, hours_any_loss=0); continue
            g = g.sort_values("hour"); pk = g.loc[g.share_unreachable.idxmax()]; m = g.pop_unreachable > 0
            a_ = A[(A.facility_type == "hospital") & (A.crossing_set == cs_) & (A.scenario_ratio == sc) & (A.state_id == pk.state_id) & (A.county == cty) & (~A.reachable)]
            c = a_.groupby("critical_crossing_baseline_path", dropna=False).pop20.sum().sort_values(ascending=False).head(3)
            res[f"{cty}|{cs_}|{sc}"] = dict(peak_hour=str(pk.hour), peak_pop_unreachable=int(pk.pop_unreachable), pop_base=int(pk.pop_base), first_loss=str(g.hour[m].iloc[0]), last_loss=str(g.hour[m].iloc[-1]), hours_any_loss=int(m.sum()),
                top_critical=[dict(crossing_id=str(i), pop_cut_off=int(p), stream=None if i not in X.index else X.loc[i].feature_name, road=None if i not in X.index else X.loc[i].road_carried,
                                   lat=None if i not in X.index else round(float(X.loc[i].lat), 4), lon=None if i not in X.index else round(float(X.loc[i].lon), 4), set_=None if i not in X.index else X.loc[i].src) for i, p in c.items()])
json.dump(res, open(O + f"p6_{tag}_critical_crossings.json", "w"), indent=1, default=str)
for k, v in res.items():
    if v.get("peak_pop_unreachable"): print(k, {x: v[x] for x in ("peak_hour", "peak_pop_unreachable", "first_loss", "last_loss", "hours_any_loss")}, [(c["crossing_id"], c["pop_cut_off"], c["stream"], c["road"]) for c in v["top_critical"]])
b = base[(base.facility_type == "hospital")]
for cty, g in b.groupby("county"):
    gg = g[g.baseline_reachable]; print("baseline", cty, "pop-weighted mean min to nearest ED hospital", round(float(np.average(gg.baseline_tt_min, weights=gg.pop20)), 1), "| baseline unreachable pop", int(g[~g.baseline_reachable].pop20.sum()), "of", int(g.pop20.sum()))
