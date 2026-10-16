"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, Check, Flame, Hospital, LoaderCircle, MapPin, Search } from "lucide-react";
import { geocode } from "@/lib/geocode";
import { blockView, getJSON, nearestBlock, type LocationView, type Lookup, type Meta } from "@/lib/sample";
import { crossingsOnRoute, rankRoutes, routeAtHour, type LngLat, type RouteCrossings, type RouteOption } from "@/lib/route";
import { matrix, openRoute, route } from "@/lib/valhalla";
import { HourSlider } from "@/components/ui/hour-slider";
import { RouteMap, type MapService } from "@/components/route/route-map";
import { RouteAnalysis, StatusBadge, type Group } from "@/components/route/route-analysis";

type Service = MapService & { sub: string; straightKm: number; timeS?: number | null; km?: number };
type Facilities = {
  hospitals: { id: string; name: string; county: string; type: string; lat: number; lon: number }[];
  fire_stations: { id: string; name: string; lat: number; lon: number }[];
};
type Origin = { lat: number; lon: number; label: string };
type Pending = "loading";

const N_FIRE = 8; // nearest fire stations listed (all 11 ED hospitals are always listed)
const flatKm = (a: { lat: number; lon: number }, b: { lat: number; lon: number }) =>
  Math.hypot((a.lon - b.lon) * 111.32 * Math.cos((a.lat * Math.PI) / 180), (a.lat - b.lat) * 110.57);
const mins = (s: number) => `${Math.round(s / 60)} min`;
const FILTERS = [["all", "All"], ["hospital", "Hospitals"], ["fire", "Fire stations"]] as const;

