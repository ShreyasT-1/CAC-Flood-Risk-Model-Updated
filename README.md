# FloodLens Lifelines

**Floods don't just damage property. They cut people off from help.**

FloodLens Lifelines forecasts when, and for how long, a neighborhood, a dialysis clinic or a nursing home may lose its road route to the nearest hospital and fire station during a flood. Insurance maps ask whether a building is in a flood zone. We ask a harder question: **can this address still reach help?**

`3 counties` · `250+ structure-seeded crossings` · `6,940 neighborhoods modeled` · `11 emergency hospitals` · `220 fire stations` · `1 hurricane replayed hour by hour`

---

## The problem nobody maps

When Hurricane Florence hit Cape Fear in 2018, the most dangerous flooding came days after the rain stopped. Rivers crested, bridges and low crossings closed, and whole communities lost their routes out. Flood tools tell you where the water will be. None of them answer what happens to the *road network* around you, and ambulances and fire engines drive roads, not floodplains.

## What it does

Pick an address. FloodLens Lifelines shows:

- **Time to isolation.** The first hour a route to help may break.
- **Isolation duration.** How long access may stay cut.
- **Detour cost.** How many extra minutes the surviving route adds.
- **Critical crossing.** The one bridge or culvert whose failure matters most to you.
- **Route redundancy.** How many hospitals and fire stations you can still reach.
- **What Breaks First.** Every crossing in the region, ranked by how many people lose access if it fails, not by how likely it is to flood.

All results are scenario-based and probabilistic. We never tell anyone a road is safe.

## The pipeline

```
NOAA National Water Model ─┐
USGS stream gauges ────────┤
NCDOT + NBI structures ────┼─►  Crossing-level hazard  ─►  Dynamic road graph  ─►  Address-level
1 m lidar terrain (HAND) ──┤     (recurrence-flow           (246,088 segments,        isolation
FEMA flood zones ──────────┤      scenarios per hour)        closures per hour)       forecast
CMS hospitals / USGS fire ─┘                                 multi-source routing
```

1. **Hazard.** For every hour, each crossing's reach flow is compared with its 2- to 50-year recurrence flows from the National Water Model.
2. **Terrain.** 1 m lidar gives each crossing's approach elevation and height above the channel, so long, high bridges aren't treated like low culverts.
3. **Network.** A closed crossing removes its road segment from a drive graph covering three counties plus a 40 km buffer.
4. **Routing.** Multi-source shortest paths run from every hospital and fire station to 6,940 Census block centroids, recomputed each hour.
5. **Output.** Per-neighborhood time to isolation, duration, detour, redundancy and the critical crossing.

## What makes it different

| Typical flood tool | FloodLens Lifelines |
|---|---|
| Is this parcel in a flood zone? | Can this address still reach a hospital? |
| Static map | Hour-by-hour dynamic network |
| Hazard only | Hazard × network consequence |
| Ranks places by flood chance | Ranks crossings by *people cut off* |
| Asks you to trust it | Reports where it is wrong |

## Proven against a real disaster

We replay **Hurricane Florence (2018)** hour by hour, from Sept 13 to Nov 6, as both a hindcast on the NWM retrospective and a replay of the archived operational forecasts. We tested our own results against 24 matched road-closure reports with a random-draw null, and we publish the outcome whichever way it goes. [TBD: updated label test after manual review.]

## Built to keep learning

- **Live forecast archive.** An hourly job archives every NWM short-range forecast cycle (18-hour leads) with its model version. This builds the real forecast-versus-reality dataset for the next storm.
- **Gauge-stage nowcast.** A gradient-boosted model trained on 236 gauges, 90 storm events and 8 years of data predicts flood-stage exceedance up to 12 hours ahead. It is tested on held-out events, 34 unseen gauges and Florence against persistence baselines, with bootstrap confidence intervals. [TBD: final onset-recall numbers after retraining.]
- **A leakage-tested pipeline.** Splits are by event and by gauge, statistics come from training data only, and automated tests recompute features from truncated data to prove nothing looks into the future.

## Radical about its limits

Most tools hide their weak spots. This one lists them:

- It models river flooding only. **Storm surge, tide and street flooding are not included.**
- Closure scenarios are not calibrated closure probabilities.
- Closure labels are sparse and positive-only, so we do not claim validation.
- Bridge deck height is not available from any public source, so we estimate it from lidar and flag where that fails.
- We **never** say a road is safe.

## Where this goes

The Cape Fear pilot is the proof of concept. The data sources are national: NWM, USGS, NBI, CMS, Census, OSM and 3DEP. The same pipeline can cover any U.S. coastal region. The end goal is a tool emergency managers can use *before* the water arrives. That means evacuating the dialysis center before its road closes, and pre-positioning an ambulance on the right side of the river.

## Repository

```
src/            numbered pipeline: gauges → crosswalk → hazard → network → routing → ML
src/phase1/     routing engine, recurrence, connectivity, label tests
data/           raw inputs, derived tables, exports (large files not committed)
reports/        phase reports, data cards, model evaluations
docs/           archiver setup, ML handoff, claims, export schema
```

## Data and credits

NOAA National Water Model and OWP, USGS NWIS and 3DEP, NCDOT, FHWA National Bridge Inventory, FEMA NFHL, CMS Hospital General Information, U.S. Census Bureau, OpenStreetMap contributors, NCAR/GDEX Stage IV. Please follow each provider's terms.

*Built by Nishaanth Jay and Shreyas T. for the Congressional App Challenge.*
