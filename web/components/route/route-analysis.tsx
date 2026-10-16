"use client";
import { AlertTriangle, CircleSlash, Route as RouteIcon } from "lucide-react";
import { CLOSED, blockedHours, routeAtHour, type HourStatus, type RouteOption } from "@/lib/route";
import { hourTime, pct, utc, type LocationView } from "@/lib/sample";
import { Tag } from "@/components/ui/tags";

type Ranked = { o: RouteOption; s: HourStatus }[];
export type Group = { kind: "hospital" | "fire"; title: string; ranked: Ranked };
const STATE = [
  { label: "Open in replay", cls: "border-blue/30 bg-soft-blue text-blue", note: "Open in this replay hour is not an all-clear: the replay sees river flow only, and streams the model did not assess are not counted." },
  { label: "At risk", cls: "border-alert/40 bg-softred text-alert", note: "Crosses streams above their 2-year flow, or the placeholder chance of a crossing flooding is 35% or more." },
  { label: "Blocked in replay", cls: "border-[#7A0000] bg-[#7A0000] text-white", note: "Crosses at least one crossing whose stream is above its 10-year flow, which closes it in this scenario." },
];
const mins = (s: number) => (s < 5400 ? `${Math.round(s / 60)} min` : `${Math.floor(s / 3600)} h ${Math.round((s % 3600) / 60)} min`);
const KIND = { fastest: "Fastest route", alternate: "Alternative route", detour: "Detour around closed crossings" };

export function StatusBadge({ state }: { state: 0 | 1 | 2 }) {
  return <span className={`inline-flex whitespace-nowrap rounded-full border px-2.5 py-1 font-ui text-xs font-semibold ${STATE[state].cls}`}>{STATE[state].label}</span>;
}

