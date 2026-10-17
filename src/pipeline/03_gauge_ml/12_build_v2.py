"""Build data/derived/ml_full_table_v2/: every existing column of ml_full_table plus three new feature groups.
Time convention (STRICTER than the old table, on purpose): row time t is the START of hour t; the hourly obs bin t covers [t, t+1).
All new features use only information available at clock time t: stage/discharge bins <= t-1 (bins that ended by t) and
Stage IV hourly accumulations whose END time is <= t. Missing stays NaN (no filling anywhere).
Groups:
  own_*   : own stage, change over 1/3/6/12/24h, fraction of flood stage, hours since last observation, 12h linear extrapolation (fraction of flood stage)
  up{k}_* : nearest 1-3 upstream usable gauges (NLDI UT, upstream_gauges.csv): dist_km, da_ratio, stage/discharge, changes, hours since obs, has_upstream flag
  rain_*  : Stage IV area-mean rain over the gauge's NLDI basin, accumulation over past 1/3/6/12/24/48/72h (needs all hours present, else NaN)
"""
import numpy as np, pandas as pd
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2])); from common import *

OLD, NEW = DER / "ml_full_table", DER / "ml_full_table_v2"
LAGS = (1, 3, 6, 12, 24)
RAINW = (1, 3, 6, 12, 24, 48, 72)
idx = pd.date_range(START, NWM_END, freq="h", tz="UTC")
N = len(idx)


def shift(a, h):
    out = np.full_like(a, np.nan); out[h:] = a[:-h]; return out


def hrs_since(S):
    ar = np.arange(len(S)); last = np.maximum.accumulate(np.where(~np.isnan(S), ar, -1))
    return np.where(last >= 0, ar - last, np.nan).astype("float32")


def cutoff(x):
    """value of the last bin that has ended by clock t = bin t-1"""
    return shift(x.astype("float64"), 1)


def rain_table():
    parts = [np.load(f) for f in sorted((DER / "stage4_catch").glob("*.npz"))]
    gs = list(parts[0]["gauges"])
    df = pd.concat([pd.DataFrame(p["rain_mm"], index=pd.to_datetime(p["hour_end"]).tz_localize("UTC"), columns=gs) for p in parts])
    df = df[~df.index.duplicated()].sort_index()
    return df.reindex(pd.date_range("2014-12-01", NWM_END, freq="h", tz="UTC"))  # index = accumulation END time


def new_feats(fs, S_raw, ups, rain_w):
    """Production feature code for one gauge. S_raw: raw hourly stage (bin t = [t,t+1)); ups: list of (dist_km, da_ratio, stage_raw, q_raw, up_flood_stage)
    for ranks 1..3; rain_w: {window: array of rolling sums indexed by accumulation END time == clock t}. Callers may pass truncated raw data."""
    n = len(S_raw); new = {}
    S = cutoff(S_raw)
    for h in LAGS: new[f"own_stage_chg_{h}h"] = S - shift(S, h)
    new["own_stage_ft"] = S
    new["own_stage_frac_fs"] = S / fs if not np.isnan(fs) else np.full(n, np.nan)
    new["own_hrs_since_obs"] = hrs_since(S)
    new["own_extrap12h_frac"] = (S + 12 * (S - shift(S, 6)) / 6) / fs if not np.isnan(fs) else np.full(n, np.nan)
    new["has_upstream"] = np.full(n, len(ups) > 0)
    new["n_upstream"] = np.full(n, len(ups), dtype="int8")
    for k in (1, 2, 3):
        pre = f"up{k}_"
        if k <= len(ups):
            dist, da, s_raw, q_raw, ufs = ups[k - 1]
            S2, Q2 = cutoff(s_raw), cutoff(q_raw)
            new[pre + "dist_km"] = np.full(n, dist); new[pre + "da_ratio"] = np.full(n, da)
            new[pre + "stage_ft"] = S2; new[pre + "stage_frac_fs"] = S2 / ufs if not np.isnan(ufs) else np.full(n, np.nan)
            new[pre + "q_cfs"] = Q2; new[pre + "hrs_since_obs"] = hrs_since(S2)
            for h in LAGS:
                new[f"{pre}stage_chg_{h}h"] = S2 - shift(S2, h); new[f"{pre}q_chg_{h}h"] = Q2 - shift(Q2, h)
        else:
            for c in ("dist_km", "da_ratio", "stage_ft", "stage_frac_fs", "q_cfs", "hrs_since_obs") + tuple(f"{a}_chg_{h}h" for a in ("stage", "q") for h in LAGS):
                new[pre + c] = np.full(n, np.nan)
    for w in RAINW: new[f"rain_catch_{w}h"] = rain_w[w]
    return {k: (np.asarray(v).astype("float32") if np.asarray(v).dtype.kind == "f" else np.asarray(v)) for k, v in new.items()}


def load_inputs():
    obs = pd.read_parquet(DER / "obs_hourly.parquet")
    st = {u: g.set_index("time_utc").reindex(idx) for u, g in obs.groupby("usgs_id")}
    cw = pd.read_csv(DER / "gauge_crosswalk.csv", dtype={"usgs_id": str}).set_index("usgs_id")
    up = pd.read_csv(DER / "upstream_gauges.csv", dtype={"usgs_id": str, "up_id": str})
    return st, cw, up


def ups_for(u, st, cw, up):
    out = []
    for v in up[up.usgs_id == u].sort_values("rank").itertuples():
        o = st[v.up_id]; ufs = cw.loc[v.up_id].flood_stage_ft if cw.loc[v.up_id].has_official_flood_stage else np.nan
        out.append((v.dist_km, v.da_ratio, o.obs_stage_ft.values, o.obs_q_cfs.values, ufs))
    return out


def rain_windows(R):
    """R: hourly DataFrame indexed by accumulation END time. Window w ending at clock t covers (t-w, t]; all w hours must be present."""
    return {w: R.rolling(w, min_periods=w).sum().reindex(idx) for w in RAINW}


def build():
    st, cw, up = load_inputs()
    rain = rain_windows(rain_table())
    import shutil; shutil.rmtree(NEW, ignore_errors=True); NEW.mkdir()
    for p in sorted(OLD.glob("usgs_id=*/part.parquet")):
        u = p.parent.name.split("=")[1]
        d = pd.read_parquet(p)
        assert (d.time_utc.values == idx.values).all() and len(d) == N
        rw = {w: (rain[w][u].values if u in rain[w].columns else np.full(N, np.nan)) for w in RAINW}
        new = new_feats(d.flood_stage_ft.iloc[0], st[u].obs_stage_ft.values, ups_for(u, st, cw, up), rw)
        d = pd.concat([d, pd.DataFrame(new)], axis=1)
        (NEW / f"usgs_id={u}").mkdir()
        d.to_parquet(NEW / f"usgs_id={u}" / "part.parquet", index=False)
    print("written", len(list(NEW.glob("usgs_id=*"))), "gauges; new cols:", len(new))


if __name__ == "__main__":
    build()
