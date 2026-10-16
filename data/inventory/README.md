# FloodLens Lifelines - dataset inventory (Area A: Triangle; Area B: Cape Fear)

Built 2026-10-14 by scripts in `src/inventory/` (re-runnable; downloads never overwrite). Machine-readable inventory: [datasets.csv](datasets.csv) (every dataset: URL, filename, path, coverage, vintage, CRS/vertical datum, license, key fields, size, SHA256, status, notes) and [sha256_files.csv](sha256_files.csv) (every file). Existing-data audit: [00_existing_audit.md](00_existing_audit.md). Road connectivity numbers: [road_quality.md](road_quality.md).

**Area A** = Wake (37183), Durham (37063), Orange (37135) + 10 km. **Area B** = New Hanover (37129), Brunswick (37019), Pender (37141) + 40 km. Counties: Census cb_2024 500k; buffers in UTM 17N.

## Bottom line (read this first)

1. **Confirmed closures with reopening times DO exist publicly - but only from mid-2022 on.** NCDOT's `NCDOT_TIMSIncidentsHistory` ArcGIS layer has start and end times. In Area A counties it yields **35 flood-related full closures (+47 in the 10 km buffer)** over 2022-2026, mostly Chantal (Jul 2025) and Debby/Helene (2024). That is a *small* positive-only label set. **There is nothing equivalent for Florence 2018, Matthew 2016 or Fran 1996** in any public source I could reach.
2. **No negatives anywhere.** TIMS lists only incidents; storm reports list only reports. A road with no record is *unknown*, not *open*. Do not train or score as if absence = no closure.
3. **Storm reports are not closures.** ~1,055 flood storm reports exist for Area A counties 2005-2026 (LSR+NCEI), kept in a separate tier.
4. **3DEP 1 m DEM covers only ~25% of Area A** (eastern fringe, Florence-2020 lidar). Wake/Durham/Orange mostly lack 3DEP 1 m; the better data is probably NC's own lidar (NC Spatial Data Download), which needs a manual sign-in. The 1 m tiles that exist total 7.2 GB - **not downloaded** (over your 5 GB flag).
5. **NC has a ready-made road-flood-depth layer**: NCDOT road inundation points (10/25/50/100/500-yr). It is modeled, not observed, but it is the closest thing to the missing "04_flood_hazard" for road crossings, for both areas.
6. The handoff README is stale: **FEMA NFHL zones for Area B already exist** at `data/phase2/fema_nfhl.parquet` (259 MB, do not commit).

Path corrections to the brief: LSR xlsx files live in `data/`, not `data/raw/`; the statewide road parquet is `data/phase2/t10/osm_roads_nc.parquet`; `data/raw/` and `data/phase0/raw/` are as stated.

## (a) Summary of every dataset

Status: `downloaded` = fetched now; `already_present` = audited, not re-downloaded; `script_only` = reproducible script/manifest but data not fetched; `not_found`.

