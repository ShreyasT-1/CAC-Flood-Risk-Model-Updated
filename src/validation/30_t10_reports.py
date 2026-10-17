"""Phase 2 / T10A: NC flood-closure road reports 2016-2022 (IEM LSR) -> candidate reports with a seed structure crossing on the named road within 500 m. Definitions: docs/validation_protocol.md (fixed before running).
Outputs data/phase2/t10/: lsr_nc_raw.parquet, structures_nc.parquet, osm_roads_nc.parquet (cache), report_candidates.csv (REVIEW FILE, nothing auto-accepted), report_crossings.parquet (reaches + q2..q50).
Usage (repo root): python src/30_t10_reports.py"""
import os, re, json, time, requests, numpy as np, pandas as pd, geopandas as gpd
O = "data/phase2/t10/"; os.makedirs(O, exist_ok=True); U = 32119   # NC State Plane (m)

# ---- 1. LSR pull, NC, 2016-2022 ----
if not os.path.exists(O + "lsr_nc_raw.parquet"):
    out = []
    for y in range(2016, 2023):
        r = requests.get("https://mesonet.agron.iastate.edu/geojson/lsr.geojson", params=dict(west=-84.4, east=-75.3, south=33.7, north=36.7, sts=f"{y}-01-01T00:00Z", ets=f"{y}-12-31T23:59Z"), timeout=300)
        r.raise_for_status(); g = gpd.GeoDataFrame.from_features(r.json()["features"], crs=4326); print(y, len(g), flush=True); out.append(g); time.sleep(1)
    pd.concat(out, ignore_index=True).to_parquet(O + "lsr_nc_raw.parquet")
L = gpd.read_parquet(O + "lsr_nc_raw.parquet"); n0 = len(L)
L = L[L.state == "NC"].drop_duplicates(["valid", "remark", "lat", "lon"]).reset_index(drop=True); n_nc = len(L)
CLOSE = re.compile(r"CLOSED|CLOSURE|IMPASS|WASHED ?OUT|BARRICAD|NOT PASSABLE|BLOCKED|UNDER WATER|CUT OFF|SUBMERGED")
ROADTXT = re.compile(r"\bROAD\b|\bRD\b|\bDR\b|\bDRIVE\b|\bST\b|\bSTREET\b|\bHWY\b|\bHIGHWAY\b|\bBLVD\b|\bAVE\b|\bBRIDGE\b|\bUS-?\d+|\bNC-?\d+|\bSR-?\d+|\bI-\d+|\bLANE\b|\bLN\b")
FLOODCAUSE = re.compile(r"FLOOD|WATER|WASH|INUNDAT|RISING|RUSHING|SUBMERG"); TREE = re.compile(r"TREE|POWER ?LINE|DOWNED LINE|LINES DOWN|\bPOLE")
SURGE = re.compile(r"SURGE|TIDE|TIDAL|OVERWASH"); OTHERST = re.compile(r"\b(SC|VA|TN|GA)\b|SOUTH CAROLINA|VIRGINIA|TENNESSEE|GEORGIA")
t = L.remark.fillna("").str.upper()
L["closure_word"] = t.map(lambda s: bool(CLOSE.search(s))); L["road_word"] = t.map(lambda s: bool(ROADTXT.search(s)))
L["flood_cause"] = t.map(lambda s: bool(FLOODCAUSE.search(s))) | L.typetext.isin(["FLASH FLOOD", "FLOOD"])
L["tree_wording"] = t.map(lambda s: bool(TREE.search(s))); L["surge_wording"] = t.map(lambda s: bool(SURGE.search(s))); L["other_state"] = t.map(lambda s: bool(OTHERST.search(s)))
L["candidate"] = L.closure_word & L.road_word & L.flood_cause & ~L.tree_wording & ~L.surge_wording & ~L.other_state
L["flood_type"] = L.typetext.isin(["FLASH FLOOD", "FLOOD", "HEAVY RAIN", "TROPICAL STORM", "HURRICANE"])
C = L[L.candidate & L.flood_type].copy(); print("LSR rows", n0, "NC dedup", n_nc, "candidates (closure+road+flood, no tree/surge)", len(C), C.typetext.value_counts().to_dict())

