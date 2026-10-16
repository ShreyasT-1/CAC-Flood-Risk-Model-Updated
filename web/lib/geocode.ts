// Address search: OpenStreetMap Nominatim, preferring the three pilot counties. One request per search (usage policy).
// Nothing the user types is logged or stored here: the query goes only to Nominatim, and is not kept after the search.
const BOX = { w: -78.65, s: 33.75, e: -77.55, n: 34.75 }; // New Hanover, Brunswick, Pender (rough box)
const VIEWBOX = `${BOX.w},${BOX.n},${BOX.e},${BOX.s}`;
const inBox = (lat: number, lon: number) => lat >= BOX.s && lat <= BOX.n && lon >= BOX.w && lon <= BOX.e;

export const ADDRESS_EXAMPLE = "e.g. 1029 N Howe St, Southport NC";
export type Place = { lat: number; lon: number; label: string };

export async function geocode(query: string): Promise<Place | string> {
  const q = query.trim();
  if (!q) return `Enter a street address with the town name (${ADDRESS_EXAMPLE}).`;
  try {
    // Not "bounded": results are only preferred inside the box, so a hit outside it can be reported as outside instead of "no match".
    const url = `https://nominatim.openstreetmap.org/search?format=jsonv2&limit=5&countrycodes=us&viewbox=${VIEWBOX}&q=${encodeURIComponent(q)}`;
    const hits: { lat: string; lon: string; display_name: string }[] = await fetch(url, { headers: { Accept: "application/json" } }).then((r) => r.json());
    const hit = hits.find((h) => inBox(+h.lat, +h.lon));
    if (hit) return { lat: +hit.lat, lon: +hit.lon, label: hit.display_name.split(", ").slice(0, 3).join(", ") };
    if (hits.length) return "That place is outside the Cape Fear pilot area (New Hanover, Brunswick and Pender counties). Try an address inside it.";
    return `No match found. Place names often fail: use a street address with the town name (${ADDRESS_EXAMPLE}).`;
  } catch {
    return "Address lookup is unavailable right now. Try again in a moment.";
  }
}
