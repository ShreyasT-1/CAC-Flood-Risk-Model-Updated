// Public FOSSGIS Valhalla server (OpenStreetMap roads, no key, fair use). GET with ?json= avoids a CORS preflight.
import { crossingsOnRoute, decodePolyline6, routeAtHour, type LngLat, type RouteCrossings } from "./route";

const BASE = "https://valhalla1.openstreetmap.de";
const loc = ([lon, lat]: LngLat) => ({ lat, lon });
const cache = new Map<string, Promise<unknown>>();

function get<T>(path: string, body: object): Promise<T> {
  const url = `${BASE}/${path}?json=${encodeURIComponent(JSON.stringify(body))}`;
  if (!cache.has(url))
    cache.set(url, fetch(url).then(async (r) => {
      const j = await r.json();
      if (!r.ok && j?.error_code !== 442) { cache.delete(url); throw new Error(j?.error ?? `routing ${r.status}`); }
      return j; // 442 = no path: returned as data, callers treat it as "no route"
    }));
  return cache.get(url) as Promise<T>;
}

/** Drive time (s) and distance (km) from one origin to many targets; null where unroutable. */
export async function matrix(from: LngLat, to: LngLat[]) {
  const j = await get<{ sources_to_targets: { time: number | null; distance: number | null }[][] }>("sources_to_targets",
    { sources: [loc(from)], targets: to.map(loc), costing: "auto" });
  return j.sources_to_targets[0].map((c) => (c.time == null ? null : { timeS: c.time, km: c.distance ?? 0 }));
}

export type Trip = { shape: LngLat[]; timeS: number; km: number; via: string };
type Raw = { trip?: { summary: { time: number; length: number }; legs: { shape: string; maneuvers?: { street_names?: string[]; length: number }[] }[] }; alternates?: Raw[] };

const box = ([lon, lat]: LngLat, d = 0.0004) => [[lon - d, lat - d], [lon + d, lat - d], [lon + d, lat + d], [lon - d, lat + d], [lon - d, lat - d]];
// Public server limits: 50 exclude_locations; exclude_polygons up to 100 vertices (20 boxes) and 10 km total perimeter.
export const MAX_POINTS = 50, MAX_BOXES = 20;

/** Fastest route plus up to `alternates` alternatives, avoiding road edges at `avoid` points and inside boxes around `hard` points. [] = no path. */
export async function route(from: LngLat, to: LngLat, avoid: LngLat[] = [], alternates = 0, hard: LngLat[] = []): Promise<Trip[]> {
  const j = await get<Raw>("route", {
    locations: [loc(from), loc(to)], costing: "auto", units: "kilometers", directions_type: "maneuvers",
    ...(alternates ? { alternates } : {}),
    ...(avoid.length ? { exclude_locations: avoid.map(loc) } : {}),
    ...(hard.length ? { exclude_polygons: hard.map((p) => box(p)) } : {}),
  });
  const trips = j.trip ? [j, ...(j.alternates ?? [])] : [];
  return trips.map(({ trip }) => {
    const names = new Map<string, number>();
    for (const m of trip!.legs[0].maneuvers ?? []) for (const n of m.street_names?.slice(0, 1) ?? []) names.set(n, (names.get(n) ?? 0) + m.length);
    const via = [...names].sort((a, b) => b[1] - a[1]).slice(0, 2).map(([n]) => n).join(" and ") || "local roads";
    return { shape: decodePolyline6(trip!.legs[0].shape), timeS: trip!.summary.time, km: trip!.summary.length, via };
  });
}

/** Route that avoids every crossing the replay closes in hour h. Each attempt excludes the closed crossings found on the last route:
 * first as a point (blocks the nearest road edge), then as a box if the route still passes it (e.g. the other carriageway). */
export async function openRoute(from: LngLat, to: LngLat, X: RouteCrossings, h: number, maxTries = 8) {
  const points = new Map<string, LngLat>(), boxes = new Map<string, LngLat>();
  for (let i = 0; i < maxTries; i++) {
    let t: Trip | undefined;
    try { [t] = await route(from, to, [...points.values()], 0, [...boxes.values()]); }
    catch (e) { return { trip: null, avoided: points.size + boxes.size, reason: `the public router refused the detour (${(e as Error).message})` }; }
    if (!t) return { trip: null, avoided: points.size + boxes.size, reason: "no road path once the closed crossings are avoided" };
    const on = crossingsOnRoute(t.shape, X);
    const shut = routeAtHour(on, h).blocked;
    if (!shut.length) return { trip: { ...t, on }, avoided: points.size + boxes.size, reason: null };
    for (const o of shut) {
      if (!points.has(o.id)) points.set(o.id, [o.lon, o.lat]);
      else if (!boxes.has(o.id)) boxes.set(o.id, [o.lon, o.lat]);
    }
    if (points.size > MAX_POINTS || boxes.size > MAX_BOXES)
      return { trip: null, avoided: points.size + boxes.size, reason: `more closed crossings than the public router can avoid at once (${MAX_POINTS})` };
  }
  return { trip: null, avoided: points.size + boxes.size, reason: `every detour found in ${maxTries} tries still crossed a closed crossing` };
}
