"""Step 5: full gauge-hour table (base columns, labels, events). Split-dependent columns (nwm_flow_pctile, Q_fs, baseline_ratio,
split, cv_fold) are added by 06_splits.py because they must be computed on TRAIN-split hours only.

Outputs: data/derived/ml_full_table/usgs_id=*/part.parquet, data/derived/events.csv, data/derived/proxy_thresholds.csv

Definitions (fixed before looking at results):
- hour label t = START of the hour; stage = hourly max, discharge = hourly mean (see 03_observed.py).
- exceed_next_{h}h[t] = 1 if max observed hourly stage in (t, t+h] >= flood stage; 0 if all h hours observed and all below;
  NaN if any hour is missing and no observed hour is >= flood stage (unknown, never filled). Primary labels only for gauges with an
  official (NWS minor-category) flood stage whose datum check passed. exceed_next_12h is the h=12 column.
- exceedance hour = hour with observed stage >= flood stage. Storm event = exceedance hours (any official gauge, statewide) chained with
  gaps < 5 days (120 h) of no exceedance anywhere.
- proxy_exceed_next_12h (all gauges with a discharge series): 1 if max observed hourly discharge in (t, t+12h] >= Q2, else 0/NaN as above.
  Q2 = median of the gauge's USGS annual peak discharges (USGS 'peaks' collection) from water years BEFORE 2015 only (so no study,
  validation or test data touch the threshold); requires >= 10 peaks, otherwise the proxy label is NaN for that gauge.
  ponytail: median of annual peaks (empirical 2-yr), not a Log-Pearson III fit.
- event_id: positive = storm event (window first..last exceedance hour); negative = quiet stretch between events. Florence's id also covers
  its +-7 day buffer so the test/buffer hours share one id.
"""
import numpy as np, pandas as pd, io
from common import *

HORIZONS = range(1, 13)
CMS_TO_CFS = 35.3146667
OUT = DER / "ml_full_table"
GAP_H = 120


def peaks(uid):
    f = RAW / "peaks" / f"{uid}.csv"
    f.parent.mkdir(exist_ok=True)
    if not f.exists():
        r = get(USGS + "collections/peaks/items", {"f": "csv", "monitoring_location_id": f"USGS-{uid}", "parameter_code": "00060",
                                                    "properties": "water_year,value", "limit": 10000})
        f.write_text(r.text if r.text.strip() else "water_year,value\n")
    d = pd.read_csv(f)
    return pd.to_numeric(d[d.water_year < 2015].value, errors="coerce").dropna()


def fwd_label(x, h, thresh):
    """1/0/NaN label for max(x[t+1..t+h]) >= thresh with explicit missing handling."""
    rev = pd.Series(x[::-1]).shift(1)
    mx = rev.rolling(h, min_periods=1).max().values[::-1]
    cnt = rev.notna().astype(float).rolling(h, min_periods=1).sum().values[::-1]
    out = np.where(mx >= thresh, 1.0, np.where(cnt == h, 0.0, np.nan))
    return out.astype("float32")


