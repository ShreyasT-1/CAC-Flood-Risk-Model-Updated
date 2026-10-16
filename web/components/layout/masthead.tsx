"use client";
import { useEffect, useState } from "react";
import { isStress } from "@/lib/sample";
import { Droplets, Menu, X } from "lucide-react";

const links = [
  ["Florence replay", "/#florence"],
  ["Route analysis", "/route"],
  ["About", "/#how"],
];

export function Masthead() {
  const [open, setOpen] = useState(false);
  const [stress, setStress] = useState(false);
  useEffect(() => setStress(isStress()), []);

  return (
    <header className="glass sticky top-0 z-40 border-b border-ink/10">
      <p role="note" className={`px-4 py-1.5 text-center font-ui text-xs sm:text-sm ${stress ? "bg-ink text-white" : "bg-yellow text-ink"}`}>
        <strong className="font-semibold">{stress ? "STRESS TEST: exaggerated values, not real." : "Sample data, not for emergency use."}</strong>
        <span className="opacity-70"> Florence 2018 replay preview · not validated · call 911 in an emergency</span>
      </p>
      <div className="mx-auto max-w-screen-xl px-4 sm:px-6">
        <div className="flex min-h-[56px] items-center justify-between gap-6">
          <a href="/" className="inline-flex min-h-11 items-center gap-2.5" aria-label="FloodLens Lifelines home">
            <span className="grid h-8 w-8 place-items-center rounded-[10px] bg-blue text-white">
              <Droplets size={18} strokeWidth={1.8} aria-hidden />
            </span>
            <span className="font-ui text-[15px] font-semibold tracking-tight">
              FloodLens <span className="text-blue">Lifelines</span>
            </span>
          </a>

          <nav aria-label="Primary" className="hidden items-center gap-1 font-ui text-sm md:flex">
            {links.map(([text, href]) => (
              <a
                key={href}
                href={href}
                className="flex min-h-11 items-center rounded-full px-4 text-ink/70 transition-colors hover:bg-ink/5 hover:text-ink"
              >
                {text}
              </a>
            ))}
          </nav>

          <button
            type="button"
            className="grid min-h-11 min-w-11 place-items-center rounded-full text-ink transition-colors hover:bg-ink/5 md:hidden"
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            onClick={() => setOpen(!open)}
          >
            {open ? <X size={20} strokeWidth={1.8} /> : <Menu size={20} strokeWidth={1.8} />}
          </button>
        </div>

        {open && (
          <nav aria-label="Mobile" className="flex animate-[rise-sm_0.3s_cubic-bezier(0.16,1,0.3,1)] flex-col border-t border-ink/10 py-2 font-ui text-base md:hidden">
            {links.map(([text, href]) => (
              <a
                key={href}
                href={href}
                onClick={() => setOpen(false)}
                className="flex min-h-12 items-center rounded-xl px-3 text-ink/80 hover:bg-ink/5"
              >
                {text}
              </a>
            ))}
          </nav>
        )}
      </div>
    </header>
  );
}
