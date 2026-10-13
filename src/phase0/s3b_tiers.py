"""Phase0 S3b: tier IEM LSR road-closure reports. gold = point within 100 m of a Spike-1 crossing whose OSM road is the road named in the remark;
silver = a road named in the remark lies within 1.5 km of the point (road/segment level); bronze = pilot-county report with closure wording but no resolvable road, or no closure wording
(excluded from counts: non-road reports). LSR coordinates are rounded to 0.01 deg (~1 km) by NWS, so the 100 m gold test is dominated by coordinate rounding -- we also report a relaxed diagnostic."""
import re, json, numpy as np, pandas as pd, geopandas as gpd
P = "data/phase0/"; U = 32617
L = gpd.read_parquet(P + "lsr_raw.parquet").drop_duplicates(["event", "valid", "remark", "lat", "lon"], keep="first").reset_index(drop=True)  # same report is logged under 2 types (e.g. TROPICAL STORM + FLASH FLOOD)
cs = gpd.read_file(P + "counties.geojson")
L = L.to_crs(U) if L.crs else L.set_crs(4326).to_crs(U)
cu = cs.to_crs(U); L["pt_county"] = gpd.sjoin(L[["geometry"]], cu[["COUNTYFP", "geometry"]], how="left", predicate="within")["COUNTYFP"].reindex(L.index).values
L["in_pilot_text"] = L.county.str.upper().isin(["NEW HANOVER", "BRUNSWICK", "PENDER"]); L["in_pilot"] = L.in_pilot_text | L.pt_county.notna()
CLOSE = re.compile(r"CLOSED|CLOSURE|IMPASS|WASHED ?OUT|BARRICAD|NOT PASSABLE|BLOCKED|UNDER WATER|OVERWASH|CUT OFF|SUBMERGED")
ROADTXT = re.compile(r"\bROAD\b|\bRD\b|\bDR\b|\bDRIVE\b|\bST\b|\bSTREET\b|\bHWY\b|\bHIGHWAY\b|\bBLVD\b|\bAVE\b|\bBRIDGE\b|\bUS-?\d+|\bNC-?\d+|\bSR-?\d+|\bI-\d+|\bLANE\b|\bLN\b")
L["closure_word"] = L.remark.fillna("").str.upper().map(lambda s: bool(CLOSE.search(s)))
L["road_word"] = L.remark.fillna("").str.upper().map(lambda s: bool(ROADTXT.search(s)))
L["flood_type"] = L.typetext.isin(["FLASH FLOOD", "FLOOD", "HEAVY RAIN", "STORM SURGE", "HIGH ASTR TIDES"])
FLOODCAUSE = re.compile(r"FLOOD|WATER|SURGE|WASH|OVERWASH|INUNDAT|RISING|RUSHING|SUBMERG")
L["flood_cause"] = L.remark.fillna("").str.upper().map(lambda s: bool(FLOODCAUSE.search(s))) | L.typetext.isin(["FLASH FLOOD", "FLOOD"])  # manual decision: tree/power-line-only closures are not flood labels
OTHERCTY = re.compile(r"IN (BLADEN|COLUMBUS|ONSLOW|HORRY|DUPLIN|SAMPSON|GEORGETOWN) COUNTY")
L["other_county_text"] = L.remark.fillna("").str.upper().map(lambda s: bool(OTHERCTY.search(s)))  # manual decision: remark names a non-pilot county -> exclude
L["candidate"] = L.in_pilot & ~L.other_county_text & L.closure_word & L.road_word & L.flood_cause
# road name normalisation
ABBR = {"ROAD": "RD", "STREET": "ST", "DRIVE": "DR", "AVENUE": "AVE", "BOULEVARD": "BLVD", "HIGHWAY": "HWY", "LANE": "LN", "COURT": "CT", "CIRCLE": "CIR", "PARKWAY": "PKWY", "TRAIL": "TRL", "NORTHEAST": "NE", "NORTHWEST": "NW", "SOUTHEAST": "SE", "SOUTHWEST": "SW", "NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W"}
DIR = {"N", "S", "E", "W", "NE", "NW", "SE", "SW"}
def norm(s):
    t = [ABBR.get(w, w) for w in re.findall(r"[A-Z0-9]+", str(s).upper())]
    while t and t[-1] in DIR: t.pop()
    return " ".join(t)
