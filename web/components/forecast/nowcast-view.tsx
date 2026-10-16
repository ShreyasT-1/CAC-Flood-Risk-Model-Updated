"use client";
import { useState } from "react";
import { ageH, hoursText, useLive, type Gauge, type Nowcast } from "@/lib/live";
import { utc } from "@/lib/sample";
import { ModeHeader } from "@/components/forecast/mode-header";

// NWS flood category (NWPS floodCategory), shown as text; never colour alone, never an all-clear.
const ORDER = ["major", "moderate", "minor", "action"];
const LABEL: Record<string, string> = {
  major: "Major flood stage", moderate: "Moderate flood stage", minor: "Minor flood stage", action: "Action stage",
  no_flooding: "Below action stage (not an all-clear)", no_observation: "No current NWS reading", obs_not_current: "NWS reading not current", not_defined: "Flood stage not defined by NWS",
};
const rank = (g: Gauge) => { const i = ORDER.indexOf(g.nws.flood_category); return i < 0 ? ORDER.length : i; };

function Row({ g, now }: { g: Gauge; now: number }) {
  const cat = g.nws.flood_category, hot = ORDER.includes(cat), th = g.nws.thresholds_ft;
  const stale = g.nws.stage_stale && g.usgs.discharge_stale;
  return (
    <li className="grid gap-x-6 gap-y-1 border-b border-divider py-3 font-ui text-sm sm:grid-cols-[1.4fr_1.2fr_1fr]">
      <div>
        <p className="font-semibold">{g.name ?? g.lid}</p>
        <p className="font-mono text-xs text-muted">NWS {g.lid} · USGS {g.usgs_site}</p>
      </div>
      <div>
        <span className={`inline-block rounded-full border px-2.5 py-0.5 text-xs font-semibold ${hot ? "border-alert bg-softred text-alert" : "border-ink/20 bg-soft-blue"}`}>{LABEL[cat] ?? cat}</span>
        {stale && <span className="ml-2 inline-block rounded-full border border-ink/40 px-2 py-0.5 text-xs font-semibold">Stale</span>}
        <p className="mt-1 font-mono text-xs text-muted">
          {g.nws.stage_ft_nws_datum !== null ? <>NWS stage {g.nws.stage_ft_nws_datum} ft{th.minor !== undefined && <> · minor flood at {th.minor} ft</>}</> : "No NWS stage"}
          {g.nws.stage_time && <> · {utc(g.nws.stage_time)} ({hoursText(ageH(g.nws.stage_time, now))})</>}
        </p>
      </div>
      <div className="font-mono text-xs text-muted">
        <p>{g.usgs.discharge_cfs !== null ? <>USGS discharge {g.usgs.discharge_cfs.toLocaleString("en-US")} cfs</> : "No USGS discharge"}{g.usgs.discharge_time && <> · {utc(g.usgs.discharge_time)}</>}</p>
        {g.usgs.gage_height_ft_usgs_datum !== null && <p>USGS gage height {g.usgs.gage_height_ft_usgs_datum} ft (own datum)</p>}
      </div>
    </li>
  );
}

export function NowcastView({ now }: { now: number }) {
  const { data: n, error } = useLive<Nowcast>("nowcast.json", true);
  const [all, setAll] = useState(false);
  if (error) return <p role="alert" className="rounded-2xl bg-softred p-5 font-ui text-sm">The nowcast file could not be loaded ({error}). The replay is unaffected.</p>;
  if (!n) return <p className="font-ui text-sm text-muted" aria-live="polite">Loading observed gauge readings…</p>;
  const gs = [...n.gauges].sort((a, b) => rank(a) - rank(b) || (a.name ?? "").localeCompare(b.name ?? ""));
  const up = gs.filter((g) => ORDER.includes(g.nws.flood_category)).length, stale = gs.filter((g) => g.stale).length, shown = all ? gs : gs.slice(0, 8);
  const age = ageH(n.generated_at, now);
  return (
    <section aria-labelledby="gauges-h" className="mb-14">
      <ModeHeader mode={n.mode} generated={n.generated_at} source={n.sources.join("; ")} stale={n.stale || (age !== null && age > 3)}
        staleNote={age !== null ? `File generated ${hoursText(age)}` : undefined} caveats={[...n.caveats, ...n.errors.map((e) => `Data error: ${e}`)]} />
      <h3 id="gauges-h" className="font-display text-2xl font-bold">River gauges: observed now</h3>
      <p className="mt-2 font-ui text-sm text-ink/80" role="status">
        {gs.length} {gs.length === 1 ? "gauge" : "gauges"} within 40 km of New Hanover, Brunswick or Pender · {up} at or above NWS action stage · {stale} stale.{n.n_other_basin ? ` ${n.n_other_basin} more gauges further up the Cape Fear basin are not shown.` : ""} Each row shows NWS&rsquo;s own category for NWS&rsquo;s stage. USGS gage height uses a different datum and is not compared with NWS stage.
      </p>
      <ul className="mt-4 border-t border-divider">{shown.map((g) => <Row key={g.lid} g={g} now={now} />)}</ul>
      {gs.length > 8 && (
        <button type="button" aria-expanded={all} onClick={() => setAll(!all)} className="mt-3 min-h-11 rounded-full border border-ink/20 px-5 font-ui text-sm font-semibold hover:bg-soft-blue">
          {all ? "Show fewer gauges" : `Show all ${gs.length} gauges`}
        </button>
      )}
    </section>
  );
}
