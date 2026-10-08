"""Step 2: map gauges -> NWM v3.0 feature_id.
Crosswalk source: the `gage_id` coordinate carried on noaa-nwm-retrospective-3-0-pds CONUS/zarr/chrtout.zarr, which is the
RouteLink `gages` field of the NWM v3.0 domain (NCAR/NOAA-OWP RouteLink_CONUS). Cross-checked against NWS NWPS `reachId`.
Output: data/derived/gauge_crosswalk.csv
"""
import numpy as np, pandas as pd, xarray as xr
from common import *

ds = xr.open_zarr("s3://noaa-nwm-retrospective-3-0-pds/CONUS/zarr/chrtout.zarr", storage_options={"anon": True})
rl = pd.DataFrame({"feature_id": ds.feature_id.values, "gage_id": ds.gage_id.values.astype(str),
                   "nwm_lat": ds.latitude.values, "nwm_lon": ds.longitude.values, "stream_order": ds.order.values})
rl["usgs_id"] = rl.gage_id.str.strip()
rl = rl[rl.usgs_id.str.fullmatch(r"\d{8,15}")].copy()  # drop blank / non-USGS gage ids
dup = rl.usgs_id.duplicated(keep=False)
print("routelink USGS gages:", len(rl), "| usgs ids mapped to >1 feature:", rl[dup].usgs_id.nunique())
rl = rl.sort_values("stream_order", ascending=False).drop_duplicates("usgs_id")  # ponytail: keep highest-order reach if duplicated

g = pd.read_csv(DER / "gauges_all.csv", dtype={"usgs_id": str})
g = g[(g.q_in_window | g.stage_in_window)]  # must have data in the study window
x = g.merge(rl, on="usgs_id", how="left")
x["crosswalk_source"] = np.where(x.feature_id.notna(), "routelink_gage_id", "")
# fallback for gauges absent from RouteLink gages: NWS NWPS reachId, only if that reach exists in the retrospective (distance checked below)
fb = x.feature_id.isna() & x.nwm_reach_id.notna()
cand = x.loc[fb, "nwm_reach_id"].astype("int64")
sub = ds[["latitude", "longitude", "order"]].sel(feature_id=cand.values[np.isin(cand.values, ds.feature_id.values)]).load()
pos = {f: i for i, f in enumerate(sub.feature_id.values)}
for i, f in cand.items():
    if f in pos:
        x.loc[i, ["feature_id", "nwm_lat", "nwm_lon", "stream_order", "crosswalk_source"]] = [
            f, float(sub.latitude[pos[f]]), float(sub.longitude[pos[f]]), int(sub.order[pos[f]]), "nwps_reachId"]
x["nws_reach_agrees"] = np.where(x.nwm_reach_id.isna(), np.nan, (x.nwm_reach_id.astype(float) == x.feature_id).astype(float))


def km(a, b, c, d):
    a, b, c, d = map(np.radians, (a, b, c, d))
    return 6371 * 2 * np.arcsin(np.sqrt(np.sin((c - a) / 2) ** 2 + np.cos(a) * np.cos(c) * np.sin((d - b) / 2) ** 2))


x["dist_km"] = km(x.lat, x.lon, x.nwm_lat, x.nwm_lon)
# ponytail: NWM reach points are mid-reach, so 5 km tolerance; no NWM drainage area in chrtout, so distance + NWPS reachId agreement
x["drainage_area_check"] = np.select(
    [x.feature_id.isna(), (x.dist_km > 5) | (x.nws_reach_agrees == 0)],
    ["no_routelink_match", "MISMATCH"], "ok")
# relaxed datum rule (applied here from data/derived/datum_check_events.csv): >=2 comparable crests, median |diff| <= 0.5 ft
ev = pd.read_csv(DER / "datum_check_events.csv", dtype={"usgs_id": str})
s = ev.groupby("usgs_id").diff_ft.agg(n="size", med="median", mx=lambda v: v.abs().max())
ok = s[(s.n >= 2) & (s.med.abs() <= 0.5)].index
x["datum_ok"] = x.usgs_id.isin(ok)
x["datum_reason"] = np.where(x.usgs_id.isin(ok), "", np.where(~x.usgs_id.isin(s.index), "no NWPS crest with USGS gage height",
                    np.where(x.usgs_id.map(s.n) < 2, "fewer than 2 comparable crest events", "median |USGS-NWS| > 0.5 ft")))
x["has_official_flood_stage"] = x.has_official_flood_stage & x.datum_ok
# keep gauges_all.csv consistent with the final datum rule (01 wrote a stricter first-pass flag); only gauges with a crest comparison change
_ga = pd.read_csv(DER / "gauges_all.csv", dtype={"usgs_id": str})
_ga = _ga.drop(columns=["n_events", "median_diff", "max_abs_diff"], errors="ignore").merge(
    s.rename(columns={"n": "n_events", "med": "median_diff", "mx": "max_abs_diff"}), left_on="usgs_id", right_index=True, how="left")
_ga["datum_ok"] = _ga.usgs_id.isin(ok) | (_ga.get("datum_ok_final", False) == True)
_ga["datum_reason"] = np.where(_ga.datum_ok, "", np.where(_ga.has_official_flood_stage & _ga.has_stage,
                      np.where(_ga.n_events.isna(), "no NWPS crest with USGS gage height", np.where(_ga.n_events < 2, "fewer than 2 comparable crest events",
                      "median |USGS-NWS| > 0.5 ft")), ""))
_ga.to_csv(DER / "gauges_all.csv", index=False)
x["flood_stage_ft"] = x.flood_stage_ft.where(x.has_official_flood_stage)
out = x[x.feature_id.notna()].copy()
out["feature_id"] = out.feature_id.astype("int64")
out = out.rename(columns={"nws_lid": "nws_lid"})[["usgs_id", "nws_lid", "feature_id", "has_official_flood_stage", "flood_stage_ft",
                                                  "lat", "lon", "in_pilot", "drainage_area_check", "dist_km", "crosswalk_source", "datum_reason", "stream_order",
                                                  "drainage_area", "county_name", "hydrologic_unit_code", "has_q", "has_stage",
                                                  "nws_reach_agrees"]]
out.to_csv(DER / "gauge_crosswalk.csv", index=False)
unmatched = x[x.feature_id.isna()][["usgs_id", "monitoring_location_name"]]
unmatched.to_csv(DER / "crosswalk_unmatched.csv", index=False)

print(f"candidate gauges (data in window): {len(x)}")
print(f"matched to feature_id: {len(out)} | unmatched: {len(unmatched)}")
print(out.drainage_area_check.value_counts().to_string()); print(out.crosswalk_source.value_counts().to_string())
print("datum exclusions among official-stage gauges:\n", x[x.nws_lid.notna() & x.flood_stage_ft.isna() & (x.datum_ok == False)].datum_reason.value_counts().to_string())
print("official flood stage (datum-ok):", int(out.has_official_flood_stage.sum()), "| in_pilot:", int(out.in_pilot.sum()),
      "| pilot with official stage:", int((out.in_pilot & out.has_official_flood_stage).sum()))
print("NWPS reachId disagrees with RouteLink:", int((out.nws_reach_agrees == 0).sum()), "of", int(out.nws_reach_agrees.notna().sum()))
print(out[out.drainage_area_check == "MISMATCH"][["usgs_id", "feature_id", "dist_km", "nws_reach_agrees"]].to_string())
