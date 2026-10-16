import { MapPin } from "lucide-react";
import { Highlight } from "@/components/ui/annotations";
import { AddressSearch } from "@/components/landing/address-search";
import { coastMain, hospitals, islands, ocean, riversMajor, roadsMajor, roadsMinor } from "@/lib/cape-fear";

const facts = [
  { value: "18 hours", label: "Replay window, hour by hour" },
  { value: "3 counties", label: "New Hanover, Brunswick, Pender" },
  { value: "2 destinations", label: "Hospitals and fire stations" },
];

/** Faint real map of the region behind the hero; the centre is masked clear for the headline. */
function Backdrop() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 1600 1000"
      preserveAspectRatio="xMidYMid slice"
      className="drift-slow pointer-events-none absolute inset-0 h-full w-full [mask-image:radial-gradient(ellipse_60%_55%_at_50%_45%,transparent_25%,black_85%)]"
    >
      <path d={ocean} fill="#2D5DA1" fillOpacity=".07" />
      <path d={islands} fill="#F9F9F7" fillOpacity=".6" />
      <path d={roadsMinor} fill="none" stroke="#111" strokeOpacity=".07" strokeWidth="1" vectorEffect="non-scaling-stroke" />
      <path d={roadsMajor} fill="none" stroke="#111" strokeOpacity=".14" strokeWidth="1.4" vectorEffect="non-scaling-stroke" />
      <path d={riversMajor} fill="none" stroke="#2D5DA1" strokeOpacity=".35" strokeWidth="2" vectorEffect="non-scaling-stroke" />
      <path d={coastMain} fill="none" stroke="#2D5DA1" strokeOpacity=".4" strokeWidth="1.4" vectorEffect="non-scaling-stroke" />
      {hospitals.map(([x, y]) => (
        <g key={`${x}-${y}`} transform={`translate(${x} ${y})`}>
          <circle r="9" fill="#fff" stroke="#2D5DA1" strokeOpacity=".5" />
          <path d="M-4 0h8M0-4v8" stroke="#2D5DA1" strokeWidth="2" strokeLinecap="round" />
        </g>
      ))}
    </svg>
  );
}

export function Hero() {
  return (
    <section className="relative overflow-hidden bg-gradient-to-b from-soft-blue via-paper to-paper">
      <Backdrop />
      <div className="pointer-events-none absolute left-1/2 top-0 h-[34rem] w-[60rem] -translate-x-1/2 rounded-full bg-blue/10 blur-3xl drift" aria-hidden />
      <div className="relative mx-auto max-w-screen-xl px-4 pb-20 pt-16 text-center sm:px-6 sm:pb-28 sm:pt-24">
        <p className="enter mx-auto inline-flex items-center gap-2 rounded-full border border-blue/20 bg-white/70 px-3.5 py-2 font-ui text-sm font-medium text-blue">
          <MapPin size={15} strokeWidth={1.8} aria-hidden />
          Cape Fear, North Carolina
        </p>
        <h1 className="enter mx-auto mt-7 [--d:90ms] max-w-4xl font-display text-[clamp(2.75rem,8vw,6rem)] font-black leading-[1.02] tracking-[-0.04em] text-balance">
          Can you still <Highlight>get to help?</Highlight>
        </h1>
        <p className="enter mx-auto mt-6 max-w-xl [--d:180ms] font-body text-lg leading-relaxed text-ink/70 sm:text-xl">
          FloodLens Lifelines shows scenarios for how flooding may interrupt road access to hospitals and fire stations.
        </p>

        <AddressSearch />

        <dl className="enter mx-auto mt-12 grid max-w-4xl grid-cols-1 divide-y divide-ink/10 border-y border-ink/10 text-left [--d:360ms] sm:mt-14 sm:grid-cols-3 sm:divide-x sm:divide-y-0">
          {facts.map(({ value, label }) => (
            <div key={value} className="px-1 py-4 sm:px-6 sm:py-5 sm:text-center">
              <dt className="font-display text-xl font-bold leading-tight">{value}</dt>
              <dd className="mt-1 font-ui text-xs leading-snug text-muted">{label}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}
