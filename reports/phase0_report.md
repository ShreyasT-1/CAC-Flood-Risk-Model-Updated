# FloodLens Lifelines - Phase 0 report (Cape Fear pilot: New Hanover, Brunswick, Pender)

Run 2026-10-10. Scripts: `src/phase0/`. Tables: `data/phase0/`. Sources and URLs: `docs/phase0_sources.md`. No routing, UI or ML was built; `data/derived/ml_full_table` and the existing pipeline were not touched. Missing values were never filled (NaN stays NaN).

## Summary

| Spike | Your threshold | Result | Verdict |
|---|---|---|---|
| 1 Crossings -> NWM reach | match >= 80% | 58.9% within 100 m overall; **43.0% for crossings found independently of NWM**; 84.6% if crossings are seeded from NCDOT structures | **CHANGE PLAN** (seed crossings from structures) |
| 2 Structures / NBI | (none given) | 96.5% of NBI bridges link to NCDOT points; only **8.8%** of OSM-derived crossings have any structure within 100 m; no deck elevation or channel-clearance field anywhere | **GO WITH CAVEATS** |
| 3 Closure labels | gold+silver Florence >= 30 | gold **1**, silver **65**, bronze 2 (+ flood-only reports, warnings). Matthew: 0 gold, 2 silver. DriveNC history does not reach 2016 or 2018 | **GO WITH CAVEATS** for road-level labels, **CHANGE PLAN** for crossing-level labels |
| 4 Elevation / HAND | plausible >= 80% | 1 m lidar DEM covers all 3 counties; official HAND is not accessible; HAND-proxy plausible for 12/20 (60%) overall, 12/12 where a reach exists | **GO WITH CAVEATS** |

Threshold sanity: 80% reach match is reasonable for structure-seeded crossings on named waterways (84.6% passes) and unreasonable for "every OSM road/stream intersection" (NWM does not model ditches and small streams). The 30 gold+silver threshold is met on paper (66) but misleading, because silver is road-level and gold is 1; I suggest "labels with a crossing on the named road within 500 m, >= 30", which Florence misses narrowly (23; 42 at 1 km). The 80% HAND threshold is reasonable.

## Spike 1 - Crossings and NWM reach mapping

**Method.** OSM roads (motorway through residential, plus service; 57,264 ways) and OSM waterways (river, stream, canal, ditch, drain, tidal_channel; 28,104 ways) were taken from the NC Geofabrik extract already on disk. Crossing = intersection of a road with an OSM waterway (clustered within 15 m per road way), plus road x NWM-reach intersections not within 30 m of an OSM-waterway crossing. Only points inside the three county polygons. Each crossing was matched to the nearest NWM reach (cap 500 m). Reach geometry came from NOAA OWP's `static_nwm_flowlines` service (3,836 reaches in the pilot bbox, all present in RouteLink). RouteLink v3.1.6 supplied order, length, slope; RouteLink has only a midpoint per reach, so it cannot supply geometry, and the NHD files cached by the old pipeline were 4 KB HTML error pages.

**Numbers** (`data/phase0/crossings.parquet`, `s1_stats.json`, unmatched: `crossings_unmatched.geojson`)
- Crossings found: **2,900** (2,092 from OSM waterways, 808 from NWM-reach intersection). Brunswick 1,535, Pender 685, New Hanover 680.
- Matched within 50 m / 100 m: **56.3% / 58.9%** overall. This is inflated: the 808 NWM-intersection crossings match at 0 m by construction. For the 2,092 OSM-waterway crossings: **39.4% / 43.0%**.
- By road: major roads (tertiary and above, n=814) 68.6% / 70.5%; local (n=2,086) 51.5% / 54.4%; OSM `bridge=*` ways (n=290) 74.8% / 79.3%. By county (100 m): Brunswick 66.7%, Pender 56.5%, New Hanover 43.7%.
- Unmatched (>100 m or none within 500 m): 1,192; 641 have no reach within 500 m.
- Crossings per reach (matched, n=756 reaches): median 1, mean 2.3, max 30; 79 reaches have >= 5 crossings.
- Stream order of matched crossings: order 1: 1,310 (**77%**), 2: 241, 3: 87, 4: 38, 5: 26, 6: 1, 7: 5. The NWM link here is mostly headwater (order-1) reaches.
- Flags: `flag_tidal_like` 150 total (77 matched) = RouteLink slope < 2e-4 and order >= 3, a heuristic of mine (RouteLink has no tidal flag; `NHDWaterbodyComID` is -9999 for every pilot reach so it is unusable). `flag_ditch_like` (OSM ditch/drain/canal) 209 total (13 matched). `flag_headwater_o1` 1,696 total. Tidal flags catch the Cape Fear and Shallotte rivers, which are tidal; the NWM does not model tide.
- Name agreement between OSM waterway name and NWM reach name (matched, token overlap): 47%; only 27% of matched crossings have an OSM waterway name at all.

