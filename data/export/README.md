# FloodLens Lifelines - data export (Cape Fear pilot: New Hanover, Brunswick, Pender)

Built by `src/export_data.py`; checked by `src/export_checks.py`; provenance (row counts, inputs, sha256) in `manifest.json`. Study area: three NC counties plus a 40 km graph buffer. **Everything here is a scenario or a structural estimate, not a prediction of any road or address being open or closed.** Closure results use NWM channel streamflow only (no surge, tide, pluvial flooding, deck height or scour). Do not describe any road, block or address as protected from flooding or as free of flood risk; absence of a flag means "not assessed" or "not triggered in this scenario", nothing more.

## Files
| File | One row per | Notes |
|---|---|---|
| `crossings_export.csv` / `.geojson` | crossing (2,920) | 321 structure-seeded (NCDOT/NBI) + 2,599 OSM-derived |
| `consequence_ranking.csv` | crossing (same ids) | structural: **no hazard or flow input** |
| `address_report_sample.json` | 25 sampled Census blocks | stamped `SAMPLE - block-centroid estimate` |
| `florence_replay_hourly.csv` | hour x crossing set x scenario | Florence hindcast, 2018-09-13 00:00 to 2018-11-06 23:00 UTC |
| `blocks_export.csv` | Census block origin | block centroid, snap distance, baseline reachability, FEMA zone |
| `live_conditions.json` / `.csv` | crossing with an NWM reach (1,686) | **live layer**, rewritten by `src/72_live_conditions.py`; sha256 not pinned in the manifest |
| `manifest.json` | file | row counts, source script, inputs, sha256, git HEAD |

## Data dictionary

### crossings_export
`id` crossing id (join key). `lat`,`lon` WGS84 degrees. `road` road carried (blank = not recorded). `stream` feature intersected (blank = not recorded); `nwm_reach_name` NWM reach name. `county`. `src` ncdot+nbi / ncdot / nbi_only (structure-seeded) or osm_secondary (OSM road x waterway intersection). `structure_type`. `data_quality` good/fair/poor (phase-0 rule, see `reports/phase0_report.md`). `seed_reliable` true/false for structure-seeded crossings (provisional rule: structure length < 35 m, stream order <= 3, not tidal; cutoffs from 14 NGS marks); **blank for OSM-derived crossings (not applicable)**. `tidal_flag` heuristic (slope < 2e-4 with order >= 3, or tidal words in name). `nbi_structure_len_m` metres (NBI item 49; blank = no NBI record). `stream_order` NWM Strahler order. `nwm_feature_id` matched NWM reach (blank = no reach within 100 m). `hazard_threshold_ok` / `hazard_ok_reason`: false when no reach or 2-yr flow < 1 cfs (not assessed). `q2_cfs` ... `q50_cfs` NOAA OWP recurrence flows of the matched reach, **cubic feet per second** (field `rf_N_0_17c`; derivation unverified); blank = not available, never filled. `hwt_cfs` NWM high-water threshold (cfs). `graph_snapped` true if the crossing is snapped to a routing-graph segment within 50 m; `graph_segment_id` that segment.
`fema_zone`, `fema_zone_subty`, `fema_zone_class`, `fema_sfha`, `fema_static_bfe`, `fema_n_overlapping_polygons`: FEMA National Flood Hazard Layer flood-hazard zone at the crossing point (see FEMA section). `fema_zone` = `UNMAPPED` and class `unmapped (no NFHL polygon)` when no polygon contains the point; that means "no NFHL polygon here", **not** low hazard. `fema_sfha` is T/F as served (blank when unmapped); `fema_static_bfe` is the FEMA base flood elevation in feet where given, blank otherwise.
**`long_bridge_flag` is not included**: it has not been computed (the terrain/HAND task was not run). `nbi_structure_len_m` is the only length information.