def main():
    cw = pd.read_csv(DER / "gauge_crosswalk.csv", dtype={"usgs_id": str}).set_index("usgs_id")
    miss = pd.read_csv(DER / "obs_missing.csv", dtype={"usgs_id": str})
    keep = miss[~miss.dropped].usgs_id.tolist()
    obs = pd.read_parquet(DER / "obs_hourly.parquet")
    nwm = pd.read_parquet(DER / "nwm_hourly.parquet")
    idx = pd.date_range(START, NWM_END, freq="h", tz="UTC")
    nwm_by = {f: g.set_index("time_utc").nwm_flow_cms.reindex(idx) * CMS_TO_CFS for f, g in nwm.groupby("feature_id")}
    obs_by = {u: g.set_index("time_utc") for u, g in obs.groupby("usgs_id")}

    # pass 1: exceedance hours statewide -> events
    exc = {}
    for u in keep:
        r = cw.loc[u]
        if r.has_official_flood_stage:
            exc[u] = (obs_by[u].obs_stage_ft.reindex(idx).values >= r.flood_stage_ft)
    anyexc = np.zeros(len(idx), bool)
    for v in exc.values():
        anyexc |= v
    ei = np.flatnonzero(anyexc)
    brk = np.flatnonzero(np.diff(ei) > GAP_H)  # gap of > 120 h means >= 5 days without any exceedance hour
    starts, ends = ei[np.r_[0, brk + 1]], ei[np.r_[brk, len(ei) - 1]]
    ev = pd.DataFrame({"event_id": np.arange(1, len(starts) + 1), "start": idx[starts], "end": idx[ends]})
    g_in = lambda s, e: [u for u, v in exc.items() if v[s:e + 1].any()]
    ev["n_gauges_exceeding"] = [len(g_in(s, e)) for s, e in zip(starts, ends)]
    ev["gauges_exceeding"] = [" ".join(g_in(s, e)) for s, e in zip(starts, ends)]
    ev["exceedance_gauge_hours"] = [int(sum(v[s:e + 1].sum() for v in exc.values())) for s, e in zip(starts, ends)]
    ev["name"] = ""
    ev.loc[(ev.start <= "2018-09-20") & (ev.end >= "2018-09-14"), "name"] = "Florence (Sept 2018)"
    ev.loc[(ev.start <= "2016-10-12") & (ev.end >= "2016-10-07"), "name"] = "Matthew (Oct 2016)"
    ev.to_csv(DER / "events.csv", index=False)
    print(ev.drop(columns="gauges_exceeding").to_string())

    # event_id per hour (shared by all gauges)
    eid = np.zeros(len(idx), int)
    for r in ev.itertuples():
        eid[(idx >= r.start) & (idx <= r.end)] = r.event_id
    fl = ev[ev.name.str.startswith("Florence")]
    if len(fl):
        f = fl.iloc[0]
        eid[(idx >= f.start - pd.Timedelta(days=7)) & (idx <= f.end + pd.Timedelta(days=7))] = f.event_id
    q, k = 0, 0  # quiet stretches: negative ids per run of zeros
    run = np.r_[True, eid[1:] != eid[:-1]]
    for i in np.flatnonzero(run):
        if eid[i] == 0:
            k -= 1; j = i
            while j < len(eid) and eid[j] == 0:
                j += 1
            eid[i:j] = k
    # pass 2: per-gauge table
    import shutil
    shutil.rmtree(OUT, ignore_errors=True)  # never mix gauges from an earlier run
    OUT.mkdir(exist_ok=True)
    q2rows = []
    for u in keep:
        r = cw.loc[u]
        o = obs_by[u].reindex(idx)
        stage, qobs = o.obs_stage_ft.values, o.obs_q_cfs.values
        nf = nwm_by[int(r.feature_id)]
        df = pd.DataFrame({"usgs_id": u, "feature_id": int(r.feature_id), "time_utc": idx, "in_pilot": bool(r.in_pilot),
                           "event_id": eid, "obs_stage_ft": stage.astype("float32"), "obs_q_cfs": qobs.astype("float32"),
                           "nwm_flow": nf.values.astype("float32")})
        for h in (1, 3, 6, 12, 24):
            df[f"nwm_chg_{h}h"] = (nf - nf.shift(h)).values.astype("float32")
            df[f"nwm_lag_{h}h"] = nf.shift(h).values.astype("float32")
        df["stream_order"] = np.int8(r.stream_order) if pd.notna(r.stream_order) else np.int8(-1)
        df["month"] = idx.month.astype("int8")
        df["flood_stage_ft"] = r.flood_stage_ft if r.has_official_flood_stage else np.nan
        df["is_exceed_now"] = (stage >= r.flood_stage_ft) if r.has_official_flood_stage else np.zeros(len(idx), bool)
        for h in HORIZONS:
            df[f"exceed_next_{h}h"] = fwd_label(stage, h, r.flood_stage_ft) if r.has_official_flood_stage else np.float32(np.nan)
        pk = peaks(u) if r.has_q else pd.Series(dtype=float)
        q2 = float(pk.median()) if len(pk) >= 10 else np.nan
        q2rows.append({"usgs_id": u, "n_peaks_pre2015": len(pk), "q2_cfs": q2})
        df["proxy_q2_cfs"] = q2
        df["proxy_exceed_next_12h"] = fwd_label(qobs, 12, q2) if (r.has_q and not np.isnan(q2)) else np.float32(np.nan)
        d = OUT / f"usgs_id={u}"
        d.mkdir(exist_ok=True)
        df.to_parquet(d / "part.parquet", index=False)
    pd.DataFrame(q2rows).to_csv(DER / "proxy_thresholds.csv", index=False)
    print("gauges written:", len(keep), "| with primary labels:", len(exc), "| with proxy threshold:", int(pd.DataFrame(q2rows).q2_cfs.notna().sum()))


if __name__ == "__main__":
    main()
