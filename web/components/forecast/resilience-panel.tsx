"use client";
import { Activity, ExternalLink, HeartPulse, House, Info, MapPin, Search, Stethoscope } from "lucide-react";
import { hourTime, isStress, band, risk, type LocationView } from "@/lib/sample";
import { useSample } from "@/components/forecast/sample-store";
import { Tag } from "@/components/ui/tags";

const KIND = { dialysis: "Dialysis site (placeholder facility)", nursing_home: "Nursing home (placeholder facility)", residential: "Residential block (sample)", address: "Your search" };
const ICON = { dialysis: HeartPulse, nursing_home: Stethoscope, residential: House, address: MapPin };

function Timeline({ loc, hour }: { loc: LocationView; hour: number }) {
  return (
    <div className="mt-6" aria-label="Illustrative band of losing access in each replay hour">
      <div className="flex h-16 items-end gap-[3px]">
        {loc.hours.map((h, i) => (
          <span
            key={i}
            title={`Hour ${i}: illustrative band ${band(h.p)}${h.lost ? ", no route in the replay" : ""}`}
            className={`flex-1 rounded-t-sm border border-ink/10 ${risk(h.p).cls} ${i === hour ? "outline outline-2 outline-offset-1 outline-blue" : ""}`}
            style={{ height: `${Math.max(6, h.p * 100)}%` }}
          />
        ))}
      </div>
      <div className="mt-1 flex gap-[3px]" aria-hidden>
        {loc.hours.map((h, i) => <span key={i} className={`h-1.5 flex-1 rounded-sm ${h.lost ? "bg-ink" : "bg-ink/10"}`} />)}
      </div>
      <p className="mt-2 font-ui text-xs text-muted">
        Bars: illustrative band of losing access <Tag synthetic /> · dark strip: no route to an emergency hospital in the replay <Tag synthetic={false} />
      </p>
    </div>
  );
}

