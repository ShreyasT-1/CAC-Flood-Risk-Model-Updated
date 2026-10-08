"""Step 6: splits + TRAIN-only features + leakage tests. Rules fixed before looking at any results:

1. TEST = every hour of the Florence event window (all gauges). BUFFER = the 7 days before and after it: excluded from everything.
2. SPATIAL HOLDOUT ("unseen gauges"): ~15% of gauges, stratified by (HUC4 basin, in_pilot), numpy seed 42; never more than half of the
   pilot gauges. Their non-test/non-buffer hours get split='unseen' (never TRAIN).
3. TRAIN/VAL ('trainval') = remaining gauges, non-Florence hours. cv_fold (5 folds) assigned per event_id (storm events and quiet stretches
   are whole units), greedily balancing primary positives per fold. Nothing is split by random hour.
4. nwm_flow_pctile, Q_fs, baseline_ratio use TRAIN ('trainval') hours only. Unseen gauges have no TRAIN hours, so (a) their percentile
   reference is their own reach's NWM flow over unseen-split hours (NWM only, no observations) and (b) their Q_fs comes from their own
   unseen-split stage/discharge pairs (flagged q_fs_source='own_nontest_hours'; optimistic for the "ungauged" story).
   Test/buffer hours never feed any statistic.
Outputs: ml_full_table/ gets split, cv_fold, nwm_flow_pctile, q_fs_cfs, q_fs_quality, q_fs_source, baseline_ratio.
         data/derived/splits.csv (event-level split/fold), holdout_gauges.csv, split_summary.csv, leakage_tests.txt
"""
import numpy as np, pandas as pd
from common import *

TBL = DER / "ml_full_table"
K = 5
parts = sorted(TBL.glob("usgs_id=*/part.parquet"))
uids = [p.parent.name.split("=")[1] for p in parts]
ev = pd.read_csv(DER / "events.csv", parse_dates=["start", "end"])
cw = pd.read_csv(DER / "gauge_crosswalk.csv", dtype={"usgs_id": str}).set_index("usgs_id").loc[uids]
fl = ev[ev.name.str.startswith("Florence", na=False)]
assert len(fl) == 1, f"expected exactly one Florence event, found {len(fl)}"
fl = fl.iloc[0]
FS, FE = fl.start, fl.end
BS, BE = FS - pd.Timedelta(days=7), FE + pd.Timedelta(days=7)

# ---- 2. spatial holdout
rng = np.random.default_rng(42)
cw["huc4"] = cw.hydrologic_unit_code.astype(str).str.zfill(8).str[:4]
hold = []
for _, grp in sorted(cw.groupby(["huc4", "in_pilot"]), key=lambda kv: (kv[0][0], kv[0][1])):
    n, x = len(grp), 0.15 * len(grp)
    k = int(x) + int(rng.random() < x - int(x))
    hold += list(rng.choice(sorted(grp.index), k, replace=False)) if k else []
pil = cw[cw.in_pilot].index
extra = [g for g in hold if g in set(pil)]
while len(extra) > len(pil) // 2:  # keep at least half of pilot gauges in train
    drop = extra.pop(); hold.remove(drop)
hold = sorted(hold)
cw["holdout"] = cw.index.isin(hold)
cw.reset_index()[["usgs_id", "huc4", "in_pilot", "has_official_flood_stage", "holdout"]].to_csv(DER / "holdout_gauges.csv", index=False)

# ---- 3. CV folds over event_ids (trainval gauges, non-test)
pos = {}
for p, u in zip(parts, uids):
    if cw.loc[u, "holdout"]:
        continue
    d = pd.read_parquet(p, columns=["event_id", "exceed_next_12h", "time_utc"])
    d = d[(d.time_utc < BS) | (d.time_utc > BE)]
    for e, v in d.groupby("event_id").exceed_next_12h.sum().items():
        pos[e] = pos.get(e, 0) + v
fl_id = int(fl.event_id)
groups = sorted((e for e in pd.read_parquet(parts[0], columns=["event_id"]).event_id.unique() if e != fl_id),
                key=lambda e: -pos.get(e, 0))
load, fold = np.zeros(K), {}
for e in groups:
    f = int(np.argmin(load + (np.arange(K) * 1e-6))); fold[e] = f; load[f] += pos.get(e, 0)
fold_pos = {f: float(load[f]) for f in range(K)}

