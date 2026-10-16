"use client";
import { useEffect, useRef, useState } from "react";
import { RISK, crossingStatus, getJSON, hourTime, pct } from "@/lib/sample";
import { BOUNDS, STYLE, esc, loadMaplibre, type ML } from "@/lib/maplibre";
import { useSample } from "@/components/forecast/sample-store";
import { HourSlider } from "@/components/ui/hour-slider";

const CROSSING_KEY = [
  ["Above 10-year flow (closed in scenario)", "#CC0000"],
  ["Above 2-year flow", "#EFAEAE"],
  ["Below 2-year flow · not flagged, not an all-clear", "#FFFFFF"],
] as const;

function Legend() {
  return (
    <div className="grid gap-4 sm:justify-items-end">
      <div>
        <p className="label mb-2.5 text-muted">
          Chance of losing access <span className="ml-1 rounded-full bg-[#EFE3FF] px-2 py-0.5 normal-case tracking-normal text-[#5A2D91]">placeholder</span>
        </p>
        <ul className="flex flex-wrap gap-x-5 gap-y-3 font-ui text-xs text-ink/80" aria-label="Isolation likelihood legend">
          {RISK.map(({ label, cls }) => (
            <li key={label} className="flex items-center gap-2">
              <span className={`h-3.5 w-5 rounded-sm border border-ink/15 ${cls}`} aria-hidden />
              {label}
            </li>
          ))}
        </ul>
      </div>
      <div>
        <p className="label mb-2.5 text-muted">
          Crossings <span className="ml-1 rounded-full bg-soft-blue px-2 py-0.5 normal-case tracking-normal text-blue">replay</span>
        </p>
        <ul className="flex flex-wrap gap-x-5 gap-y-3 font-ui text-xs text-ink/80">
          {CROSSING_KEY.map(([label, fill]) => (
            <li key={label} className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-full border border-ink/40" style={{ background: fill }} aria-hidden />
              {label}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export function ForecastMap() {
  const { data, error, hour, setHour, selected, select } = useSample();
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<ML>(null);
  const pin = useRef<ML>(null);
  const [ready, setReady] = useState(false);
  const [mapError, setMapError] = useState<string | null>(null);
  const hours = data?.meta.event.hours ?? 18;
  const start = data?.meta.event.replay_start_utc;

  const crossingsFC = () => ({
    type: "FeatureCollection",
    features: data!.crossings.map((c) => {
      const level = c.hourly[hour].level_reached.value;
      return { type: "Feature", properties: { id: c.id, name: c.name, level, cls: level === "RL0" ? 0 : crossingStatus(level).startsWith("Above 10") ? 2 : 1 },
        geometry: { type: "Point", coordinates: [c.lon, c.lat] } };
    }),
  });
  const sitesFC = () => ({
    type: "FeatureCollection",
    features: data!.sites.map((s) => ({ type: "Feature", properties: { id: s.id, name: s.name, p: s.hours[hour].p, res: s.kind === "residential" },
      geometry: { type: "Point", coordinates: [s.lon, s.lat] } })),
  });

  // Build the map once the sample data is in.
  useEffect(() => {
    if (!data || !box.current || map.current) return;
    let gone = false;
    Promise.all([loadMaplibre(), getJSON<{ features: { properties: { kind: string } }[] }>("network.geojson")])
      .then(([ml, net]) => {
        if (gone || !box.current) return;
        const m = new ml.Map({ container: box.current, style: STYLE, bounds: BOUNDS, fitBoundsOptions: { padding: 24 }, cooperativeGestures: true, attributionControl: { compact: true } });
        map.current = m;
        m.addControl(new ml.NavigationControl({ showCompass: false }), "top-right");
        m.on("load", () => {
          m.addSource("roads", { type: "geojson", data: { type: "FeatureCollection", features: net.features.filter((f) => f.properties.kind === "road") } });
          m.addLayer({ id: "roads", type: "line", source: "roads", paint: {
            "line-color": ["case", ["get", "carries_sample_crossing"], "#16345B", "#2D5DA1"],
            "line-opacity": ["case", ["get", "carries_sample_crossing"], 0.75, 0.35],
            "line-width": ["match", ["get", "highway"], "motorway", 2.6, "trunk", 2.2, "primary", 1.7, "secondary", 1.3, 0.9] } });
          m.addSource("crossings", { type: "geojson", data: crossingsFC() });
          m.addLayer({ id: "crossings", type: "circle", source: "crossings", paint: {
            "circle-radius": ["match", ["get", "cls"], 2, 6, 5], "circle-stroke-width": 1.5,
            "circle-color": ["match", ["get", "cls"], 2, "#CC0000", 1, "#EFAEAE", "#FFFFFF"],
            "circle-stroke-color": ["match", ["get", "cls"], 2, "#FFFFFF", "#111111"] } });
          m.addSource("sites", { type: "geojson", data: sitesFC(), promoteId: "id" });
          m.addLayer({ id: "sites", type: "circle", source: "sites", paint: {
            "circle-radius": ["case", ["boolean", ["feature-state", "sel"], false], 14, ["get", "res"], 8, 10],
            "circle-color": ["step", ["get", "p"], RISK[0].fill, 0.15, RISK[1].fill, 0.35, RISK[2].fill, 0.55, RISK[3].fill, 0.75, RISK[4].fill],
            "circle-stroke-color": ["case", ["boolean", ["feature-state", "sel"], false], "#2D5DA1", "#111111"],
            "circle-stroke-width": ["case", ["boolean", ["feature-state", "sel"], false], 4, [">=", ["get", "p"], 0.55], 3, 1.5] } });
          const tip = new ml.Popup({ closeButton: false, closeOnClick: false, offset: 10 });
          m.on("mousemove", "crossings", (e: ML) => {
            const f = e.features[0].properties;
            m.getCanvas().style.cursor = "pointer";
            tip.setLngLat(e.lngLat).setHTML(`<b>${esc(f.name)}</b><br>${crossingStatus(f.level)} · replay`).addTo(m);
          });
          m.on("mousemove", "sites", (e: ML) => {
            const f = e.features[0].properties;
            m.getCanvas().style.cursor = "pointer";
            tip.setLngLat(e.lngLat).setHTML(`<b>${esc(f.name)}</b><br>${pct(f.p)} chance of losing access · placeholder`).addTo(m);
          });
          for (const id of ["crossings", "sites"]) m.on("mouseleave", id, () => { m.getCanvas().style.cursor = ""; tip.remove(); });
          m.on("click", "sites", (e: ML) => select(data.sites.find((s) => s.id === e.features[0].properties.id) ?? null));
          setReady(true);
        });
      })
      .catch((e: Error) => setMapError(e.message));
    return () => { gone = true; map.current?.remove(); map.current = null; setReady(false); };
  }, [data]); // eslint-disable-line react-hooks/exhaustive-deps

  // Hour changes recolour crossings and places.
  useEffect(() => {
    if (!ready) return;
    map.current.getSource("crossings").setData(crossingsFC());
    map.current.getSource("sites").setData(sitesFC());
  }, [ready, hour]); // eslint-disable-line react-hooks/exhaustive-deps

  // Selection: highlight a sample place, or drop a pin on a searched address.
  useEffect(() => {
    if (!ready || !data) return;
    const m = map.current, ml = (window as unknown as { maplibregl: ML }).maplibregl;
    data.sites.forEach((s) => m.setFeatureState({ source: "sites", id: s.id }, { sel: s.id === selected?.id }));
    pin.current?.remove(); pin.current = null;
    if (!selected) return;
    if (selected.kind === "address") pin.current = new ml.Marker({ color: "#2D5DA1" }).setLngLat([selected.lon, selected.lat]).addTo(m);
    m.flyTo({ center: [selected.lon, selected.lat], zoom: Math.max(m.getZoom(), 10.5), essential: true });
  }, [ready, selected, data]);


  return (
    <figure>
      <div className="reveal-zoom relative overflow-hidden rounded-3xl bg-soft-blue shadow-float">
        <div className="glass pointer-events-none absolute left-4 top-4 z-[2] inline-flex items-center gap-2 rounded-full px-3 py-2 font-ui text-xs font-semibold shadow-panel">
          <span className="h-2 w-2 rounded-full bg-alert" aria-hidden />
          Florence 2018 replay · sample data
        </div>
        <div
          ref={box}
          data-lenis-prevent
          role="region"
          aria-label="Map of sample crossings and places in the Cape Fear region"
          className="block aspect-[4/5] w-full sm:aspect-[16/9]"
        />
        {(error || mapError) && (
          <p className="absolute inset-0 grid place-items-center p-8 text-center font-ui text-sm text-muted">
            The sample map could not load ({error ?? mapError}).
          </p>
        )}
        <HourSlider hour={hour} hours={hours} start={start} onChange={setHour} />
      </div>
      <div className="reveal mt-5 flex flex-col justify-between gap-5 sm:flex-row sm:items-start">
        <figcaption className="max-w-md font-ui text-xs leading-relaxed text-muted">
          Replay of the NWM v3.0 retrospective for Hurricane Florence, starting {start ? hourTime(start, 0) : "…"}. A crossing closes in this
          scenario while its stream runs above the 10-year flow. River flow only: no storm surge, tide or street flooding. Large circles are sample
          places; risk colours on them are placeholders until the forecast model is ready.
        </figcaption>
        <Legend />
      </div>
    </figure>
  );
}
