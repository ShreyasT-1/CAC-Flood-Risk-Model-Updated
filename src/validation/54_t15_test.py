"""Phase 2 / T15 Step 4: AUC of peak flow ratio (positives vs negatives) per event and pooled; cluster bootstrap over (event, county) cells; precision/recall at q2 and q10; strata. Rules fixed in docs/validation_protocol.md Amendments 3-4. Run once.
Primary = pooled over events excluding the Helene event (E5, window contains 2024-09-26..28), metric peak/q10, pass if lower 95% bound > 0.5. Everything else is secondary. Usage (repo root): python src/validation/54_t15_test.py"""
import json, numpy as np, pandas as pd
O = "data/phase2/t15/"; rng = np.random.default_rng(20261011); NB = 10000
A = pd.read_parquet(O + "t15_crossing_sets.parquet"); PK = pd.read_parquet(O + "t15_peaks.parquet"); ev = pd.read_csv(O + "t15a4_events_chosen.csv", parse_dates=["start", "last_start"])
A = A.merge(PK, on=["event_id", "feature_id"], how="left"); A = A[A.peak_cfs.notna()].copy(); A["r10"] = A.peak_cfs / A.q10_cfs; A["r2"] = A.peak_cfs / A.q2_cfs
helene = [e.event_id for e in ev.itertuples() if e.start <= pd.Timestamp("2024-09-27", tz="UTC") <= e.last_start + pd.Timedelta(days=3) and e.start >= pd.Timestamp("2024-09-20", tz="UTC")]; print("Helene event(s):", helene)
def auc(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) == 0 or len(b) == 0: return np.nan
    r = pd.Series(np.r_[a, b]).rank().values; return float((r[:len(a)].sum() - len(a) * (len(a) + 1) / 2) / (len(a) * len(b)))
from scipy.stats import rankdata
def auc_fast(pos, neg):
    if len(pos) == 0 or len(neg) == 0: return np.nan
    r = rankdata(np.r_[pos, neg]); return float((r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))
def cells_of(D, lab, col):   # {(event, county): (pos_values, neg_values)} for the metric column
    return {k: (g[g[lab]][col].values, g[~g[lab]][col].values) for k, g in D.groupby(["event_id", "cty"])}
def boot_pooled(cells, nb=NB):
    """resample (event, county) cells with replacement; pooled statistic = mean over events of the event AUC computed on the resampled cells"""
    keys = list(cells); evs = sorted({k[0] for k in keys}); out = []
    for _ in range(nb):
        pick = rng.integers(0, len(keys), len(keys)); acc = {e: ([], []) for e in evs}
        for i in pick: acc[keys[i][0]][0].append(cells[keys[i]][0]); acc[keys[i][0]][1].append(cells[keys[i]][1])
        v = [auc_fast(np.concatenate(p) if p else np.array([]), np.concatenate(n) if n else np.array([])) for p, n in acc.values()]
        v = [x for x in v if np.isfinite(x)]
        if v: out.append(np.mean(v))
    return [round(float(np.percentile(out, 2.5)), 3), round(float(np.percentile(out, 97.5)), 3)]
def boot_event(cells_e, nb=2000):   # one event: resample its county cells
    keys = list(cells_e); out = []
    for _ in range(nb):
        pick = rng.integers(0, len(keys), len(keys)); v = auc_fast(np.concatenate([cells_e[keys[i]][0] for i in pick]), np.concatenate([cells_e[keys[i]][1] for i in pick]))
        if np.isfinite(v): out.append(v)
    return [round(float(np.percentile(out, 2.5)), 3), round(float(np.percentile(out, 97.5)), 3)] if len(out) > 100 else [None, None]
