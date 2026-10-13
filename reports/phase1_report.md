# FloodLens Lifelines - Phase 1 report (Cape Fear pilot: New Hanover, Brunswick, Pender)

Run 2026-10-10. Code `src/phase1/`; outputs `data/phase1/` (first pass) and `data/phase1b/` (this pass). `ml_full_table` untouched. All times UTC. Nothing here is validated against observed closures.
**Every closure result is a SCENARIO** (flow above a recurrence level on the reach), not a probability and not a calibrated closure model. Every table names its crossing set:
- **seed** = 250 hazard-ready structure-seeded crossings (NCDOT/NBI bridges, culverts, pipes on named waterways);
- **seed_reliable** = the 147 of those that pass the provisional crest-elevation test (short, low-order, non-tidal; cutoffs from only 14 NGS marks);
- **seed_plus_osm_secondary** = seed plus 1,333 OSM-derived crossings (mostly order-1, `poor` quality) = 1,583. **Sensitivity only.**

## What the engine does
1. **Hazard.** For each crossing's NWM reach and hour, flow is compared with the reach's recurrence flows (2/5/10/25/50-yr, NOAA OWP `static_nwm_flowlines`). Crossings with no matched reach, or 2-yr flow below 1 cfs, are not assessed (1,337 of 2,920; never filled).
2. **Closure scenarios.** A crossing is closed when flow exceeds level RL2, RL5, RL10, RL25 or RL50. `REF_3.64xHWT` (3.64 x NWM high-water threshold, the median flood-stage/threshold ratio from the calibration bridge) is kept as a labelled reference, not a recurrence level.
3. **Network.** OSM drive graph (NC + SC extracts), 246,088 junction-to-junction segments / 40,774 km, covering the three counties plus 40 km. A closed crossing removes the segment it is snapped to (<= 50 m).
4. **Routing.** Multi-source shortest path (scipy) from facilities to 6,940 Census 2020 block centroids (population-weighted; no addresses). Per origin and closure state: reachable, travel time, detour minutes, baseline-path critical crossing, redundancy (facilities within 30 min for hospitals). Facilities: ED acute/critical-access hospitals (11), fire stations (214 snapped), and derived exit points.
5. **Replay.** The closure state is recomputed per hour. Hindcast = NWM v3.0 retrospective (free-running), 2018-09-13 to 2018-11-06. Forecast = archived operational NWM **v1.2-era** short-range forecasts, **starting 2018-09-17 01:00 only**.

**The forecast pass starts 2018-09-17 and cannot cover the onset of Florence** (landfall and the first flooding were 09-14 to 09-16). It uses v1.2 forecasts (00Z/12Z inits, leads 1-12 h, 2018-09-17 to 09-25; 192 of 192 expected files verified). At its first hour, 217 of 250 seed crossings are already above their 2-yr flow, so first-exceedance times are left-censored and not reported for them.

## 1. Recurrence bins (peak flow vs the reach's recurrence flows)
Hindcast, bin of the **peak** flow (counts of crossings). `data/phase1b/recurrence_*.csv` has per-crossing peak bin, first exceedance of 2/10/50-yr, hours above each, and the 3.64xHWT reference.

| Crossing set | County | <2yr | 2-5 | 5-10 | 10-25 | 25-50 | >50 |
|---|---|---|---|---|---|---|---|
| seed | Brunswick | 0 | 4 | 5 | 10 | 13 | 89 |
| seed | New Hanover | 0 | 0 | 0 | 0 | 11 | 22 |
| seed | Pender | 0 | 0 | 0 | 1 | 1 | 85 |
| seed_reliable | Brunswick / New Hanover / Pender | 0/0/0 | 3/0/0 | 2/0/0 | 4/0/0 | 8/9/1 | 49/12/58 |
| seed_plus_osm_secondary (sensitivity) | Brunswick | 7 | 84 | 41 | 64 | 148 | 589 |
| seed_plus_osm_secondary (sensitivity) | New Hanover | 0 | 0 | 0 | 7 | 113 | 166 |
| seed_plus_osm_secondary (sensitivity) | Pender | 0 | 0 | 0 | 3 | 19 | 333 |

