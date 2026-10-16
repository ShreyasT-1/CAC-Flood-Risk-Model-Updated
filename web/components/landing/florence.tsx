import { ArrowDown, History } from "lucide-react";
import { coastMain, florence, islands, ocean, riversMajor, roadsMajor, wilmington } from "@/lib/cape-fear";

const facts = [
  ["Landfall", "Sept 14, 2018 · near Wrightsville Beach"],
  ["Access", "Flooded roads cut Wilmington off for days"],
  ["Rainfall", "Record totals for a North Carolina tropical cyclone"],
];

export function Florence() {
  return (
    <section id="florence" className="scroll-mt-16 mx-auto max-w-screen-xl px-4 pb-20 sm:px-6 lg:pb-28">
      <div className="grid items-center gap-10 overflow-hidden rounded-3xl bg-[#0E2440] p-6 text-white sm:p-10 lg:grid-cols-[0.9fr_1.1fr] lg:gap-14 lg:p-14">
        <div className="reveal">
          <h2 className="font-display text-4xl font-bold leading-[1.05] tracking-[-0.03em] sm:text-6xl">
            Remember Florence
          </h2>
          <p className="mt-5 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3.5 py-2 font-ui text-xs font-semibold text-yellow">
            <History size={14} aria-hidden />
            Replay · sample preview
          </p>
          <p className="mt-5 max-w-md font-body text-lg leading-relaxed text-white/75">
            In 2018, Hurricane Florence turned Wilmington into an island. The replay below steps through 18 hours of the storm. It uses river flow only, so it misses the surge and street flooding that cut Wilmington off.
          </p>
          <dl className="mt-8 divide-y divide-white/10 border-y border-white/10">
            {facts.map(([label, value]) => (
              <div key={label} className="grid gap-1 py-4 sm:grid-cols-[7rem_1fr] sm:gap-4">
                <dt className="font-mono text-xs uppercase tracking-[0.16em] text-white/50">{label}</dt>
                <dd className="font-ui text-sm text-white/90">{value}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-4 font-ui text-xs text-white/50">Source: NOAA National Hurricane Center, Hurricane Florence report (AL062018).</p>
          <a href="#map" className="mt-7 inline-flex min-h-12 items-center gap-2 rounded-full bg-white px-6 font-ui text-sm font-semibold text-[#0E2440] transition hover:-translate-y-0.5 hover:shadow-lift">
            Step through the replay <ArrowDown size={16} aria-hidden />
          </a>
        </div>

        <figure className="reveal-zoom relative">
          <svg viewBox="200 0 1200 1000" className="block w-full rounded-2xl" role="img" aria-labelledby="fl-t">
            <title id="fl-t">Map of the Cape Fear coast with the approximate path of Hurricane Florence making landfall near Wrightsville Beach</title>
            <rect x="0" y="0" width="1600" height="1000" fill="#16345B" />
            <path d={ocean} fill="#0B1E36" />
            <path d={islands} fill="#16345B" />
            <path d={riversMajor} fill="none" stroke="#3E6FB0" strokeWidth="3" />
            <path d={roadsMajor} fill="none" stroke="#fff" strokeOpacity=".18" strokeWidth="2" />
            <path d={coastMain} fill="none" stroke="#8FB3E6" strokeOpacity=".6" strokeWidth="1.5" />
            <path d={florence.d} fill="none" stroke="#CC0000" strokeOpacity=".25" strokeWidth="60" strokeLinecap="round" />
            <path d={florence.d} fill="none" stroke="#FF8A8A" strokeWidth="4" strokeDasharray="14 12" strokeLinecap="round" />
            <g transform={`translate(${florence.landfall[0]} ${florence.landfall[1]})`}>
              <circle r="34" fill="none" stroke="#FF8A8A" strokeWidth="3" />
              <circle r="12" fill="#CC0000" stroke="#fff" strokeWidth="4" />
            </g>
            <g transform={`translate(${wilmington[0]} ${wilmington[1]})`} fontFamily="var(--font-ui)" fontWeight="600">
              <circle r="9" fill="#FFF9C4" />
              <text x="-18" y="6" textAnchor="end" fontSize="26" fill="#fff">Wilmington</text>
            </g>
          </svg>
          <figcaption className="mt-3 font-ui text-xs text-white/50">
            Approximate storm path. Map data © OpenStreetMap contributors.
          </figcaption>
        </figure>
      </div>
    </section>
  );
}
