"""Job 3a: recompute every headline in docs/claims.md from files in the repo and compare with the documented number (parsed from claims.md, not typed here).
Rows marked 'recomputed' are calculated from per-row data files; 'stored' are read from a results json/csv written by the original test script (the bootstrap CIs and long
model runs are not re-run here). Mismatch = rounded recomputed value != documented value at the documented precision. Exit 1 on any mismatch.
Usage (repo root): python src/validation/80_repro_headlines.py"""
import json, re, sys, numpy as np, pandas as pd
from scipy.stats import rankdata
CL = open("docs/claims.md", encoding="utf-8").read()
ROWS = {}
for l in CL.splitlines():
    m = re.match(r"\| (C\d+) \|", l) or re.match(r"\| \*\*(T12|T13|E1)\*\*", l)
    if m: ROWS[m.group(1)] = l


def doc(k, rx, g=1):
    m = re.search(rx, ROWS[k]); assert m, f"claims.md {k}: pattern not found {rx}"; return m.group(g).replace(",", "").rstrip(".")


def auc(p, n):
    r = rankdata(np.r_[p, n]); return (r[:len(p)].sum() - len(p) * (len(p) + 1) / 2) / (len(p) * len(n))


def t15_pooled(d):
    """pooled primary: mean event AUC of peak/q10 over events (excl. the Helene event) with >=5 positives and >=5 negatives; label = pos100"""
    A = pd.read_parquet(d + "t15_crossing_sets.parquet").merge(pd.read_parquet(d + "t15_peaks.parquet"), on=["event_id", "feature_id"], how="left")
    A = A[A.peak_cfs.notna()].copy(); A["r10"] = A.peak_cfs / A.q10_cfs
    ev = pd.read_csv(d + "t15a4_events_chosen.csv", parse_dates=["start", "last_start"])
    hel = [e.event_id for e in ev.itertuples() if e.start <= pd.Timestamp("2024-09-27", tz="UTC") <= e.last_start + pd.Timedelta(days=3) and e.start >= pd.Timestamp("2024-09-20", tz="UTC")]
    A = A[~A.event_id.isin(hel)]; a = {}
    for e, g in A.groupby("event_id"):
        if min(g.pos100.sum(), (~g.pos100).sum()) >= 5: a[e] = auc(g[g.pos100].r10.values, g[~g.pos100].r10.values)
    k = A[A.event_id.isin(a)]
    return float(np.mean(list(a.values()))), int(k.pos100.sum()), sorted(a)


R = []   # (claim, quantity, how, recomputed, documented-string)


def add(c, q, how, v, d): R.append((c, q, how, v, d))


