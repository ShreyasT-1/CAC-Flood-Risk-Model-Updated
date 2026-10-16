import { Building2, Eye, House, ShieldAlert, Sigma } from "lucide-react";

const people = [
  {
    icon: House,
    title: "Residents",
    body: "Check whether flooding could cut the roads between your address and the nearest hospital or fire station, and roughly when.",
  },
  {
    icon: Building2,
    title: "Critical-facility teams",
    body: "See which crossings could separate a hospital, clinic or station from the people and staff it depends on.",
  },
];

const principles = [
  { icon: Sigma, title: "Probabilities, not promises", body: "Every outlook is a likelihood with a time range, never a yes or no." },
  { icon: ShieldAlert, title: "No warning is not an all-clear", body: "We never show a road as safe. Missing data is labelled as missing." },
  { icon: Eye, title: "Uncertainty stays visible", body: "Patterns, labels and timestamps carry meaning, not colour alone." },
];

export function Audience() {
  return (
    <section className="mx-auto max-w-screen-xl px-4 pb-20 sm:px-6 lg:pb-28">
      <div className="grid gap-12 lg:grid-cols-[0.8fr_1.2fr] lg:gap-16">
        <div className="reveal">
          <h2 className="font-display text-4xl font-bold leading-tight tracking-[-0.03em] sm:text-6xl">
            Built for the drive that matters
          </h2>
          <p className="mt-4 max-w-md font-body text-lg leading-relaxed text-ink/70">
            For the people who need to reach help, and the people who provide it.
          </p>
        </div>

        <div className="grid gap-10 sm:grid-cols-2 sm:gap-8 lg:pt-3">
          {people.map(({ icon: Icon, title, body }) => (
            <article key={title} className="reveal border-t-2 border-ink pt-6">
              <Icon size={24} strokeWidth={1.8} className="text-blue" aria-hidden />
              <h3 className="mt-4 font-display text-2xl font-bold sm:text-3xl">{title}</h3>
              <p className="mt-3 font-body text-base leading-relaxed text-ink/70">{body}</p>
            </article>
          ))}
        </div>
      </div>

      <div className="reveal mt-16 rounded-3xl bg-white p-6 sm:p-10 lg:mt-20">
        <h3 className="font-display text-2xl font-bold sm:text-3xl">How we talk about risk</h3>
        <ul className="mt-8 grid gap-8 md:grid-cols-3 md:gap-10">
          {principles.map(({ icon: Icon, title, body }) => (
            <li key={title} className="flex gap-4 md:block">
              <Icon size={22} strokeWidth={1.8} className="mt-0.5 shrink-0 text-alert md:mt-0" aria-hidden />
              <div>
                <h4 className="font-ui text-base font-semibold md:mt-4">{title}</h4>
                <p className="mt-1.5 font-ui text-sm leading-relaxed text-ink/70">{body}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
