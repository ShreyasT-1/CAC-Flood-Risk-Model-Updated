"use client";
import { useEffect, useRef, useState } from "react";
import { BOUNDS, STYLE, esc, loadMaplibre, type ML } from "@/lib/maplibre";
import { CLOSED, type HourStatus, type RouteOption } from "@/lib/route";

export type MapService = { id: string; kind: "hospital" | "fire"; name: string; lat: number; lon: number };
type Ranked = { o: RouteOption; s: HourStatus }[];

const STATE_COLOR = ["#2D5DA1", "#CC0000", "#7A0000"]; // open in replay / at risk / blocked

export function RouteMap({ origin, services, selected, ranked, focusId, hour, onService, onRoute }: {
  origin: { lat: number; lon: number } | null;
  services: MapService[];
  selected: string[];
  ranked: Ranked;
  focusId: string | null;
  hour: number;
  onService: (id: string) => void;
  onRoute: (id: string) => void;
}) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<ML>(null);
  const pin = useRef<ML>(null);
  const handlers = useRef({ onService, onRoute });
  handlers.current = { onService, onRoute };
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let gone = false;
    loadMaplibre().then((ml) => {
      if (gone || !box.current) return;
      const m = new ml.Map({ container: box.current, style: STYLE, bounds: BOUNDS, fitBoundsOptions: { padding: 24 }, attributionControl: { compact: true } });
      map.current = m;
      m.addControl(new ml.NavigationControl({ showCompass: false }), "top-right");
      m.on("load", () => {
        const empty = { type: "FeatureCollection", features: [] };
        m.addSource("routes", { type: "geojson", data: empty });
        m.addSource("rx", { type: "geojson", data: empty });
        m.addSource("svc", { type: "geojson", data: empty });
        m.addLayer({ id: "route-casing", type: "line", source: "routes", layout: { "line-cap": "round", "line-join": "round" },
          paint: { "line-color": "#FFFFFF", "line-width": ["case", ["get", "focus"], 11, 7], "line-opacity": 0.9 } });
        m.addLayer({ id: "routes", type: "line", source: "routes", layout: { "line-cap": "round", "line-join": "round" },
          paint: { "line-color": ["match", ["get", "state"], 2, STATE_COLOR[2], 1, STATE_COLOR[1], STATE_COLOR[0]],
            "line-width": ["case", ["get", "focus"], 7, 4], "line-opacity": ["case", ["get", "focus"], 1, 0.55] } });
        m.addLayer({ id: "routes-blocked", type: "line", source: "routes", filter: ["==", ["get", "state"], 2],
          paint: { "line-color": "#FFFFFF", "line-width": ["case", ["get", "focus"], 2.5, 1.5], "line-dasharray": [2, 2] } });
        m.addLayer({ id: "rx", type: "circle", source: "rx", paint: {
          "circle-radius": ["match", ["get", "cls"], 2, 7, 1, 5.5, 4], "circle-stroke-width": 1.5,
          "circle-color": ["match", ["get", "cls"], 2, "#CC0000", 1, "#EFAEAE", 0, "#FFFFFF", "#B8BCC2"],
          "circle-stroke-color": ["match", ["get", "cls"], 2, "#FFFFFF", "#111111"] } });
        m.addLayer({ id: "svc", type: "circle", source: "svc", paint: {
          "circle-radius": ["case", ["get", "sel"], 9, 6],
          "circle-color": ["case", ["==", ["get", "kind"], "hospital"], "#FFFFFF", "#111111"],
          "circle-stroke-color": ["case", ["get", "sel"], "#2D5DA1", ["==", ["get", "kind"], "hospital"], "#CC0000", "#FFFFFF"],
          "circle-stroke-width": ["case", ["get", "sel"], 4, 2] } });
        m.addLayer({ id: "svc-label", type: "symbol", source: "svc", filter: ["get", "sel"],
          layout: { "text-field": ["get", "name"], "text-font": ["Noto Sans Regular"], "text-size": 12, "text-offset": [0, 1.3], "text-anchor": "top", "text-max-width": 12 },
          paint: { "text-color": "#111111", "text-halo-color": "#FFFFFF", "text-halo-width": 1.5 } });
        const tip = new ml.Popup({ closeButton: false, closeOnClick: false, offset: 10 });
        const hover = (id: string, html: (p: Record<string, string>) => string) => {
          m.on("mousemove", id, (e: ML) => { m.getCanvas().style.cursor = "pointer"; tip.setLngLat(e.lngLat).setHTML(html(e.features[0].properties)).addTo(m); });
          m.on("mouseleave", id, () => { m.getCanvas().style.cursor = ""; tip.remove(); });
        };
        hover("svc", (p) => `<b>${esc(p.name)}</b><br>${p.kind === "hospital" ? "Emergency hospital" : "Fire station"} · click to ${p.sel === "true" ? "remove" : "route"}`);
        hover("rx", (p) => `<b>${esc(p.name)}</b><br>${esc(p.status)}`);
        hover("routes", (p) => `<b>${esc(p.label)}</b><br>${esc(p.status)}`);
        m.on("click", "svc", (e: ML) => handlers.current.onService(e.features[0].properties.id));
        m.on("click", "routes", (e: ML) => handlers.current.onRoute(e.features[0].properties.id));
        setReady(true);
      });
    }).catch((e: Error) => setError(e.message));
    return () => { gone = true; map.current?.remove(); map.current = null; setReady(false); };
  }, []);

  // Services and origin; fit the view to the origin and selected services.
  useEffect(() => {
    if (!ready) return;
    const m = map.current, ml = (window as unknown as { maplibregl: ML }).maplibregl;
    m.getSource("svc").setData({ type: "FeatureCollection", features: services.map((s) => ({ type: "Feature",
      properties: { id: s.id, name: s.name, kind: s.kind, sel: selected.includes(s.id) }, geometry: { type: "Point", coordinates: [s.lon, s.lat] } })) });
    pin.current?.remove(); pin.current = null;
    if (!origin) return;
    pin.current = new ml.Marker({ color: "#2D5DA1" }).setLngLat([origin.lon, origin.lat]).addTo(m);
    const pts = [[origin.lon, origin.lat], ...services.filter((s) => selected.includes(s.id)).map((s) => [s.lon, s.lat])];
    const lons = pts.map((p) => p[0]), lats = pts.map((p) => p[1]);
    m.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]], { padding: { top: 60, bottom: 150, left: 50, right: 50 }, maxZoom: 13, duration: 600 });
  }, [ready, origin, services, selected]);

  // Routes and the crossings on them, coloured for the current hour.
  useEffect(() => {
    if (!ready) return;
    const m = map.current;
    const seen = new Map<string, { name: string; lat: number; lon: number; cls: number; status: string }>();
    const label = ["Open in replay (not an all-clear)", "At risk", "Blocked in replay"];
    const features = [...ranked].reverse().map(({ o, s }) => {
      for (const c of o.on) {
        const lv = c.x ? +c.x.level[hour] : -1;
        seen.set(c.id, { name: c.x?.name ?? "Stream crossing (not assessed)", lat: c.lat, lon: c.lon, cls: lv < 0 ? -1 : lv >= CLOSED ? 2 : lv > 0 ? 1 : 0,
          status: lv < 0 ? "Not assessed by the model" : lv >= CLOSED ? "Closed in scenario (above 10-year flow)" : lv > 0 ? "Above 2-year flow" : "Below 2-year flow · not an all-clear" });
      }
      return { type: "Feature", properties: { id: o.id, label: o.label, state: s.state, status: label[s.state], focus: o.id === focusId }, geometry: { type: "LineString", coordinates: o.shape } };
    });
    features.sort((a, b) => +a.properties.focus - +b.properties.focus); // focused route drawn last (on top)
    m.getSource("routes").setData({ type: "FeatureCollection", features });
    m.getSource("rx").setData({ type: "FeatureCollection", features: [...seen].map(([id, c]) => ({ type: "Feature",
      properties: { id, name: c.name, cls: c.cls, status: c.status }, geometry: { type: "Point", coordinates: [c.lon, c.lat] } })) });
  }, [ready, ranked, focusId, hour]);

  return (
    <div className="absolute inset-0">
      <div ref={box} data-lenis-prevent className="h-full w-full" role="region" aria-label="Route map" />
      {error && <p className="absolute inset-0 grid place-items-center p-8 text-center font-ui text-sm text-muted">The map could not load ({error}).</p>}
    </div>
  );
}