**Structure-seeded alternative** (from Spike 2): 299 NCDOT bridge/culvert/pipe records with a waterway-like feature name: 78.6% within 50 m and **84.6% within 100 m** of an NWM reach; 81.9% for the 293 NBI equivalents. Only 28% of those matches are order 1 (vs 77% above).

**3 failures** (see `crossings_unmatched.geojson`)
1. X019_01234, motorway "John Jay Burney Junior Freeway" (34.2574, -78.0800): OSM stream crossing, nearest NWM reach 249 m away.
2. X129_00509, Winston Boulevard over OSM stream "Burnt Mill Creek": nearest NWM reach 484 m away. A named creek the NWM does not carry.
3. X141_01717 (34.5575, -77.9472), service road over an OSM stream: no NWM reach within 500 m.

**Verdict: CHANGE PLAN.** Threshold 80% on the all-crossings table is not reachable (43% independent). Seed the crossing table from NCDOT/NBI structures on named waterways (84.6%) and keep OSM x NWM intersections only for major roads. Carry the order-1 / tidal / ditch flags into any model.

## Spike 2 - NCDOT structures and NBI

Downloaded: NCDOT StructuresPoint gdb (Q1 2026, 3.96 MB) and NBI 2025 NC (7.66 MB). NCDOT: 491 structures in the 3 counties (298 bridges, 61 pipes, 46 culverts, 82 signs, 4 other). NBI: 405 bridges. Records do **not** share a key (NCDOT `090001` vs NBI `190001`), so I linked spatially (<= 50 m): **391 of 405 (96.5%)** NBI records link, median 0.14 m, road-name agreement 93.9%.

- Structure -> crossing (nearest within 100 m): NCDOT **53.6%** (50 m: 48.7%), NBI **60.0%** (56.0%). Restricted to waterway-named features (NCDOT n=300, NBI n=293): 79.7% and 77.5%. Unmatched ones are largely signs (10-15% match) and bridges over roads.
- Name agreement among matched (structure feature name vs crossing stream name): NCDOT 70.7%, NBI 75.3%.
- Crossings with **any** structure within 100 m: **8.8%** (NCDOT 8.7%, NBI 8.1%). Major roads 21.6%; motorway 27.5%, secondary 26.6%, tertiary 23.8%, residential 4.4%, service 0.5%. Most OSM-derived crossings are small ditches/service roads with no state-inventoried structure.
- Fields we get. NBI: year built 100%, structure length 100% (a rough waterway-opening proxy, not a channel width), max span 100%, deck width 73.6%, waterway adequacy 76.8%, channel condition 76.8%, scour criticality 77.5%, feature name 100%. NCDOT: type, feature intersected, road carried, main/super/substructure type, posted weights, detour length, functional class (all >= 80%), AADT 55.8%.
- **Missing or unusable:** deck elevation and low-chord/freeboard (in neither source); waterway width (only structure length); vertical clearance is a traffic clearance, usable for 2.7-3.2% (items 10, 53) and 22.7% (54B), so not a flood clearance anyway; year built is NBI-only (NCDOT point file has none). NCDOT pipes and small culverts have no NBI record.

**3 failures** (waterway-named, no crossing within 100 m): Rockfish Creek bridge on US117/NC11 (700019); Discharge Canal bridge on NC87 (090002); Lewis Swamp pipe on SR1410 (090034, NBI 190034). These are real stream crossings our OSM-derived table missed, which is why seeding from structures is better.

