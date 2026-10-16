"""Build the SAMPLE / PREVIEW export in export/sample/ (static JSON + GeoJSON for the website preview).
Reads real pipeline outputs read-only; writes only into this folder. Real values come from the Florence hindcast replay
(data/phase2/engine, phase-1 snap, ED hospitals, crossing set `seed`, scenario RL10) and data/export/. Every value the pipeline
has not computed (isolation probability and everything derived from it, crossing flood probability, isolation tolerance) is a
PLACEHOLDER marked "synthetic": true. Run from the lifeline repo root:  python export/sample/build_sample.py"""
import json, math, os, string, datetime as dt
import numpy as np, pandas as pd, geopandas as gpd, shapely

OUT = os.path.dirname(os.path.abspath(__file__)) + os.sep
E = "data/phase2/engine/replay_hindcast_base_"           # phase-1 snap = the published export build
FAC, CSET, SCEN = "hospital_ED_acute", "seed", "RL10"
T0, NH, LOOK = pd.Timestamp("2018-09-15 12:00"), 18, 6   # 18 replay hours + 6 h look-ahead used only to shape the placeholders
CFS = 35.3146667
RNG = np.random.default_rng(20261013)
STAMP = "SAMPLE / PREVIEW - not validated, not for emergency use"
R = lambda v, n=2: None if v is None or (isinstance(v, float) and not math.isfinite(v)) else round(float(v), n)
real = lambda v: {"value": v, "synthetic": False}
synth = lambda v: {"value": v, "synthetic": True}

# Sample locations. Residential = blocks from the real 25-block sample (data/export/address_report_sample.json).
# Dialysis / nursing-home entries are PLACEHOLDER facilities: no dialysis or nursing-home inventory exists in the pipeline, so each is
# put at a real Census block centroid and given a generic name. Picked by hand to show a range of hindcast outcomes (not a random sample).
SITES = [
    ("S01", "dialysis", "Sample dialysis site A (placeholder)", "371419204033001"),
    ("S02", "dialysis", "Sample dialysis site B (placeholder)", "370190206013096"),
    ("S03", "dialysis", "Sample dialysis site C (placeholder)", "371290120083000"),
    ("S04", "nursing_home", "Sample nursing home A (placeholder)", "370190203111019"),
    ("S05", "nursing_home", "Sample nursing home B (placeholder)", "371419202042042"),
    ("S06", "nursing_home", "Sample nursing home C (placeholder)", "370190201022035"),
    ("S07", "residential", None, "370190203113023"),
    ("S08", "residential", None, "370190203161013"),
    ("S09", "residential", None, "371419205012003"),
    ("S10", "residential", None, "371290121082015"),
]
TOLERANCE_H = {"dialysis": 48, "nursing_home": 72, "residential": 72}   # placeholder assumptions, not sourced inputs

# ---------- real: hindcast closure states per hour ----------
hs = pd.read_parquet(E + "hour_state.parquet")
hs = hs[(hs.facility_type == FAC) & (hs.crossing_set == CSET) & (hs.scenario == SCEN)].set_index("hour").sort_index()
hours = pd.date_range(T0, periods=NH + LOOK, freq="h")
state = hs.loc[hours, "state_id"].values
ids = [s[3] for s in SITES]
os_ = pd.read_parquet(E + "origin_state.parquet", filters=[("facility_type", "=", FAC), ("crossing_set", "=", CSET), ("scenario", "=", SCEN)])
os_ = os_[os_.state_id.isin(set(state))]
AFF = {(r.state_id, r.geoid20): dict(lost=not bool(r.reachable), detour=R(r.detour_min, 1), crit=r.critical_crossing_baseline_path if isinstance(r.critical_crossing_baseline_path, str) else None, red=int(r.redundancy))
       for r in os_.itertuples()}
base = pd.read_parquet(E + "baseline.parquet"); base = base[base.facility_type == FAC].set_index("geoid20")
assert base.loc[ids, "baseline_reachable"].all(), "a sample block has no baseline route (not assessed)"
blocks = pd.read_csv("data/export/blocks_export.csv", dtype={"geoid20": str}).set_index("geoid20")

def block_hour(sid, g):
    """Real hindcast state of block g in closure state sid. The engine stores only affected blocks (lost access, slowed > 1 min, or
    redundancy changed; src/22_engine_p2.py), so a missing row = reachable, change <= 1 min (reported as 0), baseline redundancy."""
    return AFF.get((sid, g)) or dict(lost=False, detour=0.0, crit=None, red=int(base.loc[g, "baseline_redundancy"]))

