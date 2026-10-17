"""Phase0 S2: NCDOT StructuresPoint (Q1 2026 gdb) + NBI 2025 NC -> pilot counties; link NBI<->NCDOT by structure number; match to crossings."""
import json, numpy as np, pandas as pd, geopandas as gpd, re
P = "data/phase0/"; U = 32617
cs = gpd.read_file(P + "counties.geojson")
X = gpd.read_parquet(P + "crossings.parquet").to_crs(U)
s = gpd.read_file("zip://" + P + "raw/NCDOTStructureLocationsPoint.gdb.zip")
print(s.COUNTY.unique()[:5], len(s))
s = s[s.COUNTY.str.upper().isin(["NEW HANOVER", "BRUNSWICK", "PENDER"])].copy()
s = gpd.GeoDataFrame(s, geometry=gpd.points_from_xy(s.LONG_DD, s.LAT_DD), crs=4326)  # lat/lon cols (not the 2264 geom) so it matches NBI-style coordinates; check below
g2264 = s.geometry  # placeholder
s = gpd.read_file("zip://" + P + "raw/NCDOTStructureLocationsPoint.gdb.zip"); s = s[s.COUNTY.str.upper().isin(["NEW HANOVER", "BRUNSWICK", "PENDER"])].to_crs(U)
s["brdg_key"] = s.BRDG_NBR.astype(str).str.strip().str.lstrip("0")
# NBI
n = pd.read_csv(P + "raw/NBI_NC25.txt", dtype=str, quotechar="'", encoding="latin1", low_memory=False)
n = n[n.COUNTY_CODE_003.isin(["019", "129", "141"])].copy()
def dms(v, lon):
    v = str(v).strip()
    if not v or v == "nan" or not v.isdigit(): return np.nan
    d, rest = (int(v[:3]), v[3:]) if lon else (int(v[:2]), v[2:])
    return d + int(rest[:2]) / 60 + int(rest[2:]) / 100 / 3600
n["lat"] = n.LAT_016.map(lambda v: dms(v, False)); n["lon"] = -n.LONG_017.map(lambda v: dms(v, True))
n["brdg_key"] = n.STRUCTURE_NUMBER_008.str.strip().str.lstrip("0")
n = gpd.GeoDataFrame(n, geometry=gpd.points_from_xy(n.lon, n.lat), crs=4326).to_crs(U)
n = n[n.geometry.notna() & ~n.geometry.is_empty]
# NBI <-> NCDOT link: structure numbers do NOT share a key (NCDOT '090001' vs NBI '190001'; BSIP '0100001'), so link spatially (<=50 m) and report road-name agreement.
j = gpd.sjoin_nearest(n[["geometry", "FACILITY_CARRIED_007"]], s[["geometry", "F_CARRIED", "BRDG_NBR"]], how="left", max_distance=50, distance_col="ld")
j = j[~j.index.duplicated()]
rt = lambda x: re.sub(r"[^a-z0-9]", "", str(x).lower().replace(" ", ""))[:6]
n["ncdot_link"] = j.BRDG_NBR.reindex(n.index).values; n["link_dist_m"] = j.ld.reindex(n.index).values
n["link_road_agree"] = [rt(a) == rt(b) if pd.notna(c) else np.nan for a, b, c in zip(n.FACILITY_CARRIED_007, j.F_CARRIED.reindex(n.index), n.ncdot_link)]
lk = n.ncdot_link.notna(); sk = s.BRDG_NBR.isin(n.ncdot_link.dropna()); ld = n.link_dist_m.dropna()
# match to crossings: nearest crossing within 100 m (structure->crossing), per source
def nearest(src, tag):
    j = gpd.sjoin_nearest(src[["geometry"]], X[["crossing_id", "geometry"]], how="left", max_distance=250, distance_col="d")
    j = j[~j.index.duplicated()]; return j.crossing_id.reindex(src.index).values, j.d.reindex(src.index).values
s["crossing_id"], s["match_dist_m"] = nearest(s, "ncdot"); n["crossing_id"], n["match_dist_m"] = nearest(n, "nbi")
# name agreement (loose token overlap)
def toks(x): return set(re.findall(r"[a-z0-9]+", str(x).lower())) - {"creek", "river", "rd", "road", "ditch", "branch", "swamp", "canal", "run", "nan", "none", "sr", "us", "nc", "of", "the", "to"}
xi = X.set_index("crossing_id")
def agree(row, a, b): return bool(toks(row[a]) & toks(xi.stream_name.get(row.crossing_id)) ) if pd.notna(row.crossing_id) else np.nan
s["name_agree_stream"] = s.apply(lambda r: agree(r, "FTR_INTRSC", None), axis=1)
n["name_agree_stream"] = n.apply(lambda r: agree(r, "FEATURES_DESC_006A", None), axis=1)
# stream-crossing structures: NCDOT FTR_INTRSC looks like a waterway or structure is culvert/pipe type. Heuristic keyword list (documented).
WORDS = re.compile(r"creek|river|branch|swamp|canal|ditch|run\b|bay|sound|inlet|brook|stream|slough|pond|lake|waterway|cr\b|br\b|channel|marsh|gut|bayou|drain", re.I)
s["ftr_waterway_like"] = s.FTR_INTRSC.fillna("").str.contains(WORDS); n["ftr_waterway_like"] = n.FEATURES_DESC_006A.fillna("").str.contains(WORDS)
Xs = X.copy()
for lbl, d in (("ncdot", s), ("nbi", n)):
    for t in (50, 100):
        ids = d[d.match_dist_m <= t].crossing_id.dropna().unique(); Xs[f"has_{lbl}_{t}"] = Xs.crossing_id.isin(ids)