**Verdict: GO WITH CAVEATS.** Structures are a good seed and give identity, type, year and scour/channel condition for roughly 400 bridges. They give no elevation, so deck/low-chord height must come from lidar (Spike 4). Pipes/small culverts (most ditches) stay unmodelled.

## Spike 3 - Closure labels

| Source | Dates | Precision | Florence 2018 | Matthew 2016 |
|---|---|---|---|---|
| DriveNC / NCDOT TIMS history (ArcGIS Online) | service created 2024-10-15; 137,865 points / 31,635 lines, but only 2 records start before 2019 (both Wake) | point/line, exact | **No** (0 records in Sep-Oct 2018) | **No** |
| IEM Local Storm Reports | 1986-present (API); NWS ILM | lat/lon rounded to 0.01 deg (~1 km); text names road | Yes | Yes (thin) |
| NWS warnings / VTEC (IEM, ILM) | 2002-present | county text list (polygons for FF only, not pulled) | Yes (area level) | Yes (area level) |
| Other NCDOT closure data | none found | - | press releases only (no GIS) | none |

Plainly: **DriveNC closure history is not available for either hurricane.** I found no public per-road closure dataset for Florence or Matthew.

**LSR labels** (`closure_labels_tiered.geojson`, `lsr_labels.parquet`). Window Sep 10 - Oct 5 2018 and Oct 6-14 2016. After deduplication: Florence 146 reports in pilot counties, of which 82 have closure wording; 68 are road-flood closure candidates (closure wording + a road term + flood cause, not naming another county; 11 tree/power-line closures dropped). 54 of the 68 come from DEPT OF HIGHWAYS, 11 COUNTY OFFICIAL.

| Tier | Rule | Florence | Matthew |
|---|---|---|---|
| Gold | point <= 100 m from a Spike-1 crossing on the road named in the remark | **1** (NC-53 near I-40, Pender, 75 m) | 0 |
| Silver | a road named in the remark lies within 1.5 km of the point | **65** | 2 |
| Bronze | closure wording but no resolvable road: 2; plus flood-type LSRs with no closure wording: 19 FLASH FLOOD; plus VTEC (Florence: CF.Y 21, CF.W 11, FF.W 10, FA.W 2, FL.W 1, FL.Y 1, FF.A 1; Matthew: CF.Y 6, FF.W 4, FA.W 1, FL.W 1, FF.A 1) | 2 (+19 LSR, + warnings) | 0 (+ warnings) |

Bronze is not ground truth and is not counted toward any threshold.

Why gold is 1: NWS rounds coordinates to ~1 km, so a 100 m test is dominated by rounding. Diagnostics: only 2 Florence candidates have *any* crossing within 100 m (naive, road ignored); 23 have a crossing on the named road within 500 m and 42 within 1 km (39 unique crossings). All Florence gold+silver reports fall on 2018-09-14 to 09-17; the multi-week river flooding is absent. The labels are **positives only**: no report means "unknown", not "open".

**3 failures**
1. "ASH-LITTLE RIVER ROAD NW IS CLOSED AT HINES DRIVE ... NEAR CALABASH" (Brunswick): silver, but the nearest crossing on that road is 2.4 km from the report point.
2. "BETHEL RD SE IS CLOSED NEAR CAGNEY LANE SE" and "E BEACH DR IS WASHED OUT IN OAK ISLAND": silver, no crossing at all on the named road in our table.
3. "NEW HANOVER COUNTY OFFICIALS FOUND THAT WATER CAUSED BY STORM SURGE ... MADE US-421 IMPASSABLE": counted silver, but this is surge, not stream overtopping, so a fluvial crossing model should exclude it. (Needs a manual pass; not automated.)

**Verdict.** 66 gold+silver passes >= 30 numerically, but only 1 is crossing-precise. GO WITH CAVEATS for road-segment labels; CHANGE PLAN for crossing-level supervision (needs manual geocoding of the ~42 near-crossing candidates, or a source with real geometry). Matthew is effectively unusable.

## Spike 4 - Elevation and HAND