# ---------- placeholders shaped by the real replay (agree with it by construction; say nothing about model skill) ----------
P_FLOOR = 0.03   # placeholder for blocks the replay never touches in the window + look-ahead (flat, no noise)
def placeholder_prob(rows, base_red):
    sev = np.array([1.0 if r["lost"] else min((r["detour"] or 0) / 40, 0.6) + 0.15 * (r["red"] < base_red) for r in rows])
    p = [max(sev[t + k] * 0.85 ** k for k in range(LOOK + 1) if t + k < len(sev)) for t in range(len(sev))]
    return np.clip(P_FLOOR + 0.92 * np.array(p) + RNG.normal(0, 0.03, len(p)), 0.01, 0.97).round(2)

# ---------- every block: real replay hours + placeholder probability (address lookup on the website) ----------
touched = {g for _, g in AFF}
BLOCK = {}   # geoid -> (rows[24], p[24]) for touched blocks only
for g in sorted(touched):
    rows = [block_hour(s, g) for s in state]; BLOCK[g] = (rows, placeholder_prob(rows, int(base.loc[g, "baseline_redundancy"])))
def block_series(g):
    return BLOCK.get(g) or ([block_hour(s, g) for s in state], np.full(len(state), P_FLOOR))

def onset_and_duration(p, t):
    on = next((k for k in range(t, len(p)) if p[k] >= 0.5), None)
    if on is None: return None, None
    end = next((k for k in range(on, len(p)) if p[k] < 0.5), len(p))
    return on - t, end - on

addresses, crit_ids = [], set()
for sid_, kind, name, g in SITES:
    rows, p = block_series(g); bred = int(base.loc[g, "baseline_redundancy"])
    crit_ids |= {r["crit"] for r in rows if r["crit"]}
    tl = []
    for t in range(NH):
        tti, dur = onset_and_duration(p, t); r = rows[t]
        tl.append(dict(hour=t, valid_time_utc=hours[t].strftime("%Y-%m-%dT%H:%MZ"),
                       isolation_probability=synth(float(p[t])), time_to_isolation=synth(tti), isolation_duration=synth(dur),
                       detour_minutes=real(None if r["lost"] else r["detour"]), critical_crossing_id=real(r["crit"]),
                       route_redundancy=real(r["red"]), isolation_tolerance=synth(TOLERANCE_H[kind]), scenario_lost_access=real(r["lost"])))
    b = blocks.loc[g]; name = name or f"Residential block {sid_[1:]}, {b.county} (block centroid)"
    addresses.append(dict(id=sid_, name=name, kind=kind, facility_synthetic=kind != "residential", geoid20=g, county=b.county, pop20=int(b.pop20),
                          lat=R(b.lat, 5), lon=R(b.lon, 5), location_basis="2020 Census block centroid (not a street address)",
                          baseline_drive_min_to_nearest_ed_hospital=real(R(base.loc[g, "baseline_tt_min"], 1)), baseline_route_redundancy=real(bred), timeline=tl))

# ---------- crossings ----------
X = pd.read_csv("data/export/crossings_export.csv", dtype={"nwm_feature_id": "Int64"})
X = X[(X.src != "osm_secondary") & (X.hazard_threshold_ok.astype(str) == "True") & (X.graph_snapped.astype(str) == "True") & X.nwm_feature_id.notna()]
assert len(X) == 250, len(X)   # the `seed` set the replay closes
C = pd.read_csv("data/export/consequence_ranking.csv").set_index("id")
flall = pd.read_parquet("data/phase1b/flows_hindcast.parquet").sort_index() * CFS; fl = flall.loc[hours[:NH]]
ev_first = {c.id: next((t for t, v in zip(flall.index, flall[str(c.nwm_feature_id)].values) if v > c.q10_cfs), None) for c in X.itertuples()}   # whole Florence hindcast
ratio = {c.id: fl[str(c.nwm_feature_id)].values / c.q10_cfs for c in X.itertuples()}
first = {i: next((t for t, v in enumerate(r) if v > 1), None) for i, r in ratio.items()}
LV = [("RL50", "q50_cfs"), ("RL25", "q25_cfs"), ("RL10", "q10_cfs"), ("RL5", "q5_cfs"), ("RL2", "q2_cfs")]
def xname(road, stream, cid):
    return " over ".join(v for v in (road if isinstance(road, str) else None, string.capwords(stream) if isinstance(stream, str) else None) if v) or cid