export function RouteApp() {
  const params = useSearchParams();
  const router = useRouter();
  const [base, setBase] = useState<{ meta: Meta; fac: Facilities; X: RouteCrossings } | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [query, setQuery] = useState(params.get("q") ?? "");
  const [origin, setOrigin] = useState<Origin | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [services, setServices] = useState<Service[]>([]);
  const [filter, setFilter] = useState<"all" | "hospital" | "fire">("all");
  const [selected, setSelected] = useState<string[]>([]);
  const [routes, setRoutes] = useState<Record<string, RouteOption[] | Pending | string>>({});
  const [detours, setDetours] = useState<Record<string, RouteOption | Pending | string>>({});
  const [hour, setHour] = useState(0);
  const [focusId, setFocusId] = useState<string | null>(null);
  const [block, setBlock] = useState<LocationView | null>(null);
  const asked = useRef(new Set<string>()); // route / detour requests already made for this origin
  const token = useRef(0); // ignores answers that arrive after the origin changed

  useEffect(() => {
    Promise.all([getJSON<Meta>("meta.json"), getJSON<Facilities>("facilities.json"), getJSON<RouteCrossings>("route_crossings.json")])
      .then(([meta, fac, X]) => setBase({ meta, fac, X }))
      .catch((e: Error) => setLoadErr(e.message));
  }, []);

  async function search(q: string) {
    setBusy(true);
    const r = await geocode(q);
    setBusy(false);
    if (typeof r === "string") return setMsg(r);
    setMsg(null);
    setOrigin(r);
    const next = new URLSearchParams(params.get("data") ? { data: params.get("data")! } : {});
    next.set("q", q);
    router.replace(`/route?${next}`, { scroll: false });
  }

  // Starting point from the link: ?lat&lon&label (sample place) or ?q (address).
  useEffect(() => {
    const lat = params.get("lat"), lon = params.get("lon"), q = params.get("q");
    if (lat && lon) setOrigin({ lat: +lat, lon: +lon, label: params.get("label") ?? "Selected place" });
    else if (q && !origin) search(q);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // New origin: list services with drive times, preselect the nearest emergency hospital, load the block cross-check.
  useEffect(() => {
    if (!origin || !base) return;
    const tk = ++token.current;
    asked.current.clear();
    const here = { lat: origin.lat, lon: origin.lon };
    const list: Service[] = [
      ...base.fac.hospitals.map((h) => ({ id: h.id, kind: "hospital" as const, name: h.name, sub: `${h.type.replace(" Hospitals", "")} · ${h.county} County`, lat: h.lat, lon: h.lon, straightKm: flatKm(here, h) })),
      ...base.fac.fire_stations.map((f) => ({ id: f.id, kind: "fire" as const, name: f.name, sub: "Fire station", lat: f.lat, lon: f.lon, straightKm: flatKm(here, f) }))
        .sort((a, b) => a.straightKm - b.straightKm).slice(0, N_FIRE),
    ];
    setServices(list); setSelected([]); setRoutes({}); setDetours({}); setFocusId(null); setBlock(null);
    const pickNearest = (l: Service[]) => {
      const h = l.filter((s) => s.kind === "hospital").sort((a, b) => (a.timeS ?? a.straightKm * 1e4) - (b.timeS ?? b.straightKm * 1e4))[0];
      if (h) setSelected([h.id]);
    };
    matrix([origin.lon, origin.lat], list.map((s) => [s.lon, s.lat] as LngLat))
      .then((m) => {
        if (tk !== token.current) return;
        const timed = list.map((s, i) => ({ ...s, timeS: m[i]?.timeS ?? null, km: m[i]?.km }));
        setServices(timed); pickNearest(timed);
      })
      .catch(() => { if (tk === token.current) { setMsg("Drive times are unavailable right now, so services are listed by straight-line distance."); pickNearest(list); } });
    getJSON<Lookup>("blocks_lookup.json").then((L) => {
      if (tk !== token.current) return;
      const [b, d] = nearestBlock(L, origin.lat, origin.lon);
      setBlock(d <= 3 ? blockView(L, b, d, origin.label) : null);
    }).catch(() => {});
  }, [origin, base]);

  // Fastest route (plus any alternatives Valhalla finds) to each selected service.
  useEffect(() => {
    if (!origin || !base) return;
    const tk = token.current;
    for (const id of selected) {
      if (asked.current.has(id)) continue;
      asked.current.add(id);
      const s = services.find((x) => x.id === id)!;
      setRoutes((r) => ({ ...r, [id]: "loading" }));
      route([origin.lon, origin.lat], [s.lon, s.lat], [], 2)
        .then((trips) => {
          if (tk !== token.current) return;
          const opts: RouteOption[] = trips.map((t, i) => ({ id: `${id}-${i}`, serviceId: id, label: `${s.name}${i ? ` (alternative ${i})` : ""}`, via: t.via,
            kind: i ? "alternate" : "fastest", timeS: t.timeS, km: t.km, shape: t.shape, on: crossingsOnRoute(t.shape, base.X) }));
          setRoutes((r) => ({ ...r, [id]: opts.length ? opts : "no road route found" }));
        })
        .catch(() => { if (tk === token.current) { asked.current.delete(id); setRoutes((r) => ({ ...r, [id]: "the routing service is unavailable right now" })); } });
    }
  }, [selected, origin, base, services]);

  // When every route to a service is blocked this hour, look for a detour around the closed crossings.
  useEffect(() => {
    if (!origin || !base) return;
    const tk = token.current;
    const t = setTimeout(() => {
      for (const id of selected) {
        const opts = routes[id];
        if (!Array.isArray(opts) || !opts.every((o) => routeAtHour(o.on, hour).blocked.length)) continue;
        const key = `${id}|${hour}`;
        if (asked.current.has(key)) continue;
        asked.current.add(key);
        const s = services.find((x) => x.id === id)!;
        setDetours((d) => ({ ...d, [key]: "loading" }));
        openRoute([origin.lon, origin.lat], [s.lon, s.lat], base.X, hour)
          .then(({ trip, reason }) => {
            if (tk !== token.current) return;
            setDetours((d) => ({ ...d, [key]: trip ? { id: `${id}-d${hour}`, serviceId: id, label: `${s.name} (detour)`, via: trip.via, kind: "detour",
              timeS: trip.timeS, km: trip.km, shape: trip.shape, on: trip.on } : reason! }));
          })
          .catch(() => { if (tk === token.current) { asked.current.delete(key); setDetours((d) => ({ ...d, [key]: "the routing service is unavailable right now" })); } });
      }
    }, 350);
    return () => clearTimeout(t);
  }, [hour, selected, routes, origin, base, services]);

  const names = useMemo(() => Object.fromEntries(services.map((s) => [s.id, s.name])), [services]);
  const options = useMemo(() => selected.flatMap((id) => {
    const r = routes[id], d = detours[`${id}|${hour}`];
    return [...(Array.isArray(r) ? r : []), ...(d && typeof d === "object" ? [d] : [])];
  }), [selected, routes, detours, hour]);
  const kindOf = useMemo(() => Object.fromEntries(services.map((s) => [s.id, s.kind])), [services]);
  const groups = useMemo<Group[]>(() => ([["hospital", "Emergency hospitals"], ["fire", "Fire stations"]] as const)
    .map(([kind, title]) => ({ kind, title, ranked: rankRoutes(options.filter((o) => kindOf[o.serviceId] === kind), hour) })), [options, hour, kindOf]);
  const ranked = useMemo(() => groups.flatMap((g) => g.ranked), [groups]);
  const fastest = useMemo(() => Object.fromEntries(selected.flatMap((id) => {
    const r = routes[id];
    return Array.isArray(r) && r.length ? [[id, Math.min(...r.map((o) => o.timeS))]] : [];
  })), [selected, routes]);
  const noRoute = selected.flatMap((id) => {
    const r = routes[id], d = detours[`${id}|${hour}`];
    if (typeof r === "string" && r !== "loading") return [{ name: names[id], reason: r }];
    if (typeof d === "string" && d !== "loading") return [{ name: names[id], reason: `no detour found (${d})` }];
    return [];
  });
  const loading = selected.some((id) => routes[id] === "loading" || detours[`${id}|${hour}`] === "loading");
  const focus = ranked.some((r) => r.o.id === focusId) ? focusId : ranked[0]?.o.id ?? null;
  const bestFor = (id: string) => ranked.find((r) => r.o.serviceId === id);
  const shown = services
    .filter((s) => filter === "all" || s.kind === filter)
    .sort((a, b) => (a.timeS ?? Infinity) - (b.timeS ?? Infinity) || a.straightKm - b.straightKm);
  const mapServices = useMemo(() => services.filter((s) => filter === "all" || s.kind === filter || selected.includes(s.id)), [services, filter, selected]);
  const toggle = (id: string) => setSelected((sel) => (sel.includes(id) ? sel.filter((x) => x !== id) : [...sel, id]));
  const hours = base?.meta.event.hours ?? 18, start = base?.meta.event.replay_start_utc ?? "";

  return (
    <main id="content" className="flex flex-1 flex-col lg:min-h-0 lg:flex-row">
      <div className="relative order-1 h-[58vh] min-h-[360px] bg-soft-blue lg:order-2 lg:h-auto lg:flex-1">
        <RouteMap origin={origin} services={mapServices} selected={selected} ranked={ranked} focusId={focus} hour={hour} onService={toggle} onRoute={setFocusId} />
        {origin && <HourSlider hour={hour} hours={hours} start={start} onChange={setHour} />}
        {loading && (
          <p className="glass absolute left-4 top-4 inline-flex items-center gap-2 rounded-full px-3 py-2 font-ui text-xs font-semibold shadow-panel" role="status">
            <LoaderCircle size={14} className="animate-spin" aria-hidden /> Routing…
          </p>
        )}
      </div>

      <aside data-lenis-prevent className="order-2 w-full border-ink/10 bg-paper px-4 pb-16 pt-5 sm:px-6 lg:order-1 lg:w-[440px] lg:shrink-0 lg:overflow-y-auto lg:border-r">
        <a href="/" className="inline-flex min-h-11 items-center gap-1.5 font-ui text-sm text-muted hover:text-blue">
          <ArrowLeft size={15} aria-hidden /> Florence replay
        </a>
        <h1 className="font-display text-3xl font-bold tracking-[-0.03em]">Route analysis</h1>
        <p className="mt-1 font-ui text-sm text-muted">Routes from an address to emergency hospitals and fire stations, checked against the Florence 2018 replay.</p>

        <form className="mt-5" role="search" onSubmit={(e) => { e.preventDefault(); search(query); }}>
          <label htmlFor="route-addr" className="sr-only">Starting address</label>
          <div className="flex items-center gap-2 rounded-full border border-ink/10 bg-white p-1.5 pl-4 shadow-panel focus-within:border-blue focus-within:ring-4 focus-within:ring-blue/15">
            <Search size={18} className="shrink-0 text-blue" aria-hidden />
            <input id="route-addr" type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Enter an address in Cape Fear"
              autoComplete="street-address" className="min-h-11 w-full min-w-0 bg-transparent font-ui text-base focus-visible:outline-none" />
            <button type="submit" disabled={busy} className="inline-flex min-h-11 shrink-0 items-center gap-2 rounded-full bg-blue px-5 font-ui text-sm font-semibold text-white hover:bg-[#244d86] disabled:opacity-70">
              {busy && <LoaderCircle size={15} className="animate-spin" aria-hidden />} Go
            </button>
          </div>
        </form>
        <p aria-live="polite" className="mt-2 min-h-5 font-ui text-sm text-alert">{loadErr ? `Sample data failed to load (${loadErr}).` : msg}</p>

        {origin && (
          <p className="mt-1 flex items-start gap-2 font-ui text-sm"><MapPin size={16} className="mt-0.5 shrink-0 text-blue" aria-hidden />
            <span className="min-w-0 break-words"><b className="font-semibold">Starting at</b> {origin.label}</span></p>
        )}

        {services.length > 0 && (
          <section aria-labelledby="svc-h" className="mt-6">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 id="svc-h" className="font-ui text-sm font-semibold">Essential services</h2>
              <span className="font-ui text-xs text-muted">Tap to add or remove a route</span>
            </div>
            <div className="mt-3 flex gap-2" role="group" aria-label="Filter services">
              {FILTERS.map(([k, label]) => (
                <button key={k} type="button" onClick={() => setFilter(k)} aria-pressed={filter === k}
                  className={`min-h-9 rounded-full border px-3.5 font-ui text-xs font-semibold transition-colors ${filter === k ? "border-blue bg-blue text-white" : "border-ink/15 bg-white text-ink/75 hover:border-blue"}`}>
                  {label}
                </button>
              ))}
            </div>
            <ul className="mt-3 divide-y divide-ink/10 rounded-2xl border border-ink/10 bg-white">
              {shown.map((s) => {
                const on = selected.includes(s.id), b = bestFor(s.id), r = routes[s.id];
                const Icon = s.kind === "hospital" ? Hospital : Flame;
                return (
                  <li key={s.id}>
                    <button type="button" onClick={() => toggle(s.id)} aria-pressed={on}
                      className={`grid min-h-14 w-full grid-cols-[2rem_minmax(0,1fr)_auto] items-center gap-3 px-3 py-2.5 text-left transition-colors hover:bg-paper ${on ? "bg-soft-blue/50" : ""}`}>
                      <span className={`grid h-8 w-8 place-items-center rounded-full ${on ? "bg-blue text-white" : s.kind === "hospital" ? "bg-softred text-alert" : "bg-ink/5 text-ink"}`}>
                        {on ? <Check size={16} aria-hidden /> : <Icon size={16} aria-hidden />}
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate font-ui text-sm font-medium">{s.name}</span>
                        <span className="block truncate font-ui text-xs text-muted">{s.sub}</span>
                      </span>
                      <span className="flex flex-col items-end gap-1 text-right">
                        <span className="font-mono text-xs">{s.timeS != null ? mins(s.timeS) : s.timeS === null ? "no route" : `${s.straightKm.toFixed(0)} km`}</span>
                        {on && (b ? <StatusBadge state={b.s.state} /> : r === "loading" ? <LoaderCircle size={14} className="animate-spin text-muted" aria-label="Routing" /> : null)}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
            <p className="mt-2 font-ui text-xs leading-relaxed text-muted">
              Emergency hospitals with an ED from the CMS list and the {N_FIRE} nearest fire stations in the pipeline&rsquo;s list. Times are normal driving.
            </p>
          </section>
        )}

        {ranked.length > 0 && start && (
          <div className="mt-8">
            <RouteAnalysis groups={groups} focusId={focus} onFocus={setFocusId} hour={hour} hours={hours} start={start}
              names={names} fastest={fastest} block={block} noRoute={noRoute} />
          </div>
        )}
        {!origin && !busy && (
          <p className="mt-8 rounded-2xl bg-yellow p-4 font-ui text-sm leading-relaxed text-ink/80">
            Enter an address to list nearby emergency hospitals and fire stations. Pick one or several to compare routes, see which stream crossings
            each one uses, and how the Florence replay would have affected them hour by hour.
          </p>
        )}
      </aside>
    </main>
  );
}
