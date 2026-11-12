import { useState } from "react";

interface Hit { name: string; lon: number; lat: number }

/** Address / place search (OpenStreetMap Nominatim, limited to the study area) and "use my location". */
export function Search({ onPick }: { onPick: (lon: number, lat: number, label: string) => void }) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Hit[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    if (!q.trim()) return;
    setBusy(true); setMsg(null); setHits(null);
    try {
      const url = `https://nominatim.openstreetmap.org/search?format=jsonv2&limit=5&countrycodes=us&viewbox=-95.95,30.2,-94.8,29.4&bounded=1&q=${encodeURIComponent(q)}`;
      const res = await fetch(url, { headers: { Accept: "application/json" } });
      if (!res.ok) throw new Error(String(res.status));
      const rows = (await res.json()) as { display_name: string; lon: string; lat: string }[];
      const found = rows.map((r) => ({ name: r.display_name.split(",").slice(0, 3).join(","), lon: Number(r.lon), lat: Number(r.lat) }));
      if (!found.length) setMsg("No match inside the Houston study area. Try a street address or ZIP code.");
      else if (found.length === 1) { onPick(found[0].lon, found[0].lat, found[0].name); setHits(null); }
      else setHits(found);
    } catch {
      setMsg("Search isn't available right now. Click the map instead.");
    } finally { setBusy(false); }
  }

  function locate() {
    if (!navigator.geolocation) { setMsg("Your browser can't share your location."); return; }
    setBusy(true); setMsg(null);
    navigator.geolocation.getCurrentPosition(
      (p) => { setBusy(false); onPick(p.coords.longitude, p.coords.latitude, "Your location"); },
      () => { setBusy(false); setMsg("Couldn't get your location. Check your browser's permission."); },
      { timeout: 10000 },
    );
  }

  return (
    <div className="search">
      <form onSubmit={run} role="search">
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search an address or ZIP" aria-label="Search an address or ZIP code" />
        <button type="submit" disabled={busy}>{busy ? "…" : "Find"}</button>
      </form>
      <button className="link small-link" onClick={locate} disabled={busy}>Use my location</button>
      {msg && <p className="search-msg">{msg}</p>}
      {hits && <ul className="hits">{hits.map((h) => <li key={`${h.lon},${h.lat}`}><button onClick={() => { setHits(null); onPick(h.lon, h.lat, h.name); }}>{h.name}</button></li>)}</ul>}
    </div>
  );
}
