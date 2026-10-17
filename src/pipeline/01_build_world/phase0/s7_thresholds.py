"""Phase0 follow-up 3: per-reach recurrence-flow thresholds from NOAA OWP static_nwm_flowlines (fields high_water_threshold, rf_{50,25,10,5,2}_0_17c, cfs); join to crossings v2."""
import json, requests, numpy as np, pandas as pd, geopandas as gpd
P = "data/phase0/"
reach = gpd.read_parquet(P + "nwm_flowlines_bbox.parquet"); ids = reach.feature_id.astype("int64").tolist()
U = "https://maps.water.noaa.gov/server/rest/services/reference/static_nwm_flowlines/FeatureServer/0/query"
F = "feature_id,strm_order,high_water_threshold,rf_50_0_17c,rf_25_0_17c,rf_10_0_17c,rf_5_0_17c,rf_2_0_17c"
rows = []
for i in range(0, len(ids), 400):
    r = requests.post(U, data=dict(where="feature_id IN (%s)" % ",".join("'%d'" % x for x in ids[i:i + 400]), outFields=F, returnGeometry="false", f="json", resultRecordCount=2000), timeout=120).json()
    rows += [f["attributes"] for f in r["features"]]
T = pd.DataFrame(rows).drop_duplicates("feature_id"); T["feature_id"] = T.feature_id.astype("int64")
T = T.rename(columns={"rf_2_0_17c": "q2_cfs", "rf_5_0_17c": "q5_cfs", "rf_10_0_17c": "q10_cfs", "rf_25_0_17c": "q25_cfs", "rf_50_0_17c": "q50_cfs", "high_water_threshold": "hwt_cfs"})
T.to_parquet(P + "reach_thresholds.parquet")
q = ["q2_cfs", "q5_cfs", "q10_cfs", "q25_cfs", "q50_cfs"]
print("reaches", len(T), "with any recurrence value", int(T[q].notna().any(axis=1).sum()), "all five", int(T[q].notna().all(axis=1).sum()), "hwt", int(T.hwt_cfs.notna().sum()))
print("zero/negative q2:", int((T.q2_cfs <= 0).sum()), "non-monotonic:", int((T[q].diff(axis=1).iloc[:, 1:] < 0).any(axis=1).sum()), "hwt==q2", int(np.isclose(T.hwt_cfs, T.q2_cfs).sum()), "hwt==q5", int(np.isclose(T.hwt_cfs, T.q5_cfs).sum()), "hwt==q10", int(np.isclose(T.hwt_cfs, T.q10_cfs).sum()))
print(T.groupby("strm_order")[q + ["hwt_cfs"]].agg(lambda s: s.notna().mean()).round(2)); print(T.groupby("strm_order").q2_cfs.median().round(1).to_dict())
X = gpd.read_parquet(P + "crossings_v2.parquet"); X["feature_id"] = X.feature_id.astype("Int64")
X = X.merge(T.drop(columns="strm_order").astype({"feature_id": "Int64"}), on="feature_id", how="left")
X.to_parquet(P + "crossings_v2.parquet"); X.to_file(P + "crossings_v2.geojson", driver="GeoJSON")
st = {}
for nm, d in (("seed", X[X.src != "osm_secondary"]), ("secondary", X[X.src == "osm_secondary"]), ("all", X)):
    m = d[d.feature_id.notna()]; o1 = m[m.strm_order == 1]
    st[nm] = dict(matched=len(m), with_q2=int(m.q2_cfs.notna().sum()), with_all5=int(m[q].notna().all(axis=1).sum()), with_hwt=int(m.hwt_cfs.notna().sum()), order1=len(o1), order1_with_q2=int(o1.q2_cfs.notna().sum()),
                  order1_with_all5=int(o1[q].notna().all(axis=1).sum()), order1_with_hwt=int(o1.hwt_cfs.notna().sum()), all_crossings=len(d))
print(json.dumps(st, indent=1)); json.dump(st, open(P + "s7_stats.json", "w"), indent=1)
