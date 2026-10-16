"use client";
import { ageH, hoursText, useLive, type Coastal, type Station } from "@/lib/live";
import { utc } from "@/lib/sample";
import { ModeHeader } from "@/components/forecast/mode-header";

const W = 360, Ht = 200, PAD = { l: 34, r: 8, t: 10, b: 20 };

/** Observed vs predicted tide for one station. Lines differ by dash and weight, not colour alone. The outlook is dashed and labelled as a placeholder. */
function Chart({ s }: { s: Station }) {
  const rows = s.hourly, n = rows.length;
  const vals = rows.flatMap((r) => [r.tide_pred_m_navd88, r.observed_m_navd88, r.outlook_total_m_navd88]).filter((v): v is number => typeof v === "number");
  const lo = Math.floor(Math.min(...vals) * 2) / 2, hi = Math.ceil(Math.max(...vals) * 2) / 2;
  const x = (i: number) => PAD.l + (i / (n - 1)) * (W - PAD.l - PAD.r), y = (v: number) => PAD.t + (1 - (v - lo) / (hi - lo)) * (Ht - PAD.t - PAD.b);
  const line = (pick: (r: (typeof rows)[number]) => number | null | undefined) =>
    rows.map((r, i) => { const v = pick(r); return typeof v === "number" ? `${x(i).toFixed(1)},${y(v).toFixed(1)}` : null; }).filter(Boolean).join(" ");
  const iNow = rows.reduce((a, r, i) => (typeof r.observed_m_navd88 === "number" ? i : a), -1);
  const ticks = [lo, (lo + hi) / 2, hi];
  return (
    <svg viewBox={`0 0 ${W} ${Ht}`} className="mt-3 block w-full max-w-xl" role="img"
      aria-label={`${s.name} water level, metres above NAVD88, ${n} hourly points. Heavy solid line: observed. Thin line: predicted tide.${iNow >= 0 ? " Dashed line: placeholder outlook, not surge guidance." : " Predictions only."}`}>
      {ticks.map((t) => <g key={t}><line x1={PAD.l} x2={W - PAD.r} y1={y(t)} y2={y(t)} stroke="#E3E5E8" /><text x={PAD.l - 6} y={y(t) + 4} textAnchor="end" fontSize="11" fill="#555">{t.toFixed(1)}</text></g>)}
      {iNow >= 0 && <g><line x1={x(iNow)} x2={x(iNow)} y1={PAD.t} y2={Ht - PAD.b} stroke="#111" strokeDasharray="2 3" /></g>}
      <polyline points={line((r) => r.tide_pred_m_navd88)} fill="none" stroke="#2D5DA1" strokeWidth="1.5" />
      <polyline points={line((r) => r.observed_m_navd88)} fill="none" stroke="#111" strokeWidth="3" />
      <polyline points={line((r) => r.outlook_total_m_navd88)} fill="none" stroke="#7A5200" strokeWidth="2" strokeDasharray="6 5" />
      <text x={PAD.l} y={Ht - 5} fontSize="11" fill="#555">{rows[0].t.slice(5, 10)} UTC</text>
    </svg>
  );
}

const Legend = ({ obs }: { obs: boolean }) => (
  <ul className="mt-1 flex flex-wrap gap-x-5 gap-y-1 font-ui text-xs text-ink/80">
    <li>Metres above NAVD88</li>
    {obs && <li><b>Heavy line</b>: observed</li>}
    <li><span className="text-blue">Thin line</span>: predicted tide</li>
    {obs && <li><span className="font-semibold text-[#7A5200]">Dashed line</span>: outlook, placeholder, not surge guidance</li>}
    {obs && <li>Dotted vertical: latest observation</li>}
  </ul>
);

function StationCard({ s, now }: { s: Station; now: number }) {
  const recent = s.hourly.filter((r) => typeof r.observed_m_navd88 === "number").slice(-6).reverse();
  const res = s.latest_residual_m;
  return (
    <article className="rounded-2xl border border-ink/10 bg-white p-5 shadow-panel">
      <h4 className="font-display text-xl font-bold">{s.name} <span className="font-mono text-sm font-normal text-muted">{s.id}</span></h4>
      <p className="mt-2 flex flex-wrap gap-2 font-ui text-xs font-semibold">
        {!s.has_observations && <span className="rounded-full bg-yellow px-3 py-1">Predictions only: no observed water level here</span>}
        {s.riverine_influence && <span className="rounded-full bg-yellow px-3 py-1">Riverine: up the Cape Fear River, so the residual includes river flow, not only surge</span>}
        {s.has_observations && <span className={`rounded-full border px-3 py-1 ${s.stale ? "border-alert bg-softred text-alert" : "border-ink/20 bg-soft-blue"}`}>{s.stale ? "Stale observations" : "Observations current"}</span>}
      </p>
      {s.has_observations && s.latest_observed_time && (
        <p className="mt-3 font-ui text-sm">
          Latest residual (observed minus predicted tide): <b className="font-mono">{res === null ? "n/a" : `${res > 0 ? "+" : ""}${res.toFixed(2)} m`}</b>
          <span className="font-mono text-xs text-muted"> · {utc(s.latest_observed_time)} ({hoursText(ageH(s.latest_observed_time, now))})</span>
        </p>
      )}
      <Chart s={s} />
      <Legend obs={s.has_observations} />
      {recent.length > 0 && (
        <details className="mt-2">
          <summary className="flex min-h-11 cursor-pointer items-center font-ui text-sm font-semibold">Recent hourly values (table)</summary>
          <table className="mt-1 w-full font-mono text-xs">
            <caption className="sr-only">Recent hourly water level at {s.name}, metres NAVD88</caption>
            <thead><tr className="text-left text-muted"><th scope="col" className="py-1">Hour (UTC)</th><th scope="col">Observed</th><th scope="col">Predicted</th><th scope="col">Residual</th></tr></thead>
            <tbody>{recent.map((r) => <tr key={r.t} className="border-t border-divider"><th scope="row" className="py-1 text-left font-normal">{r.t.slice(5, 16).replace("T", " ")}</th><td>{r.observed_m_navd88}</td><td>{r.tide_pred_m_navd88}</td><td>{r.residual_m}</td></tr>)}</tbody>
          </table>
        </details>
      )}
    </article>
  );
}

/** Coastal water levels: a separate layer. Never merged with river gauges, crossings or any probability. */
export function CoastalPanel({ now }: { now: number }) {
  const { data: c, error } = useLive<Coastal>("coastal.json", true);
  if (error) return <p role="alert" className="mt-10 rounded-2xl bg-softred p-5 font-ui text-sm">The coastal water-level file could not be loaded ({error}).</p>;
  if (!c) return <p className="mt-10 font-ui text-sm text-muted" aria-live="polite">Loading coastal water levels…</p>;
  const age = ageH(c.generated_at, now);
  return (
    <section aria-labelledby="coast-h">
      <h3 id="coast-h" className="font-display text-2xl font-bold">Coastal water levels: a separate layer</h3>
      <p className="mb-4 mt-2 font-ui text-sm text-ink/80">Observed and predicted tide at three NOAA stations ({c.datum}). Shown on its own: it is not combined with the river gauges or the crossing scenarios, and is not a probability of anything.</p>
      <ModeHeader mode={c.mode} generated={c.generated_at} source={c.source} stale={c.stale || (age !== null && age > 3)} staleNote={age !== null ? `File generated ${hoursText(age)}` : undefined} caveats={c.caveats} />
      <div className="grid gap-5">{c.stations.map((s) => <StationCard key={s.id} s={s} now={now} />)}</div>
    </section>
  );
}