SEED = {}   # all 250 scenario crossings; crossings.json and route_crossings.json share these values
for c in X.itertuples():
    q = fl[str(c.nwm_feature_id)].values; rq = ratio[c.id]
    SEED[c.id] = dict(name=xname(c.road, c.stream, c.id), rq=rq, level=[next((lv for lv, col in LV if q[t] > getattr(c, col)), "RL0") for t in range(NH)],
                      p=np.clip(1 / (1 + np.exp(-3 * np.log(np.maximum(rq, 1e-6)))) + RNG.normal(0, 0.03, NH), 0.01, 0.97).round(2))   # placeholder
X = X.assign(people=X.id.map(C.people_affected).fillna(0), first=X.id.map(first), ev_first=X.id.map(ev_first))
top = X[X["first"].notna()].sort_values("people", ascending=False).head(28).id
X = X[X.id.isin(set(top) | crit_ids)].copy()
X = X.sort_values(["ev_first", "people"], ascending=[True, False], na_position="last")   # What Breaks First: earliest above RL10 in the event, then consequence
crossings = []
for rank, c in enumerate(X.itertuples(), 1):
    sd = SEED[c.id]; rq = sd["rq"]; fp = sd["p"]; name = sd["name"]; cr = C.loc[c.id]
    crossings.append(dict(
        id=c.id, name=name, road=c.road if isinstance(c.road, str) else None, stream=c.stream if isinstance(c.stream, str) else None,
        county=c.county.title(), lat=R(c.lat, 5), lon=R(c.lon, 5), nwm_feature_id=int(c.nwm_feature_id), structure_type=c.structure_type,
        data_quality=c.data_quality, tidal_flag=str(c.tidal_flag) == "True", fema_zone=c.fema_zone, q10_cfs=R(c.q10_cfs, 1),
        breaks_first_rank=rank, event_first_above_RL10_utc=real(None if pd.isna(c.ev_first) else pd.Timestamp(c.ev_first).strftime("%Y-%m-%dT%H:%MZ")),
        first_hour_above_RL10=real(None if pd.isna(c.first) else int(c.first)),
        consequence=dict(synthetic=False, rank_by_people_affected=int(cr.rank_by_people_affected), people_affected=int(cr.people_affected),
                         hosp_pop_lost_access=int(cr.hosp_pop_lost_access), hosp_pop_slowed_gt1min=int(cr.hosp_pop_slowed_gt1min),
                         hosp_max_detour_min=R(cr.hosp_max_detour_min, 1), crossings_on_same_segment=int(cr.crossings_on_same_segment)),
        hourly=[dict(hour=t, flood_probability=synth(float(fp[t])), flow_ratio_q10=real(R(rq[t], 2)),
                     level_reached=real(sd["level"][t])) for t in range(NH)]))

# ---------- watchlist (facilities only) ----------
def alert(a):
    p = [h["isolation_probability"]["value"] for h in a["timeline"]]; pk = int(np.argmax(p)); mx = p[pk]; tti = a["timeline"][0]["time_to_isolation"]["value"]
    lvl = "ACCESS WARNING (sample)" if mx >= 0.7 else "ACCESS WATCH (sample)" if mx >= 0.3 else "ACCESS OUTLOOK (sample)"
    if mx >= 0.3:
        txt = (f"{a['name']} may lose road access to an emergency hospital. Placeholder estimate: about {round(mx * 100)}% chance at the peak "
               f"hour ({a['timeline'][pk]['valid_time_utc']})" + (". Already at or above 50% at the replay start." if tti == 0 else f", first reaching 50% about {tti} h after the replay start." if tti is not None else "."))
    else:
        txt = (f"{a['name']}: placeholder chance of losing road access to an emergency hospital stays below 30% in this replay window "
               f"(peak about {round(mx * 100)}%). A low chance is not an assurance; this replay sees river flow only.")
    return dict(id=a["id"], name=a["name"], kind=a["kind"], county=a["county"], alert_level=lvl, peak_isolation_probability=synth(mx),
                peak_hour=pk, time_to_isolation_from_start=synth(tti), isolation_tolerance=synth(TOLERANCE_H[a["kind"]]), text=txt + " " + STAMP + ".")
