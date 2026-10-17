"""Step 5 checks. (1) re-read one archived cycle: rows, leads 1-18, valid = issue + lead, version present.
(2) lead-1h forecast vs v3.0 retrospective (free-running, NO data assimilation) vs USGS obs at 3 gauges, Florence.
Output: data/forecasts/florence_compare.csv (plot-ready, long) + printed stats. Differences are reported as-is.
LABEL: v1.2 operational forecasts, hindcast replay only - not skill of the current model."""
import sys
import glob
from nwm_fc import *

ROOT_DER = ROOT / "data/derived"


def check_cycle(p):
    d = pd.read_parquet(p)
    ids = reach_ids()
    assert set(d.lead_hours) == set(range(1, 19)), "leads"
    assert (d.groupby("feature_id").size() == 18).all(), "rows per reach"
    assert ((d.valid_time - d.issue_time) / pd.Timedelta(hours=1) == d.lead_hours).all(), "valid != issue + lead"
    assert d.nwm_version.notna().all() and d.feature_id.isin(ids).all() and not d.duplicated(["feature_id", "lead_hours"]).any()
    return d


if __name__ == "__main__":
    fs = sorted(glob.glob(str(OUT / "short_range/*/*.parquet")))
    d = check_cycle(fs[0]); print("cycle check OK:", fs[0], d.shape, d.nwm_version.unique().tolist())
    if len(sys.argv) > 1 and sys.argv[1] == "compare":
        fc = pd.concat(pd.read_parquet(f, filters=[("lead_hours", "==", 1)]) for f in fs if "2018" in f)
        fc = fc.rename(columns={"valid_time": "time_utc", "streamflow_cfs": "fc_lead1_cfs"})[["feature_id", "time_utc", "fc_lead1_cfs", "issue_time"]]
        cw = pd.read_csv(ROOT_DER / "gauge_crosswalk.csv", dtype={"usgs_id": str}); cw = cw[(cw.drainage_area_check == "ok") & cw.has_q]
        ob = pd.read_parquet(ROOT_DER / "obs_hourly.parquet"); ob = ob[(ob.time_utc >= "2018-09-17") & (ob.time_utc < "2018-11-14")]
        pk = ob.groupby("usgs_id").obs_q_cfs.max()
        # 3 gauges: highest Florence peak among those with >=90% observed coverage and a fc reach present
        cov = ob.groupby("usgs_id").obs_q_cfs.apply(lambda s: s.notna().mean())
        cand = cw[cw.usgs_id.isin(cov[cov >= .9].index) & cw.feature_id.isin(fc.feature_id)].copy()
        cand["peak"] = cand.usgs_id.map(pk); cand = cand.sort_values("peak", ascending=False).drop_duplicates("feature_id").head(3)
        retro = pd.read_parquet(ROOT_DER / "nwm_hourly.parquet"); retro["retro_cfs"] = retro.nwm_flow_cms * CMS_TO_CFS
        out = []
        for _, g in cand.iterrows():
            a = fc[fc.feature_id == g.feature_id].merge(retro[retro.feature_id == g.feature_id][["time_utc", "retro_cfs"]], on="time_utc", how="left")
            a = a.merge(ob[ob.usgs_id == g.usgs_id][["time_utc", "obs_q_cfs"]], on="time_utc", how="left"); a["usgs_id"] = g.usgs_id
            out.append(a)
        o = pd.concat(out); o.to_csv(OUT / "florence_compare.csv", index=False)
        for u, a in o.groupby("usgs_id"):
            a = a.dropna(subset=["fc_lead1_cfs", "retro_cfs", "obs_q_cfs"])
            st = lambda x, y: dict(bias_pct=100 * (x - y).sum() / y.sum(), rmse=((x - y) ** 2).mean() ** .5, r=x.corr(y), peak_ratio=x.max() / y.max())
            print(u, "n=", len(a), "obs peak", round(a.obs_q_cfs.max()), "at", a.loc[a.obs_q_cfs.idxmax(), "time_utc"])
            for n, x, y in [("fc1 vs obs", a.fc_lead1_cfs, a.obs_q_cfs), ("retro vs obs", a.retro_cfs, a.obs_q_cfs), ("fc1 vs retro", a.fc_lead1_cfs, a.retro_cfs)]:
                print("  ", n, {k: round(v, 2) for k, v in st(x, y).items()})