(9 seed crossings fall outside the county polygons and are not in the county rows.) Peak bins saturate: 205 of 250 seed crossings exceed their 50-yr flow in the hindcast, so the bin separates little; first-exceedance time separates more. Seed crossings, hindcast, median hours above 2/10/50-yr: Brunswick 108/35/5, New Hanover 87/19/2, Pender 144/64/26.

**Earliest 2-yr exceedance, ranked within county (hindcast, crossing set seed; full list in the CSV).**

| County | Rank | Crossing | Stream / road | First >2yr | First >10yr | Peak bin |
|---|---|---|---|---|---|---|
| Brunswick | 1 | V2_0232 | Lewis Swamp / SR1410 | 09-14 04:00 | 09-14 13:00 | 25-50 |
| Brunswick | 2 | V2_0045 | Liliput Creek / NC133 | 09-14 05:00 | 09-14 16:00 | >50 |
| New Hanover | 1 | V2_0134 | Mott Creek / SR1242 | 09-14 05:00 | 09-16 05:00 | >50 |
| New Hanover | 1 | V2_0114 | Motts Creek / River Rd | 09-14 05:00 | 09-16 05:00 | >50 |
| Pender | 1 | V2_0199 | Mullet Run / SR1561 | 09-14 10:00 | 09-15 10:00 | >50 |
| Pender | 2 | V2_0217 | Holly Shelter Creek / SR1580 | 09-14 11:00 | 09-15 07:00 | >50 |

Forecast pass (v1.2, from 09-17): 217 of 250 seed crossings left-censored at 2-yr, 20 never exceed it in the window, only 13 have an observable first exceedance; ranking by time is not meaningful there.

## 2. Facilities and graph (what was added)
- **Hospitals** (CMS Hospital General Information, geocoded with the Census geocoder; ED flag from CMS): 16 within 40 km of the boundary, 13 with ED, **11 acute or critical-access with ED** used for access (Phase 1: 4). Added: Onslow Memorial, Columbus Regional, Vidant Duplin, Sampson Regional, Cape Fear Valley-Bladen, Conway Medical Center, Grand Strand Regional. Not geocoded (4 near the region): NMC Camp Lejeune (military), Womack AMC, Betsy Johnson, MUSC Marion; 27 of 186 NC/SC CMS hospitals did not geocode.
- **Fire stations:** **220** after merging (110 USGS National Map only, 92 matched OSM+USGS within 150 m, 18 OSM only); 214 snapped. Phase 1: 40 (OSM only, 10 km). Official source: USGS National Map "Fire Stations/EMS Stations" layer (HIFLD-derived, 2021 vintage; one FCODE, so EMS-only sites cannot be separated). HIFLD itself could not be confirmed available.
- **Graph:** 10 km -> 40 km buffer, adding the SC extract (Geofabrik, 164,189,648 B) so roads and hospitals across the state line are reachable. Buffer is a bounding box of the 40 km zone.

## 3. Outside connectivity and hospital access
**Exit points, derived from the graph** (motorway/trunk/primary segments crossing the outer boundary of the three-county union; `data/phase1b/exits.csv`): I-40 (34.719, -77.945); US-421 (34.680, -78.157); US-17 north (34.478, -77.574); US-17 south at the SC line (33.895, -78.592); US-74/US-76/NC-87 west (34.308, -78.198); US-117/NC-11 (34.717, -77.979). 11 secondary-road exits (NC-904, NC-210 x2, NC-130, NC-211, NC-50, NC-53, NC-11/53, SC-179, SR-1303, Willard Rd) are in a second test set.

Loss = share of origins (baseline-reachable only) with **no** path. Hindcast, RL2 = flow above the 2-yr flow. Numbers are the **peak** share and people, with hours at >= 1% of the group. N. NH = New Hanover latitude >= 34.28 (my arbitrary split); Wilm./S. = below.

**Lose all paths to major exits (hindcast, scenario RL10; first >=1% / hours >=1%):**

