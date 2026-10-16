# PTC8 (September 2024) ranking test - T17, TEST event

Written 2026-10-16. Script: `src/81_ptc8_test.py`. Numbers: `data/phase2/ptc8/ptc8_results.json` (scored crossings: `ptc8_crossings_scored.csv`; flow meta: `ptc8_flow_meta.json`). Closure table: `data/derived_new/ptc8_closures.csv`.

## Verdict
**Registered rule: PASS, but on thin evidence. Do not present it as an independent validation.**

| | PTC8 (this test) | Same storm inside C5 (T15 event E4) |
|---|---|---|
| Closure source | TIMS `confirmed_closure`, 2024-09-14..25, areas B and B_buffer: **35 records**, 7 counties | TIMS history, statewide, points + lines: 54 records, 15 counties |
| Crossings scored | 842 (assessed, counties with >= 1 record) | 1,927 |
| Positives (within 100 m) | **8** | 26 |
| AUC of peak flow / q10 | **0.729** | 0.819 |
| 95% CI (bootstrap over counties) | **0.569 - 0.859** | 0.637 - 0.915 |
| Rule: lower bound > 0.5 | PASS | (part of the pooled C5 result) |

Sensitivities (all the same direction): 250 m labels 0.789 (0.615-0.906, 13 positives); without the three > 14-day records 0.729 (0.566-0.855, 8 positives); peak / q2 instead of q10 0.734 (0.616-0.855). Precision at the q10 line 2.9% (base rate 0.95%), recall 37.5%: 3 of 8 positives were above their 10-year flow, against 12.2% of negatives.

## Why this is not a held-out second storm
1. **PTC8 is already in C5.** It is T15 event E4 (2024-09-16..19, "Columbus, Brunswick, Duplin, Anson, Sampson"). This test re-slices the same storm with a smaller closure set, so it adds no independent evidence. It is held out only in the sense that nothing was fitted or tuned on it: the metric is the raw peak/q10 ratio, with no model.
2. **Only 8 positives, and the bootstrap is fragile.** 8 of the 35 closure records (23%) have an assessed crossing within 100 m; the other 27 are not scored at all. The 7 county clusters hold 0 to 2 positives each (Pender 0), so resampling counties swings the AUC a lot and the interval should be read as loose. A per-county AUC cannot be computed (every county has fewer than 3 positives).
3. **The unified file gives points only** (DriveNC route + milepost, "not surveyed to the crossing"); `src/52_t15_crossings.py` also used closure lines for E4, which is why E4 has more positives.
4. **Positives only.** Unrecorded closures sit in the negatives (same as C5); the precision numbers are not literally interpretable.
5. **Order and structure strata are too small** to read (stratum AUCs only where >= 5 positives: stream order >= 3 0.605 with 5 positives; reliable-analogue 0.721 with 6; not tidal 0.712 with 7).

## Data
- **Flow:** NWM operational analysis (`analysis_assim`, `channel_rt`, `tm00`) from the public GCS mirror `gs://national-water-model`, same read as `src/53_t15_flows.py`, model version in the files `v3.0`, 147 of 147 hourly files, 709 reaches, window 2024-09-14 16:00 to 2024-09-20 18:00 UTC (first start - 2 days to last start + 1 day, the Amendment 4 rule). Not the retrospective (it ends 2023-02-01). Assimilated flows, so ratios are not directly comparable with the hindcast tests (`docs/claims.md` section 4).
- **Crossings, reaches, q2/q10, assessed rule:** the same ones as `src/52_t15_crossings.py` (read from `data/phase2/t15/t15_crossing_sets.parquet`, geometry from `data/phase2/t10/structures_nc.parquet`).
- **Not used:** `data/v2/obs_hourly_ext.parquet` and `data/v2/rain_fcst.parquet`. The ranking test needs only the NWM flow and the closure points; no gauge or rain feature is in it (as in C5).

## Closure records (what the table holds)
35 records: Columbus 14, Brunswick 8, Duplin 5, Sampson 3, Bladen 2, Pender 2, Jones 1; all from NCDOT TIMS history. Start times 2024-09-16 16:57 to 2024-09-19 17:33 UTC. **End times are operator-entered** (the clear time as logged, may be an estimate or stale).
- **Probable structural damage (duration > 14 days), flagged, 3 records:** NC-211 near Southport (31.5 d, "road wash out"), SR-1406 north of Bolivia (44.0 d, "road is under water at Bell Swamp Connection NE"), SR-1529 south of Leland (42.0 d, "road wash out"). They are kept as positives in the primary test and the result is the same without them, because **none of the three is within 100 m of an assessed crossing**. They are excluded from the timing statistics below.
- **Timing (descriptive, not a claim; 32 records not flagged, end time present):** median closure duration 2.02 days (IQR 0.92-2.22). For the 8 positives, the closure start minus the hour of the NWM peak at the matched reach: median +4.3 h (IQR -19.4 to +7.9 h; positive = the record starts after the flow peak). Start times are when an operator entered the closure, not when water reached the road.

## Rules (fixed before the first run; this test is not in `docs/validation_protocol.md`)
Metric, bootstrap and pass rule copied from `src/54_t15_test.py` (AUC of peak/q10, positives vs negatives; county-cluster bootstrap, 10,000 draws; pass if the lower bound > 0.5). No threshold, feature or label rule was changed after seeing a result. The script was run twice: the second run only added the count of closure records with a crossing within 100 m; all numbers were identical.

## Website
**PTC8 was not added to the site as a replay.** A replay needs the routing engine run for the event (blocks, hospitals, detours) and none exists for PTC8, and the flow-ratio ranking here is a weak, non-independent result. The Florence replay stays the only replay.

## Suggested wording if you approve a claim (not added to `docs/claims.md`)
"In the 2024 PTC8 flood (already one of the nine T15 storms), crossings within 100 m of 8 recorded NCDOT closures had higher modelled peak-flow ratios than other assessed crossings in the same seven counties: AUC 0.73 (95% CI 0.57-0.86). Only 8 of 35 closure records matched a crossing, so this is a re-slice of the C5 evidence, not independent validation."
