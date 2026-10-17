"""Phase 2 / T10F: routing validation. 150 random origin blocks (50 per county, seed 20261011) -> engine baseline drive minutes to the nearest ED hospital vs OSRM public demo server (car profile).
OSRM demo policy (github.com/Project-OSRM/osrm-backend/wiki/Demo-server, read 2026-10-11): max 1 request/second, reasonable non-commercial use, no uptime guarantee. We send 150 requests at ~1.2 s spacing.
Definitions fixed in docs/validation_protocol.md section F. Usage (repo root): python src/validation/36_t10_routing_check.py"""
import sys, time, json, requests, numpy as np, pandas as pd
sys.path.insert(0, "src/pipeline/02_routing"); import engine2 as E
O = "data/phase2/t10/"; net = E.Net(); sets, org, fac = E.inputs(); H = pd.read_parquet("data/phase1b/hospitals_snapped.parquet"); H = H[H.ed & ~H.is_behavioral_or_nonacute].drop_duplicates("node")
hn = [int(n) for n in fac["hospital_ED_acute"]["nodes"]]; assert set(hn) == set(H.node.astype(int)), "hospital node set mismatch"
D = np.vstack([E.solve(net, set(), [n], 0)[0] for n in hn]); onode = org.node.values; T = D[:, onode]; best = T.argmin(0); tt = T.min(0) / 60; ok = np.isfinite(tt)
rng = np.random.default_rng(20261011); pick = []
for c in ["Brunswick", "New Hanover", "Pender"]: pick += list(rng.choice(np.where(ok & (org.county.values == c))[0], 50, replace=False))
rows = []; S = requests.Session(); S.headers["User-Agent"] = "FloodLens-student-validation/1.0 (non-commercial; Congressional App Challenge)"
for i in pick:
    h = H[H.node.astype(int) == hn[best[i]]].iloc[0]; o = org.iloc[i]
    url = f"https://router.project-osrm.org/route/v1/driving/{o.lon:.6f},{o.lat:.6f};{h.lon:.6f},{h.lat:.6f}?overview=false"
    try: j = S.get(url, timeout=60).json(); dur = j["routes"][0]["duration"] / 60 if j.get("code") == "Ok" else np.nan; sn = j["waypoints"][0]["distance"] if j.get("code") == "Ok" else np.nan
    except Exception as e: dur, sn = np.nan, np.nan
    rows.append(dict(geoid20=o.geoid20, county=o.county, pop20=o.pop20, hospital=h["name"], engine_min=tt[i], osrm_min=dur, origin_snap_osrm_m=sn, origin_snap_engine_m=o.snap_m)); time.sleep(1.2)
R = pd.DataFrame(rows); R["err_min"] = R.engine_min - R.osrm_min; R["abs_err"] = R.err_min.abs(); R["ape"] = R.abs_err / R.osrm_min; R.to_csv(O + "t10f_routing_pairs.csv", index=False)
v = R.dropna(subset=["osrm_min"]); st = dict(pairs=len(R), scored=len(v), mae_min=round(float(v.abs_err.mean()), 2), median_ape=round(float(v.ape.median()), 3), bias_min=round(float(v.err_min.mean()), 2), share_within_30pct=round(float((v.ape <= .30).mean()), 3),
          mean_osrm_min=round(float(v.osrm_min.mean()), 1), by_county=v.groupby("county").agg(mae=("abs_err", "mean"), med_ape=("ape", "median"), n=("ape", "size")).round(3).to_dict("index"),
          verdict_pass=bool(v.ape.median() <= .20 and (v.ape <= .30).mean() >= .90))
json.dump(st, open(O + "t10f_stats.json", "w"), indent=1); print(json.dumps(st, indent=1)); pd.set_option("display.width", 220)
print(v.sort_values("abs_err", ascending=False).head(10)[["geoid20", "county", "hospital", "engine_min", "osrm_min", "err_min", "origin_snap_osrm_m", "origin_snap_engine_m"]].round(1).to_string(index=False))
