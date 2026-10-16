"use client";
import { useCallback, useEffect, useState } from "react";
import Lenis from "lenis";
import { Droplets } from "lucide-react";
import {
  animate,
  domAnimation,
  LazyMotion,
  m,
  useMotionValue,
  useTransform,
  type MotionValue,
} from "framer-motion";
import {
  coastMain,
  fireStations,
  hospitals,
  islands,
  ocean,
  riversMajor,
  riversMinor,
  roadsMajor,
  roadsMinor,
  route,
  wilmington,
} from "@/lib/cape-fear";
import "./intro.css";

/*
 * Real-map flyover intro (~10s). Performance model (web.dev/articles/animations-guide):
 * - Overlays (rain, clouds, flash, dim, HUD, title, exit) animate only transform/opacity,
 *   which Framer Motion hands to the Web Animations API so they run on the compositor.
 * - The camera animates the SVG viewBox, so the vector map stays sharp at every zoom
 *   without rasterising a huge scaled layer.
 * - Markers are HTML, positioned from the camera's motion values, so they keep a constant
 *   size without per-frame style recalculation. No filters or backdrop blur anywhere.
 *
 * Timeline: 0.2 coast traces · 1.2 sweep reveals rivers, 1.7 roads · 2.6 facilities
 * · 3.6 storm + 18h forecast · 4.0 rivers flood · 5.3 camera pushes in · 5.8 route
 * · 6.8 crossing fails · 7.4 title card · 9.2 exit.
 */

/** Runs before first paint so the intro never flashes for visitors who will skip it. */
export const introScript = `try{if(location.pathname==="/"&&!sessionStorage.getItem("intro")&&!matchMedia("(prefers-reduced-motion: reduce)").matches)document.documentElement.setAttribute("data-intro","")}catch(e){}`;

function startSmoothScroll() {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  return new Lenis({ autoRaf: true, anchors: { offset: -64 } });
}

const steps = [
  "Tracing the Cape Fear coast",
  "Mapping roads, rivers and crossings",
  "Locating hospitals and fire stations",
  "Running the 18-hour flood forecast",
  "Checking routes to help",
];

const EXPO_OUT = [0.16, 1, 0.3, 1] as const;
const IN_OUT = [0.65, 0, 0.35, 1] as const;
const ASPECT = 0.625; // viewBox height / width (1600 x 1000)

type Camera = { x: MotionValue<number>; y: MotionValue<number>; w: MotionValue<number>; W: MotionValue<number>; H: MotionValue<number> };

/** viewBox (x, y, w) that zooms by `s` on point (px, py). */
const shot = (s: number, px: number, py: number) => {
  const w = 1600 / s;
  return { x: px - w / 2, y: py - (w * ASPECT) / 2, w };
};

/** Screen-space translate for a map point, matching preserveAspectRatio="xMidYMid slice". */
function useProjected(cam: Camera, X: number, Y: number) {
  return useTransform([cam.x, cam.y, cam.w, cam.W, cam.H], ([x, y, w, W, H]: number[]) => {
    const h = w * ASPECT;
    const s = Math.max(W / w, H / h);
    return `translate3d(${(X - x) * s + (W - w * s) / 2}px, ${(Y - y) * s + (H - h * s) / 2}px, 0)`;
  });
}

/** HTML marker pinned to a map point; children are centred on it. */
function Marker({ cam, at, children }: { cam: Camera; at: number[]; children: React.ReactNode }) {
  const transform = useProjected(cam, at[0], at[1]);
  return (
    <m.div className="absolute left-0 top-0" style={{ transform }}>
      <div className="relative -translate-x-1/2 -translate-y-1/2">{children}</div>
    </m.div>
  );
}

const pop = (delay: number) => ({
  initial: { opacity: 0, transform: "scale(0.2)" },
  animate: { opacity: 1, transform: "scale(1)" },
  transition: { delay, duration: 0.6, ease: EXPO_OUT },
});