| Crossing set | Brunswick | Pender | NH Wilm./S. | NH north |
|---|---|---|---|---|
| seed | 31.6% (42,883 people), 09-14 14:00, 37 h | 2.9% (1,687), 09-15 16:00, 71 h | 0 | 0 |
| seed_reliable | 0.9% (1,195) | 0.7% (394) | 0 | 0 |
| seed_plus_osm_secondary (sensitivity) | 73.8% (100,225) | 45.7% (26,919) | 1.8% (3,380) | 40.4% (14,612) |

Under seed, the Brunswick loss is dominated by Lockwoods Folly River/NC-211 (V2_0056, 14,088 people), Jump and Run Creek/NC-133 (V2_0280) and Orton Creek/NC-87 (V2_0009); under REF_3.64xHWT the same three. The Pender loss under seed is Burgaw Creek/SR1411, NE Cape Fear River/NC-53 and Long Creek/SR1345. Critical crossing = first closed crossing on the origin's baseline path, not a minimum cut. Under RL50 (the highest level), seed loss is Brunswick 2.1%, Pender 2.7%.

**Origin -> ED hospital access (hindcast; same sets):**

| Crossing set | Scenario | Brunswick | Pender | NH Wilm./S. | NH north |
|---|---|---|---|---|---|
| seed | RL2 | 4.3% (5,872) | 2.9% (1,687) | 0 | 0 |
| seed | RL10 | 3.7% (5,040) | 2.9% (1,687) | 0 | 0 |
| seed_reliable | RL2 / RL10 | 0.9% (1,195) | 0.7% (394) | 0 | 0 |
| seed_plus_osm_secondary (sensitivity) | RL10 | 66.6% (90,439) | 26.1% (15,349) | 1.8% (3,380) | 40.4% (14,612) |

Baseline mean drive minutes to the nearest ED hospital (no closures, population weighted): Brunswick 16.7, Pender 26.1, NH Wilm./S. 9.6, NH north 17.6. Baseline-unreachable people (islands/graph gaps) are excluded: Brunswick 631, Pender 341, NH Wilm./S. 5,031, NH north 918.

**Forecast pass (v1.2, from 09-17; seed):** Brunswick exit loss up to 32.2% at RL2 but 0.5% at RL10; Pender 2.9% at RL2; New Hanover 0. The RL2 losses are already present at the first forecast hour, so onset and duration are not observable. seed_reliable <= 0.9%.

## 4. Wilmington result (stated first, as requested)
- **Crossing sets seed and seed_reliable: Wilmington/south New Hanover and northern New Hanover lose no access to ED hospitals and no access to major exits in any closure scenario, hindcast or forecast.** This holds even at RL2, where up to 238 seed-crossing segments are closed at once (RL10: 216; RL50: 125; seed_reliable RL2: 139).
- **seed_plus_osm_secondary (sensitivity only; mostly order-1, poor-quality crossings):** New Hanover shows losses (RL10, ED access: Wilm./S. 1.8%, N. NH 40.4% = 14,612 people; first >= 1% at 09-14 11:00; last 09-16 13:00 to 09-16 22:00 depending on group). For ED access the first blocking crossings are Smith Creek at SR1302 (a structure crossing, V2_0124, with other closures), North College Road (OSM) and Ness Creek/Oakley Rd (north), and Manly Ave, Smith Creek SR1175 (Wilmington/south); for exits they are Smith Creek at MLK Pkwy (OSM), SR1175, John Jay Burney Fwy and North College Road (OSM). Do not read this as the model's estimate for Wilmington.
- Reading: with the structure crossings I have, the model finds no way in which flow alone cuts Wilmington off from its own hospital or the exits, which is a statement about my crossing inventory and hazard rule as much as about Florence. It cannot see storm surge, tide or pluvial flooding (limitations).

## 5. Label check with negatives (24 label-matched reports; crossing set: percentile among all seed crossings in the same county)
15 of 24 have an assessable crossing (8 structure crossings, 7 OSM-secondary ranked against the seed distribution); 9 lack a matched reach or valid threshold.