# ---- 2. statewide structures (NCDOT + NBI), waterway-like, merged ----
WATER = re.compile(r"creek|river|branch|swamp|canal|ditch|run\b|bay|sound|inlet|brook|stream|slough|pond|lake|waterway|\bcr\b|\bbr\b|channel|marsh|gut|bayou|drain|trib|\bcrk|\bicw\b|intracoastal|w/w|\bcut\b|\bhole\b|sauce pan|cape fear r\b", re.I)
NOT = re.compile(r"wildlife|wet ?lands|\bR/?R\b|railroad|rail road|parking", re.I); wlike = lambda x: bool(WATER.search(str(x))) and not NOT.search(str(x))
if not os.path.exists(O + "structures_nc.parquet"):
    s = gpd.read_file("zip://data/phase0/raw/NCDOTStructureLocationsPoint.gdb.zip"); s = s[s.BRDG_TYP_NM.isin(["BRIDGE", "CULVERT", "PIPE"]) & s.FTR_INTRSC.map(wlike)]
    s = gpd.GeoDataFrame(s, geometry=gpd.points_from_xy(s.LONG_DD, s.LAT_DD), crs=4326).dropna(subset=["LONG_DD", "LAT_DD"])
    n = pd.read_csv("data/phase0/raw/NBI_NC25.txt", dtype=str, quotechar="'", encoding="latin1", low_memory=False)
    def dms(v, lon):
        v = str(v).strip()
        if not v.isdigit(): return np.nan
        d, rest = (int(v[:3]), v[3:]) if lon else (int(v[:2]), v[2:]); return d + int(rest[:2]) / 60 + int(rest[2:]) / 100 / 3600
    n["lat"] = n.LAT_016.map(lambda v: dms(v, False)); n["lon"] = -n.LONG_017.map(lambda v: dms(v, True)); n = n[n.FEATURES_DESC_006A.map(wlike)].dropna(subset=["lat", "lon"])
    n = gpd.GeoDataFrame(n, geometry=gpd.points_from_xy(n.lon, n.lat), crs=4326)
    sj = s.to_crs(U); nj = n.to_crs(U); j = gpd.sjoin_nearest(nj[["geometry"]], sj[["geometry"]], how="left", max_distance=50); linked = set(j.dropna(subset=["index_right"]).index)   # NBI records within 50 m of an NCDOT seed structure
    rows = [dict(src="ncdot", feature_name=str(r.FTR_INTRSC).strip(), road_carried=str(r.F_CARRIED).strip(), county=r.COUNTY, structure_type=r.BRDG_TYP_NM, nbi_len_m=np.nan, geometry=r.geometry) for r in s.itertuples()]
    rows += [dict(src="nbi_only", feature_name=str(r.FEATURES_DESC_006A).strip(), road_carried=str(r.FACILITY_CARRIED_007).strip(), county=r.COUNTY_CODE_003, structure_type="BRIDGE(NBI)", nbi_len_m=pd.to_numeric(r.STRUCTURE_LEN_MT_049, errors="coerce"), geometry=r.geometry) for i, r in zip(n.index, n.itertuples()) if i not in linked]
    S = gpd.GeoDataFrame(rows, crs=4326); S.insert(0, "crossing_id", [f"T10_{i:05d}" for i in range(len(S))]); S.to_parquet(O + "structures_nc.parquet")
S = gpd.read_parquet(O + "structures_nc.parquet"); print("statewide waterway-like structures", len(S), S.src.value_counts().to_dict())

# ---- 3. OSM road names (statewide, cached) ----
if not os.path.exists(O + "osm_roads_nc.parquet"):
    import osmium; from shapely.geometry import LineString
    KEEP = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link"}; rr = []
    for o in osmium.FileProcessor("data/raw/nc.osm.pbf").with_locations().with_filter(osmium.filter.KeyFilter("highway")):
        if not o.is_way() or o.tags["highway"] not in KEEP or not (o.tags.get("name") or o.tags.get("ref")): continue
        try: pts = [(x.lon, x.lat) for x in o.nodes]
        except Exception: continue
        if len(pts) > 1: rr.append(dict(osm_id=o.id, name=o.tags.get("name"), ref=o.tags.get("ref"), geometry=LineString(pts)))
    gpd.GeoDataFrame(rr, crs=4326).to_parquet(O + "osm_roads_nc.parquet")
