// Address search: OpenStreetMap Nominatim, bounded to the three pilot counties. One request per search (usage policy).
const VIEWBOX = "-78.65,34.75,-77.55,33.75";

export type Place = { lat: number; lon: number; label: string };

export async function geocode(query: string): Promise<Place | string> {
  const q = query.trim();
  if (!q) return "Enter an address in New Hanover, Brunswick or Pender County.";
  try {
    const url = `https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&countrycodes=us&bounded=1&viewbox=${VIEWBOX}&q=${encodeURIComponent(q)}`;
    const hits = await fetch(url, { headers: { Accept: "application/json" } }).then((r) => r.json());
    if (!hits.length) return "No match inside the Cape Fear pilot area. Try a street address with the town name.";
    return { lat: +hits[0].lat, lon: +hits[0].lon, label: hits[0].display_name.split(", ").slice(0, 3).join(", ") };
  } catch {
    return "Address lookup is unavailable right now. Try again in a moment.";
  }
}