Xs["has_any_100"] = Xs.has_ncdot_100 | Xs.has_nbi_100; Xs["has_any_50"] = Xs.has_ncdot_50 | Xs.has_nbi_50
# field fill rates for NBI records (sentinels: nan/blank, 0 for clearance/length, 99.99 for 'no restriction')
def fill(col, bad=()):
    v = n[col].astype(str).str.strip(); ok = n[col].notna() & ~v.isin(["", "nan", *bad]); return float(ok.mean())
F = {"year_built_027": fill("YEAR_BUILT_027", ["0", "0000"]), "structure_len_049": fill("STRUCTURE_LEN_MT_049", ["0", "0.0"]), "max_span_048": fill("MAX_SPAN_LEN_MT_048", ["0", "0.0"]),
     "deck_width_052": fill("DECK_WIDTH_MT_052", ["0", "0.0"]), "min_vert_clr_010 (traffic, 99.99=n/a)": fill("MIN_VERT_CLR_010", ["99.99", "0", "0.0"]),
     "vert_clr_over_053 (99.99=n/a)": fill("VERT_CLR_OVER_MT_053", ["99.99", "0", "0.0"]), "vert_clr_under_054b": fill("VERT_CLR_UND_054B", ["0", "0.0"]),
     "waterway_eval_071": fill("WATERWAY_EVAL_071", ["N"]), "channel_cond_061": fill("CHANNEL_COND_061", ["N"]), "scour_critical_113": fill("SCOUR_CRITICAL_113", ["N"]), "feature_name_006a": fill("FEATURES_DESC_006A")}
ncdot_cols = {c: float(s[c].notna().mean()) for c in s.columns if c not in ("geometry",)}
water_s = s[s.ftr_waterway_like]; water_n = n[n.ftr_waterway_like]
st = dict(ncdot_total=len(s), ncdot_types=s.BRDG_TYP_NM.value_counts().to_dict(), nbi_total=len(n), nbi_ncdot_linked=int(lk.sum()), ncdot_linked=int(sk.sum()), link_dist_median_m=float(ld.median()), link_dist_p95=float(ld.quantile(.95)), link_road_agree=float(n.link_road_agree.dropna().astype(float).mean()),
          ncdot_matched100=float((s.match_dist_m <= 100).mean()), ncdot_matched50=float((s.match_dist_m <= 50).mean()), nbi_matched100=float((n.match_dist_m <= 100).mean()), nbi_matched50=float((n.match_dist_m <= 50).mean()),
          ncdot_waterway_like=len(water_s), ncdot_waterway_matched100=float((water_s.match_dist_m <= 100).mean()), nbi_waterway_like=len(water_n), nbi_waterway_matched100=float((water_n.match_dist_m <= 100).mean()),
          name_agree_ncdot_among_matched100=float(s[s.match_dist_m <= 100].name_agree_stream.astype(float).mean()), name_agree_nbi_among_matched100=float(n[n.match_dist_m <= 100].name_agree_stream.astype(float).mean()),
          crossings=len(Xs), xing_with_ncdot_100=float(Xs.has_ncdot_100.mean()), xing_with_nbi_100=float(Xs.has_nbi_100.mean()), xing_with_any_100=float(Xs.has_any_100.mean()), xing_with_any_50=float(Xs.has_any_50.mean()),
          xing_any_100_by_class=Xs.groupby("road_class").has_any_100.mean().round(3).to_dict(), xing_any_100_by_source=Xs.groupby("source").has_any_100.mean().round(3).to_dict(),
          xing_any_100_by_matched_reach=Xs.groupby(Xs.match_dist_m <= 100).has_any_100.mean().round(3).to_dict(),
          nbi_field_fill=F, ncdot_field_fill={k: round(v, 3) for k, v in ncdot_cols.items() if k not in ("geometry",)})
json.dump(st, open(P + "s2_stats.json", "w"), indent=1, default=str); print(json.dumps(st, indent=1, default=str))
s.to_crs(4326).to_parquet(P + "ncdot_structures_pilot.parquet"); n.to_crs(4326).to_parquet(P + "nbi_pilot.parquet"); Xs.to_crs(4326).to_parquet(P + "crossings_struct.parquet")
