// SAMPLE / PREVIEW data from the FloodLens pipeline (lifeline/export/sample, copied by `npm run sample:sync`).
// Real values come from the Florence 2018 hindcast replay; values marked synthetic are placeholders.

/** `?data=stress` loads the exaggerated stress-test copy of the sample (made by lifeline/export/sample/make_stress.py). */
export const isStress = () => typeof window !== "undefined" && new URLSearchParams(window.location.search).get("data") === "stress";
export const dataRoot = () => (isStress() ? "/data/sample/stress/" : "/data/sample/");

export type Flag<T> = { value: T; synthetic: boolean };
export type Kind = "dialysis" | "nursing_home" | "residential" | "address";

export type HourView = {
  p: number; // placeholder isolation probability, 0-1
  tti: number | null; // placeholder hours until p >= 0.5
  dur: number | null; // placeholder hours p stays >= 0.5
  lost: boolean; // replay: no route to any ED hospital
  detour: number | null; // replay: added minutes, null = no route
  crit: string | null; // replay: first closed crossing on the baseline path
  red: number; // replay: ED hospitals within 30 min
};

export type LocationView = {
  id: string;
  name: string;
  kind: Kind;
  county: string;
  lat: number;
  lon: number;
  basis: string;
  assessed: boolean;
  baselineDrive: number | null;
  baselineRed: number | null;
  tolerance: number; // placeholder hours
  hours: HourView[];
  distanceKm?: number; // address search: distance to the block centroid
  query?: string;
};

export type Crossing = {
  id: string;
  name: string;
  county: string;
  lat: number;
  lon: number;
  tidal_flag: boolean;
  fema_zone: string;
  breaks_first_rank: number;
  event_first_above_RL10_utc: Flag<string | null>;
  consequence: {
    people_affected: number;
    hosp_pop_lost_access: number;
    hosp_pop_slowed_gt1min: number;
    hosp_max_detour_min: number | null;
    crossings_on_same_segment: number;
  };
  hourly: { flood_probability: Flag<number>; flow_ratio_q10: Flag<number>; level_reached: Flag<string> }[];
};

export type Watch = { id: string; name: string; kind: Kind; county: string; alert_level: string; text: string; rank: number };

export type Meta = {
  mode?: string;
  generated_at: string;
  stale?: boolean;
  stamp: string;
  event: { name: string; note: string; replay_start_utc: string; hours: number };
  data_sources: string[];
  known_gaps: string[];
  fields: Record<string, { synthetic: boolean; definition: string }>;
};

type Block = [string, number, number, number, number, number | null, number | null, number, null | {
  p_pct: number[]; lost: number[]; detour_min: (number | null)[]; crit: (string | null)[]; red: number[];
}];
export type Lookup = {
  hours: number;
  p_floor: number;
  isolation_tolerance_hours: number;
  counties: string[];
  blocks: Block[];
  crossings: Record<string, [string, number, number]>;
};

export const getJSON = <T,>(file: string): Promise<T> =>
  fetch(dataRoot() + file).then((r) => {
    if (!r.ok) throw new Error(`${file}: ${r.status}`);
    return r.json() as Promise<T>;
  });

/** Same rule as build_sample.py: hours until p first reaches 0.5, and how long it stays there. */
export function onsetAndDuration(p: number[], t: number): [number | null, number | null] {
  let on = -1;
  for (let k = t; k < p.length; k++) if (p[k] >= 0.5) { on = k; break; }
  if (on < 0) return [null, null];
  let end = on;
  while (end < p.length && p[end] >= 0.5) end++;
  return [on - t, end - on];
}

