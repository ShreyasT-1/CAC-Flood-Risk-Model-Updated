// Self-check for lib/route.ts (Node 22.6+ strips the TypeScript types). Run: npm run check:route
import assert from "node:assert/strict";
import { blockedHours, crossingsOnRoute, decodePolyline6, rankRoutes, routeAtHour } from "../lib/route.ts";

// Polyline6 round trip on a known value (Valhalla precision 6).
const enc = (pts) => {
  let out = "", plat = 0, plon = 0;
  const one = (v) => { v = v < 0 ? ~(v << 1) : v << 1; while (v >= 0x20) { out += String.fromCharCode((0x20 | (v & 0x1f)) + 63); v >>= 5; } out += String.fromCharCode(v + 63); };
  for (const [lon, lat] of pts) { const a = Math.round(lat * 1e6), o = Math.round(lon * 1e6); one(a - plat); one(o - plon); plat = a; plon = o; }
  return out;
};
const line = [[-78.0, 34.2], [-77.99, 34.2], [-77.98, 34.21]];
assert.deepEqual(decodePolyline6(enc(line)), line);

// Crossings: one on the line, one 20 m off, one 200 m off; level digits per hour (3 = RL10 closed).
const X = { hours: 3, levels: ["RL0", "RL2", "RL5", "RL10", "RL25", "RL50"], not_assessed: [["N1", 34.205, -77.985, "osm_secondary"]],
  assessed: [
    { id: "A", lat: 34.2, lon: -77.995, level: "013", p_pct: [10, 50, 90], ratio_q10: [0.2, 0.8, 1.5] },
    { id: "B", lat: 34.20018, lon: -77.992, level: "000", p_pct: [0, 0, 0], ratio_q10: [0, 0, 0] },
    { id: "C", lat: 34.2018, lon: -77.99, level: "555", p_pct: [100, 100, 100], ratio_q10: [9, 9, 9] },
  ] };
const on = crossingsOnRoute(line, X, 30);
assert.deepEqual(on.map((o) => o.id), ["A", "B", "N1"], "A and B within 30 m in driving order, C excluded, N1 unassessed");
assert.equal(on[2].x, null);

assert.equal(routeAtHour(on, 0).state, 0);
assert.equal(routeAtHour(on, 1).state, 1, "above 2-yr flow = at risk");
assert.equal(routeAtHour(on, 2).state, 2, "RL10 = blocked");
assert.ok(Math.abs(routeAtHour(on, 1).pFail - 0.5) < 1e-9);
assert.deepEqual(blockedHours(on, 3), [2]);

// Extremes: p = 100% and 0% must stay in [0, 1]; empty route is open.
const sure = crossingsOnRoute(line, { ...X, assessed: [{ ...X.assessed[0], p_pct: [100, 0, -5] }] }, 30);
assert.equal(routeAtHour(sure, 0).pFail, 1);
assert.equal(routeAtHour(sure, 2).pFail, 0);
assert.deepEqual(routeAtHour([], 0), { blocked: [], watch: [], pFail: 0, state: 0 });

// Ranking: fewer closures first, then chance, then time.
const opt = (id, timeS, o) => ({ id, serviceId: "S", label: id, via: "", kind: "fastest", timeS, km: 1, shape: line, on: o });
const r = rankRoutes([opt("blocked", 60, on), opt("slow-open", 900, []), opt("fast-open", 300, [])], 2).map((x) => x.o.id);
assert.deepEqual(r, ["fast-open", "slow-open", "blocked"]);
console.log("route-check: all assertions passed");