def refnorm(s): return [re.sub(r"[^A-Z0-9]", "", r) for r in re.split(r"[;,]", str(s).upper()) if r.strip()]
R = gpd.read_parquet(P + "osm_roads.parquet").to_crs(U); R["nn"] = R.name.map(lambda s: norm(s) if pd.notna(s) else None); R["rn"] = R.ref.map(lambda s: refnorm(s) if pd.notna(s) else [])
X = gpd.read_parquet(P + "crossings.parquet").to_crs(U)
def mentioned(remark, near_idx):
    txt = " " + norm(remark) + " "; raw = re.sub(r"[^A-Z0-9]", "", str(remark).upper()); hit = []
    for i in near_idx:
        nn = R.nn.iat[i]; ok = isinstance(nn, str) and len(nn) > 4 and (" " + nn + " ") in txt
        if not ok:   # US-17 / NC-210 / SR-1342 / I-40 refs; OSM ref format varies ('US 17', 'NC 210') so compare squashed
            ok = any(len(r) >= 3 and r in raw for r in R.rn.iat[i])
        if ok: hit.append(i)
    return hit
rows = []
for k, r in L[L.candidate].iterrows():
    near = R.sindex.query(r.geometry.buffer(1500), predicate="intersects"); h = mentioned(r.remark, near)
    tier, cid, dxx = "bronze", None, np.nan
    if h:
        tier = "silver"; hid = R.osm_id.iloc[h].values
        cx = X[X.osm_road_id.isin(hid)]
        if len(cx):
            d = cx.distance(r.geometry); dxx = float(d.min()); cid = cx.crossing_id.iloc[int(np.argmin(d.values))]
            if dxx <= 100: tier = "gold"
    rows.append(dict(idx=k, tier=tier, named_road_hits=len(h), nearest_named_road_crossing=cid, nearest_named_road_crossing_m=dxx))
T = pd.DataFrame(rows).set_index("idx"); L = L.join(T); L["tier"] = L.tier.fillna("not_a_road_closure_candidate")
# naive diagnostic: ANY crossing within 100 m / 500 m regardless of road named
dm = L[L.candidate].geometry.apply(lambda g: float(X.distance(g).min())); L.loc[dm.index, "any_crossing_m"] = dm
out = L.to_crs(4326); out.to_parquet(P + "lsr_labels.parquet")
def cnt(ev, in_scope=True):
    d = L[(L.event == ev) & L.candidate]; return d.tier.value_counts().reindex(["gold", "silver", "bronze"]).fillna(0).astype(int).to_dict()
st = dict(florence=cnt("florence"), matthew=cnt("matthew"),
          florence_all_pilot=int(((L.event == "florence") & L.in_pilot).sum()), matthew_all_pilot=int(((L.event == "matthew") & L.in_pilot).sum()),
          florence_dropped_nonflood_closure=int(((L.event == "florence") & L.in_pilot & L.closure_word & L.road_word & ~L.flood_cause).sum()), florence_closure_word_pilot=int(((L.event == "florence") & L.in_pilot & L.closure_word).sum()), florence_candidates=int(((L.event == "florence") & L.candidate).sum()),
          florence_source_counts=L[(L.event == "florence") & L.candidate].source.value_counts().to_dict(),
          naive_any_crossing_within_100m_florence=int(((L.event == "florence") & (L.any_crossing_m <= 100)).sum()), naive_within_500m_florence=int(((L.event == "florence") & (L.any_crossing_m <= 500)).sum()),
          named_road_crossing_within_500m_florence=int(((L.event == "florence") & (L.nearest_named_road_crossing_m <= 500)).sum()),
          named_road_crossing_within_1000m_florence=int(((L.event == "florence") & (L.nearest_named_road_crossing_m <= 1000)).sum()),
          unique_gold_crossings=int(L[(L.tier == "gold")].nearest_named_road_crossing.nunique()),
          county_text_vs_point_mismatch=int((L.in_pilot_text & L.pt_county.isna()).sum()))
json.dump(st, open(P + "s3_stats.json", "w"), indent=1); print(json.dumps(st, indent=1))
pd.set_option("display.width", 250, "display.max_colwidth", 110)
for t in ("gold", "silver", "bronze"):
    print("##", t); print(L[(L.event == "florence") & (L.tier == t)][["county", "remark", "nearest_named_road_crossing_m", "any_crossing_m"]].head(6).to_string())