export function siteView(a: {
  id: string; name: string; kind: Kind; county: string; lat: number; lon: number; location_basis: string;
  baseline_drive_min_to_nearest_ed_hospital: Flag<number>; baseline_route_redundancy: Flag<number>;
  timeline: { isolation_probability: Flag<number>; time_to_isolation: Flag<number | null>; isolation_duration: Flag<number | null>;
    scenario_lost_access: Flag<boolean>; detour_minutes: Flag<number | null>; critical_crossing_id: Flag<string | null>;
    route_redundancy: Flag<number>; isolation_tolerance: Flag<number> }[];
}): LocationView {
  return {
    id: a.id, name: a.name, kind: a.kind, county: a.county, lat: a.lat, lon: a.lon, basis: a.location_basis, assessed: true,
    baselineDrive: a.baseline_drive_min_to_nearest_ed_hospital.value, baselineRed: a.baseline_route_redundancy.value,
    tolerance: a.timeline[0].isolation_tolerance.value,
    hours: a.timeline.map((h) => ({
      p: h.isolation_probability.value, tti: h.time_to_isolation.value, dur: h.isolation_duration.value, lost: h.scenario_lost_access.value,
      detour: h.detour_minutes.value, crit: h.critical_crossing_id.value, red: h.route_redundancy.value,
    })),
  };
}

/** Nearest 2020 Census block centroid to a point (the pipeline works on block centroids, not addresses). */
export function nearestBlock(L: Lookup, lat: number, lon: number): [Block, number] {
  const kx = 111.32 * Math.cos((lat * Math.PI) / 180), ky = 110.57;
  let best = L.blocks[0], bd = Infinity;
  for (const b of L.blocks) {
    const d = Math.hypot((b[3] - lon) * kx, (b[2] - lat) * ky);
    if (d < bd) { bd = d; best = b; }
  }
  return [best, bd];
}

export function blockView(L: Lookup, b: Block, km: number, query: string): LocationView {
  const [geoid, ci, lat, lon, , drive, red, assessed, r] = b;
  const p = r ? r.p_pct.map((v) => v / 100) : Array(L.hours).fill(L.p_floor);
  return {
    id: geoid, name: query, kind: "address", county: L.counties[ci], lat, lon, assessed: !!assessed,
    basis: `Nearest 2020 Census block centroid (${km.toFixed(1)} km away)`, distanceKm: km, query,
    baselineDrive: drive, baselineRed: red, tolerance: L.isolation_tolerance_hours,
    hours: Array.from({ length: L.hours }, (_, t) => {
      const [tti, dur] = onsetAndDuration(p, t);
      return {
        p: p[t], tti, dur, lost: !!r?.lost[t], detour: r ? r.detour_min[t] : 0, crit: r ? r.crit[t] : null, red: r ? r.red[t] : (red ?? 0),
      };
    }),
  };
}

export const RISK = [
  { label: "Lower", max: 0.15, fill: "#E8F0FA", cls: "bg-risk-0", solid: "bg-risk-0" },
  { label: "Moderate", max: 0.35, fill: "#F7E1E1", cls: "bg-risk-1", solid: "bg-risk-1" },
  { label: "Elevated", max: 0.55, fill: "#EFAEAE", cls: "bg-risk-2", solid: "bg-risk-2" },
  { label: "High", max: 0.75, fill: "#CC0000", cls: "bg-risk-3 hatch", solid: "bg-risk-3" },
  { label: "Very high", max: Infinity, fill: "#7A0000", cls: "bg-risk-4 hatch", solid: "bg-risk-4" },
];
export const risk = (p: number) => RISK.find((r) => p < r.max)!;

/** Crossing status from the real replay level (a scenario level, not a probability). */
export const crossingStatus = (level: string) =>
  ["RL10", "RL25", "RL50"].includes(level) ? "Above 10-year flow" : level === "RL0" ? "Below 2-year flow" : "Above 2-year flow";

export const pct = (p: number) => `${Math.round(p * 100)}%`;
export const utc = (iso: string) => iso.replace("T", " ").replace("Z", " UTC");
export const hourTime = (start: string, h: number) =>
  utc(new Date(Date.parse(start) + h * 3600e3).toISOString().slice(0, 16) + "Z");
