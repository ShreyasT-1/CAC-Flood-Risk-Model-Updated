import { Activity, Droplets, Route, Waves } from "lucide-react";

const steps = [
  { title: "Rain", description: "Rainfall forecasts show where water may collect.", icon: Droplets },
  { title: "Rivers rise", description: "Rising waterways may affect nearby roads.", icon: Waves },
  { title: "Crossings change", description: "Flooding can make key crossings harder to use.", icon: Activity },
  { title: "Access shifts", description: "Routes to hospitals and fire stations may change.", icon: Route },
];

export function HowItWorks() {
  return (
    <section id="how" className="scroll-mt-16 overflow-hidden bg-[#16345B] text-white">
      <div className="mx-auto max-w-screen-xl px-4 py-20 sm:px-6 lg:py-28">
        <div className="reveal mx-auto max-w-2xl text-center">
          <h2 className="font-display text-4xl font-bold leading-tight tracking-[-0.03em] sm:text-6xl">
            From rain to road access
          </h2>
          <p className="mt-4 font-body text-lg leading-relaxed text-white/75">
            FloodLens connects forecast water levels with the roads people rely on to reach help.
          </p>
        </div>

        {/* One connected chain: the line carries the order, so the steps need no numbers. */}
        <ol className="relative mt-14 grid gap-10 pl-16 before:absolute before:bottom-2 before:left-6 before:top-2 before:w-px before:bg-white/20 lg:grid-cols-4 lg:gap-8 lg:pl-0 lg:pt-20 lg:before:inset-x-6 lg:before:bottom-auto lg:before:top-6 lg:before:h-px lg:before:w-auto">
          {steps.map(({ title, description, icon: Icon }, index) => (
            <li key={title} className="reveal relative min-w-0">
              <span
                className={`absolute -left-16 top-0 grid h-12 w-12 place-items-center rounded-full ring-8 ring-[#16345B] lg:-top-20 lg:left-0 ${
                  index === 0 ? "bg-yellow text-ink" : "bg-[#24497A] text-white"
                }`}
              >
                <Icon size={22} strokeWidth={1.7} aria-hidden />
              </span>
              <h3 className="font-display text-2xl font-bold">{title}</h3>
              <p className="mt-2 max-w-[28ch] font-ui text-sm leading-relaxed text-white/70">{description}</p>
            </li>
          ))}
        </ol>

        <div className="reveal mx-auto mt-16 max-w-3xl rounded-3xl border border-white/15 bg-white/5 p-6 sm:p-8">
          <h3 className="font-display text-2xl font-bold sm:text-3xl">What this does not model</h3>
          <p className="mt-2 font-ui text-sm leading-relaxed text-white/75">
            The scenarios use river flow only. Anything below can close a road without showing up here, so a crossing that is not flagged is
            &ldquo;not flagged in this scenario&rdquo;, never an assurance.
          </p>
          <ul className="mt-4 list-disc space-y-2 pl-5 font-body text-base leading-relaxed text-white/85">
            <li><b>Storm surge and tide.</b> Observed coastal water levels are shown separately in the nowcast. They are not combined with the river-flow scenarios.</li>
            <li><b>Street and drainage (pluvial) flooding</b> from rain that never reaches a stream.</li>
            <li><b>Road deck height</b>, and <b>debris and scour</b> at a crossing.</li>
            <li>
              <b>Service-island cutoffs.</b> Areas that lose their route without a modelled stream crossing closing, such as the Smithville Island area
              served by Dosher Memorial Hospital on Brunswick County Emergency Management&rsquo;s service-islands map, may not appear in a river-flow-only replay.
            </li>
          </ul>
          <p className="mt-4 font-ui text-xs leading-relaxed text-white/60">
            Brunswick County Emergency Management&rsquo;s service-islands map is a modelled reference, not an observation of what happened.
          </p>
        </div>
      </div>
    </section>
  );
}