- **DEM.** USGS 3DEP 1 m, via the TNM Access API: 172 tiles intersect the bbox, 162 from project `NC_HurricaneFlorence_2020_D20` (published 2025-03-25; the project name implies 2020 lidar, acquisition dates not verified) and 10 from `SC_2023Horry_Processing_D24` (buffer). The tile bboxes cover 100% of each county's bounding area (bbox test only, not a nodata check over water). It is post-Florence terrain. Older 2014/2015 NC lidar exists at NOAA (not examined). The 3DEPElevation ImageServer returned "Invalid Token", so tiles were read remotely with range requests.
- **HAND.** NOAA OWP HAND (`s3://noaa-nws-owp-fim`) is requester-pays and needs credentials (anonymous access returned AccessDenied), so **official HAND is not available**. I computed a **HAND-proxy** instead = road crest elevation (max DEM within +-40 m along the road) minus minimum channel DEM within +-100 m along the matched NWM reach. It is not true HAND (no flow routing, no catchment) and bare-earth lidar removes bridge decks, hence the road-crest choice.
- **20 random crossings** (seed 7; `s4_sample.csv`): road elevation obtained 20/20 (one point sample was NaN, crest was fine). HAND-proxy computable for **12/20**; all 12 plausible (0.48 to 3.91 m, within my -0.5 to 30 m window). Overall **12/20 = 60%** plausible; 12/12 where a reach exists. All 8 failures are "no NWM reach within 100 m", i.e. the Spike 1 problem, not an elevation problem.
- Caveat: "plausible" means in range, not verified. Values of 0.5-2 m at some crossings could be real or could reflect water-surface lidar voids in the channel.

**3 failures:** X019_01968 (service road: 86% of the road samples nodata, nearest reach 282 m); X019_01038 (trunk, nearest reach 329 m); X141_00705 (residential, no reach).

**Verdict: GO WITH CAVEATS.** Road/channel elevation from 1 m lidar works. Replace "NOAA HAND" with a locally computed HAND (e.g. whitebox/pysheds on the 1 m tiles) or request ESIP credentials from NOAA.

## Manual decisions (all documented here)
1. OSM from the on-disk Geofabrik extract (no Overpass); roads incl. service, excl. tracks/paths.
2. Reach geometry from the NOAA OWP flowline service; RouteLink v3.1.6 used for attributes because no v3.0 file is on NOAA's directory (the v3.0.17 HydroShare copy is a gauge subset). v3.0 vs v3.1 reach IDs were not diffed.
3. Crossing clustering 15 m, dedupe 30 m, match cap 500 m, thresholds 50/100 m.
4. Tidal and ditch flags are heuristics (see Spike 1). Waterway-name detection for structures is a keyword regex.
5. NBI<->NCDOT link is spatial (<= 50 m) because no shared key exists.
6. LSR: dedupe by (event, time, text, lat, lon); closure/flood/road regexes; reports naming another county excluded; tree/power-line-only closures excluded; flood-type LSRs count as flood cause even without a flood word.
7. Spike 4 sample seed 7, crest +-40 m, channel +-100 m, plausible range -0.5 to 30 m.
8. Installed `pypdf` to read NCDOT metadata. Downloaded files live in `data/phase0/raw/` (RouteLink is 269 MB: gitignore it).

## Weakest link, and what to do

1. **Closure labels (weakest).** One gold label, positives only, three days of one storm, Matthew empty, DriveNC history absent. What to do: (a) manually geocode the ~42 Florence silver reports that have a crossing within 1 km (a few hours of work; moves gold to perhaps 25-40); (b) file a public-records request to NCDOT for the TIMS/DriveNC closure archive for Sep-Oct 2018 and Oct 2016; (c) ask NCEM/FEMA PA for Florence road damage sites; (d) in the meantime use gauge-exceedance proxies (as the existing pipeline does) and treat LSRs as validation, not training.
2. **Crossing table.** OSM x stream gives 43% reach match, 77% order-1. What to do: seed from NCDOT/NBI structures on waterway names (84.6% match), add OSM x NWM only on tertiary-and-above roads, and carry the order-1/tidal/ditch flags.
3. **Structure attributes.** No deck elevation or freeboard anywhere. What to do: derive deck height from the 1 m lidar (road crest) and accept it as approximate.
4. **HAND.** Official HAND needs credentials. What to do: request ESIP access, or compute HAND locally; the crest-minus-channel proxy is a stopgap.
