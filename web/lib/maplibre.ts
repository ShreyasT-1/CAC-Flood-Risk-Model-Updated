// MapLibre loads from a pinned CDN build at runtime (the npm registry is unreachable from the dev network); basemap is OpenFreeMap (no API key).
const CDN = "https://unpkg.com/maplibre-gl@4.7.1/dist/";
export const STYLE = "https://tiles.openfreemap.org/styles/positron";
export const BOUNDS = [[-78.65, 33.83], [-77.65, 34.65]];

export type ML = any; // eslint-disable-line @typescript-eslint/no-explicit-any
let loading: Promise<ML> | null = null;

export function loadMaplibre(): Promise<ML> {
  const w = window as unknown as { maplibregl?: ML };
  if (w.maplibregl) return Promise.resolve(w.maplibregl);
  loading ??= new Promise((resolve, reject) => {
    const css = Object.assign(document.createElement("link"), { rel: "stylesheet", href: CDN + "maplibre-gl.css" });
    const js = Object.assign(document.createElement("script"), { src: CDN + "maplibre-gl.js" });
    js.onload = () => resolve(w.maplibregl);
    js.onerror = () => { loading = null; reject(new Error("map library failed to load")); };
    document.head.append(css, js);
  });
  return loading;
}

export const esc = (s: string) => s.replace(/[&<>"]/g, (c) => `&#${c.charCodeAt(0)};`);