const fade = (delay: number, duration = 0.6) => ({
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  transition: { delay, duration, ease: "easeOut" as const },
});

/** Expanding ring around a marker; `repeat` keeps it pulsing for a fixed number of beats. */
const Ring = ({ delay, color = "border-white", size = 44, repeat = 0 }: { delay: number; color?: string; size?: number; repeat?: number }) => (
  <m.span
    aria-hidden
    className={`absolute left-1/2 top-1/2 rounded-full border-2 ${color}`}
    style={{ width: size, height: size, marginLeft: -size / 2, marginTop: -size / 2 }}
    initial={{ opacity: 0.9, transform: "scale(0.6)" }}
    animate={{ opacity: 0, transform: "scale(2.2)" }}
    transition={{ delay, duration: 1.4, ease: EXPO_OUT, repeat }}
  />
);

function MapLayer({ cam }: { cam: Camera }) {
  // One transform so x, y, w and h always come from the same frame (a derived h lagged a frame and shook the map).
  const viewBox = useTransform([cam.x, cam.y, cam.w], ([x, y, w]: number[]) => `${x} ${y} ${w} ${w * ASPECT}`);
  const [wx, wy] = wilmington;
  const scan = (delay: number) => ({ initial: { r: 0 }, animate: { r: 1500 }, transition: { delay, duration: 2.4, ease: [0.33, 0, 0.2, 1] as const } });

  return (
    <m.svg className="absolute inset-0 h-full w-full" viewBox={viewBox} preserveAspectRatio="xMidYMid slice">
      <defs>
        <pattern id="i-grid" width="40" height="40" patternUnits="userSpaceOnUse">
          <path d="M40 0H0v40" fill="none" stroke="#fff" strokeOpacity=".045" />
        </pattern>
        <pattern id="i-hatch" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <path d="M0 0v5" stroke="#fff" strokeOpacity=".55" strokeWidth="1.6" />
        </pattern>
        <clipPath id="i-scan-rivers">
          <m.circle cx={wx} cy={wy} {...scan(1.2)} />
        </clipPath>
        <clipPath id="i-scan-roads">
          <m.circle cx={wx} cy={wy} {...scan(1.7)} />
        </clipPath>
      </defs>

      <rect x="-2000" y="-2000" width="6000" height="6000" fill="#132E52" />
      <m.path d={ocean} fill="#0A1C33" {...fade(0.5, 1.2)} />
      <path d={islands} fill="#132E52" />
      <m.rect x="-2000" y="-2000" width="6000" height="6000" fill="url(#i-grid)" {...fade(0.1)} />

      {/* Coast traces itself */}
      <m.path
        d={coastMain}
        fill="none"
        stroke="#8FB3E6"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ delay: 0.2, duration: 2.2, ease: IN_OUT }}
      />
      <m.path d={islands} fill="none" stroke="#8FB3E6" strokeOpacity=".7" strokeWidth="1" vectorEffect="non-scaling-stroke" {...fade(1.4)} />

      {/* Radar sweep from Wilmington reveals rivers, then roads */}
      <g clipPath="url(#i-scan-rivers)" fill="none" strokeLinecap="round" strokeLinejoin="round">
        <path d={riversMinor} stroke="#3E6FB0" strokeWidth="1" vectorEffect="non-scaling-stroke" />
        <path d={riversMajor} stroke="#5B8FD6" strokeWidth="2" vectorEffect="non-scaling-stroke" />
      </g>
      <g clipPath="url(#i-scan-roads)" fill="none" strokeLinecap="round" strokeLinejoin="round">
        <path d={roadsMinor} stroke="#C9D6E8" strokeOpacity=".3" strokeWidth="1" vectorEffect="non-scaling-stroke" />
        <path d={roadsMajor} stroke="#E4ECF7" strokeOpacity=".62" strokeWidth="1.6" vectorEffect="non-scaling-stroke" />
      </g>
      {[1.2, 1.7].map((delay) => (
        <m.circle
          key={delay}
          cx={wx}
          cy={wy}
          fill="none"
          stroke="#8FB3E6"
          strokeWidth="1.5"
          vectorEffect="non-scaling-stroke"
          initial={{ r: 0, opacity: 0.9 }}
          animate={{ r: 1300, opacity: 0 }}
          transition={{ delay, duration: 2.4, ease: [0.33, 0, 0.2, 1] }}
        />
      ))}

      {/* Flood spreads along the real river corridors */}
      <g fill="none" strokeLinecap="round" strokeLinejoin="round">
        <m.path
          d={riversMajor}
          stroke="#2F64AE"
          vectorEffect="non-scaling-stroke"
          initial={{ opacity: 0, strokeWidth: 4 }}
          animate={{ opacity: 0.35, strokeWidth: 28 }}
          transition={{ delay: 4, duration: 2.6, ease: EXPO_OUT }}
        />
        <m.path
          d={riversMajor}
          stroke="#4F86D1"
          vectorEffect="non-scaling-stroke"
          initial={{ opacity: 0, strokeWidth: 2 }}
          animate={{ opacity: 0.6, strokeWidth: 10 }}
          transition={{ delay: 4, duration: 2.6, ease: EXPO_OUT }}
        />
      </g>
      <m.circle cx={route.crossing[0]} cy={route.crossing[1]} fill="url(#i-hatch)" initial={{ r: 0 }} animate={{ r: 7 }} transition={{ delay: 4.6, duration: 1.6, ease: EXPO_OUT }} />

      {/* The trip, on real roads: Leland across the Cape Fear River to New Hanover Regional */}
      <g fill="none" strokeLinecap="round" strokeLinejoin="round">
        {[
          { stroke: "#0A1C33", strokeOpacity: 0.6, strokeWidth: 2.2 },
          { stroke: "#fff", strokeOpacity: 1, strokeWidth: 1.2 },
        ].map((s) => (
          <m.path key={s.stroke} d={route.d} {...s} initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ delay: 5.8, duration: 1.1, ease: IN_OUT }} />
        ))}
        {/* Traffic flowing toward the crossing */}
        <m.path
          d={route.beforeCrossing}
          stroke="#FFF9C4"
          strokeWidth="1.1"
          strokeDasharray="0.1 2.5"
          initial={{ opacity: 0, strokeDashoffset: 0 }}
          animate={{ opacity: 1, strokeDashoffset: -2.6 }}
          transition={{ opacity: { delay: 6.7, duration: 0.4 }, strokeDashoffset: { delay: 6.7, duration: 0.9, ease: "linear", repeat: 2 } }}
        />
        <m.path
          d={route.afterCrossing}
          stroke="#FF5A5A"
          strokeWidth="1.25"
          strokeDasharray="1.6 1.6"
          initial={{ opacity: 0 }}
          animate={{ opacity: [0, 1, 0.3, 1, 1] }}
          transition={{ delay: 6.9, duration: 0.9, times: [0, 0.2, 0.35, 0.5, 1] }}
        />
      </g>
    </m.svg>
  );
}

