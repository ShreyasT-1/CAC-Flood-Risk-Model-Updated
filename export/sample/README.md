# FloodLens Lifelines: SAMPLE / PREVIEW export

**Sample data, not for emergency use.** This folder shows how pipeline results could look on the website. It is not validated output. The project's kill tests have not passed, and no forecast skill, new hydrologic model, or validation against Florence closures is claimed (see `docs/claims.md` sections 2 and 3). Wording stays probabilistic: a location "may lose access", with an "X% chance". A low chance is never an assurance, because the hazard is river flow only.

Every value is one of two kinds, and each value says which:
- **`"synthetic": false`**: a real pipeline output, read unchanged from the Florence hindcast replay or `data/export/`.
- **`"synthetic": true`**: a **placeholder** for something the pipeline has not computed yet (mainly the ML isolation model being built by a teammate). Placeholder values look plausible and follow the real replay, but they are not results.

Per-hour values are wrapped as `{"value": ..., "synthetic": true|false}`, so a consumer cannot read a value without its flag. `meta.json` → `fields` repeats each field's flag, unit and definition.

## Run the preview
```
cd export/sample
python -m http.server 8765
# open http://localhost:8765/preview.html
```
The page has to be served over HTTP, because opening it as a `file://` URL blocks `fetch`. MapLibre GL 4.7.1 loads from unpkg and the basemap from OpenFreeMap (keyless Positron vector style). Rebuild the data from the repo root with `python export/sample/build_sample.py`. It reads pipeline files read-only, writes only into this folder, and ends with a self-check covering synthetic flags, banned words, the 2 MB network limit and record counts.

## What is replayed
| | |
|---|---|
| Region | Cape Fear pilot: New Hanover, Brunswick, Pender (NC) |
| Event | Hurricane Florence 2018, **hindcast replay**: NWM v3.0 retrospective, free-running |
| Window | 18 replay hours from 2018-09-15 12:00 UTC. In the published export, people losing ED-hospital access in the `seed` RL10 scenario rise from 637 to 6,668 over this window |
| Closure scenario | crossing set `seed` (250 hazard-ready, structure-seeded crossings); a crossing's road segment closes while flow is above its **10-year recurrence flow** (RL10). This is a scenario level, not a probability |
| Access target | ED acute / critical-access hospitals; phase-1 origin snap (the published build) |

The 18 hours are **replay hours**. They are not a forecast issued at the time.

## Files
| File | Size | Contents |
|---|---|---|
| `meta.json` | ~5 KB | region, event, scenario, status flags (`sample: true`, `validated: false`, `kill_tests_passed: false`), known gaps, data sources, field dictionary |
| `addresses.json` | ~89 KB | 10 locations × 18 hours |
| `blocks_lookup.json` | ~1.7 MB | every 2020 Census block in the 3 counties (6,940), columnar: real replay hours (`lost`, `detour_min`, `crit`, `red`) for the 3,115 blocks the replay touches, plus the **placeholder** `p_pct` (24 h); `replay: null` = untouched (placeholder floor 3%); `assessed: 0` = no baseline route, not assessed (88 blocks). Used by the website's address search; the 10 sample sites are checked to match their block rows |
| `route_crossings.json` | ~220 KB | all 2,920 crossings for the website's route analysis: the 250 the replay can close with real per-hour `level` (digit string indexing `levels`) and `ratio_q10`, plus **placeholder** `p_pct` (same values as `crossings.json`; checked); the other 2,670 as `not_assessed` [id, lat, lon, reason] |
| `facilities.json` | ~22 KB | the pipeline's essential services, real locations: 11 ED acute / critical-access hospitals (the engine's set) and 214 fire stations. Note: the fire-station list includes "Surf City Police Department" (an OSM tagging issue in the pipeline input) and 3 unnamed stations |
| `crossings.json` | ~118 KB | 33 crossings × 18 hours, with "What Breaks First?" rank |
| `facilities_watchlist.json` | ~4 KB | 6 facilities ranked by peak placeholder chance, with alert text |
| `network.geojson` | ~185 KB | major roads in the 3 counties (motorway to tertiary), merged by class and name; every road segment carrying a sample crossing kept as its own feature (`seg_id`); crossing points |
| `preview.html` | ~13 KB | single-page MapLibre preview |
| `build_sample.py` | ~20 KB | builds all of the above |