watch = sorted((alert(a) for a in addresses if a["kind"] != "residential"),
               key=lambda w: (-w["peak_isolation_probability"]["value"], w["time_to_isolation_from_start"]["value"] if w["time_to_isolation_from_start"]["value"] is not None else 99))
for i, w in enumerate(watch, 1): w["rank"] = i

# ---------- network.geojson: major roads in the 3 counties + every segment carrying an included crossing ----------
S = gpd.read_parquet("data/phase1b/graph_segments.parquet")
cty = gpd.read_file("data/phase0/counties.geojson").to_crs(S.crs).union_all()
keep_seg = set(C.loc[X.id, "graph_segment_id"].dropna().astype(int))
S = S[(S.highway.isin(["motorway", "trunk", "primary", "secondary", "tertiary"]) & S.intersects(cty)) | S.seg_id.isin(keep_seg)]
hit = S.seg_id.isin(keep_seg)   # segments carrying a sample crossing stay individual (seg_id); the rest merge by class + name to stay small
rest = S[~hit].assign(name=S.name.fillna("")).dissolve(["highway", "name"]).reset_index()
rest["geometry"] = shapely.line_merge(rest.geometry.values)
S = pd.concat([S[hit].assign(sample=True), rest.assign(sample=False, seg_id=-1)], ignore_index=True)
S = gpd.GeoDataFrame(S, geometry="geometry", crs=rest.crs)
S = S.assign(geometry=S.geometry.simplify(30)).to_crs(4326)
S["geometry"] = shapely.set_precision(S.geometry.values, 1e-5)
feats = [dict(type="Feature", properties=dict(kind="road", highway=s.highway, name=s.name if isinstance(s.name, str) and s.name else None, carries_sample_crossing=s.sample,
                                              seg_id=int(s.seg_id) if s.sample else None), geometry=shapely.geometry.mapping(s.geometry)) for s in S.itertuples()]
feats += [dict(type="Feature", properties=dict(kind="crossing", id=c["id"], name=c["name"]), geometry=dict(type="Point", coordinates=[c["lon"], c["lat"]])) for c in crossings]

# ---------- blocks_lookup.json: every origin block, columnar, for the website's address lookup ----------
CTY = sorted(blocks.county.unique())
def replay_of(g):
    if g not in BLOCK: return None   # untouched: route kept, detour 0, no critical crossing, baseline redundancy, p = p_floor every hour
    rows, p = BLOCK[g]
    return dict(p_pct=[int(round(v * 100)) for v in p], lost=[int(r["lost"]) for r in rows[:NH]], detour_min=[None if r["lost"] else r["detour"] for r in rows[:NH]],
                crit=[r["crit"] for r in rows[:NH]], red=[r["red"] for r in rows[:NH]])
lookup_rows = [[g, CTY.index(b.county), R(b.lat, 5), R(b.lon, 5), int(b.pop20), R(base.loc[g, "baseline_tt_min"], 1),
                int(base.loc[g, "baseline_redundancy"]) if bool(base.loc[g, "baseline_reachable"]) else None,
                int(bool(base.loc[g, "baseline_reachable"])), replay_of(g) if bool(base.loc[g, "baseline_reachable"]) else None]
               for g, b in blocks.iterrows() if g in base.index]
LOOKUP = dict(sample=True, stamp=STAMP, replay_start_utc=hours[0].strftime("%Y-%m-%dT%H:%MZ"), hours=NH, lookahead_hours=LOOK, p_floor=P_FLOOR, isolation_tolerance_hours=TOLERANCE_H["residential"], counties=CTY,
              columns=["geoid20", "county_idx", "lat", "lon", "pop20", "baseline_drive_min", "baseline_redundancy", "assessed", "replay"],
              fields={"p_pct": dict(synthetic=True, definition="PLACEHOLDER isolation probability, percent, for the 18 replay hours + 6 look-ahead hours (same rule as addresses.json). replay = null means p_floor every hour."),
                      "isolation_tolerance_hours": dict(synthetic=True, definition="PLACEHOLDER assumption for a residential block (hours without access)"),
                      "lost": dict(synthetic=False, definition="1 = no route to any ED hospital in that replay hour"),
                      "detour_min": dict(synthetic=False, definition="added drive time vs baseline; 0 = 1 min or less; null = no route"),
                      "crit": dict(synthetic=False, definition="first closed crossing on the baseline path; null = none"),
                      "red": dict(synthetic=False, definition="ED hospitals within 30 min that hour"),
                      "assessed": dict(synthetic=False, definition="0 = no baseline route in the graph (block on a road fragment): not assessed, never zero risk")},
              blocks=lookup_rows)