| # | Dataset | Area | Status | Local path | Main limitation |
|---|---|---|---|---|---|
| 1 | NG911 road centerlines (NC 911 Board/OneMap) | A | downloaded | raw_new/nc_ng911_centerlines | only 46.7% of length connected; roadclass 4% filled; no route no./bridge flag |
| 2 | OSM drive network (from existing PBF) | A | downloaded | derived_new/osm_extract | 99.7% connected; 67% of ways are service roads; maxspeed 17%, oneway 14% |
| 3 | NCDOT State Maintained Roads (Q3 2022) | A, B | downloaded | raw_new/ncdot_state_maintained_roads | state roads only, 2022 snapshot |
| 4 | 3DEP 1 m DEM tile manifest (27 tiles, 7.17 GB) | A | script_only | raw_new/dem_3dep/tile_manifest.csv | ~25% of Area A; >5 GB |
| 5 | 3DEP 1/3 arc-sec NED (4 tiles, 2.0 GB) | A | downloaded | raw_new/dem_3dep/ned_13 | ~10 m, mixed-vintage; not road-crest grade |
| 6 | 3DEP lidar workunit index | A, B | downloaded | raw_new/dem_3dep/lidar_workunits_*.csv | index only |
| 7 | NC Spatial Data Download lidar/DEM | A, B | script_only (manual) | - | sign-in required |
| 8 | FEMA NFHL zones | A | downloaded | raw_new/fema_nfhl | not depth grids |
| 9 | FEMA NFHL zones (pilot) | B | already_present | data/phase2/fema_nfhl.parquet | B counties +0.05 deg only |
| 10 | FEMA NFHL LOMRs, BFE lines, cross-sections | A, B | downloaded | raw_new/fema_nfhl | see section below |
| 11 | NCDOT road inundation points 10-500 yr | A, B | downloaded | raw_new/ncdot_inundation_points | modeled; units unverified; inundated points only |
| 12 | NC FRIS depth grids / FIMAN | A, B | not_found | - | FRIS site is a JS shell |
| 13 | NOAA OWP HAND FIM | A, B | not_found | - | requester-pays bucket (prior audit) |
| 14 | Event inundation (Florence/Matthew/Fran/Helene-Triangle) | A, B | not_found | - | nothing public found; Helene extents are Western NC |
| 15 | NCDOT TIMS incident history | A, B | downloaded | raw_new/ncdot_tims_history | 2022+ only; operator-entered end times |
| 16 | NCDOT TIMS Helene archive | statewide | downloaded | raw_new/ncdot_tims_helene | mostly Western NC |
| 17 | NCDOT live TIMS hourly snapshots | statewide | already_present | data/closures_live | 4 days old |
| 18 | IEM Local Storm Reports NC 2005-2026 | A, B | downloaded | raw_new/iem_lsr_nc | reports, not closures |
| 19 | NCEI Storm Events 2005-2026 | A, B | downloaded | raw_new/ncei_storm_events | reports, not closures; many county-wide |
| 20 | OpenFEMA PA projects (cat C/D) | A, B | downloaded | raw_new/openfema_pa | no coordinates, no damage date |
| 21 | Unified flood road-event table | A, B | derived | derived_new/flood_road_events_unified.csv | keyword-selected; see section (b) |
| 22 | NCDOT structures + NBI + OSM/LSR existing files | A, B | already_present | data/phase0/raw etc. | see 00_existing_audit.md |
| 23 | CMS Hospital General Information | A, B | already_present | data/phase1/raw | no coordinates/trauma/beds |
| 24 | OEMS trauma list (hand-keyed) | A, B | downloaded | raw_new/oems_trauma | typed from web page |
| 25 | HIFLD hospitals (3rd-party mirror, 2017-era data) | A, B | downloaded | raw_new/hifld_hospitals_mirror | stale; HIFLD Open is offline |
| 26 | Consolidated hospitals | A, B | derived | derived_new/hospitals_AB.csv | fuzzy matched; not verified vs NC DHSR |
| 27 | NC OSFM fire stations (hosted copy, 2024-11) | A, B | downloaded | raw_new/nc_fire_stations_osfm | third-party host; no closures registry |
| 28 | Wake County GIS fire stations | A | downloaded | raw_new/wake_county_fire_stations | Wake only |
| 29 | Consolidated fire stations | A, B | derived | derived_new/fire_stations_AB.csv | Durham/Orange county layers not found |
| 30 | Census counties 2024 | A, B | downloaded | raw_new/census_counties | - |

Git: `data/raw_new/`, `data/derived_new/osm_extract/` and `data/phase2/fema_nfhl.parquet` are in `.gitignore`. Small derived tables and this folder can be committed.

## Roads (item 1)

* **OSM drive network** (extracted from the existing `data/raw/nc.osm.pbf`, 2026-10-09; ODbL): 248,362 ways, 40,968 km in A+10 km. 99.7% of length is one connected component. 24% of way ends are dangling (mostly service roads/driveways/ dead ends). Tags: highway 100%, name 30%, ref 3%, maxspeed 17%, oneway 14%; 1,745 bridge ways, 316 tunnel, 10 ford. **Best routing candidate for Area A** after dropping `highway=service` and applying default speeds/oneway rules.
* **NG911 centerlines** (`services.gis.nc.gov/secure/rest/services/NC1Map_Transportation/FeatureServer/0`, public despite the `/secure/` path): 119,607 segments in A+10 km (905,208 statewide). Newest names/addresses (dateupdate up to 2026-09-22) and oneway on 63% - but only **46.7% of length** forms the largest connected component, because segments from different local authorities do not share vertices. It would need snapping/ topology repair before routing. `roadclass` is filled for 4%, `speedlimit` for 16%; no route numbers, no bridge/tunnel flag.
* **NCDOT State Maintained Roads** (Q3 2022 snapshot, 359,236 statewide; 39,687 segments in A+10 km): 99.2% connected, has RouteClass/RouteNumber, but state-maintained only. Use to attach route numbers/class to OSM, not as the network.
* NC OneMap/NCDOT "full statewide" centerlines with speed + one-way beyond these were not found as a public service (NC_Local_Roads requires a token).
* Recommendation: route on OSM; attach `ref` from NCDOT State Maintained; flag bridge/culvert edges by spatial join to the NCDOT structures file (2,112 structures in A counties).

