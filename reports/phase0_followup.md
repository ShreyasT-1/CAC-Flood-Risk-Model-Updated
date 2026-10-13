# Phase 0 follow-up (2026-10-10)

Scripts `src/phase0/s5..s9`; outputs in `data/phase0/`. `ml_full_table` untouched. Nothing was filled: distances beyond 100 m keep the distance but the reach fields are blank; NaN stays NaN.

## 1. RouteLink v3.1.6 vs v3.0 retrospective feature_ids
- Whole network: v3.0 retrospective `chrtout.zarr` has 2,776,734 feature_ids; RouteLink v3.1.6 has 2,776,734; **0 ids in one and not the other.**
- Our 256 gauge-crosswalk reaches (`gauge_crosswalk.csv`, 262 rows, 256 unique ids): **256 in v3.0, 256 in v3.1.6, 0 changed, 0 missing.** All 3,836 pilot-bbox reaches are in both.
- Attribute drift: stream order in the crosswalk equals RouteLink order for 256/256. USGS id appears in RouteLink `gages` for 217/256 (rest not listed there; crosswalk came from NWPS or other sources, not a v3.1 difference I can attribute). Median gauge-to-reach-midpoint offset 0.44 km.
- Caveat: identical ID sets do not prove identical geometry or parameters; I did not diff those. Detail: `s5_routelink_diff.csv`.

## 2. Crossings v2 (`crossings_v2.parquet` / `.geojson`)
Seed = NCDOT bridges/culverts/pipes + NBI bridges whose feature name looks like a waterway (my regex extended after reading the 106 rejected names; wildlife crossings, wetlands and railroads excluded). NCDOT and NBI records for the same structure are merged (spatial link). Secondary = Phase-0 OSM x stream crossings with no seed structure within 100 m, flagged `src = osm_secondary`.

| | Seed | Secondary (OSM) | All |
|---|---|---|---|
| Crossings | **321** (292 NCDOT+NBI, 16 NCDOT only, 13 NBI only; 201 bridges, 61 pipes, 46 culverts, 13 NBI-only bridges) | 2,599 | 2,920 |
| Matched to reach within 100 m | **80.1%** (257); within 50 m 74.5% | 55.0% (1,429) | 57.7% |
| On order-1 reaches | **73** (28.4% of matched) | 1,238 (86.6%) | 1,311 (77.8%) |
| Order distribution (matched) | 1:73, 2:88, 3:55, 4:30, 5:8, 7:3 | 1:1238, 2:142, 3:25, 4:4, 5:17, 6:1, 7:2 | |
| data_quality good / fair / poor | **123 / 134 / 64** | 0 / 187 / 2,412 | 123 / 321 / 2,476 |
| Distinct reaches | 219 | 602 | 778 |

- Seed match is 80.1%, below the 84.6% I quoted in Phase 0. The difference is the extended name filter (it added names like Discharge Canal, Hood Creek, Driving Creek, which sit away from any NWM reach) and merging NCDOT/NBI duplicates. Treat 80% as the honest figure; it only just clears your threshold.
- Name agreement (structure feature name vs NWM reach name) among matched seeds: 73.5%. 46 seed crossings have more than one reach within 100 m (confluences), 181 across all.
- `data_quality` rule (mine): **good** = seed, reach <= 50 m, order >= 2, not tidal-like, and (name agrees or NBI record). **poor** = no reach within 100 m, or a secondary crossing that is order-1 or ditch-like. **fair** = everything else. Tidal-like: slope < 2e-4 with order >= 3, or a tidal word in the feature name (68 seeds).
- Failure examples (seed, unmatched): Discharge Canal / NC87 (no reach within 500 m), Hood Creek / NC87 (none), Town Creek / SR1411 (119 m).