function Markers({ cam }: { cam: Camera }) {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0">
      {fireStations.map((at, i) => (
        <Marker key={`f${at}`} cam={cam} at={at}>
          <m.span className="block h-[9px] w-[9px] rounded-full border-[1.5px] border-[#0E2440] bg-[#FF8A6B]" {...pop(2.6 + i * 0.03)} />
        </Marker>
      ))}
      {hospitals.map((at, i) => (
        <Marker key={`h${at}`} cam={cam} at={at}>
          <m.span className="relative grid h-[18px] w-[18px] place-items-center rounded-full bg-white" {...pop(2.8 + i * 0.1)}>
            <Ring delay={2.8 + i * 0.1} size={36} />
            <svg viewBox="-6 -6 12 12" className="h-[9px] w-[9px]">
              <path d="M-4 0h8M0-4v8" stroke="#2D5DA1" strokeWidth="2.4" strokeLinecap="round" />
            </svg>
          </m.span>
        </Marker>
      ))}

      <Marker cam={cam} at={route.hospital}>
        <m.span className="absolute bottom-4 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full bg-white px-3 py-1 font-ui text-[13px] font-semibold text-ink" {...fade(6.6)}>
          New Hanover Regional
        </m.span>
      </Marker>
      <Marker cam={cam} at={route.address}>
        <m.span className="relative block h-[18px] w-[18px] rounded-full border-[3.5px] border-[#0E2440] bg-yellow" {...pop(5.5)}>
          <Ring delay={5.5} size={52} repeat={3} />
        </m.span>
        <m.span className="absolute bottom-6 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full bg-white px-3 py-1 font-ui text-[13px] font-semibold text-ink" {...fade(5.7)}>
          Your address
        </m.span>
      </Marker>
      <Marker cam={cam} at={route.crossing}>
        <m.span className="relative grid h-7 w-7 place-items-center" {...pop(6.8)}>
          <Ring delay={6.8} size={56} color="border-[#FF6B6B]" repeat={2} />
          <span className="grid h-7 w-7 place-items-center rounded-full border-[3px] border-white bg-alert">
            <svg viewBox="-6 -6 12 12" className="h-3 w-3">
              <path d="M-4.5-4.5l9 9M4.5-4.5l-9 9" stroke="#fff" strokeWidth="2.8" strokeLinecap="round" />
            </svg>
          </span>
        </m.span>
        <m.span className="absolute bottom-6 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full bg-alert md:bottom-auto md:top-6 px-3 py-1 font-ui text-[13px] font-semibold text-white" {...fade(7)}>
          Crossing may flood
        </m.span>
      </Marker>
    </div>
  );
}