R = gpd.read_parquet(O + "osm_roads_nc.parquet").to_crs(U); print("OSM named roads", len(R))

ABBR = {"ROAD": "RD", "STREET": "ST", "DRIVE": "DR", "AVENUE": "AVE", "BOULEVARD": "BLVD", "HIGHWAY": "HWY", "LANE": "LN", "COURT": "CT", "CIRCLE": "CIR", "PARKWAY": "PKWY", "TRAIL": "TRL", "NORTHEAST": "NE", "NORTHWEST": "NW", "SOUTHEAST": "SE", "SOUTHWEST": "SW", "NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W"}
DIR = {"N", "S", "E", "W", "NE", "NW", "SE", "SW"}
def norm(s):
    tk = [ABBR.get(w, w) for w in re.findall(r"[A-Z0-9]+", str(s).upper())]
    while tk and tk[-1] in DIR: tk.pop()
    return " ".join(tk)
def road_keys(c):   # names/refs of the road a structure carries: its record + any OSM road within 30 m (same as phase-0 s9)
    names, refs = set(), set()
    for v in re.split(r"[,;/&]", str(c.road_carried)):
        v = v.strip()
        if v and v.lower() not in ("none", "nan"): refs.add(re.sub(r"[^A-Z0-9]", "", v.upper())); names.add(norm(v))
    for _, r in R.iloc[R.sindex.query(c.geometry.buffer(30), predicate="intersects")].iterrows():
        if pd.notna(r["name"]): names.add(norm(r["name"]))
        if pd.notna(r["ref"]):
            for v in re.split(r"[;,]", str(r["ref"])): refs.add(re.sub(r"[^A-Z0-9]", "", v.upper()))
    return {x for x in names if len(x) > 4}, {x for x in refs if len(x) >= 3}
def mentions(remark, k):
    txt = " " + norm(remark) + " "; raw = re.sub(r"[^A-Z0-9]", "", str(remark).upper())
    return [x for x in k[0] if (" " + x + " ") in txt] + [r for r in k[1] if re.search(r"(?<![0-9])" + re.escape(r.rstrip("SNEWBY") if re.match(r"^(US|NC|SR|I)\d+[A-Z]+$", r) else r) + r"(?![0-9])", raw)]
SPLIT = re.compile(r"\b(NEAR|AT|BETWEEN|FROM|INTERSECTION|NORTH OF|SOUTH OF|EAST OF|WEST OF|AND|ON|OFF|BY)\b|[&/]")
def in_subject(remark, hits):   # suggestion only: is the matched road named BEFORE the first locator word (the closed road) rather than as a landmark?
    subj = SPLIT.split(str(remark).upper())[0]; ns = " " + norm(subj) + " "; raw = re.sub(r"[^A-Z0-9]", "", subj)
    return any((" " + h + " ") in ns or (re.sub(r"[^A-Z0-9]", "", h) in raw and len(h) >= 3) for h in hits)

# ---- 4. match reports -> structures on the named road within 500 m ----
Cp = C.to_crs(U); Sp = S.to_crs(U); rows = []
for k, r in Cp.iterrows():
    near = Sp.iloc[Sp.sindex.query(r.geometry.buffer(1000), predicate="intersects")]
    best = None
    for i, c in near.iterrows():
        d = float(c.geometry.distance(r.geometry)); h = mentions(r.remark, road_keys(c))
        if h and (best is None or d < best[1]): best = (c.crossing_id, d, h)
    rows.append(dict(report_id=k, time_utc=r.valid, county=r.county, source=r.source, lsr_type=r.typetext, lat=r.lat, lon=r.lon, remark=r.remark, n_structures_within_1km=len(near),
                     crossing_id=None if best is None else best[0], crossing_dist_m=None if best is None else round(best[1]), matched_on=None if best is None else "; ".join(best[2]),
                     matched_in_subject=None if best is None else in_subject(r.remark, best[2])))
M = pd.DataFrame(rows); M = M.merge(S[["crossing_id", "src", "feature_name", "road_carried", "structure_type", "nbi_len_m"]], on="crossing_id", how="left")
w500 = M.crossing_dist_m <= 500; print("reports with a structure on a named road: <=1km", int(M.crossing_id.notna().sum()), "| <=500m", int(w500.sum()))

