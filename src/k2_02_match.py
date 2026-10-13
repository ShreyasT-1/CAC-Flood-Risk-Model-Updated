"""Kill Test 2, Step 2: rule-based matching of kept closures to crossings. No manual picking.
R = 1.5 km (pre-registered). A closure's candidate crossings = crossings within R of the report point whose road name or ref matches ANY road
identifier parsed from the remark (the main road and any named cross-street, since the report point is at/near their intersection).
status: matched | no_road_match (no OSM way whose name/ref matches a parsed road lies within R of the point at all)
        | no_crossing_within_R (a matching road is within R, but it crosses no NWM reach within R).
Output: data/derived/closure_matches.csv (one row per kept closure), data/derived/closure_match_candidates.csv (long: closure x crossing)
"""
import re
import numpy as np, pandas as pd, geopandas as gpd
from common import *

R = 1500.0
DIRW = {"NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W", "NORTHEAST": "NE", "NORTHWEST": "NW", "SOUTHEAST": "SE", "SOUTHWEST": "SW"}
ABBR = {"ROAD": "RD", "STREET": "ST", "AVENUE": "AVE", "DRIVE": "DR", "LANE": "LN", "BOULEVARD": "BLVD", "HIGHWAY": "HWY", "CUTTOFF": "CUTOFF",
        "PLACE": "PL", "CIRCLE": "CIR", "TRAIL": "TRL", "PARKWAY": "PKWY", "MOUNT": "MT", "SAINT": "ST"}
DIRS = {"N", "S", "E", "W", "NE", "NW", "SE", "SW"}
ROUTE = re.compile(r"\b(I|US|NC|SR)[- ]?(\d{1,4})\b")


def name_key(s):
    """Normalised road-name key: upper, abbreviations unified, leading/trailing compass words dropped."""
    if not isinstance(s, str):
        return None
    toks = [ABBR.get(DIRW.get(t, t), DIRW.get(t, t)) for t in re.findall(r"[A-Z0-9']+", s.upper())]
    while toks and toks[-1] in DIRS:
        toks.pop()
    while len(toks) > 1 and toks[0] in DIRS:
        toks.pop(0)
    return " ".join(toks) or None


def ref_keys(s):
    return {f"{a} {n}" for part in str(s).upper().split(";") for a, n in ROUTE.findall(part)} if isinstance(s, str) else set()


def keys_of_road(name, ref):
    k = ref_keys(ref)
    nk = name_key(name)
    if nk:
        k.add(nk)
        k |= ref_keys(name)  # names like "US 17 Business" carry the route too
    return k


def parsed_keys(roads_str):
    out = set()
    for r in str(roads_str).split(" | "):
        if r and r != "nan":
            out |= ref_keys(r) or {name_key(r)}
    return {k for k in out if k}


def main():
    cl = pd.read_csv(DER / "florence_closures.csv")
    cl = cl[cl.status == "keep"].copy()
    cr = gpd.read_parquet(DER / "crossings.parquet").to_crs(32617)
    cr["keys"] = [keys_of_road(n, r) for n, r in zip(cr.name, cr.ref)]
    rd = pd.concat([gpd.read_parquet(f) for f in sorted(RAW.glob("osm_roads_*.parquet"))], ignore_index=True)
    rd = gpd.GeoDataFrame(rd.drop_duplicates("osm_id"), crs=4326).to_crs(32617)
    rd["keys"] = [keys_of_road(n, r) for n, r in zip(rd.name, rd.ref)]
    pts = gpd.GeoSeries(gpd.points_from_xy(cl.lon, cl.lat), crs=4326).to_crs(32617).values
    csi, rsi = cr.sindex, rd.sindex

    rows, long = [], []
    for (i, c), p in zip(cl.iterrows(), pts):
        want = parsed_keys(c.roads)
        near_cr = cr.iloc[csi.query(p.buffer(R), predicate="intersects")]
        near_cr = near_cr[[bool(k & want) for k in near_cr.keys]]
        near_cr = near_cr.assign(dist_m=near_cr.geometry.distance(p)).query("dist_m <= @R").sort_values("dist_m")
        if len(near_cr):
            status = "matched"
        else:
            near_rd = rd.iloc[rsi.query(p.buffer(R), predicate="intersects")]
            near_rd = near_rd[[bool(k & want) for k in near_rd.keys]]
            status = "no_crossing_within_R" if len(near_rd) else "no_road_match"
        for x in near_cr.itertuples():
            long.append({"report_id": c.report_id, "crossing_id": x.crossing_id, "dist_m": round(x.dist_m), "osm_name": x.name, "osm_ref": x.ref,
                         "road_class": x.road_class, "bridge": x.bridge, "feature_id": x.feature_id, "stream_order": x.stream_order})
        rows.append({"report_id": c.report_id, "time_utc": c.time_utc, "county": c.county, "strict": c.strict, "lat": c.lat, "lon": c.lon,
                     "parsed_roads": c.roads, "status": status, "n_candidates": len(near_cr),
                     "n_candidate_reaches": near_cr.feature_id.nunique(), "road_classes": "|".join(sorted(set(near_cr.road_class))),
                     "candidate_crossing_ids": " ".join(map(str, near_cr.crossing_id)), "remark": c.remark})
    m = pd.DataFrame(rows)
    m.to_csv(DER / "closure_matches.csv", index=False)
    L = pd.DataFrame(long)
    L.to_csv(DER / "closure_match_candidates.csv", index=False)

    print(f"R = {R/1000} km | kept closures: {len(m)} (strict {int(m.strict.sum())}) | crossings available: {len(cr)}")
    for lab, d in (("BROAD", m), ("STRICT", m[m.strict])):
        vc = d.status.value_counts()
        print(f"{lab}: n={len(d)} | matched={vc.get('matched', 0)} | no_crossing_within_R={vc.get('no_crossing_within_R', 0)} | no_road_match={vc.get('no_road_match', 0)}"
              f" | share unscored (no crossing or road) = {(len(d) - vc.get('matched', 0)) / len(d):.1%}"
              f" | share no_crossing_within_R = {vc.get('no_crossing_within_R', 0) / len(d):.1%}")
    print("\nmatched by county:", m[m.status == 'matched'].county.value_counts().to_dict())
    s = m[m.status == "matched"].sample(min(15, int((m.status == "matched").sum())), random_state=0)
    print("\n15 RANDOM MATCHED EXAMPLES")
    for r in s.itertuples():
        cand = L[L.report_id == r.report_id].head(4)
        cs = "; ".join(f"[{x.crossing_id}] {x.osm_name or ''}/{x.osm_ref or ''} {x.road_class} d={x.dist_m}m reach={x.feature_id} so={x.stream_order}{' BRIDGE' if str(x.bridge) not in ('nan', 'None', 'no') else ''}"
                       for x in cand.itertuples())
        print(f"\n#{r.report_id} {r.county[:3]} {'STRICT' if r.strict else 'broad'} ({r.n_candidates} cand / {r.n_candidate_reaches} reaches)\n  remark: {r.remark[:170]}\n  parsed: {r.parsed_roads}\n  candidates: {cs}")


if __name__ == "__main__":
    main()
