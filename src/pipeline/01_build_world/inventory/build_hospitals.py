"""Consolidate hospitals for Area A (+10 km) and Area B (+40 km): CMS (ED flag, type, ownership; no coords) + OSM (coords, operator, beds) + HIFLD mirror (coords, beds, trauma; SOURCE DATA 2017) + OEMS trauma list (hand-keyed from https://oems.nc.gov/trauma/, read 2026-10-14).
Output: data/derived_new/hospitals_AB.csv. Name matching is fuzzy -> match_score column; review rows < 0.8. Usage: python -I src/pipeline/01_build_world/inventory/build_hospitals.py"""
import os, sys, re, difflib, pandas as pd, geopandas as gpd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common_geo import areas, ROOT
os.chdir(ROOT); AR = areas()
# OEMS-designated trauma centers (name fragment -> level); only those the OEMS page lists
TRAUMA = {"duke university hospital": "I", "unc hospitals": "I", "university of north carolina hospitals": "I", "unc medical center": "I", "wakemed raleigh": "I", "wakemed health & hospitals": "I",
          "new hanover regional medical center": "II", "wakemed cary": "III", "cape fear valley medical center": "III", "unc health pardee": "III", "johnston": None}
STOP = re.compile(r"\b(hospital|hospitals|medical|center|centre|inc|regional|health|healthcare|system|systems|the|of|at|campus|memorial|services|llc|and)\b|[^a-z ]")
def norm(s): return re.sub(r"\s+", " ", STOP.sub(" ", str(s).lower())).strip()
cms = pd.read_csv("data/phase1/raw/Hospital_General_Information.csv", dtype=str); cms = cms[cms.State == "NC"].copy()
osm = gpd.read_parquet("data/derived_new/osm_extract/osm_firestations_hospitals_AB_buf.parquet"); osm = osm[osm.amenity == "hospital"].copy()
hf = gpd.read_parquet("data/raw_new/hifld_hospitals_mirror/hifld_hospitals_mirror_NC_2021snapshot.parquet")
cand = [dict(src="osm", name=r.name, geom=r.geometry, operator=r.operator, beds=r.beds, emerg=r.emergency, trauma=None) for r in osm.itertuples() if r.name] + \
       [dict(src="hifld2017", name=r.NAME, geom=r.geometry, operator=r.OWNER, beds=None if r.BEDS in (-999, None) else r.BEDS, emerg=None, trauma=r.TRAUMA, county=r.COUNTY, city=r.CITY) for r in hf.itertuples()]
ALIAS = {  # CMS name -> name used by OSM/HIFLD (renames/system rebrands); verified by eye
    "NOVANT HEALTH NEW HANOVER REGIONAL MEDICAL CENTER": "New Hanover Regional Medical Center", "PENDER MEMORIAL HOSPITAL": "Pender Medical Center",
    "NOVANT HEALTH BRUNSWICK MEDICAL CENTER": "Brunswick Medical Center", "WAKEMED, RALEIGH CAMPUS": "WakeMed Health & Hospitals: Raleigh Campus", "UNC HOSPITALS": "UNC Medical Center",
    "DURHAM VA MEDICAL CENTER": "VA MEDICAL CENTER - DURHAM", "J ARTHUR DOSHER MEMORIAL HOSPITAL": "J. ARTHUR DOSHER MEMORIAL HOSPITAL", "VIDANT DUPLIN HOSPITAL": "ECU Health Duplin Hospital",
    "WAKEMED, CARY HOSPITAL": "WakeMed Cary Hospital", "NMC Camp Lejeune": "Naval Medical Center Camp Lejeune"}
def clean(s): return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", str(s).lower()))
rows = []
for r in cms.itertuples():
    q = ALIAS.get(r._2, r._2); n = norm(q)
    def best(src):
        sc = [(difflib.SequenceMatcher(None, n, norm(c["name"])).ratio(), c) for c in cand if c["src"] == src and (src == "osm" or str(c.get("city", "")).upper() == str(r._4).upper())]
        sc = sorted(sc, key=lambda t: -t[0]); return sc[0] if sc and sc[0][0] >= 0.85 else None
    po, ph = best("osm"), best("hifld2017"); prim = po or ph
    base = dict(facility_id=r._1, name=r._2, address=r.Address, city=r._4, county=r._7, ed=r._11, hospital_type=r._9, ownership=r._10)
    if not prim: rows.append(dict(base, coord_src="UNLOCATED", match_score=0)); continue
    g = prim[1]["geom"]; g = g if g.geom_type == "Point" else g.representative_point()
    beds = (ph[1]["beds"] if ph else None) or (po[1]["beds"] if po else None)
    names = clean(r._2) + " | " + clean(po[1]["name"] if po else "")
    lvl = next((v for k, v in TRAUMA.items() if v and k in names), None)
    rows.append(dict(base, lat=g.y, lon=g.x, coord_src=prim[1]["src"], match_name=prim[1]["name"], match_score=round(prim[0], 2), system_operator=(po[1]["operator"] if po else None) or (ph[1]["operator"] if ph else None),
                     beds=beds, beds_src=("osm tag / hifld(2017 data)" if beds else None), trauma_level_oems=lvl, trauma_hifld2017=ph[1]["trauma"] if ph else None))
d = pd.DataFrame(rows)
# OSM hospitals with no CMS row within 300 m (CMS file is missing some facilities): add as osm_only, ED from OSM emergency tag
have = gpd.GeoSeries(gpd.points_from_xy(d.lon.dropna(), d.lat.dropna()), crs=4326).to_crs(32617)
extra = []
for r in osm.itertuples():
    pt = r.geometry if r.geometry.geom_type == "Point" else r.geometry.representative_point()
    if len(have) and gpd.GeoSeries([pt], crs=4326).to_crs(32617).iloc[0].distance(have.union_all()) < 300: continue
    extra.append(dict(facility_id=f"osm:{r.osm_id}", name=r.name, city=None, county=None, ed=("Yes" if r.emergency == "yes" else "No" if r.emergency == "no" else None), hospital_type="osm_only (not in CMS file)", lat=pt.y, lon=pt.x, coord_src="osm",
                      match_score=None, system_operator=r.operator, beds=r.beds, beds_src="osm tag" if r.beds else None, trauma_level_oems=next((v for k, v in TRAUMA.items() if v and k in clean(r.name)), None)))
d = pd.concat([d, pd.DataFrame(extra)], ignore_index=True)
gg = gpd.GeoDataFrame(d, geometry=gpd.points_from_xy(d.lon, d.lat), crs=4326)
d["area"] = [("A" if AR["A"][1].contains(p) else "B" if AR["B"][1].contains(p) else None) if p is not None and not p.is_empty else None for p in gg.geometry]
d["ed"] = d.ed.map({"Yes": True, "No": False})
out = d[d.area.notna() | (d.coord_src == "UNLOCATED") & d.county.str.upper().isin(["WAKE", "DURHAM", "ORANGE", "NEW HANOVER", "BRUNSWICK", "PENDER"])]
out.to_csv("data/derived_new/hospitals_AB.csv", index=False)
pd.set_option("display.width", 250, "display.max_columns", 30, "display.max_colwidth", 38)
print(out[["name", "city", "area", "ed", "coord_src", "match_name", "match_score", "beds", "trauma_level_oems", "trauma_hifld2017", "system_operator"]].to_string())
print(out.groupby("area").agg(n=("name", "size"), ed=("ed", "sum")))