## Elevation (item 2)

* **3DEP 1 m**: TNM Access API (`tnmaccess.nationalmap.gov/api/v1/products`, dataset "Digital Elevation Model (DEM) 1 meter") returns **27 tiles (7.17 GB)** for A+10 km, all `NC_HurricaneFlorence_2020_D20` (QL1, collected 2019-12..2020-02, published 2025-03-25, NAVD88/GEOID18, 0.5 m nominal pulse spacing). Tile bounding boxes cover only ~25% of A+10 km. Manifest: `raw_new/dem_3dep/tile_manifest.csv`. **Not downloaded** (size > 5 GB). Say the word and I will fetch them, or fetch only tiles that intersect the study corridor.
* **Why Wake/Durham/Orange lack 1 m in 3DEP** (3DEP index layer 24, `lidar_workunits_A.csv`): only 2001/2003 legacy workunits (3 m, "does not meet" 1 m spec) cover them; QL2 2014 projects exist for Nash/Johnston/Franklin only. NC's 2015 statewide Phase 3 QL2 lidar (NCFMP) is the likely Triangle source but is distributed through NC Spatial Data Download (sign-in) and NOAA Digital Coast; **I could not confirm which phase covers each county**.
* **1/3 arc-second**: 4 NED tiles downloaded (1.97 GB, EPSG:4269, NAVD88 per USGS docs). Note: API URLs sit under a `historical/` path - confirm current versions before relying on them. ~10 m posting; fine for catchment-scale, not for culvert/road-crest height.
* **NC lidar/SDD**: `sdd.nc.gov` and `fris.nc.gov` are JavaScript apps (805-1,015 byte shells); no API found; sign-in needed. Manual path: sign in, choose Wake/Durham/Orange QL2 DEM tiles. Not scripted.

## Flood hazard (item 3)

