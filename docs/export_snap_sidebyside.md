## Origin snap: phase-1 snap vs phase-2 re-snap (checked 2026-10-12)
The phase-2 re-snap moved blocks that the phase-1 snap had left on tiny disconnected road fragments onto the largest connected part of the graph. It cut baseline-unreachable people but **failed a manual check**, so **this export uses the phase-1 snap**. Check (`src/validation/60_resnap_check.py`, `data/phase2/resnap_check/resnap_check.csv`): 30 random blocks that were unreachable under the phase-1 snap and reachable under the re-snap, plus all 21 blocks the re-snap dropped.
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