### consequence_ranking
Closing one crossing removes the whole junction-to-junction OSM segment it is snapped to (`crossings_on_same_segment` crossings share a segment and therefore share identical values). Baseline = no closures. Origins = 6,940 Census 2020 block centroids (snap = `phase1`, see "Choices made"); facilities = 11 ED acute/critical-access hospitals and 214 snapped fire stations. "Lost access" = the block has no route to any facility; "slowed" = still reachable but > 1 minute longer. `hosp_*`/`fire_*`: `pop_lost_access`, `blocks_lost_access`, `pop_slowed_gt1min` (people, blocks; 2020 population), `added_person_hours` (sum over slowed blocks of population x extra drive time, hours), `max_detour_min` (largest added drive time among still-reachable blocks, minutes; 0 if none). `people_affected` / `blocks_affected`: blocks that lose access to, or are slowed by > 1 min to, hospital or fire station. `rank_by_people_affected`: 1 = largest, ties share a rank. `consequence_status`: `assessed` or `not assessed: ...` (crossing not snapped to the graph; its consequence columns are blank). A value of 0 means "no block changes in this single-closure test" - it does not mean the crossing is unimportant for other facilities, other closures combined, or other routes (exits are not included).

### address_report_sample
25 random block centroids (seed 20261011; 8 Brunswick, 9 New Hanover, 8 Pender) among blocks with baseline access to both facility types. **Block centroids, not addresses.** `baseline_nearest_*` = nearest facility by OSM drive time (minutes, no traffic). `critical_crossing_*` = the crossing on the baseline path whose single closure hurts this block most, with its effect; `redundancy` = number of ED hospitals within 30 min and fire stations within 10 min of the centroid at baseline. Each record carries `stamp`.

### florence_replay_hourly
`hour_utc` (UTC). `crossing_set` seed (250 hazard-ready structure-seeded crossings) or seed_reliable (147). `scenario` RL2/RL5/RL10/RL25/RL50 = flow **above** the reach's 2/5/10/25/50-year recurrence flow (a scenario level, not a probability). `n_crossings_assessed`, `n_crossings_above_level` (count of crossings, strictly above). `blocks_lost_*_access`, `people_lost_*_access`: blocks / people with no route to any ED hospital or fire station in that hour's closure state (blocks that were already unreachable at baseline are excluded). Fire-station columns are blank for `seed_reliable` (**not computed**). Label: hindcast, NWM v3.0 retrospective, free-running (no data assimilation). The Florence layer saturates (205 of 250 seed crossings exceed their 50-year flow), so the levels separate little at the peak.