const RAIN =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='90' height='160'%3E%3Cg stroke='%23fff' stroke-opacity='.22' stroke-linecap='round'%3E%3Cpath d='M10 4v26M40 62v20M70 108v30M25 122v14M60 18v16M82 70v18'/%3E%3C/g%3E%3C/svg%3E\")";

/** Storm overlays: transform/opacity only, so they composite without repainting the map. */
function Storm() {
  const storm = { initial: { opacity: 0 }, animate: { opacity: [0, 1, 1, 0] } };
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
      <m.div
        className="absolute -inset-[15%]"
        style={{
          background:
            "radial-gradient(closest-side, rgb(4 12 24 / 0.55), transparent) 10% 20% / 45% 40% no-repeat, radial-gradient(closest-side, rgb(4 12 24 / 0.5), transparent) 70% 35% / 50% 45% no-repeat, radial-gradient(closest-side, rgb(4 12 24 / 0.45), transparent) 35% 75% / 55% 40% no-repeat",
        }}
        {...storm}
        animate={{ ...storm.animate, transform: ["translate3d(6%, -3%, 0)", "translate3d(-6%, 3%, 0)"] }}
        transition={{ opacity: { delay: 3.4, duration: 4, times: [0, 0.2, 0.75, 1] }, transform: { delay: 3.4, duration: 4, ease: "linear" } }}
      />
      <m.div className="absolute -inset-x-[15%] inset-y-0 rotate-[14deg]" {...storm} transition={{ delay: 3.6, duration: 3.8, times: [0, 0.2, 0.75, 1] }}>
        <m.div
          className="absolute inset-x-0 -top-[160px] bottom-0"
          style={{ backgroundImage: RAIN }}
          initial={{ transform: "translate3d(0, 0, 0)" }}
          animate={{ transform: "translate3d(0, 160px, 0)" }}
          transition={{ delay: 3.6, duration: 0.38, ease: "linear", repeat: 10 }}
        />
      </m.div>
      <m.div
        className="absolute inset-0 bg-[#DCE8FF]"
        initial={{ opacity: 0 }}
        animate={{ opacity: [0, 0.22, 0.04, 0.16, 0] }}
        transition={{ delay: 4.5, duration: 0.9, times: [0, 0.08, 0.16, 0.24, 1] }}
      />
    </div>
  );
}