Website: `npm run sample:sync` in `lifelineswebsite/` copies the JSON/GeoJSON files into `public/data/sample/`.

## Stress-test copy
`python export/sample/make_stress.py` writes `stress/` with the same schema and **deliberately exaggerated** values (0% to 100% ramps, every scenario crossing closed from replay hour 6, every block cut off from hour 9, 999.9-minute detours, 9,999,999 people affected, a 117-character facility name). It is not a scenario and not real; it only exists to test how the website copes with extremes. The site loads it with `?data=stress` and switches the banner to "STRESS TEST".

## Field definitions

### addresses.json → `addresses[]`
| Field | Real or placeholder | Meaning |
|---|---|---|
| `id`, `name`, `kind` | see note | `kind` = `dialysis`, `nursing_home` or `residential`. **Dialysis and nursing-home entries are placeholder facilities** (`facility_synthetic: true`). The pipeline has no inventory of those facility types, so each sits at a real Census block centroid under a generic name. Residential entries are blocks from the real 25-block sample in `data/export/address_report_sample.json` |
| `geoid20`, `county`, `pop20`, `lat`, `lon` | real | 2020 Census block and its centroid. **Not a street address** |
| `baseline_drive_min_to_nearest_ed_hospital`, `baseline_route_redundancy` | real | no-closure drive time (OSM default speeds, no traffic) and ED hospitals within 30 min |
| `timeline[].hour`, `valid_time_utc` | n/a | replay hour 0-17 and its UTC time |
| `timeline[].isolation_probability` | **placeholder** | 0-1 chance of losing every route to an ED hospital. Built from the block's real replay state over the next 6 h plus noise, so it **agrees with the replay by construction and says nothing about model skill** |
| `timeline[].time_to_isolation` | **placeholder** | hours until `isolation_probability` first reaches 0.5 (0 = already there); null = not within the window + 6 h |
| `timeline[].isolation_duration` | **placeholder** | hours it stays at or above 0.5 from that onset, truncated at the window + 6 h |
| `timeline[].isolation_tolerance` | **placeholder** | assumed hours a location can go without access: dialysis 48, nursing home 72, residential 72. Constant across hours; not a sourced input |
| `timeline[].scenario_lost_access` | real | true = no route to any ED hospital in that hour's RL10 closure state |
| `timeline[].detour_minutes` | real | added drive time vs baseline. 0 = changed by 1 min or less (the engine stores only affected blocks, `src/22_engine_p2.py`); null = no route |
| `timeline[].critical_crossing_id` | real | first closed crossing on the block's baseline path; null = none closed on that path |
| `timeline[].route_redundancy` | real | ED hospitals within 30 min under that hour's closures |

Selection: picked by hand to show a range of replay outcomes (lost access, long detours, little change). **Not a random or representative sample.**

### crossings.json → `crossings[]`
| Field | Real or placeholder | Meaning |
|---|---|---|
| `id`, `name`, `road`, `stream`, `county`, `lat`, `lon`, `nwm_feature_id`, `structure_type`, `data_quality`, `tidal_flag`, `fema_zone`, `q10_cfs` | real | from `data/export/crossings_export.csv`. FEMA zone is a comparison layer only |
| `consequence.*` | real | structural effect of closing this crossing alone (`data/export/consequence_ranking.csv`), with no hazard input. `people_affected` counts people who lose access to, or are slowed by more than 1 min to, an ED hospital or fire station |
| `breaks_first_rank` | real (derived) | "What Breaks First?" order: `event_first_above_RL10_utc`, then `consequence.people_affected` |
| `event_first_above_RL10_utc` | real | first hour of the whole Florence hindcast (from 2018-09-13) with flow above the 10-year flow |
| `first_hour_above_RL10` | real | the same, within the 18-hour window (flows can dip and rise again) |
| `hourly[].flow_ratio_q10` | real | hindcast flow / 10-year recurrence flow |
| `hourly[].level_reached` | real | highest recurrence level strictly exceeded (`RL0` … `RL50`); a scenario level, **not a probability** |
| `hourly[].flood_probability` | **placeholder** | logistic function of the real `flow_ratio_q10` plus noise. Not a calibrated closure probability |