* **NFHL** (`hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer`; layers 28 zones, 1 LOMRs, 16 BFEs, 14 cross-sections; verified live 2026-10-14). The server resets/empties large geometry requests, so `fetch_nfhl.py` pulls object IDs then geometry in small chunks. Fetched 2026-10-14 (A+10 km; B+40 km for non-zone layers): **zones A 32,969** (AE 6,547; AE floodway 582; X 0.2% 4,651; X *1% future conditions* 19,932 - Wake's FIRM includes future-conditions polygons; X minimal 1,252), **BFE lines A 4,427 / B 10,072**, **cross-sections A 13,740 / B 16,076**, **LOMRs A 48 / B 17**. **Known gap: one 0.1-degree tile of the Area B BFE-line ID query failed (lon -78.48, lat 34.08); BFE lines for B are incomplete there.** Area B zones were *not* re-fetched (use data/phase2/fema_nfhl.parquet; it does not extend to the full 40 km buffer).
* **NFHL does not contain depth grids.** `DEPTH` is a -9999 placeholder except 1 polygon in A, and `STATIC_BFE` is set for only 95 A polygons; effective floodway is the zone subtype `FLOODWAY`. Zone X ("0.2 PCT") and "minimal hazard" polygons dominate counts.
* **NCDOT road inundation points** (`NCDOT_Statewide_Inundation_Points`, layers 0-4 = 10/25/50/100/500-yr): A+10 km 1,929 / 3,292 / 4,877 / 7,387 / 13,895 points; B+40 km 8,562 / 26,759 / 43,004 / 58,416 / 96,211. Fields `road_elev`, `wse`, `depth`, `route_name`, `evac_route`. Median 100-yr depth where inundated: 1.5 (A) vs 3.5 (B) in service units (**units not stated; probably feet - unverified**). Every point has depth > 0, i.e. only overtopped locations are listed. Metadata (xfer.services.ncdot.gov/gisdot/Metadata/Atlas/NCDOT Road Inundation Points.pdf) warns it must not replace field surveys.
* **NC FRIS depth grid / 1% depth / FIMAN**: not found (see datasets.csv). Request path: NC Floodplain Mapping Program, (919) 715-5711 (number from a FRIS fact sheet; verify).
* **Event inundation**: nothing usable found for Florence 2018, Matthew 2016, Fran 1996, or Helene in the Triangle. Leads (not downloaded): USGS Matthew flood-map files for Neuse River at Smithfield (data.gov); NASA Disasters Sentinel-1 water extent for Helene (maps.disasters.nasa.gov/download/gis_products/event_specific/2024/hurricane_helene_202409/sentinel1/); NOAA NGS Emergency Response Imagery for Helene (`noaa-eri-pds` S3; storms.ngs.noaa.gov) - imagery, not depth; NC Helene estimated inundation (Western NC only); ICEYE Helene (commercial). USGS FIM: no library found for Wake/Durham/Orange. Florence ERI was not confirmed in my searches.

## (b) Flood-related road events: confirmed closures vs storm reports

Unified table: `data/derived_new/flood_road_events_unified.csv` (3,183 rows; columns source, source_type, event, start_time, end_time, end_time_kind, lat, lon, road_name, county, area, geometry_quality, confidence, detail, source_id). **Always filter on `source_type`; never pool tiers.** `area` is A/B (inside the counties) or A_buffer/B_buffer.

| Tier (`source_type`) | Source | A counties | A buffer | B counties | B buffer | Time range | Reopen time? |
|---|---|---|---|---|---|---|---|
| **confirmed_closure** | NCDOT TIMS history (Condition = Closed or IsFullClosure, flood keywords) | 35 | 47 | 72 | 172 | 2022-10 .. 2026 | yes (EndDateTime on 99.7%) |
| water_over_road | TIMS flood-keyword rows that were not full closures (e.g. partial access) | 17 | 3 | 25 | 25 | 2022-2026 | mostly |
| structure_damage | OpenFEMA PA cat C/D projects (no coordinates) | 75 | - | 179 | - | disasters 1999-2025 | no (county + applicant only, start_time = declaration date) |
| **storm_report (NOT closure)** | IEM LSR (flood types or flood words in remark) | 664 | 96 | 545 | 281 | 2005-2026 | no |
| **storm_report (NOT closure)** | NCEI Storm Events (Flash Flood, Flood) | 391 | 54 | 325 | 177 | 2005-2026 | event end only |

Confirmed closures in Area A counties by event (date-window label only, not verified against storm tracks): Chantal Jul 2025: 16 (+23 buffer); Debby Aug 2024: 3 (+7); Helene Sep 2024: 6 (+1); Ian 2022: 1; other dates: 9 (+16). By start year across all areas: 2022: 4, 2023: 87, 2024: 163, 2025: 68, 2026: 4.

**Data quality, bluntly**
* TIMS is an operations log, not a research dataset. Median duration of the flood closures is 49 h overall (23 h in A); 26 of 325 exceed 14 days (structural washouts, not flood duration); many durations are round numbers (1, 2, 4, 73 h), i.e. operator estimates or auto-expiry. `EndDateTime` is "cleared in the system", not verified reopening.
* Points sit at DriveNC route+milepost locations, not at the surveyed crossing; matching to crossings will need a distance tolerance and name/route check.
* Selection is by keywords (flood, high water, washout, water over/across, submerged, overtop). Closures logged with unhelpful `Reason` text are missed. Recall unknown.
* Coverage starts 2022 (7.5k statewide records), ramps in 2023: **no Matthew, Florence, Michael, Dorian, Isaias, Fred**. The layer's `CreationDate` starts 2024-10-15, so rows with earlier start times were apparently loaded later (back-filled); how complete 2022-2024 is cannot be determined from the service - treat early counts as possible undercounts.
* IEM/NCEI reports: LSR positions are reporter/WFO estimates; 516 of 664 Area-A LSR rows mention road words in the remark, but a remark is not a closure. NCEI times are local time, converted to UTC with a fixed offset (DST not handled).
* The previous Florence labels (`data/phase0/closure_labels_tiered.geojson`) remain the only Florence-era labels; they are Area B, positives-only, partly unreviewed.

**Records still to request** (reopening times not public for pre-2022 events or for county/municipal closures):
1. NCDOT Public Records (online form; see `docs/records_requests.md` drafts): Division 5 (Wake, Durham) and Division 7 (Orange) maintenance/emergency-operations closure logs, Chantal Jul 2025 and Helene Sep 2024 reopening dates; Division 3 for Cape Fear (Matthew/Florence). Divisions confirmed from TIMS `Division` values.
2. Wake, Durham and Orange County Emergency Management and the municipal public-works/transportation departments (Raleigh, Durham, Chapel Hill/Hillsborough): flooded-road barricade logs; none are open data (searched Raleigh/Durham/Chapel Hill portals - found only floodplain layers and a one-off Durham storm-traffic PDF).
3. NC Emergency Management / FEMA PA site lists for Category C damage with coordinates.
4. **Waze for Cities**: not public. Access requires applying as a government agency or road operator and signing terms that, per a 2018 report, prohibit public redistribution. **511/DriveNC**: current-only; the new DriveNC API needs a developer key; the old TIMS API retired 2026-05-27 (per `src/closures_live.py`). Continue the hourly archive in `data/closures_live`.

## Hospitals and fire stations (items 5, 6)

* **Hospitals** (`derived_new/hospitals_AB.csv`): A: 19 rows (12 with ED); B: 15 rows (11 with ED; consistent with the 11 ED hospitals already in the pilot). ED flag from CMS; coordinates from OSM (fallback HIFLD mirror); trauma level from the OEMS list (Duke, UNC, WakeMed Raleigh = Level I; NHRMC = II; WakeMed Cary, Cape Fear Valley = III); beds from OSM tag or the 2017-era HIFLD mirror (-999 = unknown). **System** is only the OSM `operator`/HIFLD owner where present. 9 (A) + 4 (B) rows exist only in OSM (CMS file lacks them, e.g. Duke Raleigh, WakeMed North); their ED flag is the OSM tag and is unverified (NHRMC Orthopedic shows "emergency=yes", doubtful). 3 psychiatric CMS rows are unlocated. **No NC DHSR facility list (beds/ED licensure) was found as a download** - DHSR data would need a request or manual export. HIFLD Open went offline in Aug 2025; the mirror used is third-party and 2017-era; Data Rescue Project / DataLumos holds snapshots (https://www.datalumos.org/datalumos/project/239161).
* **Fire stations** (`derived_new/fire_stations_AB.csv`): A: 191 OSFM + 10 Wake-GIS-only + 26 OSM-only rows; B: 164 OSFM + 13 OSM-only. `active` = listed by the OSFM 9S program layer (hosted copy edited 2024-11-04, third-party ArcGIS account, provenance unconfirmed) or published by Wake County (item modified 2026-09-28, CC BY 4.0); OSM-only rows are "unverified". 6 OSFM Wake stations have no Wake-GIS station within 500 m (possibly closed, moved or merged); 50 rows are flagged as possible duplicates (within 100 m). No source offers a closed/merged-station registry. Durham and Orange County station layers were not found; the OSFM list is the only authoritative-looking source for them. The earlier pilot list (220, OSM-only) for Area B should be reconciled against the 164 OSFM B stations.

## (c) Gaps and next steps

1. Decide on the 7.17 GB 1 m DEM (partial coverage) vs getting NC QL2 lidar via SDD sign-in (likely full coverage). For crossing-level work, QL2 2015 (Triangle) + QL1 2020 (east) is the realistic mix; vertical datum NAVD88 (confirm per tile; 2015 data in NC State Plane ft).
2. Build a crossing inventory for Area A: NCDOT structures (2,112 in counties, 2,550 in buffer) + NBI (1,302), snapped to the OSM network - not yet done.
3. Obtain Area A NFHL + inundation points joined to crossings; unit-check `depth` before use.
4. File the records requests above (priority: NCDOT Division 5/7 for Chantal and Helene reopen times; they would validate TIMS).
5. Verify hospital ED status for the OSM-only rows and replace the HIFLD-mirror beds with a current source.
6. Manually check Durham/Orange fire stations (county GIS), and the six Wake OSFM-only stations.
7. Timestamps: re-run `src/inventory/build_closure_table.py` periodically; TIMS history grows daily.

## (d) Which handoff "MISSING/PARTIAL" items this completes

| handoff_for_shreyas item | Status before | After this inventory |
|---|---|---|
| 03 terrain (PARTIAL, proxy only) | no DEM raster | Area A: tile manifest + 1/3 arc-sec rasters (coarse) + workunit index; **1 m not stored**; full completion needs the 7.17 GB tiles (partial A coverage) and/or NC QL2 lidar via SDD. Area B: tile index already exists; 1 m tiles still not downloaded |
| 04 flood hazard (MISSING) | empty | Not "missing" any more: Area B NFHL zones already existed (data/phase2); now also Area A NFHL, LOMR/BFE/cross-section layers, and NCDOT modeled road-inundation depths for A and B. Still no depth grids, no event extents |
| 05 closures (PARTIAL / WEAK) | Florence positives only | Adds 2022-2026 confirmed closures **with reopen times** (A: 35+47; B: 72+172), water-over-road rows, and multi-year storm-report tier. **Still weak:** small n, positives only, none for Florence/Matthew |
| 01/02/06 for Area A | none | Roads (OSM, NG911, NCDOT), structures/NBI already statewide, hospitals/fire stations consolidated - with the caveats above |