function Hud() {
  const hours = useMotionValue(0);
  const label = useTransform(hours, (v) => `+${String(Math.round(v)).padStart(2, "0")}H`);
  useEffect(() => {
    const c = animate(hours, 18, { delay: 3.8, duration: 1.9, ease: [0.45, 0, 0.55, 1] });
    return () => c.stop();
  }, [hours]);

  return (
    <div aria-hidden>
      <m.div className="i-frame absolute inset-[14px] sm:inset-6" {...fade(0.1)} />
      <m.div className="absolute left-6 top-6 flex items-center gap-2.5 font-mono text-xs uppercase tracking-[0.2em] text-white/80 sm:left-10 sm:top-10" {...fade(0.2)}>
        <span className="grid h-7 w-7 place-items-center rounded-lg bg-white text-blue">
          <Droplets size={15} strokeWidth={2} aria-hidden />
        </span>
        FloodLens Lifelines
      </m.div>
      <m.div className="absolute right-6 top-7 hidden text-right font-mono text-xs uppercase leading-relaxed tracking-[0.2em] text-white/60 sm:right-10 sm:top-10 sm:block" {...fade(0.4)}>
        34.2257° N · 77.9447° W
        <br />
        New Hanover · Brunswick · Pender
      </m.div>

      <div className="absolute bottom-24 left-6 w-[min(22rem,calc(100%-3rem))] sm:bottom-10 sm:left-10">
        <div className="relative h-6 font-ui text-sm font-medium text-white">
          {steps.map((step, i) => {
            const last = i === steps.length - 1;
            return (
              <m.p
                key={step}
                className="absolute inset-0"
                initial={{ opacity: 0, transform: "translateY(8px)" }}
                animate={
                  last
                    ? { opacity: 1, transform: "translateY(0px)" }
                    : { opacity: [0, 1, 1, 0], transform: ["translateY(8px)", "translateY(0px)", "translateY(0px)", "translateY(-8px)"] }
                }
                transition={{ delay: 0.3 + i * 1.3, duration: last ? 0.5 : 1.3, times: last ? undefined : [0, 0.15, 0.85, 1], ease: "easeInOut" }}
              >
                <span className="mr-2 inline-block h-1.5 w-1.5 -translate-y-0.5 rounded-full bg-yellow" />
                {step}
              </m.p>
            );
          })}
        </div>
        <m.div className="mt-3" {...fade(3.7)}>
          <div className="flex items-baseline justify-between font-mono text-xs uppercase tracking-[0.2em] text-white/60">
            <span>Forecast</span>
            <m.span className="text-sm font-semibold tabular-nums text-yellow [contain:layout_paint]">{label}</m.span>
          </div>
          <div className="mt-2 h-1 overflow-hidden rounded-full bg-white/15">
            <m.div
              className="h-full origin-left rounded-full bg-yellow"
              initial={{ transform: "scaleX(0)" }}
              animate={{ transform: "scaleX(1)" }}
              transition={{ delay: 3.8, duration: 1.9, ease: [0.45, 0, 0.55, 1] }}
            />
          </div>
        </m.div>
      </div>
    </div>
  );
}

function TitleCard() {
  const line = (delay: number) => ({
    initial: { transform: "translateY(110%)" },
    animate: { transform: "translateY(0%)" },
    transition: { delay, duration: 1.1, ease: EXPO_OUT },
  });
  return (
    <>
      <m.div
        aria-hidden
        className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgb(10_28_51/0.66),rgb(10_28_51/0.94))]"
        {...fade(7.4, 0.9)}
      />
      <div className="absolute inset-0 grid place-items-center px-6 text-center text-white">
        <div>
          <p className="font-display text-[clamp(3rem,11vw,8.5rem)] font-black leading-[0.95] tracking-[-0.04em]">
            <span className="inline-block overflow-hidden pb-[0.08em] align-bottom">
              <m.span className="inline-block" {...line(7.6)}>FloodLens</m.span>
            </span>{" "}
            <span className="inline-block overflow-hidden pb-[0.08em] align-bottom">
              <m.span className="inline-block text-yellow" {...line(7.75)}>Lifelines</m.span>
            </span>
          </p>
          <m.p className="mt-6 font-body text-lg text-white/80 sm:text-2xl" {...fade(8.1)}>
            Can you still get to help?
          </m.p>
        </div>
      </div>
    </>
  );
}

