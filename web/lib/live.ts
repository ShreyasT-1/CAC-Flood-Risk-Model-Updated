// Live layers written by lifeline/src/live/45_nowcast.py and 44_forecast_preview.py (copied to public/data/sample/ by refresh_live.yml or `npm run sample:sync`).
// Each file carries its own mode, generated_at, stale, source and caveats; the UI reads them and hard-codes none of that text.
import { useEffect, useState } from "react";

export type Hourly = { t: string; tide_pred_m_navd88: number | null; observed_m_navd88?: number; residual_m?: number; outlook_total_m_navd88?: number; mode?: string; synthetic?: boolean; stale?: boolean };
export type Station = { id: string; name: string; has_observations: boolean; riverine_influence: boolean; latest_observed_time: string | null; stale: boolean; latest_residual_m: number | null; latest_residual_time: string | null; hourly: Hourly[] };
export type Coastal = { mode: string; stale: boolean; generated_at: string; datum: string; source: string; caveats: string[]; outlook_synthetic: boolean; stations: Station[] };

export type Gauge = {
  lid: string; usgs_site: string; name: string | null; stale: boolean;
  usgs: { discharge_cfs: number | null; discharge_time: string | null; discharge_stale: boolean; gage_height_ft_usgs_datum: number | null; gage_height_time: string | null };
  nws: { stage_ft_nws_datum: number | null; stage_time: string | null; stage_stale: boolean; flood_category: string; thresholds_ft: Record<string, number> };
};
export type Nowcast = { mode: string; stale: boolean; generated_at: string; sources: string[]; caveats: string[]; errors: string[]; gauges: Gauge[]; gauge_rule?: string; n_pilot_area?: number; n_other_basin?: number };

export type FcHour = { lead_hours: number; valid_time: string; flow_cfs: number | null; flow_ratio_q10: number | null; scenario_state: string | null };
export type Forecast = {
  mode: string; label: string; not_a_closure_probability: boolean; stale: boolean; generated_at: string; source: string; caveats: string[]; nwm_version: string;
  cycle_issue_time: string; cycle_age_hours: number; fallback: { used: boolean; skipped_newer_cycles: { cycle: string; reason: string }[]; note: string };
  crossings: { id: string; name: string; q10_cfs: number; in_model_output: boolean; hourly: FcHour[] }[];
};

export type Load<T> = { data: T | null; error: string | null };
/** Fetch one live JSON file; failure is shown as text, never hidden (the replay keeps working). */
export function useLive<T>(file: string, active: boolean): Load<T> {
  const [s, set] = useState<Load<T>>({ data: null, error: null });
  useEffect(() => {
    if (!active) return;
    let gone = false;
    fetch(`/data/sample/${file}`, { cache: "no-cache" }).then((r) => { if (!r.ok) throw new Error(`${file}: ${r.status}`); return r.json() as Promise<T>; })
      .then((data) => !gone && set({ data, error: null })).catch((e: Error) => !gone && set({ data: null, error: e.message }));
    return () => { gone = true; };
  }, [file, active]);
  return s;
}

const H = 3600e3;
/** Hours since an ISO time (null if unparseable). `now` is passed in so render stays pure. */
export const ageH = (iso: string | null | undefined, now: number) => { const t = iso ? Date.parse(iso) : NaN; return Number.isNaN(t) ? null : Math.max(0, (now - t) / H); };
export const hoursText = (h: number | null) => (h === null ? "unknown age" : h < 1 ? "under 1 h ago" : `${Math.round(h)} h ago`);