if __name__ == "__main__":
    # C1/C2 T10-B/C: per-report file
    P = pd.read_csv("data/phase2/t10/t10bc_per_report_primary_hour.csv"); j = json.load(open("data/phase2/t10/t10bc_results.json"))[0]
    add("C1", "T10-B AUC (mean per-report matched AUC)", "recomputed", P.auc.mean(), doc("C1", r"AUC \*\*([\d.]+)\*\*")); add("C1", "n reports", "recomputed", len(P), doc("C1", r"(\d+) provisional"))
    add("C1", "AUC CI low", "stored", j["auc_ci95"][0], doc("C1", r"CI ([\d.]+)-")); add("C1", "AUC CI high", "stored", j["auc_ci95"][1], doc("C1", r"CI [\d.]+-([\d.]+)"))
    add("C1", "% reports above q2", "recomputed", 100 * P.rep_gt_q2.mean(), doc("C1", r"at ([\d.]+)% of reports")); add("C1", "% control hours above q2", "recomputed", 100 * P.ctrl_gt_q2.mean(), doc("C1", r"vs ([\d.]+)% of control"))
    add("C2", "peak within +-24h, reports %", "recomputed", 100 * P.hit_rep.mean(), doc("C2", r"\*\*([\d.]+)%\*\* of reports")); add("C2", "peak within +-24h, controls %", "recomputed", 100 * P.hit_ctrl.mean(), doc("C2", r"vs \*\*([\d.]+)%\*\* of controls"))
    add("C2", "difference", "recomputed", P.hit_rep.mean() - P.hit_ctrl.mean(), doc("C2", r"\(difference \+([\d.]+),"))
    # C3, C4 stored stats
    s = json.load(open("data/phase2/t10/t10d_stats.json"))
    add("C3", "peak ratio within 0.5-2.0, %", "stored", 100 * s["share_peak_ratio_0p5_to_2"], doc("C3", r"\*\*([\d.]+)%\*\*")); add("C3", "gauge-events scored", "stored", s["gauge_events_scored"], doc("C3", r"of (\d+) gauge-events"))
    add("C3", "median |peak-time error| h", "stored", s["median_abs_peak_time_err_h"], doc("C3", r"error \*\*([\d.]+) h")); add("C3", "median NSE", "stored", s["median_nse"], doc("C3", r"NSE ([\d.]+)")); add("C3", "gauges", "stored", s["gauges"], doc("C3", r"at (\d+) pilot gauges"))
    f = json.load(open("data/phase2/t10/t10f_stats.json"))
    add("C4", "median abs error %", "stored", 100 * f["median_ape"], doc("C4", r"error \*\*([\d.]+)%\*\*")); add("C4", "within +-30%, %", "stored", 100 * f["share_within_30pct"], doc("C4", r"\*\*([\d.]+)%\*\* within"))
    add("C4", "MAE min", "stored", f["mae_min"], doc("C4", r"MAE ([\d.]+) min")); add("C4", "bias min", "stored", f["bias_min"], doc("C4", r"bias (-[\d.]+) min")); add("C4", "n blocks", "stored", f["pairs"], doc("C4", r"n = (\d+)"))
    # C5 T15
    for d, nm, cc in (("data/phase2/t15/", "six-event", r"AUC \*\*([\d.]+)\*\*"), ("data/phase2/t15_nine/", "nine-event", r"; \*\*([\d.]+)\*\*")):
        a, npos, evs = t15_pooled(d)
        add("C5", f"T15 {nm} pooled AUC (events {','.join(evs)})", "recomputed", a, doc("C5", cc)); add("C5", f"T15 {nm} positives", "recomputed", npos, doc("C5", r"(\d+) / (\d+) positives", 1 if nm == "six-event" else 2))
    # C6 consequence ranking
    co = pd.read_csv("data/export/consequence_ranking.csv"); asd = co[co.consequence_status == "assessed"]; top = co.sort_values("rank_by_people_affected").iloc[0]
    add("C6", "crossings assessed", "recomputed", len(asd), doc("C6", r"for ([\d,]+) of")); add("C6", "crossings total", "recomputed", len(co), doc("C6", r"of ([\d,]+) crossings"))
    add("C6", "top-ranked people affected", "recomputed", top.people_affected, doc("C6", r"slows ([\d,]+) people")); add("C6", "top-ranked blocks affected", "recomputed", top.blocks_affected, doc("C6", r"\((\d+) blocks\)"))
    add("C6", "top-ranked people losing hospital or fire access", "recomputed", top.hosp_pop_lost_access + top.fire_pop_lost_access, doc("C6", r"with (\d+) people losing"))
    # C7 Florence replay
    h = pd.read_csv("data/export/florence_replay_hourly.csv"); sd = h[(h.crossing_set == "seed") & (h.scenario == "RL2")]; rc = pd.read_csv("data/phase1b/recurrence_hindcast_nwm_v30_retro.csv")
    add("C7", "seed crossings above RL2 at peak hour", "recomputed", sd.n_crossings_above_level.max(), doc("C7", r"\((\d+) of 250 at the peak")); add("C7", "seed crossings assessed", "recomputed", sd.n_crossings_assessed.max(), doc("C7", r"of (\d+) at the peak"))
    add("C7", "seed crossings whose peak exceeds q50", "recomputed", int(((rc.in_seed) & (rc.peak_bin == "above_50")).sum()), doc("C7", r"(\d+) of 250 exceed the 50-year"))
    # C8 ML nowcast (read from ml_example_v2_results.csv written by src/pipeline/03_gauge_ml/ml_example_v2.py)
    M = pd.read_csv("data/phase2/ml_example_v2_results.csv"); M = M[M.population.str.startswith("onset") & ~M.score.str.startswith("DIFF")]
    for es, rx in (("TEST Florence", r"Florence \(test\) \*\*([\d.]+)\*\* vs ([\d.]+)"), ("UNSEEN gauges (non-Florence)", r"unseen gauges ([\d.]+) vs ([\d.]+)"), ("VAL (fold 4, trained gauges)", r"validation fold ([\d.]+) vs ([\d.]+)")):
        g = M[M.eval_set == es]; add("C8", f"{es}: model recall@50% precision", "stored", g[g.score == "hgb_seedavg"].recall50.iloc[0], doc("C8", rx, 1)); add("C8", f"{es}: best persistence recall@50%", "stored", g[g.score.str.contains("persist")].recall50.max(), doc("C8", rx, 2))
    # C9 FEMA
    F = pd.read_csv("data/phase2/fema_vs_rl10_florence_hindcast.csv"); sdF = F[F.crossing_set.str.startswith("seed (")].set_index("fema_zone_class"); al = sdF.loc["ALL"]
    add("C9", "seed crossings assessed", "recomputed", al.n_assessed, doc("C9", r"of the (\d+) hazard-ready")); add("C9", "above RL10", "recomputed", al.n_above_rl10, doc("C9", r"\*\*(\d+) \("))
    add("C9", "above RL10 %", "recomputed", 100 * al.n_above_rl10 / al.n_assessed, doc("C9", r"\(([\d.]+)%\)\*\* exceed"))
    ab, nb = sdF.loc["[SFHA yes/no x above RL10] among above: share in SFHA"], sdF.loc["[..] among NOT above: share in SFHA"]
    add("C9", "above RL10 and in SFHA", "recomputed", ab.n_above_rl10, doc("C9", r"\*\*(\d+) of those")); add("C9", "of those above RL10", "recomputed", ab.n_assessed, doc("C9", r"of those (\d+) \("))
    add("C9", "not above RL10, in SFHA", "recomputed", nb.n_above_rl10, doc("C9", r"and (\d+) of the \d+ that do not")); add("C9", "not above RL10", "recomputed", nb.n_assessed, doc("C9", r"and \d+ of the (\d+) that do not"))
    # C10 / T16 from out-of-fold predictions (non-Helene events pooled; Helene separate)
    O0 = pd.read_parquet("data/phase2/t16/t16_oof_predictions.parquet"); O = O0[O0.event_id != "E5"]
    pool = lambda c: float(np.mean([auc(g[g.y == 1][c].values, g[g.y == 0][c].values) for _, g in O.groupby("event_id")]))
    add("C10", "T16 baseline (raw peak/q10) pooled AUC", "recomputed", pool("base"), doc("C10", r"vs \*\*([\d.]+)\*\* \(0")); add("C10", "T16 HGB pooled AUC", "recomputed", pool("hgb_without_hand"), doc("C10", r"pooled AUC \*\*([\d.]+)\*\*"))
    add("C10", "T16 logistic pooled AUC", "recomputed", pool("logistic_without_hand"), doc("C10", r"logistic: ([\d.]+)")); add("C10", "T16 HGB minus baseline", "recomputed", pool("hgb_without_hand") - pool("base"), doc("C10", r"paired difference \*\*\+([\d.]+)"))
    Hh = O0[O0.event_id == "E5"]
    add("C10", "Helene HGB AUC", "recomputed", auc(Hh[Hh.y == 1].hgb_without_hand.values, Hh[Hh.y == 0].hgb_without_hand.values), doc("C10", r"Helene \(held out.*?\) ([\d.]+) vs"))
    add("C10", "Helene baseline AUC", "recomputed", auc(Hh[Hh.y == 1].base.values, Hh[Hh.y == 0].base.values), doc("C10", r"Helene \(held out.*?\) [\d.]+ vs ([\d.]+)"))
    # failed-test table (stored)
    t12 = json.load(open("data/phase2/t12/t12_results.json"))["results"][0]; add("T12", "AUC", "stored", t12["auc"], doc("T12", r"AUC \*\*([\d.]+)\*\*")); add("T12", "HWM above crest n", "stored", t12["n_hwm_above"], doc("T12", r"at (\d+) of \d+ \("))
    t13 = json.load(open("data/phase2/t13/t13_results.json"))["results"][0]; add("T13", "AUC", "stored", t13["auc"], doc("T13", r"AUC \*\*([\d.]+)\*\*")); add("T13", "crossings inside flood extent", "stored", t13["n_inside"], doc("T13", r"(\d+) of 250 crossings inside"))
    e1 = json.load(open("data/phase2/t10/t10e_results.json"))["q10_cfs"]
    add("E1", "listed hit share %", "stored", 100 * e1["listed_hit_share"], doc("E1", r"([\d.]+)% \(55/70\)")); add("E1", "unlisted hit share %", "stored", 100 * e1["unlisted_hit_share"], doc("E1", r"vs ([\d.]+)% \(30/46\)")); add("E1", "one-sided p", "stored", e1["fisher_p_one_sided"], doc("E1", r"p = ([\d.]+)"))
    # export row counts: files vs manifest vs README
    man = json.load(open("data/export/manifest.json"))["files"]; rd = open("data/export/README.md", encoding="utf-8").read()
    n = {"crossings_export.csv": len(pd.read_csv("data/export/crossings_export.csv")), "consequence_ranking.csv": len(co), "blocks_export.csv": len(pd.read_csv("data/export/blocks_export.csv")),
         "florence_replay_hourly.csv": len(h), "address_report_sample.json": len(json.load(open("data/export/address_report_sample.json")))}
    for m in man:
        if m["file"] in n: add("export", f"rows {m['file']} (file vs manifest)", "recomputed", n[m["file"]], str(m["rows"]))
    add("export", "crossings rows vs README", "recomputed", n["crossings_export.csv"], re.search(r"crossing \(([\d,]+)\)", rd).group(1).replace(",", "")); add("export", "blocks rows vs README", "recomputed", n["blocks_export.csv"], re.search(r"Origins = ([\d,]+) Census", rd).group(1).replace(",", ""))
    add("export", "hourly rows = 1320 h x 2 sets x 5 scenarios", "recomputed", n["florence_replay_hourly.csv"], str(1320 * 2 * 5))
    bad, rows = 0, []
    for c, q, how, v, d in R:
        dec = len(d.split(".")[1]) if "." in d else 0; ok = round(float(v), dec) == round(float(d), dec); bad += not ok
        rows.append(dict(claim=c, quantity=q, how=how, recomputed=round(float(v), max(dec, 3)), documented=d, status="ok" if ok else "MISMATCH"))
    T = pd.DataFrame(rows); pd.set_option("display.width", 250, "display.max_colwidth", 70, "display.max_rows", 200); print(T.to_string(index=False)); T.to_csv("data/review/repro_headlines.csv", index=False)
    print(f"\n{len(T)} quantities, {bad} mismatches"); sys.exit(1 if bad else 0)
