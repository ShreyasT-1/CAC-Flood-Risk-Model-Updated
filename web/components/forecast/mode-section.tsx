"use client";
import { useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { ageH, hoursText, useLive, type Forecast } from "@/lib/live";
import { hourTime, utc } from "@/lib/sample";
import { CoastalPanel } from "@/components/forecast/coastal-panel";
import { NowcastView } from "@/components/forecast/nowcast-view";
import { ModeHeader } from "@/components/forecast/mode-header";
import { useSample } from "@/components/forecast/sample-store";

const MODES = [
  { id: "replay", label: "Replay", sub: "Florence 2018" },
  { id: "nowcast", label: "Nowcast", sub: "observed now" },
  { id: "forecast", label: "Forecast preview", sub: "unvalidated" },
] as const;
type Mode = (typeof MODES)[number]["id"];

const ReplayHeader = () => {
  const { data } = useSample();
  const m = data?.meta;
  if (!m) return null;
  return (
    <>
      <p role="note" className="mb-4 rounded-2xl border border-[#E6DFA3] bg-yellow px-5 py-4 font-ui text-sm font-semibold">
        Replay of a past storm (NWM v3.0 hindcast), not a forecast.
      </p>
      <ModeHeader mode={m.mode ?? "REPLAY"} generated={m.generated_at} source={m.data_sources[0]} stale={!!m.stale} fixed
        staleNote={`Replay starts ${hourTime(m.event.replay_start_utc, 0)}; the data are fixed, not live.`} caveats={[m.event.note, m.stamp, ...m.known_gaps]} />
    </>
  );
};

const nearZero = (v: number) => (v < 0.01 ? "under 1%" : `${Math.round(v * 100)}%`);

type Row = { id: string; name: string; max: number; first: string | null; n: number };

/** Shared result block: which sample crossings go above their 10-year flow, and the bars of the highest flows. */
function Results({ rows, missing, example }: { rows: Row[]; missing: number; example?: boolean }) {
  const flagged = rows.filter((r) => r.n > 0).sort((a, b) => b.max - a.max), top = [...rows].sort((a, b) => b.max - a.max).slice(0, 6);
  const run = example ? "this example" : "this run";
  return (
    <>
      {flagged.length === 0 ? (
        <p role="status" className="rounded-2xl bg-soft-blue p-5 font-body text-base leading-relaxed">
          Nothing above the 10-year flow in {run}, which is not an all-clear. This view looks at river flow only, for {rows.length} sample crossings.
        </p>
      ) : (
        <div role="status" className="rounded-2xl bg-softred p-5 font-body text-base leading-relaxed">
          <p className="font-semibold">{flagged.length} of {rows.length} sample crossings are above their 10-year flow in at least one hour of {run} (a scenario, not a probability of closure):</p>
          <ul className="mt-2 list-disc pl-5">
            {flagged.map((r) => <li key={r.id}>{r.name}: {r.n} h flagged, first at {r.first}, peak {r.max.toFixed(2)}× the 10-year flow</li>)}
          </ul>
        </div>
      )}
      {missing > 0 && <p className="mt-3 font-ui text-xs text-muted">{missing} crossings had no model output in this cycle and are not shown.</p>}

      <h3 className="label mt-8 text-muted">Highest modelled flow, as a share of the 10-year flow</h3>
      <ul className="mt-3 space-y-3">
        {top.map((r) => (
          <li key={r.id} className="font-ui text-sm">
            <div className="flex justify-between gap-4"><span>{r.name}</span><span className="font-mono">{nearZero(r.max)}</span></div>
            <div className="relative mt-1 h-2.5 rounded-full bg-ink/10" aria-hidden>
              <div className="h-full rounded-full bg-blue" style={{ width: `${Math.min(100, r.max * 100)}%` }} />
              <div className="absolute inset-y-[-3px] right-0 w-0.5 bg-ink" />
            </div>
          </li>
        ))}
      </ul>
      <p className="mt-2 font-ui text-xs text-muted">The black tick at the right end is the 10-year flow (100%). A low share is not an assurance for any road.</p>
    </>
  );
}

function LivePreview({ active, now }: { active: boolean; now: number }) {
  const { data: f, error } = useLive<Forecast>("forecast_latest.json", active);
  if (error) return <p role="alert" className="rounded-2xl bg-softred p-5 font-ui text-sm">The forecast preview file could not be loaded ({error}). The replay is unaffected.</p>;
  if (!f) return <p className="font-ui text-sm text-muted" aria-live="polite">Loading forecast preview…</p>;
  const live = ageH(f.cycle_issue_time, now);
  const stale = f.stale || (live !== null && live > 6);
  const rows: Row[] = f.crossings.filter((c) => c.in_model_output).map((c) => {
    const flagged = c.hourly.filter((h) => h.scenario_state === "scenario: flagged");
    return { id: c.id, name: c.name, max: Math.max(0, ...c.hourly.map((h) => h.flow_ratio_q10 ?? 0)), first: flagged[0] ? utc(flagged[0].valid_time) : null, n: flagged.length };
  });
  return (
    <>
      <ModeHeader mode={f.mode} generated={f.generated_at} source={f.source} stale={stale} caveats={f.caveats}
        staleNote={live !== null ? `Cycle issued ${hoursText(live)}` : undefined}>
        <p className="mt-4 flex flex-wrap gap-2 font-ui text-xs font-semibold">
          <span className="rounded-full bg-soft-blue px-3 py-1">{f.label}</span>
          {f.not_a_closure_probability && <span className="rounded-full bg-yellow px-3 py-1">Not a closure probability</span>}
        </p>
        <dl className="mt-4 grid gap-x-8 gap-y-2 font-ui text-sm sm:grid-cols-[auto_1fr]">
          <dt className="label text-muted">Cycle issued</dt><dd className="font-mono">{utc(f.cycle_issue_time)}</dd>
          <dt className="label text-muted">Cycle age at generation</dt><dd className="font-mono">{f.cycle_age_hours} h</dd>
          <dt className="label text-muted">Leads</dt><dd className="font-mono">1 to 18 h after issue · {f.nwm_version}</dd>
          {f.fallback.used && <><dt className="label text-muted">Fallback</dt><dd>{f.fallback.note} (skipped: {f.fallback.skipped_newer_cycles.map((s) => `${s.cycle}, ${s.reason}`).join("; ")})</dd></>}
        </dl>
      </ModeHeader>
      <Results rows={rows} missing={f.crossings.length - rows.length} />
    </>
  );
}

/** Past-storm example so the view is not empty in calm weather: the 18 Florence replay hours (NWM v3.0 hindcast flow), laid out like forecast leads. */
function ExamplePreview() {
  const { data } = useSample();
  if (!data) return <p className="font-ui text-sm text-muted" aria-live="polite">Loading example…</p>;
  const m = data.meta, start = m.event.replay_start_utc;
  const rows: Row[] = data.crossings.map((c) => {
    const hrs = c.hourly.map((h) => h.flow_ratio_q10.value), first = hrs.findIndex((r) => r > 1);
    return { id: c.id, name: c.name, max: Math.max(0, ...hrs), first: first < 0 ? null : hourTime(start, first), n: hrs.filter((r) => r > 1).length };
  });
  return (
    <>
      <p role="note" className="mb-4 rounded-2xl border border-[#E6DFA3] bg-yellow px-5 py-4 font-ui text-sm font-semibold">
        Example run of a past storm (Hurricane Florence, 2018). Not live, not a forecast, not validated.
      </p>
      <ModeHeader mode="EXAMPLE · PAST STORM (HINDCAST)" generated={m.generated_at} source={m.data_sources[0]} stale={false} fixed
        staleNote={`Fixed data, not live. Leads 1 to ${m.event.hours} h are the replay hours starting ${hourTime(start, 0)}.`}
        caveats={["The flows are the NWM v3.0 retrospective (a free-running hindcast), laid out like forecast leads. No forecast was issued at the time and none is shown.",
          "Not validated, and no forecast skill is claimed. River flow only; no surge, tide or drainage flooding.",
          "The Florence hindcast is saturated: many crossings are above their 10-year flow at once, so this example shows the layout, not how often the live view will look like this.", ...m.known_gaps]} />
      <Results rows={rows} missing={0} example />
    </>
  );
}

function ForecastPreview({ active, now }: { active: boolean; now: number }) {
  const [view, setView] = useState<"live" | "example">("live");
  const opt = (id: "live" | "example", label: string) => (
    <button type="button" aria-pressed={view === id} onClick={() => setView(id)}
      className={`min-h-11 flex-1 rounded-full px-4 font-ui text-sm font-semibold transition ${view === id ? "bg-ink text-white" : "text-ink hover:bg-white/70"}`}>{label}</button>
  );
  return (
    <>
      <div role="group" aria-label="Forecast preview view" className="mb-5 flex max-w-xl flex-col gap-1 rounded-full bg-soft-blue p-1 sm:flex-row">
        {opt("live", "Latest NWM run")}
        {opt("example", "Example run: Florence 2018 hindcast leads")}
      </div>
      {view === "live" ? <LivePreview active={active} now={now} /> : <ExamplePreview />}
    </>
  );
}

/** Replay (default) | Nowcast | Forecast preview. Only the active mode is rendered; the three never share a panel. */
export function ModeSection({ replay }: { replay: ReactNode }) {
  const [mode, setMode] = useState<Mode>("replay");
  const [now] = useState(() => Date.now());
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  const onKey = (e: KeyboardEvent, i: number) => {
    const j = e.key === "ArrowRight" ? (i + 1) % 3 : e.key === "ArrowLeft" ? (i + 2) % 3 : e.key === "Home" ? 0 : e.key === "End" ? 2 : -1;
    if (j < 0) return;
    e.preventDefault(); setMode(MODES[j].id); tabs.current[j]?.focus();
  };
  return (
    <div>
      <div role="tablist" aria-label="Data mode" className="mx-auto mb-8 flex max-w-2xl flex-col gap-2 rounded-3xl bg-soft-blue p-2 sm:flex-row">
        {MODES.map((m, i) => (
          <button key={m.id} ref={(el) => { tabs.current[i] = el; }} role="tab" id={`tab-${m.id}`} aria-selected={mode === m.id} aria-controls={`panel-${m.id}`}
            tabIndex={mode === m.id ? 0 : -1} onClick={() => setMode(m.id)} onKeyDown={(e) => onKey(e, i)}
            className={`min-h-12 flex-1 rounded-2xl px-4 py-2 text-center font-ui text-sm font-semibold transition ${mode === m.id ? "bg-ink text-white shadow-panel" : "text-ink hover:bg-white/70"}`}>
            {m.label}<span className="block text-xs font-normal opacity-80">{m.sub}</span>
          </button>
        ))}
      </div>
      <div role="tabpanel" id="panel-replay" aria-labelledby="tab-replay" hidden={mode !== "replay"} tabIndex={0}>
        {mode === "replay" && <><ReplayHeader />{replay}</>}
      </div>
      <div role="tabpanel" id="panel-nowcast" aria-labelledby="tab-nowcast" hidden={mode !== "nowcast"} tabIndex={0} className="mx-auto max-w-4xl">
        {mode === "nowcast" && <><NowcastView now={now} /><CoastalPanel now={now} /></>}
      </div>
      <div role="tabpanel" id="panel-forecast" aria-labelledby="tab-forecast" hidden={mode !== "forecast"} tabIndex={0} className="mx-auto max-w-4xl">
        <ForecastPreview active={mode === "forecast"} now={now} />
      </div>
    </div>
  );
}