XALL = pd.read_csv("data/export/crossings_export.csv").set_index("id")
LOOKUP["crossings"] = {c: [xname(XALL.road[c], XALL.stream[c], c), R(XALL.lat[c], 5), R(XALL.lon[c], 5)]
                       for c in sorted({x for r in lookup_rows if r[8] for x in r[8]["crit"] if x})}   # real: name, lat, lon of every referenced crossing

# ---------- route analysis: every crossing + essential services (website /route page) ----------
LVI = ["RL0", "RL2", "RL5", "RL10", "RL25", "RL50"]
ROUTE_X = dict(sample=True, stamp=STAMP, hours=NH, levels=LVI,
    note="assessed = the 250 crossings the replay can close (seed set); a route through one is blocked in the scenario while its level is RL10 or higher. Other crossings are listed so a route can say it crosses streams the model did not assess.",
    fields={"level": dict(synthetic=False, definition="per-hour index into levels (real replay)"), "ratio_q10": dict(synthetic=False, definition="flow / 10-year flow per hour (real replay)"),
            "p_pct": dict(synthetic=True, definition="PLACEHOLDER flood chance per hour, percent (same values as crossings.json)")},
    assessed=[dict(id=i, name=v["name"], lat=R(XALL.lat[i], 5), lon=R(XALL.lon[i], 5), county=str(XALL.county[i]).title(), fema_zone=XALL.fema_zone[i],
                   tidal=str(XALL.tidal_flag[i]) == "True", first_above_RL10_utc=None if pd.isna(ev_first[i]) else pd.Timestamp(ev_first[i]).strftime("%Y-%m-%dT%H:%MZ"),
                   people_affected=int(C.people_affected.get(i, 0) if pd.notna(C.people_affected.get(i)) else 0),
                   level="".join(str(LVI.index(l)) for l in v["level"]), ratio_q10=[R(r, 2) for r in v["rq"]], p_pct=[int(round(x * 100)) for x in v["p"]])
              for i, v in SEED.items()],
    not_assessed=[[i, R(r.lat, 5), R(r.lon, 5), "osm_secondary" if r.src == "osm_secondary" else (r.hazard_ok_reason if str(r.hazard_threshold_ok) != "True" else "not snapped")]
                  for i, r in XALL.iterrows() if i not in SEED])
Hs = pd.read_parquet("data/phase1b/hospitals_snapped.parquet"); Hs = Hs[Hs.ed & ~Hs.is_behavioral_or_nonacute]   # the engine's ED hospital set
Fs = pd.read_parquet("data/phase1b/firestations_snapped.parquet")
FACILITIES = dict(sample=True, source="pipeline facility sets (data/phase1b): CMS ED acute / critical-access hospitals, geocoded; fire stations from OSM + USGS National Map. Real locations.",
    hospitals=[dict(id=f"H{i:02d}", name=r["name"].title(), county=string.capwords(r.county), type=r.hospital_type, lat=R(r.lat, 5), lon=R(r.lon, 5)) for i, (_, r) in enumerate(Hs.iterrows())],
    fire_stations=[dict(id=f"F{i:03d}", name=r["name"] if isinstance(r["name"], str) else "Fire station (unnamed in source)", lat=R(r.lat, 5), lon=R(r.lon, 5)) for i, (_, r) in enumerate(Fs.iterrows())])

