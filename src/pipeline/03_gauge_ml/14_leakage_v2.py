"""Leakage tests for the v2 table (appends to data/derived/leakage_tests_v2.txt; the old tests are re-run on the v2 table too).
 1. old tests (split structure) on v2: event/fold/holdout/buffer
 2. old columns of v2 are identical to ml_full_table
 3. FOR EACH new feature group (own stage, upstream gauges, catchment rain): recompute from raw data that is TRUNCATED at t (everything after the
    knowledge cutoff replaced by NaN, then the production code path is rerun) on a random sample of gauge-hours and assert zero mismatches.
    This is also the "no feature uses a value after t" test: any dependence on later data would change the recomputed value.
 4. catchment-rain accumulations end at or before t: the rain value used at row t has accumulation END time <= t (checked on the raw index),
    and equals the sum of the raw hourly values over (t-w, t].
 5. independent re-derivation of the basin-mean rain for sampled hours from the raw GRIB (re-download of the month tar, shapely intersection, no sparse matrix)
"""
import importlib.util, gzip, io, json, re, tarfile
import numpy as np, pandas as pd, requests
import eccodes as ec
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2])); from common import *

spec = importlib.util.spec_from_file_location("b", Path(__file__).parent / "12_build_v2.py"); b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
V2, OLD = b.NEW, b.OLD
parts = sorted(V2.glob("usgs_id=*/part.parquet")); uids = [p.parent.name.split("=")[1] for p in parts]
rs = np.random.default_rng(7)
L = []
st, cw, up = b.load_inputs()
R = b.rain_table()
idx = b.idx; N = len(idx)


def rd(u, cols=None): return pd.read_parquet(V2 / f"usgs_id={u}" / "part.parquet", columns=cols)


# 1/2: structure unchanged
full = pd.concat([rd(u, ["usgs_id", "split", "event_id", "cv_fold", "time_utc"]) for u in uids])
tv, te = full[full.split.isin(["trainval", "unseen"])], full[full.split == "test"]
L.append(("no event_id appears in both test and trainval/unseen", set(te.event_id).isdisjoint(set(tv.event_id))))
L.append(("no event_id spans two cv folds", full[full.split == "trainval"].groupby("event_id").cv_fold.nunique().max() == 1))
hold = pd.read_csv(DER / "holdout_gauges.csv", dtype={"usgs_id": str}); hold = set(hold[hold.holdout].usgs_id)
L.append(("34 unseen gauges, none has a trainval row", len(hold) == 34 and full[(full.split == "trainval") & full.usgs_id.isin(hold)].empty))
ev = pd.read_csv(DER / "events.csv", parse_dates=["start", "end"]); fl = ev[ev.name.str.startswith("Florence", na=False)].iloc[0]
BS, BE = fl.start - pd.Timedelta(days=7), fl.end + pd.Timedelta(days=7)
L.append(("no trainval/unseen row inside test+buffer window", ((full.time_utc >= BS) & (full.time_utc <= BE) & full.split.isin(["trainval", "unseen"])).sum() == 0))
bad = 0
for u in uids[::7]:
    o, n = pd.read_parquet(OLD / f"usgs_id={u}" / "part.parquet"), rd(u)
    bad += int(not o.reset_index(drop=True).equals(n[o.columns].reset_index(drop=True)))
L.append((f"all old columns identical in v2 (every 7th gauge), mismatching gauges={bad}", bad == 0))

# 3: truncated recompute, per group
def trunc(a, t_row):  # keep bins <= t_row-1 (ended by clock t); everything later -> NaN
    a = a.copy(); a[t_row:] = np.nan; return a


names = {"own": [], "up": [], "rain": []}
mm = {"own": 0, "up": 0, "rain": 0}; cnt = {"own": 0, "up": 0, "rain": 0}
samp_g = rs.choice(len(uids), 60, replace=False)
for gi in samp_g:
    u = uids[gi]; d = rd(u)
    fs = d.flood_stage_ft.iloc[0]
    ups_full = b.ups_for(u, st, cw, up)
    for t_row in rs.integers(100, N - 100, 6):
        S = trunc(st[u].obs_stage_ft.values, t_row)
        ups_t = [(a, bb, trunc(s_, t_row), trunc(q_, t_row), f_) for a, bb, s_, q_, f_ in ups_full]
        # rain truncated: accumulation END times > clock t removed
        Rt = R.copy(); Rt.loc[Rt.index > idx[t_row]] = np.nan
        rw = {w: (Rt[u].rolling(w, min_periods=w).sum().reindex(idx).values if u in Rt.columns else np.full(N, np.nan)) for w in b.RAINW}
        new = b.new_feats(fs, S, ups_t, rw)
        for c, v in new.items():
            grp = "own" if c.startswith("own_") else ("rain" if c.startswith("rain_") else "up")
            if c in ("has_upstream", "n_upstream"): grp = "up"
            tab = d[c].values[t_row]; cnt[grp] += 1
            if not np.isclose(tab, v[t_row], rtol=1e-5, atol=1e-6, equal_nan=True):
                mm[grp] += 1