| Series | Metric | Reported crossings, median percentile | Random-draw null (mean of medians) | One-sided p |
|---|---|---|---|---|
| hindcast v3.0 | peak recurrence bin | 63.2 (all 15 are in the >50-yr bin, as are 82% of seed crossings) | 58.0 | 0.58 |
| hindcast v3.0 | earliest 2-yr exceedance | 50.0 (mean 59.6; 12 of 15 >= 50, 6 of 15 >= 75) | 49.9 | 0.78 |
| forecast v1.2 | peak bin (09-17 on) | 51.5 | 50.2 | 0.53 |
| forecast v1.2 | earliest 2-yr | 33.3 (n = 3; 11 of 15 censored) | 44.9 | 0.98 |

**Reported crossings are not ranked higher than other crossings in their county** on either metric, in either series. The hazard layer cannot separate reported from unreported crossings with this label set, and the set is 15 reports, positives-only labels, unreviewed. Threshold of 30 labels with a crossing on the named road within 500 m: **24, not met**; no validation is claimed.

## 6. To verify (real-world check list; nothing below is claimed as fact)
- NCDOT/DriveNC closure and reopening times for I-40, US-421, US-17, US-74/76, US-117/NC-11, NC-211, NC-133, NC-87 and NC-53 (ask NCDOT for the TIMS archive for Sep-Oct 2018).
- Whether Wilmington/New Hanover residents kept road access to New Hanover Regional Medical Center during Sep 14-20, and whether exits from the region were all closed (New Hanover County Emergency Management after-action, Novant Health, local news, NC Emergency Management).
- Whether southern Brunswick (NC-211 / Lockwoods Folly, NC-133, NC-87) was cut off from hospitals and exits; whether Dosher and Novant Brunswick stayed accessible (Brunswick County EM).
- Whether Burgaw/Pender were cut off from Pender Memorial and exits (NC-53, US-117, I-40, NE Cape Fear River).
- NWS ILM storm summary, NHC Florence report and USGS peak stages/high-water marks for timing and magnitude of the river flooding; the NWM hindcast peak timing against gauges.
- Any surge, tide or ocean overwash closures (US-421 along the river, barrier islands) that this system cannot represent.

## 7. Limitations
Full list in `reports/phase1_limitations.md`. In short:
- **Surge/tide/coastal flooding not in the hazard** (NWM channel streamflow only; NOAA treats total water level as a separate SCHISM-based product from v3.0, one-way coupled; the 2018 forecasts had none). Pluvial/urban drainage, culvert capacity, debris, scour and deck height also absent.
- **Thresholds:** 137 of 3,836 reaches have a 2-yr flow of 0 (excluded, never filled); order-1 reaches are the NWM's weakest and make up almost the whole OSM-secondary set; the peak bin saturates (205 of 250 seed crossings above the 50-yr flow in the hindcast).
- **Recurrence flows:** only documentation is the field alias; the derivation (and "17c") is unverified. 3.64xHWT is a reference from 100 gauged reaches, not a probability.
- **Labels:** positives only, 24 (not 30), 15 assessable, unreviewed, coordinates rounded to ~1 km; no validation claimed.
- **Replay inputs:** hindcast is free-running (no data assimilation); forecast pass is v1.2, starts 2018-09-17, uses 00Z/12Z inits with leads 1-12 h, and cannot show onset.
- **Network/facilities:** OSM defaults for speed, no turn restrictions; segment-level closures; hospitals only those that geocoded; fire stations from an older (2021) USGS layer plus OSM; exits are major roads only (secondary-road exits tested separately in `p8_*`); NH north/south split at latitude 34.28 is arbitrary.
- **seed_reliable cutoffs** (length < 35 m, order <= 3, not tidal) come from 14 NGS marks and are provisional.

## Files
`data/phase1b/`: `recurrence_{hindcast_nwm_v30_retro,forecast_nwm_v12_shortrange}.csv`, `exits.csv`, `hospitals_40km.csv`, `fire_stations_40km.csv`, `p8_*_loss_summary.csv`, `p8_*_critical_crossings.csv`, `p9_label_negatives_*.{csv,json}`, `replay_*` parquet. `data/phase1/p6b_label_vs_replay.csv` is the 24-report table.
