import { useEffect, useState } from "react";

// Neighbourhood names from OpenStreetMap Nominatim (reverse geocoding), one
// request at a time (their usage policy asks for at most 1 per second),
// cached per square for the session. Silent if offline.
const cache = new Map<string, string | null>();
const waiting = new Map<string, ((n: string | null) => void)[]>();
let chain: Promise<void> = Promise.resolve();

function lookup(key: string, lon: number, lat: number): Promise<string | null> {
  if (cache.has(key)) return Promise.resolve(cache.get(key)!);
  return new Promise((resolve) => {
    const list = waiting.get(key);
    if (list) { list.push(resolve); return; }
    waiting.set(key, [resolve]);
    chain = chain.then(async () => {
      let name: string | null = null;
      try {
        const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=jsonv2&zoom=14&lat=${lat}&lon=${lon}`, { headers: { Accept: "application/json" } });
        if (res.ok) {
          const a = ((await res.json()) as { address?: Record<string, string> }).address ?? {};
          const local = a.neighbourhood ?? a.suburb ?? a.quarter ?? a.hamlet ?? a.village;
          const town = a.city ?? a.town ?? a.village ?? a.county;
          name = local && town && local !== town ? `${local}, ${town}` : local ?? town ?? null;
        }
      } catch { name = null; }
      cache.set(key, name);
      (waiting.get(key) ?? []).forEach((f) => f(name));
      waiting.delete(key);
      await new Promise((r) => setTimeout(r, 1100));
    });
  });
}

export function usePlaceName(key: string, lon: number, lat: number): string | null {
  const [name, setName] = useState<string | null>(cache.get(key) ?? null);
  useEffect(() => {
    let live = true;
    lookup(key, lon, lat).then((n) => { if (live) setName(n); });
    return () => { live = false; };
  }, [key, lon, lat]);
  return name;
}
