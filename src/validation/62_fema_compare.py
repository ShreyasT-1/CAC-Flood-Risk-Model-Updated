"""T4: assign the FEMA NFHL flood-hazard zone (data/phase2/fema_nfhl.parquet) to every crossing and every Census block origin (point-in-polygon; highest-hazard polygon wins where polygons overlap),
then compare with the Florence hindcast scenario level RL10 (peak NWM v3.0 retrospective flow above the reach's 10-year recurrence flow, any hour 2018-09-13..2018-11-06).
FEMA zones are a COMPARISON layer, not ground truth and not a model input. 'unmapped' = no NFHL polygon at the point; it does not mean low hazard.
Usage (repo root): python src/validation/62_fema_compare.py"""
import numpy as np, pandas as pd, geopandas as gpd
O = "data/phase2/"; F = gpd.read_parquet(O + "fema_nfhl.parquet")
def klass(z, st, sfha):
    st = st.upper() if isinstance(st, str) else ""
    if z in ("VE", "V"): return "SFHA: V/VE (coastal high hazard)"
    if z in ("A", "AE", "AH", "AO", "A99", "AR") or sfha == "T": return "SFHA: A/AE/AH/AO"
    if z == "X" and "0.2" in st: return "X shaded (0.2% annual chance)"
    if z == "X" and "LEVEE" in st: return "X protected by levee"
    if z == "X": return "X minimal"
    if z == "D": return "D (undetermined)"
    return "other: " + str(z)
F["zone_class"] = [klass(z, s, h) for z, s, h in zip(F.fld_zone, F.zone_subty, F.sfha_tf)]
RANK = {"SFHA: V/VE (coastal high hazard)": 0, "SFHA: A/AE/AH/AO": 1, "X protected by levee": 2, "X shaded (0.2% annual chance)": 3, "D (undetermined)": 4, "X minimal": 5}; F["rk"] = F.zone_class.map(RANK).fillna(6)
def assign(P):   # P: GeoDataFrame of points in 4326 with a unique 'key'
    j = gpd.sjoin(P[["key", "geometry"]], F[["fld_zone", "zone_subty", "sfha_tf", "zone_class", "rk", "static_bfe", "geometry"]], how="left", predicate="within").sort_values(["key", "rk"])
    n = j.groupby("key").fld_zone.apply(lambda s: s.notna().sum()); j = j.drop_duplicates("key").set_index("key")
    out = pd.DataFrame(dict(fema_zone=j.fld_zone.fillna("UNMAPPED"), fema_zone_subty=j.zone_subty, fema_zone_class=j.zone_class.fillna("unmapped (no NFHL polygon)"), fema_sfha=j.sfha_tf, fema_static_bfe=j.static_bfe.where(j.static_bfe > -9000), fema_n_overlapping_polygons=n.reindex(j.index)))
    return out
V = pd.read_parquet("data/phase0/crossings_v2.parquet"); P = gpd.GeoDataFrame({"key": V.crossing_id.values}, geometry=gpd.points_from_xy(V.lon, V.lat), crs=4326); A = assign(P); A.index.name = "id"; A.to_csv(O + "fema_assign_crossings.csv")
org = pd.read_parquet("data/phase1b/origins_snapped.parquet"); Pb = gpd.GeoDataFrame({"key": org.geoid20.values}, geometry=gpd.points_from_xy(org.lon, org.lat), crs=4326); B = assign(Pb); B.index.name = "geoid20"; B.to_csv(O + "fema_assign_blocks.csv")
print("crossings", len(A), A.fema_zone_class.value_counts().to_dict()); print("blocks", len(B), "people by class:", org.assign(c=B.fema_zone_class.reindex(org.geoid20).values).groupby("c").pop20.sum().to_dict())
# ---- Florence hindcast RL10 vs FEMA ----
fl = pd.read_parquet("data/phase1b/flows_hindcast.parquet") * 35.3146667; pk = fl.max()
V = V.merge(A, left_on="crossing_id", right_index=True); V["peak_cfs"] = V.feature_id.map(lambda f: pk.get(str(int(f))) if pd.notna(f) else np.nan)
V["assessed"] = V.hazard_threshold_ok.fillna(False) & V.peak_cfs.notna(); V["above_rl10"] = V.peak_cfs > V.q10_cfs; V["above_rl2"] = V.peak_cfs > V.q2_cfs
seed = V.src != "osm_secondary"; sets = {"seed (250 hazard-ready structure-seeded)": seed, "seed_reliable": seed & V.crest_elev_reliable.fillna(False), "seed_plus_osm_secondary (sensitivity)": pd.Series(True, index=V.index)}
rows = []
for sn, m in sets.items():
    D = V[m & V.assessed]
    for z, g in list(D.groupby("fema_zone_class")) + [("ALL", D)]:
        rows.append(dict(crossing_set=sn, fema_zone_class=z, n_assessed=len(g), n_above_rl10=int(g.above_rl10.sum()), share_above_rl10=round(float(g.above_rl10.mean()), 3), n_above_rl2=int(g.above_rl2.sum()), share_above_rl2=round(float(g.above_rl2.mean()), 3)))
    sf = D.fema_zone_class.str.startswith("SFHA"); ab = D.above_rl10
    rows.append(dict(crossing_set=sn, fema_zone_class="[SFHA yes/no x above RL10] among above: share in SFHA", n_assessed=int(ab.sum()), n_above_rl10=int((ab & sf).sum()), share_above_rl10=round(float(sf[ab].mean()), 3) if ab.any() else np.nan))
    rows.append(dict(crossing_set=sn, fema_zone_class="[..] among NOT above: share in SFHA", n_assessed=int((~ab).sum()), n_above_rl10=int((~ab & sf).sum()), share_above_rl10=round(float(sf[~ab].mean()), 3) if (~ab).any() else np.nan))
T = pd.DataFrame(rows); T.to_csv(O + "fema_vs_rl10_florence_hindcast.csv", index=False); pd.set_option("display.width", 220, "display.max_colwidth", 70); print(T.to_string(index=False))
V[["crossing_id", "src", "fema_zone", "fema_zone_class", "peak_cfs", "q10_cfs", "above_rl10", "assessed"]].to_csv(O + "fema_vs_rl10_per_crossing.csv", index=False)