export function RouteAnalysis({ groups, focusId, onFocus, hour, hours, start, names, fastest, block, noRoute }: {
  groups: Group[]; focusId: string | null; onFocus: (id: string) => void; hour: number; hours: number; start: string;
  names: Record<string, string>; fastest: Record<string, number>; block: LocationView | null; noRoute: { name: string; reason: string }[];
}) {
  const live = groups.filter((g) => g.ranked.length);
  if (!live.length) return null;
  const all = live.flatMap((g) => g.ranked);
  const cur = all.find((r) => r.o.id === focusId) ?? all[0];
  const group = live.find((g) => g.ranked.includes(cur))!;
  const ranked = group.ranked, best = ranked[0];
  const { o, s } = cur;
  const bh = blockedHours(o.on, hours);
  const assessed = o.on.filter((c) => c.x), other = o.on.length - assessed.length;
  const extra = o.timeS - (fastest[o.serviceId] ?? o.timeS);
  const allBlocked = best.s.state === 2;

  return (
    <section aria-labelledby="ra" className="space-y-6">
      <div className={`rounded-2xl border p-5 ${allBlocked ? "border-[#7A0000] bg-softred" : "border-ink/10 bg-white"}`}>
        <p className="label text-muted">{cur === best ? `${allBlocked ? "No open route found" : "Best route"} · ${group.title.toLowerCase()}` : "Route you selected"}</p>
        <h2 id="ra" className="mt-1 font-display text-2xl font-bold leading-tight tracking-[-0.02em]">{names[o.serviceId]}</h2>
        <p className="mt-1 font-ui text-sm text-muted">{KIND[o.kind]} via {o.via}</p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <StatusBadge state={s.state} />
          <span className="font-mono text-xs text-muted">{hourTime(start, hour)}</span>
        </div>
        <p className="mt-2 font-ui text-xs leading-relaxed text-muted">{STATE[s.state].note}</p>
        {cur === best && (
          <p className="mt-3 font-body text-sm leading-relaxed text-ink/80">
            {allBlocked
              ? `Every route found to the selected ${group.title.toLowerCase()} crosses a crossing that is closed in this replay hour${noRoute.length ? ", and no detour around the closures was found" : ""}. Shown: the option with the fewest closures. Call 911 in an emergency.`
              : `Ranked first of ${ranked.length} option${ranked.length > 1 ? "s" : ""}: open in the replay this hour, ${pct(s.pFail)} placeholder chance that a crossing on it floods, and ${mins(o.timeS)} in normal traffic.`}
          </p>
        )}
      </div>

      <dl className="grid grid-cols-2 gap-x-5 border-y border-ink/10">
        {([
          ["Drive time (normal roads)", mins(o.timeS), null],
          ["Compared with fastest", extra > 30 ? `+${mins(extra)}` : "Fastest", null],
          ["Distance", `${o.km.toFixed(1)} km`, null],
          ["Chance a crossing on it floods", pct(s.pFail), true],
          ["Hours blocked in replay", `${bh.length} of ${hours}`, false],
          ["First blocked", bh.length ? hourTime(start, bh[0]) : "Not in this window", false],
        ] as [string, string, boolean | null][]).map(([k, v, syn], i) => (
          <div key={k} className={`min-w-0 py-3 ${i < 4 ? "border-b border-ink/10" : ""}`}>
            <dt className="font-ui text-xs text-muted">{k}{syn !== null && <Tag synthetic={syn} />}</dt>
            <dd className="mt-0.5 break-words font-mono text-sm font-medium">{v}</dd>
          </div>
        ))}
      </dl>

      <div>
        <h3 className="font-ui text-sm font-semibold">This route, hour by hour</h3>
        <div className="mt-3 flex h-14 items-end gap-[3px]" aria-label="Route status per replay hour">
          {Array.from({ length: hours }, (_, h) => {
            const st = routeAtHour(o.on, h);
            return (
              <span key={h} title={`${hourTime(start, h)}: ${STATE[st.state].label}, ${pct(st.pFail)} placeholder chance`}
                className={`flex-1 rounded-t-sm ${["bg-blue/70", "bg-alert", "bg-[#7A0000] hatch"][st.state]} ${h === hour ? "outline outline-2 outline-offset-1 outline-ink" : ""}`}
                style={{ height: `${Math.max(10, st.pFail * 100)}%` }} />
            );
          })}
        </div>
        <p className="mt-2 font-ui text-xs text-muted">
          Colour: replay status <Tag synthetic={false} /> · height: chance a crossing floods <Tag synthetic />
        </p>
      </div>

      <div>
        <h3 className="font-ui text-sm font-semibold">Stream crossings on this route ({o.on.length})</h3>
        {assessed.length === 0 ? (
          <p className="mt-2 font-ui text-sm text-muted">None of the 250 crossings the replay can close lie on this route.</p>
        ) : (
          <ol className="mt-2 divide-y divide-ink/10 border-y border-ink/10">
            {assessed.map((c) => {
              const lv = +c.x!.level[hour], r = c.x!.ratio_q10[hour];
              return (
                <li key={c.id} className="grid grid-cols-[3.2rem_minmax(0,1fr)] gap-2 py-2.5">
                  <span className="font-mono text-xs text-muted">{c.km.toFixed(1)} km</span>
                  <div className="min-w-0">
                    <p className="flex flex-wrap items-center gap-x-2 font-ui text-sm font-medium">
                      <span className="min-w-0 break-words">{c.x!.name}</span>
                      {lv >= CLOSED ? <span className="rounded-full bg-alert px-2 py-px font-ui text-[11px] font-semibold text-white">closed</span>
                        : lv > 0 ? <span className="rounded-full bg-softred px-2 py-px font-ui text-[11px] font-semibold text-alert">above 2-yr</span> : null}
                    </p>
                    <p className="mt-0.5 font-ui text-xs leading-relaxed text-muted">
                      Flow {r == null ? "unknown" : `${r}× the 10-year flow`} <Tag synthetic={false} /> · flood chance {c.x!.p_pct[hour]}% <Tag synthetic /> ·
                      first above 10-yr {c.x!.first_above_RL10_utc ? utc(c.x!.first_above_RL10_utc) : "not in replay"} · FEMA {c.x!.fema_zone}
                      {c.x!.tidal ? " · tidal: surge may matter more than river flow" : ""} · {c.x!.people_affected.toLocaleString()} people affected if it closes alone
                    </p>
                  </div>
                </li>
              );
            })}
          </ol>
        )}
        {other > 0 && (
          <p className="mt-2 font-ui text-xs text-muted">
            Plus {other} stream crossing{other > 1 ? "s" : ""} the model did not assess (no flow threshold, or OpenStreetMap-only). Unassessed is not the same as open.
          </p>
        )}
      </div>

      <div>
        <h3 className="font-ui text-sm font-semibold">All route options ({all.length})</h3>
        {live.map((g) => (
          <div key={g.kind} className="mt-3">
            <p className="label text-muted">{g.title}</p>
            <ol className="mt-1 divide-y divide-ink/10 border-y border-ink/10">
              {g.ranked.map(({ o: r, s: st }, i) => (
                <li key={r.id}>
                  <button type="button" onClick={() => onFocus(r.id)} aria-pressed={r.id === o.id}
                    className={`grid min-h-12 w-full grid-cols-[1.5rem_minmax(0,1fr)_auto] items-center gap-2 py-2 text-left transition-colors hover:bg-paper ${r.id === o.id ? "bg-soft-blue/60" : ""}`}>
                    <span className="font-mono text-xs text-muted">{i + 1}</span>
                    <span className="min-w-0">
                      <span className="block truncate font-ui text-sm font-medium">{names[r.serviceId]}</span>
                      <span className="block truncate font-ui text-xs text-muted">
                        {KIND[r.kind]} · {mins(r.timeS)} · {pct(st.pFail)} chance{r.on.some((c) => !c.x) ? ` · ${r.on.filter((c) => !c.x).length} unassessed` : ""}
                      </span>
                    </span>
                    <StatusBadge state={st.state} />
                  </button>
                </li>
              ))}
            </ol>
          </div>
        ))}
        {noRoute.map((n) => (
          <p key={n.name} className="mt-2 flex gap-2 font-ui text-xs text-alert"><CircleSlash size={14} className="mt-px shrink-0" aria-hidden />{n.name}: {n.reason}.</p>
        ))}
        <p className="mt-2 font-ui text-xs leading-relaxed text-muted">
          Ranking: fewest closed crossings first (open routes lead), then the lower placeholder chance (in 5-point steps), then the shorter drive.
        </p>
      </div>

      {block && (
        <div className="rounded-2xl bg-soft-blue/60 p-4">
          <h3 className="flex items-center gap-2 font-ui text-sm font-semibold"><RouteIcon size={15} aria-hidden /> Cross-check: the model&rsquo;s own road network</h3>
          {!block.assessed ? (
            <p className="mt-2 font-ui text-sm text-ink/80">Your Census block has no route in the model&rsquo;s network, so the replay did not assess it. That is a gap, not a low risk.</p>
          ) : (
            <p className="mt-2 font-ui text-sm leading-relaxed text-ink/80">
              In the pipeline&rsquo;s routing of your nearest Census block ({block.distanceKm?.toFixed(1)} km away), the block has
              {block.hours.some((h) => h.lost) ? ` no route to any emergency hospital in ${block.hours.filter((h) => h.lost).length} of ${hours} hours` : " a route to an emergency hospital in every hour"}
              {block.hours[hour].lost ? ", including this one" : block.hours[hour].detour ? `; this hour adds ${block.hours[hour].detour} min` : ""}.
              <Tag synthetic={false} /> Its road network and speeds differ from the routes above, so the two can disagree.
            </p>
          )}
        </div>
      )}

      <p className="flex gap-2 font-ui text-xs leading-relaxed text-muted">
        <AlertTriangle size={14} className="mt-0.5 shrink-0" aria-hidden />
        Routes from OpenStreetMap via Valhalla, normal traffic. Closures come from the Florence 2018 replay (river flow only: no surge, tide or street
        flooding). Crossings are matched to a route within 30 m. Sample data, not validated, not for emergency use.
      </p>
    </section>
  );
}
