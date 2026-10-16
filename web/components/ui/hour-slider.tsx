"use client";
import { hourTime } from "@/lib/sample";

/** Floating 18-hour replay slider shared by the replay map and the route analysis map. */
export function HourSlider({ hour, hours, start, onChange }: { hour: number; hours: number; start?: string; onChange: (h: number) => void }) {
  const text = start ? hourTime(start, hour) : "";
  return (
    <div className="glass absolute inset-x-3 bottom-3 z-[2] rounded-2xl border border-white/60 p-4 shadow-float sm:inset-x-auto sm:bottom-5 sm:left-1/2 sm:w-[min(34rem,calc(100%-2rem))] sm:-translate-x-1/2">
      <div className="mb-1 flex flex-wrap items-baseline justify-between gap-3">
        <label htmlFor="hour" className="font-ui text-sm font-semibold">Step through 18 replay hours</label>
        <span key={hour} className="pop inline-block font-mono text-sm font-semibold text-blue" aria-live="polite">{text}</span>
      </div>
      <input
        id="hour"
        type="range"
        min={0}
        max={hours - 1}
        step={1}
        value={hour}
        onChange={(event) => onChange(Number(event.target.value))}
        aria-valuetext={`Replay hour ${hour}, ${text}`}
        className="min-h-11 w-full cursor-pointer"
      />
      <div aria-hidden className="relative h-4 font-mono text-xs text-muted">
        {[0, 3, 6, 12, hours - 1].map((h) => (
          <span key={h} className="absolute" style={{ left: `${(h / (hours - 1)) * 100}%`, transform: `translateX(-${(h / (hours - 1)) * 100}%)` }}>
            {h === 0 ? "START" : `+${h}H`}
          </span>
        ))}
      </div>
    </div>
  );
}