## 3. NWM recurrence-interval thresholds
- **Exists, with thin documentation.** The NOAA OWP `static_nwm_flowlines` service carries `high_water_threshold` and `rf_{50,25,10,5,2}_0_17c` per reach, in cfs; aliases read "2%, 4%, 10%, 20%, 50% Streamflow (cfs)", i.e. the 50/25/10/5/2-year flows. That alias text is the only definition I found. I checked the NCO RouteLink/parm/constants directories, the water.noaa.gov NWM pages and a web search: none define these fields. "17c" being Bulletin 17C is my inference. How the flows were derived (which simulation, which years) is **unknown**. URLs are in `docs/phase0_sources.md`.
- Coverage: all 3,836 pilot reaches have all six fields non-null. Crossings: seed 257/257 matched, **order-1 crossings 73/73 (seed), 1,311/1,311 (all)**. Joined as `q2_cfs q5_cfs q10_cfs q25_cfs q50_cfs hwt_cfs`.
- Quality, which coverage hides: 137 reaches (112 of them order-1) have a 2-year flow of exactly 0; that hits 2 seed crossings (1 on order-1) and 7 secondary. Order-1 median 2-year flow is 6.4 cfs, and 94 secondary order-1 crossings are under 1 cfs. Values are monotonic (no reach violates q2 <= q5 <= ... <= q50). `high_water_threshold` equals q2/q5/q10 on only 146/114/113 reaches, so it is a separate quantity. Treat order-1 thresholds as present but weak.

## 4. Deck elevation check (10+ NBI bridges, 14 tested)
- **No source gives deck elevation** (NBI has none; NGS marks are not on decks). I used the best independent evidence available: 14 NGS datasheet marks (NAVD88 orthometric height) set in bridge abutments/footings/massive structures/pavement within 60 m of seed bridges, compared with the 1 m lidar (`s8_deck_check.csv`).
- **Bare-earth DEM at the mark minus mark height:** median -1.2 m (DEM lower), mean |diff| 1.24 m, p90 2.25 m. Part of this is expected (marks sit above ground on structures), so it shows bare-earth/under-structure lowering, not an error figure.
- **Bridge-centre DEM is not deck:** 12 of 14 bridge points read 1-6 m below the approach (e.g. Cawcaw Swamp 5.9 m vs approach 9.7 m; Discharge Canal 1.1 vs 5.8). Bare-earth processing removed or interpolated under the decks.
- **Road crest (max within +-40 m along the road) minus mark:** median -0.15 m, mean |diff| 0.81 m; within 1 m for 10/14. No systematic offset, so the datum (NAVD88) looks consistent.
- Failures: Intracoastal W/W US74/76 high-level bridge (crest -1.21 vs mark +1.90, -3.1 m: the whole +-40 m window is over water); Discharge Canal NC87 (-2.3 m); Royal Oak River US17 (+1.45 m); Alligator Creek (-1.0 m).
- **Verdict:** approach/road-crest elevation is usable to roughly +-1 m for short and medium bridges and culverts with embankment approaches, and is **biased low for long or high-level bridges**, so crest should be flagged unreliable when NBI structure length is large (I did not set that cut-off; 14 points are too few). The true deck height and low-chord are not obtainable from this data. Verification here is against ground/structure marks, not deck surveys.

## 5. Label review list
`data/phase0/florence_label_review.csv`: 81 Florence reports (pilot counties; closure wording or flood type) within 1 km of a v2 crossing, 58 of them Phase-0 closure candidates. Columns: report text, time, source, nearest crossing (set, quality, stream, road, distance), `road_name_match_nearest` yes/no, nearest crossing whose road the remark names, its distance, which road string matched, and blank `reviewer_decision / reviewer_crossing_id / reviewer_notes`. Sorted by distance to the named-road crossing. **Nothing is auto-accepted.** Known noise for you to reject: the road match also fires on cross streets used as landmarks ("near PROJECT RD", "near SIDBURY RD"), and tree/power-line closures with "blocked" wording (Whisper Creek Lane) are in the list.

## 6. Label threshold: >= 30 labels with a crossing on the named road within 500 m
- **Current count: 24 reports (23 unique crossings). Threshold NOT met.** Using seed (structure-based) crossings only: 9. Using good/fair crossings only: 9. Named-road crossing within 1 km: 43; within 100 m: 1.
- 24 is an upper bound before manual review, because cross-street landmark matches are counted. I therefore make **no validation claim** from these labels; they are candidates only.
- Reaching 30 needs about 6 more reviewer-accepted matches, which is plausible from the 19 reports between 500 m and 1 km, but only after your review.

## Task list
- [x] 1 RouteLink diff  - [x] 2 crossings v2  - [x] 3 recurrence thresholds  - [x] 4 deck check  - [x] 5 review CSV  - [x] 6 threshold count (24/30, not met)

Environment notes: installed `zstandard`; zarr/s3fs cannot resolve DNS here (aiodns), so S3 reads outside curl will fail; `data/phase0/raw/` holds the 269 MB RouteLink.
