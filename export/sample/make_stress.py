"""STRESS-TEST copy of the sample export: same schema, exaggerated values, written to export/sample/stress/.
NOT real and NOT a scenario: it exists to check how the website handles extremes. Run after build_sample.py:
    python export/sample/make_stress.py
Per replay hour h (0-17): h 0-2 everything at its floor (0% chances, below the 2-year flow); h 3-5 every crossing above the 2-year flow;
h >= 6 every one of the 250 scenario crossings above the 50-year flow (all closed) and chances ramp to exactly 100% at h 17;
every assessed block loses its route from h 9 with 999.9-min detours before that; 9,999,999 people affected; tolerance 0 h."""
import json, os, shutil

SRC = os.path.dirname(os.path.abspath(__file__)) + os.sep
OUT = SRC + "stress" + os.sep
os.makedirs(OUT, exist_ok=True)
STAMP = "STRESS TEST - exaggerated values, not real, not for any use"
NH = 18
load = lambda f: json.load(open(SRC + f, encoding="utf-8"))
dump = lambda f, o: json.dump(o, open(OUT + f, "w", encoding="utf-8"), separators=(",", ":"), allow_nan=False, ensure_ascii=False)
P = [round(h / (NH - 1), 4) for h in range(NH)]            # 0.0 ... 1.0 inclusive
LEVEL = ["RL0" if h < 3 else "RL2" if h < 6 else "RL50" for h in range(NH)]
LOST = [h >= 9 for h in range(NH)]
LONG = "Sample nursing home with an extremely long placeholder name to test wrapping and truncation everywhere in the interface"

def onset(p, t):
    on = next((k for k in range(t, len(p)) if p[k] >= 0.5), None)
    if on is None: return None, None
    end = next((k for k in range(on, len(p)) if p[k] < 0.5), len(p))
    return on - t, end - on

meta = load("meta.json"); meta["stamp"] = STAMP; meta["stress_test"] = True
meta["known_gaps"] = ["STRESS TEST: every value here is exaggerated on purpose."] + meta["known_gaps"]
dump("meta.json", meta)

A = load("addresses.json"); A["stamp"] = STAMP
for i, a in enumerate(A["addresses"]):
    if a["kind"] == "nursing_home" and i == 3: a["name"] = LONG
    for t, h in enumerate(a["timeline"]):
        tti, dur = onset(P, t)
        h["isolation_probability"]["value"] = P[t]; h["time_to_isolation"]["value"] = tti; h["isolation_duration"]["value"] = dur
        h["scenario_lost_access"]["value"] = LOST[t]; h["detour_minutes"]["value"] = None if LOST[t] else 999.9
        h["route_redundancy"]["value"] = 0; h["isolation_tolerance"]["value"] = 0
        h["critical_crossing_id"]["value"] = h["critical_crossing_id"]["value"] or "V2_0056"
    a["baseline_route_redundancy"]["value"] = 0
dump("addresses.json", A)

C = load("crossings.json"); C["stamp"] = STAMP
for c in C["crossings"]:
    c["consequence"].update(people_affected=9_999_999, hosp_pop_lost_access=9_999_999, hosp_max_detour_min=999.9)
    for t, h in enumerate(c["hourly"]):
        h["flood_probability"]["value"] = P[t]; h["level_reached"]["value"] = LEVEL[t]; h["flow_ratio_q10"]["value"] = 0.0 if t < 3 else 50.0
dump("crossings.json", C)

W = load("facilities_watchlist.json"); W["stamp"] = STAMP
for w in W["watchlist"]:
    w["alert_level"] = "ACCESS WARNING (sample)"; w["peak_isolation_probability"]["value"] = 1.0
    w["text"] = "STRESS TEST: " + w["text"] * 3
    a = next(x for x in A["addresses"] if x["id"] == w["id"]); w["name"] = a["name"]
dump("facilities_watchlist.json", W)

R = load("route_crossings.json"); R["stamp"] = STAMP
L = "".join(str(R["levels"].index(l)) for l in LEVEL)
for x in R["assessed"]:
    x.update(level=L, p_pct=[round(p * 100) for p in P], ratio_q10=[0.0 if t < 3 else 50.0 for t in range(NH)], people_affected=9_999_999)
dump("route_crossings.json", R)

B = load("blocks_lookup.json"); B["stamp"] = STAMP; B["isolation_tolerance_hours"] = 0
pp = [round(p * 100) for p in P] + [100] * (len(B["blocks"][0][8]["p_pct"]) - NH if any(b[8] for b in B["blocks"]) else 6)
for b in B["blocks"]:
    if b[7]:   # assessed: every block hit
        b[8] = dict(p_pct=pp, lost=[int(v) for v in LOST], detour_min=[None if v else 999.9 for v in LOST], crit=["V2_0056"] * NH, red=[0] * NH)
dump("blocks_lookup.json", B)

for f in ("facilities.json", "network.geojson"): shutil.copy(SRC + f, OUT + f)

# self-check: strict JSON, extremes present, banned wording absent
for f in os.listdir(OUT):
    t = open(OUT + f, encoding="utf-8").read(); json.loads(t)
    assert "safe" not in t.lower() and "no risk" not in t.lower(), f
x = load("stress/route_crossings.json")["assessed"][0]
assert x["p_pct"][0] == 0 and x["p_pct"][-1] == 100 and x["level"][6:] == "5" * (NH - 6)
print("stress files:", {f: os.path.getsize(OUT + f) for f in sorted(os.listdir(OUT))})
