# Road dataset quality (Area A = Wake+Durham+Orange +10 km)

- **OSM drive highways (nc.osm.pbf 2026-10-09)**: 248,362 segments, 40,968 km; components 185; largest component = 99.7% of length; 2nd largest 0.10%; dangling ends 120,157 (24.2% of segment ends)
  - fields present: highway=100%, name=30%, ref=3%, oneway tag=14% (absent means two-way by default except motorways/roundabouts), maxspeed=17%, bridge=1,745 ways, tunnel=316, ford=10
  - highway mix (share of ways): service=67%, residential=22%, tertiary=3%, secondary=3%, primary=2%, trunk=1%, motorway_link=1%
- **NG911 centerlines (NC 911 Board / NC OneMap)**: 119,607 segments, 25,220 km; components 336; largest component = 46.7% of length; 2nd largest 12.03%; dangling ends 22,947 (9.6% of segment ends)
  - fields: roadclass=4%, speedlimit>0=16%, oneway=63%, st_name=100%, dateupdate range 2014-06-24 17:20:52 .. 2026-09-22 00:00:00
  - roadclass values: {nan: 115203, 'Secondary Route': 1291, 'Public': 1058, 'Local': 1017, 'Local/Municipal': 435, 'PVT': 306, 'NC': 181, 'Secondary': 65, 'US': 47, 'Waterway': 3}; oneway values: {'BI': 67455, nan: 44285, 'FT': 4318, 'TF': 2467, 'B': 1082}
  - NO route number, NO bridge/tunnel flag, NO functional class in NG911 -> join structures/NBI spatially for bridge flags.
- **NCDOT State Maintained Roads (Q3 2022 snapshot)**: 39,687 segments, 12,232 km; components 92; largest component = 99.2% of length; 2nd largest 0.06%; dangling ends 6,816 (8.6% of segment ends)
  - fields: RouteClass=100%, RouteNumber=100%, StreetName=97%; state-maintained only (no private/municipal streets) -> not a complete routing network