# ---- 5. NWM reach + recurrence flows for the matched crossings ----
need = S[S.crossing_id.isin(M[w500].crossing_id)].copy(); FS = "https://maps.water.noaa.gov/server/rest/services/reference/static_nwm_flowlines/FeatureServer/0/query"; rr = []
for r in need.to_crs(U).itertuples():
    ll = gpd.GeoSeries([r.geometry], crs=U).to_crs(4326).iloc[0]; e = f"{ll.x - .003},{ll.y - .003},{ll.x + .003},{ll.y + .003}"
    j = requests.get(FS, params=dict(where="1=1", geometry=e, geometryType="esriGeometryEnvelope", inSR=4326, spatialRel="esriSpatialRelIntersects", outFields="feature_id,name,strm_order,high_water_threshold,rf_50_0_17c,rf_25_0_17c,rf_10_0_17c,rf_5_0_17c,rf_2_0_17c", outSR=4326, f="geojson"), timeout=120).json()
    g = gpd.GeoDataFrame.from_features(j["features"], crs=4326) if j.get("features") else []
    if len(g):
        g = g.to_crs(U); d = g.distance(r.geometry); i = int(np.argmin(d.values)); rr.append(dict(crossing_id=r.crossing_id, feature_id=int(g.feature_id.iloc[i]), reach_name=g["name"].iloc[i], strm_order=g.strm_order.iloc[i], reach_dist_m=float(d.iloc[i]),
              q2_cfs=g.rf_2_0_17c.iloc[i], q5_cfs=g.rf_5_0_17c.iloc[i], q10_cfs=g.rf_10_0_17c.iloc[i], q25_cfs=g.rf_25_0_17c.iloc[i], q50_cfs=g.rf_50_0_17c.iloc[i], hwt_cfs=g.high_water_threshold.iloc[i]))
RC = pd.DataFrame(rr, columns=["crossing_id", "feature_id", "reach_name", "strm_order", "reach_dist_m", "q2_cfs", "q5_cfs", "q10_cfs", "q25_cfs", "q50_cfs", "hwt_cfs"]); RC["assessed"] = (RC.reach_dist_m <= 100) & (RC.q2_cfs >= 1)
RC.loc[RC.reach_dist_m > 100, ["feature_id", "reach_name", "strm_order", "q2_cfs", "q5_cfs", "q10_cfs", "q25_cfs", "q50_cfs", "hwt_cfs"]] = np.nan   # beyond 100 m is not a match; distance kept
M = M.merge(RC, on="crossing_id", how="left"); M["assessed"] = M.assessed.fillna(False).astype(bool)

# ---- 6. suggested decisions (automatic, conservative; reviewer overrides) ----
def sug(r):
    if pd.isna(r.crossing_id) or r.crossing_dist_m > 500: return "reject", "no_structure_on_named_road_within_500m"
    if not r.assessed: return "reject", "crossing_not_assessed(no_reach<=100m_or_q2<1cfs)"
    if not r.matched_in_subject: return "reject", "named_road_only_as_landmark(after_locator_word)"
    return "accept", "named_road_is_closed_road;structure_on_it;reach_assessed"
M[["suggested_decision", "suggested_reason"]] = M.apply(lambda r: pd.Series(sug(r)), axis=1); M["reviewer_decision"] = ""; M["reviewer_notes"] = ""
M.sort_values(["suggested_decision", "time_utc"]).to_csv(O + "report_candidates.csv", index=False); M[M.assessed].to_parquet(O + "report_crossings.parquet")
st = dict(lsr_rows=n0, nc_dedup=n_nc, candidates=len(C), structure_within_1km_on_named_road=int(M.crossing_id.notna().sum()), within_500m=int(w500.sum()), assessed=int((w500 & M.assessed).sum()),
          suggested_accept=int((M.suggested_decision == "accept").sum()), unique_crossings=int(M[M.suggested_decision == "accept"].crossing_id.nunique()), by_year=M[M.suggested_decision == "accept"].time_utc.str[:4].value_counts().sort_index().to_dict())
json.dump(st, open(O + "t10a_stats.json", "w"), indent=1); print(json.dumps(st, indent=1))
