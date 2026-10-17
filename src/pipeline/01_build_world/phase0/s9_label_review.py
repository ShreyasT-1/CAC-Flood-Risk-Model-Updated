"""Phase0 follow-up 5+6: (5) Florence storm reports within 1 km of a v2 crossing -> CSV for manual review (nothing auto-accepted);
(6) new label threshold: >= 30 labels with a crossing on the NAMED road within 500 m. Road-name match is automatic and conservative; the reviewer decides."""
import re, json, numpy as np, pandas as pd, geopandas as gpd
P = "data/phase0/"; U = 32617
L = gpd.read_parquet(P + "lsr_labels.parquet").to_crs(U)
L = L[(L.event == "florence") & L.in_pilot & (L.closure_word | L.typetext.isin(["FLASH FLOOD", "FLOOD"]))].copy()
X = gpd.read_parquet(P + "crossings_v2.parquet").to_crs(U); R = gpd.read_parquet(P + "osm_roads.parquet").to_crs(U)
ABBR = {"ROAD": "RD", "STREET": "ST", "DRIVE": "DR", "AVENUE": "AVE", "BOULEVARD": "BLVD", "HIGHWAY": "HWY", "LANE": "LN", "COURT": "CT", "CIRCLE": "CIR", "PARKWAY": "PKWY", "TRAIL": "TRL",
        "NORTHEAST": "NE", "NORTHWEST": "NW", "SOUTHEAST": "SE", "SOUTHWEST": "SW", "NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W"}
DIR = {"N", "S", "E", "W", "NE", "NW", "SE", "SW"}
def norm(s):
    t = [ABBR.get(w, w) for w in re.findall(r"[A-Z0-9]+", str(s).upper())]
    while t and t[-1] in DIR: t.pop()
    return " ".join(t)
def road_keys(c):
    """names/refs of the road a crossing sits on: seed record road_carried + any OSM road within 30 m (name and ref)."""
    names, refs = set(), set()
    for v in re.split(r"[,;/&]", str(c.road_carried)):
        v = v.strip()
        if v and v.lower() != "none" and v.lower() != "nan": refs.add(re.sub(r"[^A-Z0-9]", "", v.upper())); names.add(norm(v))
    for _, r in R.iloc[R.sindex.query(c.geometry.buffer(30), predicate="intersects")].iterrows():
        if pd.notna(r["name"]): names.add(norm(r["name"]))
        if pd.notna(r["ref"]):
            for v in re.split(r"[;,]", str(r["ref"])): refs.add(re.sub(r"[^A-Z0-9]", "", v.upper()))
    return {n for n in names if len(n) > 4}, {r for r in refs if len(r) >= 3}
K = {i: road_keys(c) for i, c in X.iterrows()}
def mentions(remark, k):
    txt = " " + norm(remark) + " "; raw = re.sub(r"[^A-Z0-9]", "", str(remark).upper())
    hit = [n for n in k[0] if (" " + n + " ") in txt] + [r for r in k[1] if re.search(r"(?<![0-9])" + re.escape(r.rstrip("SNEWBY") if re.match(r"^(US|NC|SR|I)\d+[A-Z]+$", r) else r) + r"(?![0-9])", raw)]
    return hit
rows = []
for k, r in L.iterrows():
    d = X.distance(r.geometry); near = d[d <= 1000].sort_values()
    if near.empty: continue
    match = [(i, dd, mentions(r.remark, K[i])) for i, dd in near.items()]; match = [m for m in match if m[2]]
    i0 = near.index[0]; c0 = X.loc[i0]
    best = min(match, key=lambda m: m[1]) if match else None
    rows.append(dict(report_id=r.name, time_utc=r.valid, county=r.county, source=r.source, lsr_type=r.typetext, lat=r.lat, lon=r.lon, remark=r.remark, auto_tier_from_phase0=r.tier,
                     nearest_crossing_id=c0.crossing_id, nearest_crossing_dist_m=round(float(near.iloc[0]), 0), nearest_crossing_set=c0.src, nearest_crossing_quality=c0.data_quality, nearest_crossing_stream=c0.feature_name, nearest_crossing_road=c0.road_carried,
                     road_name_match_nearest="yes" if mentions(r.remark, K[i0]) else "no",
                     named_road_crossing_id=None if best is None else X.loc[best[0]].crossing_id, named_road_crossing_dist_m=None if best is None else round(float(best[1]), 0),
                     named_road_crossing_set=None if best is None else X.loc[best[0]].src, named_road_crossing_quality=None if best is None else X.loc[best[0]].data_quality, named_road_matched_on=None if best is None else "; ".join(best[2]),
                     n_crossings_within_1km=int(len(near)), reviewer_decision="", reviewer_crossing_id="", reviewer_notes=""))
C = pd.DataFrame(rows).sort_values(["named_road_crossing_dist_m", "nearest_crossing_dist_m"], na_position="last"); C.to_csv(P + "florence_label_review.csv", index=False)
# threshold count (auto, unreviewed): Florence closure candidates (Phase-0 rule) with a crossing on the named road <= 500 m
cand = C[C.auto_tier_from_phase0.isin(["gold", "silver", "bronze"])]
def cnt(df, sets=None):
    d = df[df.named_road_crossing_dist_m <= 500]
    if sets: d = d[d.named_road_crossing_set.isin(sets)]
    return dict(reports=len(d), unique_crossings=int(d.named_road_crossing_id.nunique()))
st = dict(reports_in_csv=len(C), closure_candidates_in_csv=len(cand), within_500m_named_road_any_set=cnt(cand), within_500m_named_road_seed_only=cnt(cand, ["ncdot", "ncdot+nbi", "nbi_only"]),
          within_500m_named_road_good_fair_only=int(((cand.named_road_crossing_dist_m <= 500) & cand.named_road_crossing_quality.isin(["good", "fair"])).sum()),
          within_1km_named_road=int(cand.named_road_crossing_dist_m.notna().sum()), within_100m_named_road=cnt(cand.assign(named_road_crossing_dist_m=cand.named_road_crossing_dist_m.where(cand.named_road_crossing_dist_m <= 100))) if False else int((cand.named_road_crossing_dist_m <= 100).sum()),
          nearest_is_road_match=int((C.road_name_match_nearest == "yes").sum()), threshold=30)
st["threshold_met"] = st["within_500m_named_road_any_set"]["reports"] >= 30
json.dump(st, open(P + "s9_stats.json", "w"), indent=1, default=str); print(json.dumps(st, indent=1, default=str))
pd.set_option("display.width", 250, "display.max_colwidth", 70)
print(C[["time_utc", "remark", "nearest_crossing_dist_m", "road_name_match_nearest", "named_road_crossing_dist_m", "named_road_matched_on"]].head(12).to_string())
