"""Extract from the existing data/raw/nc.osm.pbf (Geofabrik, 2026-10-09; read-only): drive-network lines for Area A+10km (with tags), fire_station and hospital features for A+10km and B+40km.
Usage: python -I src/inventory/osm_extract.py"""
import os, sys, re, pyogrio, pandas as pd, geopandas as gpd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common_geo import areas, ROOT
os.chdir(ROOT); AR = areas(); PBF = "data/raw/nc.osm.pbf"
DRIVE = {"motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link", "tertiary", "tertiary_link", "unclassified", "residential", "living_street", "service"}
def tag(s, k):
    m = re.search(r'"%s"=>"([^"]*)"' % re.escape(k), s if isinstance(s, str) else ""); return m.group(1) if m else None
out = "data/derived_new/osm_extract"; os.makedirs(out, exist_ok=True)
bb = AR["A"][1].bounds
if not os.path.exists(f"{out}/osm_drive_lines_areaA_buf.parquet"):  # lines pass is slow; skip if already extracted
    ln = pyogrio.read_dataframe(PBF, layer="lines", bbox=bb, where="highway IS NOT NULL", use_arrow=False)
    ln = ln[ln.highway.isin(DRIVE)].copy()
    for k in ["oneway", "maxspeed", "bridge", "tunnel", "ref", "lanes", "surface", "access", "junction", "ford"]:
        ln[k] = ln.other_tags.map(lambda s: tag(s, k))
    ln = ln.drop(columns=["other_tags"]); ln = ln[ln.intersects(AR["A"][1])]
    ln.to_parquet(f"{out}/osm_drive_lines_areaA_buf.parquet"); print("drive lines A", len(ln))
rows = []
for lay in ("points", "multipolygons"):
    for k, bbx in (("A", AR["A"][1]), ("B", AR["B"][1])):
        g = pyogrio.read_dataframe(PBF, layer=lay, bbox=bbx.bounds, where=("amenity IN ('fire_station','hospital')" if lay == "multipolygons" else "other_tags LIKE '%fire_station%' OR other_tags LIKE '%\"hospital\"%'"), use_arrow=False)
        if not len(g): continue
        if "amenity" not in g: g["amenity"] = g.other_tags.map(lambda s: tag(s, "amenity"))
        g = g[g.amenity.isin(["fire_station", "hospital"])].copy()
        g["geometry"] = g.geometry.representative_point() if lay == "multipolygons" else g.geometry
        g = g[g.intersects(bbx)]; g["area"] = k; g["osm_layer"] = lay
        for t_ in ["emergency", "operator", "healthcare", "beds", "addr:street", "addr:housenumber", "addr:city", "fire_station:type", "opening_hours", "disused", "abandoned", "was:amenity", "name", "alt_name"]:
            if t_ not in g: g[t_] = g.other_tags.map(lambda s, t_=t_: tag(s, t_))
        rows.append(g.drop(columns=["other_tags"], errors="ignore"))
r = pd.concat(rows, ignore_index=True); r = gpd.GeoDataFrame(r, crs=4326)
r = r.loc[:, ~r.columns.duplicated()]
r.to_parquet(f"{out}/osm_firestations_hospitals_AB_buf.parquet"); print(r.groupby(["amenity", "area", "osm_layer"]).size())