# ---------- meta ----------
FIELDS = {
    "isolation_probability": (True, "0-1", "PLACEHOLDER for the ML isolation model (not built yet). Shaped from the real replay state of this block over the next 6 h plus noise, so it agrees with the replay by construction and says nothing about any model's skill."),
    "time_to_isolation": (True, "hours", "PLACEHOLDER: hours from this hour until isolation_probability first reaches 0.5 (0 = already); null = not within the window + 6 h."),
    "isolation_duration": (True, "hours", "PLACEHOLDER: hours isolation_probability stays >= 0.5 from that onset (truncated at the window + 6 h)."),
    "isolation_tolerance": (True, "hours", "PLACEHOLDER assumption per facility type (dialysis 48, nursing home 72, residential 72); constant across hours; not a sourced input."),
    "flood_probability": (True, "0-1", "PLACEHOLDER: logistic function of the real flow / q10 ratio plus noise; not a calibrated closure probability."),
    "detour_minutes": (False, "minutes", "Real hindcast replay: added drive time to the nearest ED hospital vs baseline. 0 = changed by 1 min or less (engine stores only affected blocks); null = no route (see scenario_lost_access)."),
    "critical_crossing_id": (False, "crossing id", "Real hindcast replay: first closed crossing on the block's baseline path to an ED hospital; null = none closed on that path this hour."),
    "route_redundancy": (False, "count", "Real hindcast replay: ED hospitals reachable within 30 min under that hour's closures."),
    "scenario_lost_access": (False, "bool", "Real hindcast replay: true = no route to any ED hospital in that hour's RL10 closure state."),
    "flow_ratio_q10": (False, "ratio", "Real: NWM v3.0 retrospective flow of the crossing's reach / its 10-year recurrence flow (> 1 = above RL10)."),
    "level_reached": (False, "RL0..RL50", "Real: highest recurrence level strictly exceeded that hour (a scenario level, not a probability)."),
    "event_first_above_RL10_utc": (False, "UTC time", "Real: first hour of the whole Florence hindcast (from 2018-09-13) with flow above the 10-year flow. breaks_first_rank sorts by this, then by consequence.people_affected."),
    "first_hour_above_RL10": (False, "replay hour", "Real: first hour in the window with flow above the 10-year flow; null = not in the window."),
    "consequence": (False, "people / blocks / min", "Real structural consequence of closing this crossing alone (data/export/consequence_ranking.csv; no hazard input)."),
}
meta = dict(
    sample=True, mode="REPLAY", stale=False, stamp=STAMP, generated_at=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    region=dict(name="Cape Fear pilot, North Carolina", counties=["New Hanover", "Brunswick", "Pender"]),
    event=dict(name="Hurricane Florence (2018) - hindcast replay", replay_start_utc=hours[0].strftime("%Y-%m-%dT%H:%MZ"), hours=NH,
               note="Replay of the NWM v3.0 retrospective (free-running hindcast). The 18 replay hours are hours of a past storm replayed in order, not a forecast issued at the time."),
    scenario=dict(crossing_set=CSET, crossing_set_note="250 hazard-ready, structure-seeded crossings (NCDOT/NBI)", closure_rule=SCEN,
                  closure_rule_note="A crossing's whole road segment is removed while its reach flow exceeds its 10-year recurrence flow. A scenario level, not a probability.",
                  facility="ED acute / critical-access hospitals", snap="phase1"),
    status=dict(validated=False, kill_tests_passed=False,
                note="Preview only. Project kill tests are not passed: Kill Test 1 met its all-hours bar but reports/sample_model.md finds no usable onset skill, and crossing-level tests T12, T13, E1 failed (docs/claims.md). No forecast skill and no new hydrologic model is claimed. Not validated against Florence closures."),
    known_gaps=["The Florence replay and the closure scenarios use river flow only: no storm surge, tide, wave run-up, rain/drainage flooding or river-surge interaction. Observed coastal water levels (coastal.json, NOWCAST) are shown separately and are not combined with crossings; their outlook is a persistence placeholder, not surge guidance.",
                "Four modes are kept apart: REPLAY (this Florence hindcast), NOWCAST (nowcast.json, coastal.json: observed now), FORECAST (forecast_latest.json: NWM short-range, unvalidated, river flow only, not a closure probability), OUTLOOK-PERSISTENCE (placeholder). A replay is never a forecast.",
                "New Hanover (Wilmington) shows little or no loss of access here. That reflects the crossing inventory and graph, not Florence: Wilmington was documented as cut off, and test E3 failed to reproduce it.",
                "Dialysis and nursing-home entries are placeholder facilities at real Census block centroids; no facility inventory of those types is in the pipeline.",
                "The Florence hindcast saturates: most seed crossings exceed their 10-year flow at the peak."],
    data_sources=["NOAA National Water Model v3.0 retrospective (hourly channel flow)", "NOAA OWP recurrence flows (static_nwm_flowlines)",
                  "NCDOT structure locations and NBI 2025 (crossing inventory)", "OpenStreetMap Geofabrik NC/SC extract (road graph, default speeds)",
                  "US Census 2020 blocks (origins, population)", "CMS Hospital General Information (ED hospitals)", "FEMA NFHL (comparison layer only)"],
    pipeline_inputs=["data/phase2/engine/replay_hindcast_base_{hour_state,origin_state,baseline}.parquet", "data/phase1b/flows_hindcast.parquet",
                     "data/phase1b/graph_segments.parquet", "data/phase0/counties.geojson", "data/export/crossings_export.csv",
                     "data/export/consequence_ranking.csv", "data/export/blocks_export.csv"],
    fields={k: dict(synthetic=s, unit=u, definition=d) for k, (s, u, d) in FIELDS.items()},
    files=["meta.json", "addresses.json", "blocks_lookup.json", "route_crossings.json", "facilities.json", "crossings.json", "facilities_watchlist.json", "network.geojson", "nowcast.json", "coastal.json", "forecast_latest.json", "README.md", "preview.html", "build_sample.py"])

