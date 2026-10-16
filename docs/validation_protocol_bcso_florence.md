# Validation protocol G (Brunswick Sheriff's Office Florence calls), fixed 2026-10-14 BEFORE any call was snapped to a crossing or compared with any flow

Data: `data/bcso_florence/` (received from the Brunswick County Sheriff's Office, 2026-10-14; sha256 in `SHA256SUMS.txt`). Before this file was written, only row counts, date ranges, coordinate ranges and incident-type counts were looked at (road-flood calls 205, water rescues 194, tree/debris calls 419; Sept 12-24 2018; lon/lat in Brunswick County). No call was joined to anything. If a test fails it is reported as failed; no re-run with changed thresholds, distances, windows or crossing sets. A sha256 of this file is printed at the top of the report.

Labels are **hindcast, single-storm (Florence), scenario-level**: NWM v3.0 retrospective (free-running, no data assimilation). Nothing here is forecast skill or a closure probability. A call is a report that flooding was seen at a place and time, not an official closure; absence of a call is not absence of flooding. Dispatch call coordinates/time precision is unknown; see assumptions.

## A. Call sets
- W = rows of FlorenceWaterCalls.xlsx with IncTypeDesc "Storm-Roads (Flooding or Ice)" (primary). R = rows with IncTypeDesc "Water Rescue" (secondary; FlorenceWaterRescues.xlsx, de-duplicated against the Water Rescue rows of FlorenceWaterCalls by IncNo). T = FlorenceTreeCalls.xlsx (exposure control: where people call in a storm for a non-flood reason).
- Drop rows with missing coordinates; de-duplicate by IncNo. Time = IncDate + time of day of IncTime, **assumed America/New_York local time**, converted to UTC, floored to the hour. (Assumption stated, not tested; sensitivity S1 below.)
- Window E = 2018-09-12 00:00 to 2018-09-25 00:00 America/New_York (fixed, covers all calls).

## B. Crossings and reaches
- Crossing set: `data/phase2/t10/structures_nc.parquet` (NCDOT structures + NBI NC 2025, waterway-like names), each matched to the nearest NWM reach <= 100 m from `data/phase2/t15/nc_reaches.parquet`; **assessed** if q2 >= 1 cfs and q10 >= q2 (the T15 rule).
- A call is **snapped** to the nearest assessed crossing within **500 m** (Euclid., NC State Plane); calls with none are unsnapped and are reported, never analysed. No road-name matching (calls carry no road name). Sensitivity S2: 250 m and 1000 m.
- Per-call reach = the snapped crossing's reach. Flow: NWM v3.0 retro hourly m3s -> cfs (x 35.3147), E window for G2/G3, 1979-02-01..2022-12-31 September hours for G1.

## C. Tests (all three pre-declared; none dropped if it fails)
**G2, timing within the storm (primary).** For each snapped W call: P_e = percentile (strictly-below + half ties) of the reach's flow at the call hour among all hourly flows in window E on that reach. Under no timing information, mean P_e = 0.5. Statistic = mean P_e over snapped W calls; also share of calls whose reach flow at the call hour exceeds that reach's q2 vs share of all E hours on those reaches above q2. 95% CI: 10,000 bootstrap resamples of **reaches** (feature_id) as clusters, percentile method (single storm, so storm clusters = 1; reach clustering only partly handles spatial dependence). **Pass** if the CI lower bound of mean P_e > 0.5.
**G3, where (exposure-controlled, primary).** Unit = unique assessed crossing. Statistic s = peak flow in window E / q10 of its reach. Positives = unique crossings snapped by >= 1 W call. Controls = unique crossings snapped by >= 1 T call and by no W call. AUC = P(s_positive > s_control) + 0.5 P(tie), computed on reach-level (one value per reach, reach counted positive if any positive crossing, control otherwise if only control crossings) to avoid duplicating a reach's flow. CI: 10,000 bootstrap resamples of reaches. **Pass** if AUC CI lower bound > 0.5.
**G1, percentile against the 44-yr record (same form as protocol B).** For each snapped W call: P = percentile of reach flow at the call hour among all **September** hours 1979-2022 on that reach (reference includes Sept 2018); controls = 200 random September hours on the same reach excluding 2018-09-09..2018-09-28 (RNG seed 20261014); matched AUC (mean over calls of P(call flow > control flow) + 0.5 P(tie)); share above q2 and q10 for calls vs controls. Bootstrap by reach. **Pass** if AUC CI lower > 0.5 AND (share_gt_q2 calls - controls) CI lower > 0. Reported as **expected to pass trivially** (Florence was a record event); it is the comparability test, not the discriminating one.

## D. Secondary (reported, no pass/fail)
- G2 and G3 repeated for R (rescues) in place of W.
- S1: G2 with window-max +-6 h flow and with times shifted by +-1 h (time-zone sanity).
- S2: snap distance 250 m and 1000 m.
- Coverage: counts and share of W, R, T calls snapped, and the stream-order mix of snapped reaches.
- Where W calls snapped to a reach never above q2 in E (the model says "no flood"): list count and top reaches (misses).
- Reach-level: share of reaches with peak > q10 in E that have >= 1 W call within 500 m (reported with the T-matched comparison from G3, not as a stand-alone verdict).

## E. What results license
Pass = the hazard layer ranks times and places of Florence flooding reports in Brunswick above exposure-matched tree-call places and above random hours of the same storm. It is still one storm, hindcast, and call-based. It does not show closure probability, forecast skill, or isolation accuracy. Failing G3 would mean the layer does not discriminate where, as in T10-E1; that is reported as failed.

## Amendment 1 (2026-10-14, still before any flow was compared with any call)
The shell used for this analysis cannot reach the NOAA S3 bucket (proxy 403), so the Florence-window flows come from the existing local file `data/phase1/florence_nwm_v30_retro_hourly_m3s.parquet` (NWM v3.0 retro, 2018-09-13 00:00 UTC .. 2018-11-06 23:00 UTC, m3/s). Window E is therefore **effectively 2018-09-13 00:00 UTC .. 2018-09-25 04:00 UTC** (the first ~20 h of the originally defined window are missing). Direction of the effect: dropping those low pre-storm hours from the reference raises the reference distribution, which lowers each call's P_e, i.e. makes G2 harder to pass, not easier. Reaches not present in that file are dropped and counted. G1 needs the 1979-2022 September record, which is not available in this shell; it is run only if `python src/42_bcso_florence.py fetchSept` is run on a machine with S3 access, otherwise it is reported as not run. No other definition changed.
