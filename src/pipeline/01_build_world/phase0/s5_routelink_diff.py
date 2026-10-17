"""Phase0 follow-up 1: are the 256 crosswalk reaches present in (a) the v3.0 retrospective chrtout.zarr feature_id coord and (b) RouteLink v3.1.6? Any attribute drift?"""
import numpy as np, pandas as pd, xarray as xr, json
d = pd.read_csv("data/derived/gauge_crosswalk.csv", dtype={"usgs_id": str}); ids = np.sort(d.feature_id.unique())
# zarr/s3fs fails DNS here (aiodns); read the single feature_id chunk (zstd, int64, 2,776,734 values) fetched with curl from .../chrtout.zarr/feature_id/0
import zstandard
fz = np.frombuffer(zstandard.ZstdDecompressor().decompress(open("data/phase0/raw/retro30_feature_id.zst", "rb").read(), max_output_size=2776734 * 8), dtype="<i8"); print("v3.0 retrospective feature_ids:", len(fz))
rl = xr.open_dataset("data/phase0/raw/RouteLink_CONUS_v3.1.6.nc")
R = pd.DataFrame({"feature_id": rl["link"].values.astype("int64"), "rl_order": rl["order"].values, "rl_lat": rl["lat"].values, "rl_lon": rl["lon"].values, "rl_gage": [b.decode().strip() if isinstance(b, bytes) else str(b).strip() for b in rl["gages"].values], "rl_len": rl["Length"].values}).drop_duplicates("feature_id")
in30, in31 = np.isin(ids, fz), np.isin(ids, R.feature_id)
print("reaches", len(ids), "in v3.0 retro", in30.sum(), "in v3.1.6 RouteLink", in31.sum(), "both", (in30 & in31).sum(), "v3.0 only", (in30 & ~in31).sum(), "v3.1.6 only", (~in30 & in31).sum(), "neither", (~in30 & ~in31).sum())
print("whole-network: retro", len(fz), "RouteLink", len(R), "retro-not-in-RL", (~np.isin(fz, R.feature_id)).sum(), "RL-not-in-retro", (~np.isin(R.feature_id.values, fz)).sum())
g = d.drop_duplicates("feature_id").merge(R, on="feature_id", how="left")
g["order_changed"] = g.stream_order.notna() & g.rl_order.notna() & (g.stream_order != g.rl_order)
g["gage_in_rl"] = [(str(u) in str(rg)) if pd.notna(rg) else np.nan for u, rg in zip(g.usgs_id, g.rl_gage)]
g["xy_off_km"] = np.hypot((g.lat - g.rl_lat) * 111, (g.lon - g.rl_lon) * 111 * np.cos(np.radians(g.lat)))
print("order differs:", int(g.order_changed.sum()), "of", int(g.rl_order.notna().sum()), "| usgs id found in RouteLink gages:", int(g.gage_in_rl.fillna(False).astype(bool).sum()), "| gauge->reach midpoint median km", round(g.xy_off_km.median(), 2))
g["in_v30_retro"] = np.isin(g.feature_id, fz); g["in_v316_routelink"] = np.isin(g.feature_id, R.feature_id)
g[["usgs_id", "feature_id", "in_v30_retro", "in_v316_routelink", "stream_order", "rl_order", "order_changed", "rl_gage", "gage_in_rl", "xy_off_km"]].to_csv("data/phase0/s5_routelink_diff.csv", index=False)
print(g[~g.in_v316_routelink | g.order_changed | ~g.in_v30_retro][["usgs_id", "feature_id", "in_v30_retro", "in_v316_routelink", "stream_order", "rl_order"]].to_string())
# pilot-area reaches too
P = pd.read_parquet("data/phase0/nwm_flowlines_bbox.parquet"); pid = P.feature_id.astype("int64").values
print("pilot-bbox NOAA-service reaches", len(pid), "in v3.0 retro", int(np.isin(pid, fz).sum()), "in RouteLink v3.1.6", int(np.isin(pid, R.feature_id).sum()))