def dump(name, obj):
    with open(OUT + name, "w", encoding="utf-8") as f: json.dump(obj, f, separators=(",", ":"), allow_nan=False, ensure_ascii=False)
dump("meta.json", meta)
dump("addresses.json", dict(sample=True, stamp=STAMP, addresses=addresses))
dump("crossings.json", dict(sample=True, stamp=STAMP, crossings=crossings))
dump("facilities_watchlist.json", dict(sample=True, stamp=STAMP, watchlist=watch))
dump("network.geojson", dict(type="FeatureCollection", features=feats))
dump("blocks_lookup.json", LOOKUP)
dump("route_crossings.json", ROUTE_X)
dump("facilities.json", FACILITIES)

# ---------- self-check ----------
def flagged(o, path="$"):
    """Every {"value": ...} leaf must carry a boolean `synthetic`; placeholder fields must be synthetic=True."""
    if isinstance(o, dict):
        if "value" in o: assert isinstance(o.get("synthetic"), bool), path
        for k, v in o.items():
            if k in ("isolation_probability", "time_to_isolation", "isolation_duration", "isolation_tolerance", "flood_probability", "peak_isolation_probability"):
                assert v["synthetic"] is True, f"{path}.{k} must be synthetic"
            flagged(v, f"{path}.{k}")
    elif isinstance(o, list): [flagged(v, f"{path}[{i}]") for i, v in enumerate(o)]
for f in ("addresses.json", "crossings.json", "facilities_watchlist.json", "meta.json"): flagged(json.load(open(OUT + f, encoding="utf-8")))
assert all(v["synthetic"] is (k in ("p_pct", "isolation_tolerance_hours")) for k, v in LOOKUP["fields"].items()), "lookup synthetic flags"
for a in addresses:   # sample sites must agree with the lookup row of their block
    rp = next(r for r in lookup_rows if r[0] == a["geoid20"])[8]
    assert [h["isolation_probability"]["value"] for h in a["timeline"]] == ([v / 100 for v in rp["p_pct"][:NH]] if rp else [P_FLOOR] * NH), a["id"]
assert os.path.getsize(OUT + "blocks_lookup.json") < 3_000_000, "blocks_lookup.json over 3 MB"
assert len(ROUTE_X["assessed"]) == 250 and len(ROUTE_X["assessed"]) + len(ROUTE_X["not_assessed"]) == len(XALL)
for c in crossings:   # crossings.json must agree with route_crossings.json
    r = next(a for a in ROUTE_X["assessed"] if a["id"] == c["id"])
    assert [round(h["flood_probability"]["value"] * 100) for h in c["hourly"]] == r["p_pct"] and [LVI[int(k)] for k in r["level"]] == [h["level_reached"]["value"] for h in c["hourly"]], c["id"]
assert len(FACILITIES["hospitals"]) == 11, len(FACILITIES["hospitals"])
for f in os.listdir(OUT):
    if f.endswith((".json", ".geojson", ".md", ".html")):
        t = open(OUT + f, encoding="utf-8").read().lower()
        for w in ("safe", "no risk"): assert w not in t, f"forbidden string '{w}' in {f}"
assert os.path.getsize(OUT + "network.geojson") < 2_000_000, "network.geojson over 2 MB"
assert len(addresses) == 10 and all(len(a["timeline"]) == NH for a in addresses) and all(len(c["hourly"]) == NH for c in crossings)
print({f: os.path.getsize(OUT + f) for f in sorted(os.listdir(OUT))}); print("crossings", len(crossings), "road features", len(S), "checks OK")