for grp, label in (("own", "own stage"), ("up", "upstream gauges"), ("rain", "catchment rain")):
    L.append((f"{label}: features recomputed from raw data truncated at t match the table (60 gauges x 6 hours, {cnt[grp]} values), mismatches={mm[grp]}", mm[grp] == 0 and cnt[grp] > 0))

# 4: rain accumulation end times and raw sums
bad = 0; chk = 0
for gi in rs.choice(len(uids), 30, replace=False):
    u = uids[gi]
    if u not in R.columns: continue
    d = rd(u, ["time_utc"] + [f"rain_catch_{w}h" for w in b.RAINW])
    for t_row in rs.integers(100, N - 100, 6):
        t = idx[t_row]
        for w in b.RAINW:
            win = R[u].loc[(R.index > t - pd.Timedelta(hours=w)) & (R.index <= t)]  # END times in (t-w, t]
            exp = win.sum() if (len(win) == w and win.notna().all()) else np.nan
            chk += 1; bad += int(not np.isclose(d[f"rain_catch_{w}h"].values[t_row], exp, rtol=1e-4, atol=1e-5, equal_nan=True))
            assert win.index.max() <= t
L.append((f"rain accumulations: window = hourly values with END time in (t-w, t], none after t ({chk} values), mismatches={bad}", bad == 0))

# 5: independent re-derivation of the basin mean from raw GRIB
from shapely.geometry import shape, box
from shapely.ops import transform, unary_union
import pyproj
tr = pyproj.Transformer.from_crs(4326, b_proj := "+proj=stere +lat_0=90 +lat_ts=60 +lon_0=-105 +x_0=0 +y_0=0 +R=6371200 +units=m", always_xy=True)
s4 = importlib.util.spec_from_file_location("s4", Path(__file__).parent / "11_stage4_catch.py"); m4 = importlib.util.module_from_spec(s4); s4.loader.exec_module(m4)
x0, y0 = tr.transform(-119.023, 23.117)
bad = 0; chk = 0
for ym in ("201609", "201809"):
    tarf = RAW / "stage4" / f"stage4.{ym}.tar"
    if not tarf.exists():
        with requests.get(m4.BASE + f"stage4.{ym}.tar", stream=True, timeout=300) as r:
            with open(tarf, "wb") as fh:
                for ch in r.iter_content(1 << 20): fh.write(ch)
    z = np.load(DER / "stage4_catch" / f"{ym}.npz"); times = pd.to_datetime(z["hour_end"]); gl = list(z["gauges"])
    # pick 2 hours with rain and 3 gauges
    pick = [(i, g) for i in rs.choice(len(times), 3, replace=False) for g in rs.choice(len(gl), 2, replace=False)]
    want = {times[i].strftime("%Y%m%d%H"): i for i, _ in pick}
    fields = {}
    with tarfile.open(tarf) as outer:
        for mb in outer:
            if not mb.isfile() or not mb.name.startswith("ST4."): continue
            with tarfile.open(fileobj=outer.extractfile(mb)) as inner:
                for im in inner:
                    mt = re.fullmatch(r"ST4\.(\d{10})\.01h\.gz", im.name)
                    if mt and mt.group(1) in want:
                        h = ec.codes_new_from_message(gzip.decompress(inner.extractfile(im).read()))
                        fields[mt.group(1)] = ec.codes_get_values(h).reshape(m4.NY, m4.NX).copy(); ec.codes_release(h)
    for i, g in pick:
        fc = json.loads((RAW / "nldi_basin" / f"{gl[g]}.json").read_text())["features"]
        if not fc: continue
        poly = unary_union([transform(tr.transform, shape(x["geometry"])) for x in fc])
        v = fields[times[i].strftime("%Y%m%d%H")]; num = den = 0.0
        minx, miny, maxx, maxy = poly.bounds
        for j in range(max(0, int((miny - y0) / m4.DX) - 1), min(m4.NY, int((maxy - y0) / m4.DX) + 2)):
            for k in range(max(0, int((minx - x0) / m4.DX) - 1), min(m4.NX, int((maxx - x0) / m4.DX) + 2)):
                a = poly.intersection(box(x0 + m4.DX * (k - .5), y0 + m4.DX * (j - .5), x0 + m4.DX * (k + .5), y0 + m4.DX * (j + .5))).area
                if a > 0 and v[j, k] < 9998: num += a * v[j, k]; den += a
        exp = num / den if den > 0 else np.nan
        chk += 1; bad += int(not np.isclose(z["rain_mm"][i, g], exp, rtol=1e-3, atol=1e-3, equal_nan=True))
L.append((f"basin-mean rain re-derived independently from raw GRIB ({chk} gauge-hours), mismatches={bad}", bad == 0 and chk > 0))

txt = ["LEAKAGE TESTS v2 (new feature groups + structure)"] + [f"[{'PASS' if ok else 'FAIL'}] {n}" for n, ok in L]
(DER / "leakage_tests_v2.txt").write_text("\n".join(txt)); print("\n".join(txt))