# ---- 4. per-gauge split + TRAIN-only features
def qfs(stage, q, fs):
    ok = ~(np.isnan(stage) | np.isnan(q))
    s, qq = stage[ok], q[ok]
    for w, name in ((0.25, "good"), (0.5, "ok"), (1.0, "poor")):
        m = np.abs(s - fs) <= w
        if m.sum() >= 10:
            return float(np.median(qq[m])), name
    return np.nan, "none"

rows, ref_check = [], {}
for p, u in zip(parts, uids):
    d = pd.read_parquet(p)
    t = d.time_utc
    is_test = ((t >= FS) & (t <= FE)).values
    is_buf = ((t >= BS) & (t <= BE)).values & ~is_test
    h = bool(cw.loc[u, "holdout"])
    d["split"] = np.where(is_test, "test", np.where(is_buf, "buffer", "unseen" if h else "trainval"))
    d["cv_fold"] = np.where(d.split == "trainval", d.event_id.map(fold), -1).astype("int8")
    refm = (d.split == ("unseen" if h else "trainval")).values
    ref = np.sort(d.nwm_flow.values[refm & d.nwm_flow.notna().values])
    d["nwm_flow_pctile"] = (np.searchsorted(ref, d.nwm_flow.values, side="right") / len(ref)).astype("float32") if len(ref) else np.float32(np.nan)
    d.loc[d.nwm_flow.isna(), "nwm_flow_pctile"] = np.nan
    ref_check[u] = (ref, refm)
    fs_ = d.flood_stage_ft.iloc[0]
    if np.isnan(fs_):
        qf, ql = np.nan, "n/a"
    else:
        qf, ql = qfs(d.obs_stage_ft.values[refm], d.obs_q_cfs.values[refm], fs_)
    d["q_fs_cfs"], d["q_fs_quality"] = qf, ql
    d["q_fs_source"] = "own_nontest_hours" if h else "train_hours"
    d["baseline_ratio"] = (d.nwm_flow / qf).astype("float32") if not np.isnan(qf) else np.float32(np.nan)
    d.to_parquet(p, index=False)
    rows.append({"usgs_id": u, "holdout": h, "q_fs_cfs": qf, "q_fs_quality": ql, "n_ref_hours": int(refm.sum())})
qq = pd.DataFrame(rows)
qq.to_csv(DER / "q_fs_estimates.csv", index=False)

# ---- splits.csv (event level)
sp = pd.DataFrame({"event_id": groups + [fl_id]})
sp["kind"] = np.where(sp.event_id > 0, "storm_event", "quiet_stretch")
sp["split"] = np.where(sp.event_id == fl_id, "test(+7d buffer)", "trainval")
sp["cv_fold"] = sp.event_id.map(fold).fillna(-1).astype(int)
sp["primary_pos_12h_trainval_gauges"] = sp.event_id.map(pos).fillna(0)
sp = sp.merge(ev[["event_id", "start", "end", "name"]], on="event_id", how="left").sort_values("event_id", key=abs)
sp.to_csv(DER / "splits.csv", index=False)

# ---- 5. split summary + warnings
full = pd.concat([pd.read_parquet(p, columns=["usgs_id", "split", "event_id", "cv_fold", "flood_stage_ft", "proxy_exceed_next_12h"] +
                                  [f"exceed_next_{h}h" for h in range(1, 13)]) for p in parts])
S = []
for name, g in full.groupby("split"):
    r = {"split": name, "gauges": g.usgs_id.nunique(), "storm_events_in_split": g[g.event_id > 0].event_id.nunique(),
         "storm_events_with_primary_pos_12h": g[(g.event_id > 0) & (g.exceed_next_12h == 1)].event_id.nunique(),
         "rows": len(g), "primary_gauges": g[g.flood_stage_ft.notna()].usgs_id.nunique()}
    for h in range(1, 13):
        r[f"primary_pos_{h}h"] = int((g[f"exceed_next_{h}h"] == 1).sum())
    r["primary_pos_gauges_12h"] = g[g.exceed_next_12h == 1].usgs_id.nunique()
    r["proxy_pos_12h"] = int((g.proxy_exceed_next_12h == 1).sum())
    S.append(r)
S = pd.DataFrame(S)
S.to_csv(DER / "split_summary.csv", index=False)
W = []
t = S[S.split == "test"].iloc[0]
if t.primary_pos_12h < 30 or t.primary_pos_gauges_12h < 5:
    W.append(f"TEST SET TOO SMALL: {int(t.primary_pos_12h)} primary positive gauge-hours (12h) and {int(t.primary_pos_gauges_12h)} gauges with positives "
             f"(need >= 30 and >= 5)")
for f, v in fold_pos.items():
    if v == 0:
        W.append(f"CV fold {f} has NO primary positives")

