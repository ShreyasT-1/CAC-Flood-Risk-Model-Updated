# FloodLens Lifelines - data handoff for Shreyas (generated 2026-10-11)
Pilot area: New Hanover, Brunswick, Pender (NC) + 40 km buffer (NC+SC roads).

| Your item | Status | Folder |
|---|---|---|
| Road network | COMPLETE | 01_road_network (OSM drive graph, 246,088 segments; 6,940 Census 2020 block origins) |
| Bridge/crossing inventory | COMPLETE for pilot | 02_crossings (crossings_v2 = NCDOT+NBI, 250 hazard-ready seed crossings; OSM-secondary ones are poor quality, filter on data_quality) |
| Terrain elevation | PARTIAL - proxy only | 03_terrain_proxy (HAND-type crest-minus-channel samples from 3DEP 1 m lidar; NO full DEM raster stored; tnm_1m_products.parquet is the tile index to download it) |
| Flood hazard maps | MISSING | 04_flood_hazard is empty. FEMA NFHL not ingested yet. Hazard in our work = NWM flow vs recurrence thresholds (reach_thresholds.parquet, recurrence_hindcast_*). |
| Historical road closures | PARTIAL / WEAK | 05_closures (Florence 2018: positives only, partly unreviewed; reviewer_decision column blank until reviewed. Do NOT treat as ground truth or full labels) |
| Hospital/fire locations | COMPLETE | 06_facilities (11 ED hospitals, 220 fire stations, 214 snapped to graph) |

07_consequence_outputs = our routing results (which crossing loss cuts hospital/fire access).
ML table is NOT in this folder (1 GB): data/derived/ml_full_table_v2 - use v2 not v1; Florence = TEST, never tune on it. See docs/DATA_CARD_v2.md.
Caveats: see docs/phase1_limitations.md. Nowcast, not forecast. Scenarios, not probabilities.
