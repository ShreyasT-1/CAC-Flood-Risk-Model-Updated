"""Connectivity + field completeness of road datasets for Area A. Writes data/inventory/road_quality.md. Usage: python -I src/inventory/road_quality.py
Connectivity = lines are linked when they share a (rounded) vertex. OSM ways are linked at shared nodes (vertex sharing); NG911/NCDOT segments by shared vertices too.
This ignores grade separation (bridges/overpasses sharing no node are correctly unlinked; same-coordinate false links are rare). Dangling = way/segment END vertex touched by no other line."""
import os, sys, numpy as np, pandas as pd, geopandas as gpd
from collections import Counter
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common_geo import ROOT
os.chdir(ROOT)
out = []
def P(s=""): out.append(s); print(s)


def analyse(name, g, prec):
    g = g[g.geometry.notna() & ~g.geometry.is_empty].explode(index_parts=False).reset_index(drop=True)
    gu = g.to_crs(32617); length = gu.length.values
    ids, rows, cnt, ends = {}, [], Counter(), []
    for i, geom in enumerate(g.geometry):
        cs = np.round(np.array(geom.coords)[:, :2], prec)
        vs = [ids.setdefault((x, y), len(ids)) for x, y in cs]
        rows.append(vs); cnt.update(set(vs)); ends.append((vs[0], vs[-1]))
    r = np.repeat(np.arange(len(rows)), [len(v) for v in rows]); c = np.concatenate(rows)
    m = coo_matrix((np.ones(len(r)), (r, c)), shape=(len(rows), len(ids))).tocsr()
    adj = m @ m.T
    n, lab = connected_components(adj, directed=False)
    sz = pd.Series(length).groupby(lab).sum().sort_values(ascending=False)
    dang = sum(1 for a, b in ends for v in (a, b) if cnt[v] == 1 and a != b)
    P(f"- **{name}**: {len(g):,} segments, {length.sum()/1000:,.0f} km; components {n:,}; largest component = {100*sz.iloc[0]/length.sum():.1f}% of length; "
      f"2nd largest {100*sz.iloc[1]/length.sum():.2f}%; dangling ends {dang:,} ({100*dang/(2*len(g)):.1f}% of segment ends)")


P("# Road dataset quality (Area A = Wake+Durham+Orange +10 km)\n")
osm = gpd.read_parquet("data/derived_new/osm_extract/osm_drive_lines_areaA_buf.parquet")
analyse("OSM drive highways (nc.osm.pbf 2026-10-09)", osm, 7)
P(f"  - fields present: highway={osm.highway.notna().mean():.0%}, name={osm.name.notna().mean():.0%}, ref={osm.ref.notna().mean():.0%}, oneway tag={osm.oneway.notna().mean():.0%} (absent means two-way by default except motorways/roundabouts), "
  f"maxspeed={osm.maxspeed.notna().mean():.0%}, bridge={osm.bridge.notna().sum():,} ways, tunnel={osm.tunnel.notna().sum():,}, ford={osm.ford.notna().sum()}")
P("  - highway mix (share of ways): " + ", ".join(f"{k}={v:.0%}" for k, v in osm.highway.value_counts(normalize=True).head(7).items()))
ng = gpd.read_parquet("data/raw_new/nc_ng911_centerlines/ng911_centerlines_areaA_buf.parquet")
analyse("NG911 centerlines (NC 911 Board / NC OneMap)", ng, 6)
P(f"  - fields: roadclass={ng.roadclass.notna().mean():.0%}, speedlimit>0={(pd.to_numeric(ng.speedlimit, errors='coerce').fillna(0) > 0).mean():.0%}, oneway={ng.oneway.notna().mean():.0%}, st_name={ng.st_name.notna().mean():.0%}, dateupdate range {pd.to_datetime(ng.dateupdate, unit='ms', errors='coerce').min()} .. {pd.to_datetime(ng.dateupdate, unit='ms', errors='coerce').max()}")
P("  - roadclass values: " + str(ng.roadclass.value_counts(dropna=False).head(10).to_dict()) + "; oneway values: " + str(ng.oneway.value_counts(dropna=False).to_dict()))
P("  - NO route number, NO bridge/tunnel flag, NO functional class in NG911 -> join structures/NBI spatially for bridge flags.")
sm = gpd.read_parquet("data/raw_new/ncdot_state_maintained_roads/state_maintained_roads_areaA_buf.parquet")
analyse("NCDOT State Maintained Roads (Q3 2022 snapshot)", sm, 6)
P(f"  - fields: RouteClass={sm.RouteClass.notna().mean():.0%}, RouteNumber={sm.RouteNumber.notna().mean():.0%}, StreetName={sm.StreetName.notna().mean():.0%}; state-maintained only (no private/municipal streets) -> not a complete routing network")
open("data/inventory/road_quality.md", "w", encoding="utf-8").write("\n".join(out))