export function ResiliencePanel() {
  const { data, hour, selected: loc, select, crossingName } = useSample();
  const start = data?.meta.event.replay_start_utc;
  const syn = (field: string) => data?.meta.fields[field]?.synthetic ?? true;
  const h = loc?.hours[hour];
  const r = h ? risk(h.p) : null;

  const metrics: [string, string, boolean][] = !loc || !h || !loc.assessed ? [] : [
    ["Isolation band (illustrative)", band(h.p), syn("isolation_probability")],
    ["Time to isolation", h.tti === null ? "Not in replay window" : h.tti === 0 ? "Now" : `In about ${h.tti} h`, syn("time_to_isolation")],
    ["Isolation duration", h.dur === null ? "-" : `About ${h.dur} h`, syn("isolation_duration")],
    ["Detour", h.lost ? "No route" : h.detour ? `+${h.detour} min` : "1 min or less", syn("detour_minutes")],
    ["Critical crossing", h.crit ? crossingName(h.crit) : "None closed on the usual route", syn("critical_crossing_id")],
    ["Route redundancy", `${h.red} ED hospital${h.red === 1 ? "" : "s"} within 30 min (usually ${loc.baselineRed ?? "-"})`, syn("route_redundancy")],
  ];

  return (
    <div className="mt-8 grid grid-cols-1 items-start gap-4 lg:grid-cols-3">
      <section className="reveal rounded-3xl border border-ink/10 bg-white p-6 sm:p-8 lg:col-span-2" aria-labelledby="res" aria-live="polite">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 id="res" className="font-ui text-sm font-semibold">{loc ? loc.name : "Your route"}</h3>
            <p className="mt-0.5 font-ui text-sm text-muted">
              {loc ? `${KIND[loc.kind]} · ${loc.county} · ${loc.basis}` : "Emergency hospital access"}
            </p>
          </div>
          {r && loc?.assessed ? (
            <span className={`rounded-full border border-ink/10 px-3 py-1.5 font-ui text-xs font-semibold ${r.solid} ${r.max > 0.55 ? "text-white" : "text-ink"}`}>
              Illustrative · {r.label}
            </span>
          ) : (
            <span className="rounded-full border border-ink/10 bg-paper px-3 py-1.5 font-ui text-xs font-semibold text-muted">Sample replay</span>
          )}
        </div>

        {!loc ? (
          <>
            <p className="mt-8 font-display text-3xl font-bold leading-tight tracking-[-0.02em] sm:text-4xl">Pick a place to see its route</p>
            <p className="mt-3 inline-flex items-center gap-2 font-ui text-sm text-muted">
              <Search size={16} aria-hidden />
              Choose a place to watch, or search an address above for full route analysis.
            </p>
          </>
        ) : !loc.assessed ? (
          <>
            <p className="mt-8 font-display text-3xl font-bold leading-tight tracking-[-0.02em] sm:text-4xl">Not assessed</p>
            <p className="mt-3 max-w-xl font-body text-sm leading-relaxed text-ink/75">
              This block sits on a road fragment with no route to an emergency hospital in the model&rsquo;s road network, so it was not assessed. That is
              a gap in the model, not a low risk.
            </p>
          </>
        ) : (
          <>
            <p className="mt-8 font-display text-3xl font-bold leading-tight tracking-[-0.02em] sm:text-4xl">
              {h!.lost ? "No route to an emergency hospital in this replay hour" : "Not flagged in this replay hour"}
            </p>
            <p className="mt-3 inline-flex flex-wrap items-center gap-2 font-mono text-sm text-blue">
              <Activity size={16} aria-hidden />
              Illustrative band: {band(h!.p)} <Tag synthetic={syn("isolation_probability")} />
            </p>
            {!h!.lost && (
              <p className="mt-2 font-ui text-xs text-muted">Not flagged is not an all-clear: this replay sees river flow only.</p>
            )}
            <Timeline loc={loc} hour={hour} />
          </>
        )}

        <dl className="mt-8 grid grid-cols-2 gap-x-6 border-t border-ink/10 sm:grid-cols-3">
          {(metrics.length ? metrics : ["Isolation band (illustrative)", "Time to isolation", "Isolation duration", "Detour", "Critical crossing", "Route redundancy"].map((l) => [l, "-", false] as [string, string, boolean])).map(([label, value, s], index) => (
            <div key={label} className={`min-w-0 py-4 ${index < 4 ? "border-b border-ink/10" : ""} ${index >= 3 ? "sm:border-b-0" : ""}`}>
              <dt className="font-ui text-xs leading-snug text-muted">
                {label}
                {metrics.length ? <Tag synthetic={s} /> : null}
              </dt>
              <dd className="mt-1 break-words font-mono text-sm font-medium">{value}</dd>
            </div>
          ))}
        </dl>
        {loc && (
          <a
            href={`/route?${new URLSearchParams({ lat: String(loc.lat), lon: String(loc.lon), label: loc.name, ...(isStress() ? { data: "stress" } : {}) })}`}
            target="_blank"
            rel="noopener"
            className="mt-6 inline-flex min-h-11 items-center gap-2 rounded-full bg-blue px-5 font-ui text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-[#244d86] hover:shadow-lift"
          >
            Plan routes from here <ExternalLink size={15} aria-hidden />
            <span className="sr-only">(opens in a new window)</span>
          </a>
        )}
        {loc?.assessed && (
          <p className="mt-2 font-ui text-xs text-muted">
            Assumed tolerance without access: {loc.tolerance} h <Tag synthetic={syn("isolation_tolerance")} />
          </p>
        )}
        {loc?.county === "New Hanover" && (
          <p className="mt-3 rounded-xl bg-yellow px-3 py-2 font-ui text-xs leading-relaxed text-ink/80">
            In 2018 Wilmington was cut off, but this replay shows little loss of access in New Hanover. The gap comes from the model&rsquo;s crossing list
            and road network, so low values here are not evidence of low exposure.
          </p>
        )}
        <p className="mt-4 font-mono text-xs leading-relaxed text-muted">
          Replay hour {hour}: {start ? hourTime(start, hour) : "…"} <span className="px-1">|</span> Source: FloodLens sample export, Florence 2018 hindcast,
          not validated
        </p>
      </section>

      <div className="grid min-w-0 grid-cols-1 gap-4">
        <details className="reveal group rounded-3xl border border-[#E6DFA3] bg-yellow">
          <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-4 px-6 py-4 font-ui text-sm font-semibold marker:hidden [&::-webkit-details-marker]:hidden">
            <span className="inline-flex items-center gap-2">
              <Info size={17} strokeWidth={1.8} aria-hidden />
              What this means
            </span>
            <span className="text-xl transition-transform group-open:rotate-45" aria-hidden>+</span>
          </summary>
          <div className="space-y-2 px-6 pb-6 font-body text-sm leading-relaxed text-ink/80">
            <p>
              <b>Replay</b> values come from re-running Hurricane Florence through the model&rsquo;s road network: which crossings&rsquo; streams ran above
              their 10-year flow, and what that did to drive times to emergency hospitals.
            </p>
            <p>
              <b>Placeholder</b> values stand in for the forecast model that is still being built. They follow the replay, so they show the layout, not
              forecast skill.
            </p>
          </div>
        </details>

        <section className="reveal rounded-3xl bg-soft-blue/60 p-6" aria-labelledby="watch">
          <div className="flex items-center justify-between gap-3">
            <h3 id="watch" className="font-ui text-sm font-semibold">Places to watch</h3>
            <span className="rounded-full bg-white px-2.5 py-1 font-ui text-xs font-semibold text-blue">Sample</span>
          </div>
          <ul className="mt-2">
            {(data?.watch ?? []).map((w) => {
              const site = data!.sites.find((s) => s.id === w.id)!;
              const Icon = ICON[w.kind];
              const p = site.hours[hour].p;
              return (
                <li key={w.id}>
                  <button
                    type="button"
                    onClick={() => select(site)}
                    aria-pressed={loc?.id === w.id}
                    className={`flex min-h-12 w-full items-center gap-3 border-b border-ink/10 py-2 text-left transition-colors hover:text-blue ${loc?.id === w.id ? "text-blue" : ""}`}
                  >
                    <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-white text-blue">
                      <Icon size={16} strokeWidth={1.8} aria-hidden />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-ui text-sm font-medium">{w.name.replace(" (placeholder)", "")}</span>
                      <span className="block font-ui text-[11px] text-muted">{w.alert_level.replace(" (sample)", "")} · {w.county}</span>
                    </span>
                    <span className={`shrink-0 rounded-full px-2 py-0.5 font-mono text-xs ${risk(p).solid} ${p >= 0.55 ? "text-white" : "text-ink"}`}><span className="mr-1 text-[10px] uppercase tracking-wide opacity-80">Illustrative</span>{band(p)}</span>
                  </button>
                </li>
              );
            })}
          </ul>
          <p className="mt-3 font-ui text-xs leading-relaxed text-muted">
            Placeholder facilities placed at real Census block centres; chances are placeholders. Bands only order places against each other; they are not probabilities. Alert levels follow the watch/warning style but are
            not National Weather Service products.
          </p>
        </section>
      </div>
    </div>
  );
}