# ---- 6. leakage tests
L = []
tv = full[full.split.isin(["trainval", "unseen"])]
te = full[full.split == "test"]
L.append(("no event_id appears in both test and trainval/unseen", set(te.event_id) .isdisjoint(set(tv.event_id))))
L.append(("no event_id spans two cv folds", full[full.split == "trainval"].groupby("event_id").cv_fold.nunique().max() == 1))
L.append(("no holdout gauge has a trainval row", not full[(full.split == "trainval") & full.usgs_id.isin(hold)].shape[0]))
L.append(("pilot gauges in train >= half of pilot gauges", (~cw[cw.in_pilot].holdout).sum() >= len(pil) / 2))
L.append(("no trainval/unseen row inside test+buffer window", True))  # by construction of split; verified next line
tt = pd.concat([pd.read_parquet(p, columns=["time_utc", "split"]) for p in parts])
L[-1] = (L[-1][0], bool(((tt.time_utc >= BS) & (tt.time_utc <= BE) & tt.split.isin(["trainval", "unseen"])).sum() == 0))
# feature causality: recompute features from NWM truncated at t for random gauge-hours
nw = pd.read_parquet(DER / "nwm_hourly.parquet")
rs, bad = np.random.default_rng(0), 0
samp = rs.choice(len(parts), 40)
for i in samp:
    d = pd.read_parquet(parts[i])
    fid = d.feature_id.iloc[0]
    ser = nw[nw.feature_id == fid].set_index("time_utc").nwm_flow_cms * 35.3146667
    for j in rs.integers(30, len(d) - 30, 8):
        tj = d.time_utc.iloc[j]
        past = ser[ser.index <= tj]  # only information available at t
        exp = {"nwm_flow": past.iloc[-1], "nwm_lag_6h": past.iloc[-7], "nwm_chg_24h": past.iloc[-1] - past.iloc[-25]}
        for c, v in exp.items():
            if not np.isclose(d[c].iloc[j], v, rtol=1e-4, equal_nan=True):
                bad += 1
L.append((f"features recomputed from data <= t match table (40 gauges x 8 hours x 3 features), mismatches={bad}", bad == 0))
bad = 0  # label windows: recompute from raw obs for a few gauges
for i in rs.choice([k for k, u in enumerate(uids) if cw.loc[u, "has_official_flood_stage"]], 10):
    d = pd.read_parquet(parts[i])
    s = d.obs_stage_ft.values
    for j in rs.integers(30, len(d) - 30, 20):
        w = s[j + 1:j + 7]
        exp = 1.0 if np.nanmax(np.r_[w, -1e9]) >= d.flood_stage_ft.iloc[0] else (0.0 if (~np.isnan(w)).all() else np.nan)
        if not (np.isnan(exp) and np.isnan(d.exceed_next_6h.iloc[j])) and exp != d.exceed_next_6h.iloc[j]:
            bad += 1
L.append((f"exceed_next_6h equals max stage over (t, t+6] only (10 gauges x 20 hours), mismatches={bad}", bad == 0))
bad = 0  # pctile reference must be TRAIN-only: recompute independently
for u in uids[::10]:
    ref, refm = ref_check[u]
    d = pd.read_parquet(TBL / f"usgs_id={u}" / "part.parquet", columns=["nwm_flow", "nwm_flow_pctile", "split"])
    want = "unseen" if cw.loc[u, "holdout"] else "trainval"
    ref2 = np.sort(d.nwm_flow[(d.split == want)].dropna().values)
    x = d.nwm_flow.dropna().iloc[::997]
    exp = np.searchsorted(ref2, x.values, side="right") / max(len(ref2), 1)
    bad += int(not np.allclose(d.nwm_flow_pctile.loc[x.index].values, exp, atol=1e-5, equal_nan=True))
L.append((f"nwm_flow_pctile reference = {'TRAIN' } hours only (unseen gauges: unseen hours), mismatched gauges={bad}", bad == 0))

txt = ["LEAKAGE TESTS"] + [f"[{'PASS' if ok else 'FAIL'}] {n}" for n, ok in L] + ["", "WARNINGS"] + (W or ["none"]) + ["", S.T.to_string(),
       "", f"holdout gauges ({len(hold)}): {' '.join(hold)}", f"cv fold primary positives (12h): {fold_pos}",
       f"Florence event_id={fl_id} window {FS} .. {FE}; buffer {BS} .. {BE}"]
(DER / "leakage_tests.txt").write_text("\n".join(txt))
print("\n".join(txt))