### live_conditions (live layer)
**A scenario view of operational NOAA National Water Model output, not a closure forecast.** Each run of `src/72_live_conditions.py` reads the newest available hourly *Standard Analysis & Assimilation* `channel_rt` file (`tm00`; AWS `noaa-nwm-pds`, then the GCS mirror, then NOMADS; up to 12 h back) and compares the current modelled flow of each crossing's reach with that reach's own recurrence flows. It is a nowcast display of NOAA output: **no new validation claim** is made for it (the pilot tests in `docs/claims.md` concern other data and say nothing about this layer's skill at any road).
JSON top level: `available` (false = nothing could be read; then `explanation` says why, `crossings` is empty and no value is shown), `stale` (true when the cycle is older than `stale_after_minutes` = 360), `age_minutes` (now minus cycle time at `generated_at`), `generated_at`, `source` (`url`, `network`, `nwm_version` as stored in the file, reach counts), `cycle_time_utc`, `valid_time_utc` (equal for tm00), `label` (the scenario statement), `level_definitions`, `level_counts`, `crossings`.
Per crossing (JSON and CSV): `crossing_id` (join key to `crossings_export`), `nwm_feature_id`, `cycle_time_utc`, `valid_time_utc`, `flow_cfs` (m3/s x 35.3146667), `ratio_q2` ... `ratio_q50` (flow divided by the reach's q2/q5/q10/q25/q50 recurrence flow; blank/null when the crossing is `not_assessed`), `level_reached` (`RL0` = at or below the 2-year flow; `RL2`...`RL50` = strictly above that recurrence flow, highest reached; `not_assessed` = `hazard_threshold_ok` false; `no_flow_value` = reach missing from the file), `age_minutes`, `stale` (repeated per row for CSV-only readers). Levels are scenario labels, **not probabilities** and not statements about any road being open or closed. Missing values are never filled.
Caveats: operational analysis flows are assimilated and differ from the v3.0 retrospective behind the other tests; the file's model version is recorded in `source.nwm_version`; the recurrence flows' provenance is unverified (see limitations); NOAA documents the analysis product on water.noaa.gov/about/nwm, but the AWS registry page only describes the short-range product, so the analysis path on that bucket was confirmed by request, not by its registry page. A file older than 6 h is flagged `stale` and the app should say so.

## Units and vintages
Flow cfs (retrospective files are m3/s x 35.3146667); distances m; times min unless stated; coordinates WGS84. Population: 2020 Census blocks (`nc2020.pl`, TIGER 2020 block boundaries). Structures: NCDOT StructureLocationsPoint (Q1 2026 download) and NBI 2025 NC file. Streams/thresholds: NOAA OWP `static_nwm_flowlines`; reach matching via NWM RouteLink v3.1.6. Road network: OpenStreetMap Geofabrik NC and SC extracts (as on disk; extract date not recorded in this repo). Hospitals: CMS Hospital General Information (geocoded with the Census geocoder). Fire stations: USGS National Map layer (HIFLD-derived, 2021 vintage) merged with OSM. Hindcast flows: NWM v3.0 retrospective, 2018-09-13 to 2018-11-06.

### blocks_export
One row per origin block: `geoid20`, `county`, `pop20` (2020 population), `lat`/`lon` (centroid), `snap_m` (distance to the snapped graph node, metres), `baseline_reachable_ed_hospital` / `baseline_reachable_fire_station` (false = no baseline route in the graph; such blocks are excluded from loss counts), and the same `fema_*` columns as above for the block centroid.

## FEMA NFHL comparison layer
Source: FEMA public ArcGIS service `https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28` ("Flood Hazard Zones", ArcGIS Server 11.1; verified 2026-10-12; the older `/gis/nfhl/rest/...` path returns "Not Found"). Downloaded for the pilot bounding box into `data/phase2/fema_nfhl.parquet` (fetch time stored per row); the service carries no dataset-vintage field, so the vintage is "as served on the fetch date". Zone assigned by point-in-polygon at the crossing point or block centroid; where polygons overlap the highest-hazard one is used. **FEMA zones are a comparison layer only: not ground truth, not a model input, and not a statement about any road or address.** Comparison with the Florence hindcast: `docs/claims.md` and `data/phase2/fema_vs_rl10_florence_hindcast.csv`.

## Origin snap: phase-1 snap vs phase-2 re-snap (checked 2026-10-12)
The phase-2 re-snap moved blocks that the phase-1 snap had left on tiny disconnected road fragments onto the largest connected part of the graph. It cut baseline-unreachable people but **failed a manual check**, so **this export uses the phase-1 snap**. Check (`src/60_resnap_check.py`, `data/phase2/resnap_check/resnap_check.csv`): 30 random blocks that were unreachable under the phase-1 snap and reachable under the re-snap, plus all 21 blocks the re-snap dropped.
- **10 of 30** sampled blocks were snapped to a node whose only roads are service roads (flagged as wrong); 0 to ramps (0); 0 had the straight line to the snapped node crossing an OSM river/canal/tidal channel (a crude test: streams and ditches were not counted). A further 16 of 30 moved more than 500 m (median snap distance 202 m with the phase-1 snap, 531 m after the re-snap); that criterion is mine, not counted in the flag. More than 3 flagged, so the re-snap is not used.
- The 21 dropped blocks (578 people) were all unreachable under the phase-1 snap; their nearest node on the main network is 1.6-6.2 km away, and 14 of 21 would cross water to reach it (Caswell Beach / Oak Island blocks). They are dropped under the re-snap and kept (as baseline-unreachable) under the phase-1 snap.

| | Phase-1 snap (this export) | Phase-2 re-snap (alternative build) |
|---|---|---|
| origin blocks / people | 6,940 / 421,319 | 6,919 / 420,741 |
| blocks / people with no baseline route to an ED hospital (excluded from loss counts) | 88 / 6,921 | 2 / 168 |
| median / blocks over 500 m snap distance | 88 m / 352 | 88 m / 351 |
| crossings whose single closure changes access or time for any block | 1046 | 1050 |
| top 3 `people_affected` (people) | [43394, 43394, 43313] | [43513, 43513, 43432] |
| Florence hindcast seed set, RL2: peak people / blocks losing ED-hospital access | 7,500 / 249 | 7,582 / 251 |
| same, RL10 | 6,668 / 204 | 6,750 / 206 |
| same, RL10, fire-station access (people) | 4,507 | 4,589 |

The choice barely moves the headline numbers (RL2 peak people losing ED-hospital access differs by 82 people, 1.1%); it matters for the 88 blocks left on fragments. Rank agreement of `people_affected` between the two builds (Spearman, crossings in both): 0.997. The phase-1 snap has its own weakness: the 88 baseline-unreachable blocks sit on isolated fragments, so their access is **not assessed** (not zero), and people there are missing from every loss count.


## Choices made in this export
- Origins: **snap = `phase1`.** The default and published build uses the **phase-1 snap** (each block to its nearest graph node, blocks > 1,500 m from a node dropped). The phase-2 re-snap (blocks moved to the largest connected part of the graph) failed a manual check on 2026-10-12 (see the side-by-side section) and is kept only as an alternative build in `data/phase2/export_resnap_alt/`. Phase-1 baseline-unreachable blocks keep `baseline_reachable_* = false` and are excluded from loss counts, as in phase 1.
- The hourly file reuses the phase-2 replay outputs `data/phase2/engine/replay_hindcast_{base|resnap}_*` matching the snap.
- The consequence ranking skips any crossing-segment pair not on a baseline shortest-path tree because a single closure there cannot change any shortest time; those get 0 by construction.


---
# Known limitations (copied verbatim from `reports/phase1_limitations.md`)

# Phase 1 prototype - limitations (read before using any output)

Every closure result is a **SCENARIO** (flow / high_water_threshold above a chosen ratio), not a probability and not a calibrated closure model. Hindcast and forecast runs are labelled in every file name (`replay_hindcast_*`, `replay_forecast_*`).

## Not in the hazard at all
1. **Storm surge, tide and coastal flooding.** The hazard is NWM channel streamflow (`channel_rt` / retrospective `chrtout`) only. NOAA describes tide and surge as a separate coastal total-water-level product, linked to the NWM from v3.0 through SCHISM with ocean forcing from STOFS and P-SURGE (https://water.noaa.gov/about/nwm); that coupling is one-way (hydrology does not receive coastal updates) and is not in the streamflow series we replay. The 2018 operational forecasts (v1.2 era) had no coastal component at all. Wilmington's US-421 and the barrier islands are exposed to surge and tidal flooding that this system cannot see; one Florence report we matched ("storm surge ... made US-421 impassable") is exactly this case. Source for the v3.0 coupling statement: https://water.noaa.gov/about/nwm and the NOAA OWP coastal-coupling webinar (https://www.weather.gov/media/watercommunity/Webinar/2026Jul16/NWM%20TWL%20Coastal%20Modeling%20-%20Coastal%20Coupling%20CoP%20Webinar%20-%20July%202026.pdf), both read via search summaries, not the full v3.0 technical documentation.
2. **Pluvial / urban drainage / ditch flooding**, levee and culvert-capacity failures, road washouts, debris, wind and tree closures. NWM reaches do not model stormwater systems. The label check below shows closures reported on roads with no matched reach.
3. **Deck elevation / freeboard / scour.** Closure is a function of flow ratio only. No source gives deck or low-chord height (Phase 0). Long, high-level or tidal bridges can be "closed" by a flow ratio although their decks sit far above the water; the `seed_reliable` crossing set excludes the ones our provisional rule flags, and results from `seed` and `seed_plus_osm_secondary` should be read with this in mind.

## Hazard-threshold weaknesses
4. **The ratio-to-closure mapping is uncalibrated and sits at the wrong scale.** Official flood stage corresponds to a median **3.6 x** `high_water_threshold` (about 1.4 x the 2-year flow; p90 27 x threshold; n = 100 gauged reaches, `p2_stats.json`). The requested scenario ratios 0.5-1.5 therefore close roads at flows far below flood stage.
5. **Saturation in the Florence replay.** The hindcast peak flow was 8.7-143 x threshold (median 32 x) on every structure-seeded crossing, so ratios 0.5, 0.75, 1.0 and 1.5 give identical results at the peak. Extended scenarios (3.64, 10, 30, 60, 100) were added; they are my choice, not calibrated.
6. **Zero / tiny thresholds.** 137 of 3,836 pilot reaches (112 order-1) have a 2-year flow of exactly 0. `hazard_threshold_ok = false` removes them (plus any with q2 < 1 cfs, my arbitrary minimum). Excluded crossings are never closed by the hazard, which understates risk where it matters least-known.
7. **Order-1 weakness.** 77% of OSM-derived crossing matches are order-1 reaches; the NWM's weakest. For structure-seeded crossings it is 28%. The secondary OSM set is almost entirely order-1 and `poor` quality; `seed_plus_osm_secondary` results are a sensitivity test, not a best estimate.
8. **Free-running hindcast.** The v3.0 retrospective has no data assimilation and 2018 has well-known timing/magnitude errors in tropical-storm events. In the label comparison, 2 of 15 reports have flow below threshold at the reported hour though the replay peaks 9-30 x later (timing).
9. **The v3.0 vs v1.2 forecasts differ in model version, forcing and network**; the forecast pass is not an apples-to-apples replay of the hindcast. Its short-range lead time (<= 12 h used) is also a bounded subset (see report).

## Labels
10. **Positives only.** LSR closure reports say a road was closed; absence of a report is "unknown", not "open". There is no way here to count false alarms.
11. **Tiny and unreviewed.** 24 reports have a crossing on the named road within 500 m (threshold 30: NOT met); 9 of them are structure-seeded crossings, and 9 of the 24 have no reach/threshold at all. They are candidates until reviewed by hand. Coordinates are rounded to ~1 km. The label comparison is qualitative and proves nothing about skill.

## Network / people model
12. **Routing:** OSM drive network, default speeds by road class, no traffic, no turn restrictions, no maxspeed parsing; ferries, gates and private roads ignored. Parallel arcs keep only the fastest. A closure removes the whole junction-to-junction segment containing the crossing, which can be long.
13. **Origins:** 2020 Census block centroids snapped to the nearest graph node (origins >1.5 km from a node dropped; 390 snap >500 m); snap distance is not driven. 2020 population, not time-of-day or evacuations.
14. **Facilities:** only 4 hospitals with emergency services lie inside the 10 km buffer (CMS list geocoded with the Census geocoder; two military hospitals did not geocode and are out of scope). Columbus Regional (Whiteville), Cape Fear Valley-Bladen, Onslow Memorial, Vidant Duplin and the Horry/Georgetown (SC) hospitals lie outside the buffer and are absent. The CMS 'Emergency Services = Yes' flag also admits behavioural-health hospitals (none fall inside the buffer), so western and northern origins may show artificial isolation. Fire stations are from OSM (HIFLD availability could not be confirmed), a volunteer-built list.
15. **Critical crossing** = the first closed crossing on the baseline shortest path, not a minimum cut. **Redundancy** = number of facilities reachable within 30 min (hospitals) or 10 min (fire stations) under the current closures.
16. **Baseline unreachable origins** (islands, graph gaps; 5,949 people in New Hanover) are reported separately and excluded from loss counts.

## Not done
No individual addresses, no ML, no live feeds, no UI. Nothing here has been validated against observed closures.