function Scene({ onDone }: { onDone: () => void }) {
  const cam: Camera = {
    x: useMotionValue(0),
    y: useMotionValue(0),
    w: useMotionValue(1600),
    W: useMotionValue(1440),
    H: useMotionValue(900),
  };

  useEffect(() => {
    const size = () => {
      cam.W.set(window.innerWidth);
      cam.H.set(window.innerHeight);
    };
    size();
    window.addEventListener("resize", size);

    // Narrow screens zoom less so the whole trip stays in frame.
    const narrow = window.innerWidth < 768;
    const [cx, cy] = [(route.address[0] + route.hospital[0]) / 2, (route.address[1] + route.hospital[1]) / 2];
    const frames = [shot(1.3, 800, 500), shot(1, 800, 500), shot(1.05, 800, 500), shot(narrow ? 1.6 : 3.2, cx, cy), shot(narrow ? 1.75 : 3.5, cx, cy)];
    const options = {
      duration: 9.2,
      times: [0, 0.37, 0.576, 0.74, 1],
      ease: [
        [0.33, 0, 0.2, 1],
        [0.45, 0, 0.55, 1],
        [0.65, 0, 0.25, 1],
        [0.3, 0, 0.7, 1],
      ] as [number, number, number, number][],
    };
    const runs = (["x", "y", "w"] as const).map((k) => animate(cam[k], frames.map((f) => f[k]), options));
    return () => {
      window.removeEventListener("resize", size);
      runs.forEach((r) => r.stop());
    };
    // Motion values are stable for the component's lifetime.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <m.div
      className="absolute inset-0"
      initial={{ opacity: 1, transform: "scale(1)" }}
      animate={{ opacity: 0, transform: "scale(1.08)" }}
      transition={{ delay: 9.2, duration: 1, ease: [0.7, 0, 0.84, 0] }}
      onAnimationComplete={onDone}
    >
      <MapLayer cam={cam} />
      <Markers cam={cam} />
      <Storm />
      <div aria-hidden className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_45%,rgb(10_28_51/0.75))]" />
      <Hud />
      <TitleCard />
    </m.div>
  );
}

/** Cinematic flyover of the real Cape Fear map, then Lenis smooth scrolling. */
export function Intro() {
  const [playing, setPlaying] = useState(true);

  const finish = useCallback(() => {
    document.documentElement.removeAttribute("data-intro");
    try {
      sessionStorage.setItem("intro", "1");
    } catch {}
    setPlaying(false);
  }, []);

  useEffect(() => {
    if (!document.documentElement.hasAttribute("data-intro")) setPlaying(false);
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && finish();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [finish]);

  useEffect(() => {
    if (playing) return;
    const lenis = startSmoothScroll();
    return () => lenis?.destroy();
  }, [playing]);

  if (!playing) return null;

  return (
    <LazyMotion features={domAnimation} strict>
      <div className="intro" role="dialog" aria-label="FloodLens Lifelines introduction">
        <Scene onDone={finish} />
        <m.button
          type="button"
          onClick={finish}
          className="absolute bottom-6 right-6 min-h-11 rounded-full border border-white/25 bg-[#0A1C33]/70 px-5 font-ui text-sm font-medium text-white transition-colors hover:bg-white/20 sm:bottom-10 sm:right-10"
          {...fade(0.6)}
        >
          Skip intro
        </m.button>
      </div>
    </LazyMotion>
  );
}
