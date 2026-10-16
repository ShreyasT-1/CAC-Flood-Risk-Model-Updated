import type { ReactNode } from "react";
import { utc } from "@/lib/sample";

/** Timestamp, source, staleness and caveats of the active mode. Every string comes from that mode's JSON file. */
export function ModeHeader({ mode, generated, source, stale, staleNote, caveats, children, fixed }: {
  mode: string; generated: string; source: string; stale: boolean; staleNote?: string; caveats: string[]; children?: ReactNode; fixed?: boolean;
}) {
  return (
    <div className="mb-6 rounded-2xl border border-ink/10 bg-white p-5 shadow-panel">
      <dl className="grid gap-x-8 gap-y-3 font-ui text-sm sm:grid-cols-[auto_1fr]">
        <dt className="label text-muted">Mode</dt>
        <dd className="font-mono font-semibold">{mode}</dd>
        <dt className="label text-muted">Generated</dt>
        <dd className="font-mono">{utc(generated)}</dd>
        <dt className="label text-muted">Source</dt>
        <dd>{source}</dd>
        <dt className="label text-muted">Status</dt>
        <dd>
          <span className={`inline-block rounded-full border px-2.5 py-0.5 text-xs font-semibold ${stale && !fixed ? "border-alert bg-softred text-alert" : "border-ink/20 bg-soft-blue text-ink"}`}>
            {fixed ? "Fixed past-storm data, not live" : stale ? "Stale: older than the file's freshness limit" : "Within the freshness limit"}
          </span>
          {staleNote && <span className="ml-2 text-xs text-muted">{staleNote}</span>}
        </dd>
      </dl>
      {children}
      {caveats.length > 0 && (
        <details className="mt-4 border-t border-divider pt-3">
          <summary className="flex min-h-11 cursor-pointer items-center font-ui text-sm font-semibold">Caveats ({caveats.length})</summary>
          <ul className="mt-2 list-disc space-y-1.5 pl-5 font-body text-sm leading-relaxed text-ink/80">
            {caveats.map((c) => <li key={c}>{c}</li>)}
          </ul>
        </details>
      )}
    </div>
  );
}
