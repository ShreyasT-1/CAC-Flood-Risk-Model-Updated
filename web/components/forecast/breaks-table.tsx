"use client";
import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { crossingStatus, hourTime, pct, utc } from "@/lib/sample";
import { useSample } from "@/components/forecast/sample-store";

const STATUS = {
  "Above 10-year flow": "border-alert bg-alert text-white",
  "Above 2-year flow": "border-[#EFAEAE] bg-softred text-ink",
  "Below 2-year flow": "border-ink/15 bg-white text-muted",
} as const;

export function BreaksTable() {
  const { data, hour } = useSample();
  const [all, setAll] = useState(false);
  const rows = data ? (all ? data.crossings : data.crossings.slice(0, 8)) : [];
  const start = data?.meta.event.replay_start_utc;

  return (
    <section id="breaks" className="mx-auto max-w-screen-xl px-4 pb-20 sm:px-6 lg:pb-28">
      <div className="reveal mx-auto max-w-2xl text-center">
        <h2 className="font-display text-4xl font-bold leading-tight tracking-[-0.03em] sm:text-6xl">
          What breaks first?
        </h2>
        <p className="mt-4 font-body text-lg leading-relaxed text-ink/70">
          Crossings in the order their streams first ran above the 10-year flow during the Florence replay, with what closing each one would do.
        </p>
      </div>

      <div className="reveal mx-auto mt-12 max-w-4xl overflow-hidden rounded-3xl bg-white shadow-float sm:mt-14">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-ink/10 px-5 py-4 sm:px-6">
          <h3 className="font-ui text-sm font-semibold">
            Crossing watch <span className="font-mono font-normal text-muted">· status at {start ? hourTime(start, hour) : "…"}</span>
          </h3>
          <span className="rounded-full bg-soft-blue px-3 py-1.5 font-ui text-xs font-medium text-blue">Florence 2018 replay · sample</span>
        </div>

        {!data && <p className="px-6 py-10 text-center font-ui text-sm text-muted">Loading sample crossings…</p>}
        <ol className="divide-y divide-ink/10">
          {rows.map((c) => {
            const h = c.hourly[hour];
            const status = crossingStatus(h.level_reached.value);
            const k = c.consequence;
            return (
              <li key={c.id}>
                <details className="group">
                  <summary className="grid min-h-[76px] cursor-pointer list-none grid-cols-[44px_minmax(0,1fr)_auto_20px] items-center gap-3 px-4 py-3 marker:hidden transition-colors hover:bg-paper sm:grid-cols-[56px_minmax(0,1fr)_auto_20px] sm:gap-4 sm:px-6 [&::-webkit-details-marker]:hidden">
                    <span className="font-mono text-xl font-medium tabular-nums text-muted">
                      {String(c.breaks_first_rank).padStart(2, "0")}
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate font-ui text-sm font-semibold sm:text-base">{c.name}</span>
                      <span className="mt-1 block font-ui text-xs text-muted">
                        {c.county} · first above 10-year flow {c.event_first_above_RL10_utc.value ? utc(c.event_first_above_RL10_utc.value) : "not in replay"}
                        <span className="sm:hidden"> · {status}</span>
                      </span>
                    </span>
                    <span className={`hidden whitespace-nowrap rounded-full border px-3 py-1.5 font-mono text-xs sm:inline-flex ${STATUS[status]}`}>
                      {status}
                    </span>
                    <ChevronDown size={17} className="text-muted transition-transform group-open:rotate-180" aria-hidden />
                  </summary>
                  <div className="max-w-3xl space-y-2 px-[4.5rem] pb-5 pr-6 font-body text-sm leading-relaxed text-ink/75 sm:px-24">
                    <p>
                      If this crossing closed on its own, <b>{k.people_affected.toLocaleString()}</b> people would lose their route or be slowed by more than a
                      minute to an emergency hospital or fire station
                      {k.hosp_pop_lost_access ? `, ${k.hosp_pop_lost_access.toLocaleString()} of them with no route to a hospital at all` : ""}.
                      {k.hosp_max_detour_min ? ` Longest added drive: ${k.hosp_max_detour_min} min.` : ""}
                      {k.crossings_on_same_segment > 1 ? ` Shares its road segment with ${k.crossings_on_same_segment - 1} other crossing(s).` : ""}
                    </p>
                    <p className="font-ui text-xs text-muted">
                      Replay: flow {h.flow_ratio_q10.value}× the 10-year flow this hour · FEMA zone {c.fema_zone}
                      {c.tidal_flag ? " · tidal (river flow may not capture its flooding)" : ""} · placeholder flood chance {pct(h.flood_probability.value)}
                    </p>
                  </div>
                </details>
              </li>
            );
          })}
        </ol>
        {data && data.crossings.length > 8 && (
          <button
            type="button"
            onClick={() => setAll(!all)}
            className="flex min-h-12 w-full items-center justify-center border-t border-ink/10 font-ui text-sm font-semibold text-blue hover:bg-paper"
          >
            {all ? "Show fewer" : `Show all ${data.crossings.length} crossings`}
          </button>
        )}
        <p className="border-t border-ink/10 px-5 py-3 font-ui text-xs leading-relaxed text-muted sm:px-6">
          Closure impact uses the model&rsquo;s road network with default speeds and 2020 Census blocks. It has not been checked against real closures.
          Below the 2-year flow means not flagged, not an all-clear.
        </p>
      </div>
    </section>
  );
}