def table(D, lab, label):
    rows = []
    for e, g in list(D.groupby("event_id")) + [("ALL", D)]:
        p, n = g[g[lab]], g[~g[lab]]; rec = dict(group=label, event_id=e, n=len(g), n_pos=len(p), n_neg=len(n), n_counties=g.cty.nunique(), auc_r10=np.nan, auc_r2=np.nan)
        if min(len(p), len(n)) >= 5:
            rec["auc_r10"] = round(auc(p.r10, n.r10), 3); rec["auc_r2"] = round(auc(p.r2, n.r2), 3)
            ce = cells_of(g, lab, "r10"); rec["auc_r10_ci95_county_boot"] = boot_event({k: v for k, v in ce.items()})
        else: rec["note"] = "too few (<5 positives or negatives)"
        for q, c in (("q2", "r2"), ("q10", "r10")):
            hit = g[c] > 1; rec[f"precision_{q}"] = round(float((g[hit][lab]).mean()), 3) if hit.any() else np.nan; rec[f"recall_{q}"] = round(float(hit[g[lab]].mean()), 3) if len(p) else np.nan
        rec["share_gt_q10_pos"] = round(float((p.r10 > 1).mean()), 3) if len(p) else np.nan; rec["share_gt_q10_neg"] = round(float((n.r10 > 1).mean()), 3) if len(n) else np.nan; rows.append(rec)
    return pd.DataFrame(rows)
out = {}; T = []
for lab, name in (("pos100", "100 m (primary)"), ("pos250", "250 m (sensitivity)")):
    for grp_name, mask in (("excl_helene", ~A.event_id.isin(helene)), ("helene_only", A.event_id.isin(helene)), ("all_events", A.event_id.notna())):
        D = A[mask]; t = table(D, lab, f"{name}|{grp_name}"); T.append(t)
        evs = [e for e, g in D.groupby("event_id") if min(g[lab].sum(), (~g[lab]).sum()) >= 5]; Dp = D[D.event_id.isin(evs)]
        if len(evs) == 0: out[f"{lab}|{grp_name}"] = dict(note="no event with >= 5 positives and negatives"); continue
        for col in ("r10", "r2"):
            cells = cells_of(Dp, lab, col); pooled = float(np.mean([auc_fast(g[g[lab]][col].values, g[~g[lab]][col].values) for e, g in Dp.groupby("event_id")]))
            out[f"{lab}|{grp_name}|{col}"] = dict(events=evs, pooled_mean_event_auc=round(pooled, 3), ci95_boot_event_county_cells=boot_pooled(cells), n_pos=int(Dp[lab].sum()), n_neg=int((~Dp[lab]).sum()))
pd.concat(T).to_csv(O + "t15_results_by_event.csv", index=False)
# strata (primary labelling, primary pool = excl_helene and helene separately), metric r10
S = []
for grp_name, mask in (("excl_helene", ~A.event_id.isin(helene)), ("helene_only", A.event_id.isin(helene))):
    D = A[mask]
    for sname, col in (("order_class", "order_class"), ("reliable_analogue", "reliable_analogue"), ("tidal", "tidal"), ("structure_class", "structure_class")):
        for v, g in D.groupby(col):
            p, n = g[g.pos100], g[~g.pos100]; S.append(dict(pool=grp_name, stratum=f"{sname}={v}", n=len(g), n_pos=len(p), n_neg=len(n), auc_r10=round(auc(p.r10, n.r10), 3) if min(len(p), len(n)) >= 5 else np.nan, note="" if min(len(p), len(n)) >= 5 else "too few (<5)",
                                                         precision_q10=round(float(g[g.r10 > 1].pos100.mean()), 3) if (g.r10 > 1).any() else np.nan, recall_q10=round(float((g[g.pos100].r10 > 1).mean()), 3) if len(p) else np.nan))
pd.DataFrame(S).to_csv(O + "t15_results_strata.csv", index=False)
prim = out.get("pos100|excl_helene|r10"); prim["verdict"] = None if prim is None or "ci95_boot_event_county_cells" not in prim else ("PASS" if prim["ci95_boot_event_county_cells"][0] and prim["ci95_boot_event_county_cells"][0] > .5 else "FAIL")
out["PRIMARY"] = prim; json.dump(out, open(O + "t15_results.json", "w"), indent=1, default=str)
pd.set_option("display.width", 250, "display.max_columns", 30); print(json.dumps(out, indent=1, default=str)); print(pd.concat(T)[lambda d: d.group.str.startswith("100")].to_string(index=False)); print(pd.DataFrame(S).to_string(index=False))
