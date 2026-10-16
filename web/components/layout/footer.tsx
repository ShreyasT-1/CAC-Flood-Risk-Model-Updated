import { Droplets } from "lucide-react";

const cols = [
  ["Explore", [["Florence replay", "/#florence"], ["Route analysis", "/route"], ["What breaks first", "/#breaks"]]],
  ["About", [["How it works", "/#how"]]],
] as const;

export function Footer() {
  return (
    <footer className="bg-[#F2F2EF]">
    <div className="mx-auto max-w-screen-xl px-4 py-12 sm:px-6">
      <div className="grid grid-cols-2 gap-8 md:grid-cols-[1.3fr_1fr_1fr_1.2fr]">
        <div className="col-span-2 md:col-span-1">
          <a href="/" className="inline-flex min-h-11 items-center gap-2.5 font-display text-xl font-bold tracking-[-0.025em]">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-blue text-white">
              <Droplets size={19} aria-hidden />
            </span>
            FloodLens <span className="text-blue">Lifelines</span>
          </a>
          <p className="mt-3 max-w-[30ch] font-body text-sm leading-relaxed text-muted">
            Exploring how flooding may change access to help across Cape Fear.
          </p>
        </div>
        {cols.map(([title, links]) => (
          <div key={title}>
            <h3 className="font-ui text-xs font-semibold uppercase tracking-[0.12em] text-muted">{title}</h3>
            <ul className="mt-2 font-ui text-sm">
              {links.map(([text, href]) => (
                <li key={text}><a href={href} className="inline-flex min-h-11 items-center text-ink/75 underline-offset-4 hover:text-blue hover:underline">{text}</a></li>
              ))}
            </ul>
          </div>
        ))}
        <div>
          <h3 className="font-ui text-xs font-semibold uppercase tracking-[0.12em] text-muted">Privacy</h3>
          <p className="mt-3 font-ui text-sm leading-relaxed text-ink/75">No user data is stored. Address searches are sent to OpenStreetMap Nominatim to find a location.</p>
        </div>
      </div>
      <p className="mt-10 border-t border-ink/10 pt-5 font-ui text-xs leading-relaxed text-muted">
        Cape Fear, North Carolina <span className="px-1.5">|</span> Built for the Congressional App Challenge
      </p>
    </div>
    </footer>
  );
}
