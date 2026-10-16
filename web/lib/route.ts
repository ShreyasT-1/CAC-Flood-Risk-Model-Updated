// Route risk from the Florence replay. Pure functions (no imports) so scripts/route-check.mjs can run them under Node.

export type LngLat = [number, number];

export type XAssessed = {
  id: string; name: string; lat: number; lon: number; county: string; fema_zone: string; tidal: boolean;
  first_above_RL10_utc: string | null; people_affected: number;
  level: string; // one digit per hour: index into RouteCrossings.levels (real replay)
  ratio_q10: (number | null)[]; // real replay
  p_pct: number[]; // PLACEHOLDER flood chance, percent
};
export type RouteCrossings = { hours: number; levels: string[]; assessed: XAssessed[]; not_assessed: [string, number, number, string][] };

export type OnRoute = { id: string; km: number; lat: number; lon: number; x: XAssessed | null; reason?: string };
export type HourStatus = { blocked: OnRoute[]; watch: OnRoute[]; pFail: number; state: 0 | 1 | 2 };

export const CLOSED = 3; // levels[3] = RL10: the scenario closes the crossing at or above this
export const AT_RISK_P = 0.35;

/** Google/Valhalla encoded polyline, precision 6. */
export function decodePolyline6(s: string): LngLat[] {
  const out: LngLat[] = [];
  let i = 0, lat = 0, lon = 0;
  const next = () => {
    let b, shift = 0, v = 0;
    do { b = s.charCodeAt(i++) - 63; v |= (b & 0x1f) << shift; shift += 5; } while (b >= 0x20);
    return v & 1 ? ~(v >> 1) : v >> 1;
  };
  while (i < s.length) { lat += next(); lon += next(); out.push([lon / 1e6, lat / 1e6]); }
  return out;
}

/** Crossings within `tolM` metres of the route line, in driving order. */
export function crossingsOnRoute(shape: LngLat[], X: RouteCrossings, tolM = 30): OnRoute[] {
  if (shape.length < 2) return [];
  const lat0 = shape[0][1], kx = 111320 * Math.cos((lat0 * Math.PI) / 180), ky = 110570;
  const P = shape.map(([lo, la]) => [lo * kx, la * ky]);
  const cum = [0];
  for (let i = 1; i < P.length; i++) cum.push(cum[i - 1] + Math.hypot(P[i][0] - P[i - 1][0], P[i][1] - P[i - 1][1]));
  let [x0, y0, x1, y1] = [Infinity, Infinity, -Infinity, -Infinity];
  for (const [x, y] of P) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
  const hits: OnRoute[] = [];
  const test = (id: string, lat: number, lon: number, x: XAssessed | null, reason?: string) => {
    const px = lon * kx, py = lat * ky;
    if (px < x0 - tolM || px > x1 + tolM || py < y0 - tolM || py > y1 + tolM) return;
    let best = Infinity, along = 0;
    for (let i = 1; i < P.length; i++) {
      const [ax, ay] = P[i - 1], dx = P[i][0] - ax, dy = P[i][1] - ay, L2 = dx * dx + dy * dy;
      const t = L2 ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / L2)) : 0;
      const d = Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
      if (d < best) { best = d; along = cum[i - 1] + t * Math.sqrt(L2); }
    }
    if (best <= tolM) hits.push({ id, km: along / 1000, lat, lon, x, reason });
  };
  for (const x of X.assessed) test(x.id, x.lat, x.lon, x);
  for (const [id, lat, lon, reason] of X.not_assessed) test(id, lat, lon, null, reason);
  return hits.sort((a, b) => a.km - b.km);
}

/** Replay status of a route in hour h: blocked if any assessed crossing is at or above RL10. pFail is the PLACEHOLDER chance any crossing floods. */
export function routeAtHour(on: OnRoute[], h: number): HourStatus {
  const blocked: OnRoute[] = [], watch: OnRoute[] = [];
  let q = 1;
  for (const o of on) {
    if (!o.x) continue;
    const lv = +o.x.level[h];
    if (lv >= CLOSED) blocked.push(o); else if (lv > 0) watch.push(o);
    q *= 1 - Math.min(100, Math.max(0, o.x.p_pct[h])) / 100;
  }
  const pFail = 1 - q;
  return { blocked, watch, pFail, state: blocked.length ? 2 : watch.length || pFail >= AT_RISK_P ? 1 : 0 };
}

export type RouteOption = {
  id: string; serviceId: string; label: string; via: string;
  kind: "fastest" | "alternate" | "detour";
  timeS: number; km: number; shape: LngLat[]; on: OnRoute[];
};

/** Best first: fewest closed crossings (open routes first), then lower placeholder chance (5-point steps), then faster. */
export function rankRoutes(opts: RouteOption[], h: number) {
  return opts
    .map((o) => ({ o, s: routeAtHour(o.on, h) }))
    .sort((a, b) => a.s.blocked.length - b.s.blocked.length
      || Math.round(a.s.pFail * 20) - Math.round(b.s.pFail * 20) || a.o.timeS - b.o.timeS);
}

/** Hours (of the replay window) in which the route is blocked. */
export const blockedHours = (on: OnRoute[], hours: number) =>
  Array.from({ length: hours }, (_, h) => h).filter((h) => on.some((o) => o.x && +o.x.level[h] >= CLOSED));
