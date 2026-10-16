# Phase 2 / G: Brunswick Sheriff's Office Florence calls vs the hazard layer

Run 2026-10-14. Protocol: `docs/validation_protocol_bcso_florence.md` (sha256 at run time `4e3f4e6df816d3c34055697b9a2177519944ecf393dd979266052af20ca72bb2`, includes Amendment 1), written before any call was snapped or compared. Code: `src/42_bcso_florence.py`; outputs `data/phase2/bcso/`. Hindcast (NWM v3.0 retro), single storm (Florence), scenario-level; calls are reports, not official closures. Source of calls: Brunswick County Sheriff's Office (data/bcso_florence/).

## Verdicts
| Test | Result | Verdict |
|---|---|---|
| **G2** timing within Florence (42 road-flood calls, 26 reaches) | mean within-storm flow percentile at call hour 0.846 [0.797, 0.892]; 90.5% of calls above q2 vs 47.4% of all window hours | **PASS** |
| **G3** where, vs tree-call places (26 vs 16 reaches) | AUC 0.635 [0.445, 0.815]; peak/q10 median 4.99 vs 3.00; 100% vs 87.5% of reaches above q10 | **FAIL** (CI includes 0.5) |
| **G1** vs 44-yr September record | not run: needs NOAA S3, unreachable from this shell | not run |

Secondary (no pass/fail): rescues G2 mean 0.849 [0.759, 0.911] (n=37); rescues G3 AUC 0.684 [0.503, 0.856] (n=22 vs 18; borderline, one of several looks, do not headline); window-max +-6 h G2 0.911; time shifts -1/+1 h G2 0.832/0.849 (time-zone assumption not fragile); 1000 m snap G2 0.857, G3 AUC 0.529 [0.386, 0.669]; 250 m G3 too few reaches. No road-flood call sits on a reach that never exceeded q2.

## Coverage (the main limitation)
Only 42 of 205 road-flood calls (20.5%) snap to an assessed crossing within 500 m (37/194 rescues, 41/410 tree calls). Snapped calls: 27 crossings, 26 reaches (stream orders 1-6, mostly 2-3). The other ~80% have no modeled crossing nearby (coastal, tidal, small drainage, or structures not in the NCDOT/NBI waterway set), so these tests say nothing about them.

## What this licenses
- The layer is good at **when**, again: at the hours people called in flooded roads, flow on the nearest modeled reach is high within the storm. Independent of the LSR-based T10-B/C.
- The layer is **not shown to be good at which places**: during Florence nearly every modeled reach in the area exceeded q10, so the layer cannot separate flood-call places from tree-call places (G3 fails, same pattern as T10-E1). Report as failed.
- Do not claim closure probability, forecast skill, or isolation accuracy from this. One storm, ~26 reaches, calls not closures.

## Caveats
- Times assumed America/New_York local; shifts of 1 h change nothing.
- Window E effectively starts 2018-09-13 00:00 UTC (Amendment 1); conservative for G2.
- G3 power is low (26 vs 16 reaches); a pass or fail here is weak evidence either way.
- Reach bootstrap only partly handles spatial dependence.
- To finish G1 on a machine with S3 access: `python src/42_bcso_florence.py fetchSept` then `python src/42_bcso_florence.py tests`.
