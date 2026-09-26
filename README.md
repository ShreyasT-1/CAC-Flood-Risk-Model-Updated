# Coastal Flood Risk Model for Congressional App Challenge

A predictive model for coastal flood insurance risk, covering regions within 30 miles of the coastline from Maine to Florida (14 East Coast states).

## What the model predicts

Each row is one coastal tract in one time window. The model predicts flood insurance claims in a later period using only information available earlier — no leakage from the future.

- **Targets:** claim counts, and claims occurring outside FEMA-designated high-risk zones, over the target window (with policy-years as exposure).
- **Train:** features from 2009–2013 → claims in 2014–2017.
- **Test:** features from 2013–2017 → claims from 2018 onward (includes Hurricanes Florence, Dorian, and Helene).
- **Val:** a held-out set of whole counties, excluded from training.
- **Predict:** current tracts scored with no known target (production inference).

## Data sources

| Source | Provides |
|---|---|
| OpenFEMA NFIP claims | Claim counts, payments, and zones by tract and year |
| OpenFEMA NFIP policies | Policy-years by tract and year, in and out of flood zones |
| Census ACS / Gazetteer | Housing units, land/water area, tract centroids |
| Natural Earth coastline | Distance to coast |
| USGS elevation service | Elevation at tract centroid |
| NOAA Atlas 14 | 100-year, 24-hour rainfall |
| FEMA NFHL map service | Share of tract area in high-risk flood zones |
| USGS high-water marks | Historical flood marks near each tract |

## Input features

**Claims history:** `claimRateFeat`, `outsideClaimRateFeat`, `paidPerPolicyYearFeat`, `claimRateSlope`, `claimsHistPerHousingUnit`

**Insurance & coverage:** `sfhaPolicyShare`, `takeUpRate`

**Flood zone map:** `sfhaAreaShare`, `moderateAreaShare`

**Historical flooding:** `hwmMarksBefore`

**Geography:** `lat`, `lon`, `landSqmi`, `waterShare`, `distToCoastMi`

**Physical:** `elevMeanFt`, `elevMinFt`, `elevRangeFt`, `rain100yr24hrIn`