Included crossings: the 28 with the highest `people_affected` among `seed` crossings above RL10 at some point in the window, plus every critical crossing of the 10 locations. Total: 33.

### facilities_watchlist.json → `watchlist[]`
Dialysis and nursing-home entries only, ranked by `peak_isolation_probability` (**placeholder**), then by `time_to_isolation_from_start` (**placeholder**). `alert_level` is `ACCESS WARNING (sample)` when the peak is 70% or more, `ACCESS WATCH (sample)` at 30% or more, and `ACCESS OUTLOOK (sample)` otherwise. The level names follow the NWS watch/warning style but are not NWS products. `text` is probabilistic wording that ends with the sample stamp.

### network.geojson
`kind: "road"` features: `highway`, `name`, `carries_sample_crossing`, `seg_id` (only on segments carrying a sample crossing; this matches `graph_segment_id` in `data/export/crossings_export.csv`). Geometry is simplified to about 30 m with coordinates rounded to 1e-5°. `kind: "crossing"` features: `id`, `name`. Source: the OSM routing graph `data/phase1b/graph_segments.parquet`.

## Known gaps (also in `meta.json`)
- River flow only: no storm surge, tide, or rain/drainage flooding, and no deck height or scour.
- **New Hanover (Wilmington) shows little or no loss of access in this replay.** That comes from the crossing inventory and graph, not from Florence: Wilmington was documented as cut off, and test E3 failed to reproduce it. Do not read the low New Hanover values as low exposure.
- The Florence hindcast saturates: most seed crossings exceed their 10-year flow at the peak, so levels barely separate.
- 88 blocks (6,921 people) with no baseline route are "not assessed" in the pipeline. None of them are used here.
- No USGS data is read by this sample. If a later version adds gauge data, it should use the USGS Water Data API (api.waterdata.usgs.gov), not legacy WaterServices.

## What to plug in when real outputs exist
| Placeholder now | Replace with | Where |
|---|---|---|
| `isolation_probability` | ML isolation model output per block (or facility) per replay hour | `placeholder_prob()` in `build_sample.py` |
| `time_to_isolation`, `isolation_duration` | derive from the model output with the same 0.5 rule, or take them from the model if it predicts them directly | `onset_and_duration()` |
| `flood_probability` | the crossing-level model's probability, if one is built and passes its kill test; otherwise drop the field and show `level_reached` only | crossings block |
| `isolation_tolerance` | sourced per-facility values (facility survey or an agreed planning assumption) | `TOLERANCE_H` |
| placeholder dialysis / nursing-home sites | a real facility inventory (e.g. CMS dialysis and nursing-home provider files, geocoded), snapped like the hospitals and run through `src/22_engine_p2.py` as origins | `SITES` |
| replay hours | real forecast issue time and lead hours, once forecast-mode runs exist | `T0`, `hours` |
| `status.kill_tests_passed: false`, `sample: true` | flip only after the kill tests pass and the owner signs off; then remove the banner | `meta`, `preview.html` |

When a field becomes real, set its `synthetic` flag to `false` and update `FIELDS` in the build script. The self-check fails if a known placeholder field is marked real, so update the list in `flagged()` too.

## Live files (not part of the Florence REPLAY; each has its own mode label)
- `nowcast.json` (NOWCAST): observed USGS discharge/gage height and NWS stage + flood category at 46 pilot gauges. `python src/45_nowcast.py` also refreshes `coastal.json`.
- `coastal.json` (NOWCAST + OUTLOOK-PERSISTENCE): NOAA CO-OPS observed/predicted water level, NAVD88 m. Outlook rows are `synthetic: true` persistence placeholders.
- `forecast_latest.json` (FORECAST): NWM short-range, unvalidated, river flow only, not a closure probability. `python src/44_forecast_preview.py`.
Every record has a UTC time; stale = observation > 3 h old (forecast: cycle > 6 h old).
