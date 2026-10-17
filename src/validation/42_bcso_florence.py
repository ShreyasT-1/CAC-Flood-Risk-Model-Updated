"""Phase 2 / G: Brunswick Sheriff's Office Florence calls vs the NWM hazard layer. Definitions, thresholds, pass rules: docs/validation_protocol_bcso_florence.md (fixed before any call was snapped or compared).
Stages (repo root):  python src/validation/42_bcso_florence.py snap | fetchE | fetchSept | tests     ('tests' needs the first three; fetchSept is long, resumable per year)"""
import sys, os, json, hashlib, numpy as np, pandas as pd, geopandas as gpd
sys.path.insert(0, "src/live"); O = "data/phase2/bcso/"; D = "data/bcso_florence/"; U = 32119; os.makedirs(O, exist_ok=True)
CFS = 35.3146667; E0 = pd.Timestamp("2018-09-12 04:00"); E1 = pd.Timestamp("2018-09-25 04:00")   # 2018-09-12 00:00 .. 09-25 00:00 America/New_York as naive UTC
NBOOT = 10000; NCTRL = 200; SEED = 20261014
def calls(f, kind=None):
    d = pd.read_excel(D + f); d = d.dropna(subset=["XCoor", "YCoor"]).drop_duplicates("IncNo"); d = d[pd.to_numeric(d.XCoor, errors="coerce").notna()]
    if kind: d = d[d.IncTypeDesc == kind]
    loc = d.IncDate.dt.normalize() + (d.IncTime - pd.Timestamp("1900-01-01"))
    d = d.assign(t_utc=loc.dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC").dt.tz_localize(None).dt.floor("h"))
    return gpd.GeoDataFrame(d[["IncNo", "IncTypeDesc", "t_utc"]], geometry=gpd.points_from_xy(d.XCoor.astype(float), d.YCoor.astype(float)), crs=4326).to_crs(U).reset_index(drop=True)
def load_sets():
    W = calls("FlorenceWaterCalls.xlsx", "Storm-Roads (Flooding or Ice)")
    R = calls("FlorenceWaterCalls.xlsx", "Water Rescue"); R2 = calls("FlorenceWaterRescues.xlsx"); R = pd.concat([R, R2[~R2.IncNo.isin(R.IncNo)]], ignore_index=True)
    T = calls("FlorenceTreeCalls.xlsx"); return W, R, T
def crossings(bounds):
    RCH = gpd.read_parquet("data/phase2/t15/nc_reaches.parquet").to_crs(U); S = gpd.read_parquet("data/phase2/t10/structures_nc.parquet").to_crs(U)
    x0, y0, x1, y1 = bounds; S = S.cx[x0 - 3000:x1 + 3000, y0 - 3000:y1 + 3000]; RCH = RCH.cx[x0 - 6000:x1 + 6000, y0 - 6000:y1 + 6000]
    m = gpd.sjoin_nearest(S[["crossing_id", "geometry"]], RCH[["feature_id", "strm_order", "rf_2_0_17c", "rf_10_0_17c", "geometry"]], how="left", max_distance=100, distance_col="reach_dist_m"); m = m[~m.index.duplicated()]
    S = S.join(m[["feature_id", "strm_order", "rf_2_0_17c", "rf_10_0_17c", "reach_dist_m"]].rename(columns={"rf_2_0_17c": "q2_cfs", "rf_10_0_17c": "q10_cfs"}))
    S["assessed"] = S.feature_id.notna() & (S.q2_cfs >= 1) & (S.q10_cfs >= S.q2_cfs); return S[S.assessed].copy()
def snap(C, S, dist):
    j = gpd.sjoin_nearest(C, S[["crossing_id", "feature_id", "strm_order", "q2_cfs", "q10_cfs", "geometry"]], how="inner", max_distance=dist, distance_col="snap_m")
    j = j.sort_values(["snap_m", "crossing_id"]); j = j[~j.index.duplicated()].sort_index(); j["feature_id"] = j.feature_id.astype("int64"); return j
def stage_snap():
    W, R, T = load_sets(); allp = pd.concat([W, R, T]); S = crossings(tuple(allp.total_bounds)); S.drop(columns="geometry").to_csv(O + "assessed_crossings_region.csv", index=False); print("assessed crossings in region", len(S))
    out = {}
    for nm, C in dict(W=W, R=R, T=T).items():
        for dist in (250, 500, 1000):
            j = snap(C, S, dist); out[f"{nm}_{dist}"] = dict(calls=len(C), snapped=len(j), share=round(len(j) / len(C), 3), crossings=int(j.crossing_id.nunique()), reaches=int(j.feature_id.nunique()))
            if dist == 500: j.drop(columns="geometry").assign(set=nm).to_csv(O + f"snapped_{nm}_500.csv", index=False)
            if dist in (250, 1000): j.drop(columns="geometry").assign(set=nm).to_csv(O + f"snapped_{nm}_{dist}.csv", index=False)
    print(json.dumps(out, indent=1)); json.dump(out, open(O + "coverage.json", "w"), indent=1)
def reach_ids():
    ids = set()
    for f in os.listdir(O):
        if f.startswith("snapped_") and f.endswith(".csv"): ids |= set(pd.read_csv(O + f).feature_id.astype("int64"))
    return sorted(ids)
def stage_fetchE():
    import nwm_retro; ids = reach_ids(); print("reaches", len(ids)); df = nwm_retro.fetch(ids, "2018-08-25", "2018-10-10"); df.to_parquet(O + "flows_E.parquet"); print(df.shape)
def stage_localE():   # Amendment 1: Florence-window flows from the existing phase-1 file (this shell cannot reach S3)
    F = pd.read_parquet("data/phase1/florence_nwm_v30_retro_hourly_m3s.parquet"); ids = [str(i) for i in reach_ids()]; have = [i for i in ids if i in F.columns]; print("reaches needed", len(ids), "available", len(have), "dropped", sorted(set(ids) - set(have))); F[have].to_parquet(O + "flows_E.parquet"); json.dump(dict(needed=len(ids), available=len(have), dropped=sorted(set(ids) - set(have))), open(O + "flows_E_coverage.json", "w"))
def stage_fetchSept():
    import nwm_retro; ids = reach_ids()
    for y in range(1979, 2023):
        f = O + f"sept_{y}.parquet"
        if os.path.exists(f): continue
        t0 = pd.Timestamp(f"{y}-09-01 00:00"); t0 = max(t0, pd.Timestamp("1979-02-01 01:00")); df = nwm_retro.fetch(ids, t0, pd.Timestamp(f"{y}-09-30 23:00")); df.to_parquet(f); print(y, df.shape, flush=True)
# ------------------------------------------------------------------ tests
def pct(sv, x): lo = np.searchsorted(sv, x, "left"); hi = np.searchsorted(sv, x, "right"); return (lo + .5 * (hi - lo)) / len(sv)
def boot_ratio(num, den, grp, rng):   # cluster bootstrap of sum(num)/sum(den) over groups
    g = pd.DataFrame(dict(n=num, d=den, g=grp)).groupby("g").sum(); n_, d_ = g.n.values, g.d.values; k = len(g); ii = rng.integers(0, k, (NBOOT, k)); v = n_[ii].sum(1) / d_[ii].sum(1); return [round(float(np.quantile(v, .025)), 3), round(float(np.quantile(v, .975)), 3)]
def g2(J, FE, win=0, shift=0):
    rows = []
    for r in J.itertuples():
        f = FE[str(r.feature_id)].values.astype(float) * CFS; idx = FE.index; w = (idx >= E0) & (idx < E1); fw = f[w]
        if np.isnan(fw).mean() > .1: continue
        t = r.t_utc + pd.Timedelta(hours=shift); 
        if t not in idx: continue
        i = idx.get_loc(t); v = np.nanmax(f[max(0, i - win):i + win + 1]) if win else f[i]
        if np.isnan(v): continue
        sv = np.sort(fw[~np.isnan(fw)]); rows.append(dict(IncNo=r.IncNo, feature_id=r.feature_id, pe=pct(sv, v), gt_q2=v > r.q2_cfs, ehrs_gt_q2=float(np.mean(fw[~np.isnan(fw)] > r.q2_cfs))))
    X = pd.DataFrame(rows)
    if len(X) < 10: return dict(n=len(X), note="too few"), X
    rng = np.random.default_rng(SEED); ci = boot_ratio(X.pe.values, np.ones(len(X)), X.feature_id.values, rng)
    return dict(n_calls=len(X), n_reaches=int(X.feature_id.nunique()), mean_pe=round(float(X.pe.mean()), 3), mean_pe_ci95=ci, share_calls_gt_q2=round(float(X.gt_q2.mean()), 3), share_Ehours_gt_q2=round(float(X.ehrs_gt_q2.mean()), 3), pass_G2=bool(ci[0] > .5)), X
def auc(a, b): return (((a[:, None] > b[None, :]).sum() + .5 * (a[:, None] == b[None, :]).sum()) / (len(a) * len(b)))
def g3(JP, JC, FE):
    w = (FE.index >= E0) & (FE.index < E1); q10 = pd.concat([JP, JC]).drop_duplicates("feature_id").set_index("feature_id").q10_cfs
    s = lambda fid: float(np.nanmax(FE[str(fid)].values[w].astype(float) * CFS) / q10[fid])
    pos = sorted(set(JP.feature_id)); ctl = sorted(set(JC.feature_id) - set(pos)); a = np.array([s(f) for f in pos]); b = np.array([s(f) for f in ctl])
    if len(a) < 10 or len(b) < 10: return dict(n_pos=len(a), n_ctl=len(b), note="too few")
    rng = np.random.default_rng(SEED); au = auc(a, b); bs = [auc(a[rng.integers(0, len(a), len(a))], b[rng.integers(0, len(b), len(b))]) for _ in range(NBOOT)]
    ci = [round(float(np.quantile(bs, .025)), 3), round(float(np.quantile(bs, .975)), 3)]
    return dict(n_pos_reaches=len(a), n_ctl_reaches=len(b), auc=round(float(au), 3), auc_ci95=ci, median_peak_over_q10_pos=round(float(np.median(a)), 2), median_peak_over_q10_ctl=round(float(np.median(b)), 2), share_peak_gt_q10_pos=round(float((a > 1).mean()), 3), share_peak_gt_q10_ctl=round(float((b > 1).mean()), 3), pass_G3=bool(ci[0] > .5))
def g1(J):
    SP = {y: pd.read_parquet(O + f"sept_{y}.parquet") for y in range(1979, 2023) if os.path.exists(O + f"sept_{y}.parquet")}
    if len(SP) < 44: return dict(note=f"only {len(SP)}/44 Septembers fetched; not run")
    rng = np.random.default_rng(SEED); ref = {}; ctl = {}
    for f in J.feature_id.unique():
        arrs = {y: SP[y][str(f)].values.astype(float) * CFS for y in SP}; ref[f] = np.sort(np.concatenate([a[~np.isnan(a)] for a in arrs.values()]))
        pool = np.concatenate([a[~np.isnan(a)] for y, a in arrs.items() if y != 2018]); ex = SP[2018].index; a18 = arrs[2018]; keep = (ex < pd.Timestamp("2018-09-09")) | (ex >= pd.Timestamp("2018-09-28")); pool = np.concatenate([pool, a18[keep & ~np.isnan(a18)]]); ctl[f] = pool
    rows = []
    for r in J.itertuples():
        i = SP[2018].index.get_loc(r.t_utc) if r.t_utc in SP[2018].index else None
        if i is None: continue
        v = SP[2018][str(r.feature_id)].values[i] * CFS
        if np.isnan(v): continue
        c = rng.choice(ctl[r.feature_id], NCTRL); rows.append(dict(feature_id=r.feature_id, p=pct(ref[r.feature_id], v), auc=float(np.mean(v > c) + .5 * np.mean(v == c)), gt_q2=v > r.q2_cfs, gt_q10=v > r.q10_cfs, c_gt_q2=float(np.mean(c > r.q2_cfs)), c_gt_q10=float(np.mean(c > r.q10_cfs))))
    X = pd.DataFrame(rows); rng = np.random.default_rng(SEED); g = X.groupby("feature_id"); k = len(g); S = g[["auc", "gt_q2", "c_gt_q2", "gt_q10", "c_gt_q10"]].sum().values; N = g.size().values; ii = rng.integers(0, k, (NBOOT, k))
    A = S[ii].sum(1) / N[ii].sum(1)[:, None]; ci = lambda v: [round(float(np.quantile(v, .025)), 3), round(float(np.quantile(v, .975)), 3)]
    ac, d2, d10 = ci(A[:, 0]), ci(A[:, 1] - A[:, 2]), ci(A[:, 3] - A[:, 4])
    return dict(n_calls=len(X), n_reaches=k, median_pct_calls=round(float(X.p.median()), 3), auc=round(float(X.auc.mean()), 3), auc_ci95=ac, share_gt_q2_calls=round(float(X.gt_q2.mean()), 3), share_gt_q2_ctrl=round(float(X.c_gt_q2.mean()), 4), d_gt_q2_ci95=d2, share_gt_q10_calls=round(float(X.gt_q10.mean()), 3), share_gt_q10_ctrl=round(float(X.c_gt_q10.mean()), 4), d_gt_q10_ci95=d10, pass_G1=bool(ac[0] > .5 and d2[0] > 0))
def stage_tests():
    FE = pd.read_parquet(O + "flows_E.parquet"); sha = hashlib.sha256(open("docs/validation_protocol_bcso_florence.md", "rb").read()).hexdigest(); res = dict(protocol_sha256=sha, coverage=json.load(open(O + "coverage.json")))
    ld = lambda n, d=500: pd.read_csv(O + f"snapped_{n}_{d}.csv", parse_dates=["t_utc"])
    have = set(FE.columns); ld0 = ld; ld = lambda n, d=500: (lambda x: x[x.feature_id.astype(str).isin(have)])(ld0(n, d))
    W, R, T = ld("W"), ld("R"), ld("T")
    res["G2_W"], X = g2(W, FE); X.to_csv(O + "g2_W_per_call.csv", index=False); res["G3_W_vs_T"] = g3(W, T, FE)
    res["G2_R"], _ = g2(R, FE); res["G3_R_vs_T"] = g3(R, T, FE)
    res["S1_G2_W_window6h"], _ = g2(W, FE, win=6)
    for sh in (-1, 1): res[f"S1_G2_W_shift{sh:+d}h"], _ = g2(W, FE, shift=sh)
    for d in (250, 1000): res[f"S2_G2_W_{d}m"], _ = g2(ld("W", d), FE); res[f"S2_G3_W_vs_T_{d}m"] = g3(ld("W", d), ld("T", d), FE)
    # misses: W calls whose reach never exceeded q2 in E
    w = (FE.index >= E0) & (FE.index < E1); pk = W.assign(peak_over_q2=[np.nanmax(FE[str(f)].values[w] * CFS) / q for f, q in zip(W.feature_id, W.q2_cfs)]); res["misses_W_reach_never_gt_q2"] = int((pk.peak_over_q2 <= 1).sum()); pk.to_csv(O + "W_peak_over_q2.csv", index=False)
    res["strm_order_mix_W"] = W.strm_order.value_counts().sort_index().to_dict()
    res["G1_W"] = g1(W); json.dump(res, open(O + "results.json", "w"), indent=1, default=str); print(json.dumps(res, indent=1, default=str))
if __name__ == "__main__": dict(snap=stage_snap, fetchE=stage_fetchE, localE=stage_localE, fetchSept=stage_fetchSept, tests=stage_tests)[sys.argv[1]]()
