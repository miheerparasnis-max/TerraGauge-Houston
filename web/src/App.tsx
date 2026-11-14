import { useEffect, useMemo, useState } from "react";
import type { Cell, Meta, Mode, Sites } from "./types";
import { MapView, type Layers } from "./MapView";
import { Card } from "./Card";
import { HowWeKnow, SensorPage } from "./Pages";
import { CONFIDENCE, MODES, PRIORITY, movementColor, num } from "./labels";

type Tab = "map" | "how" | "sensor";

async function getJSON<T>(name: string): Promise<T> {
  const res = await fetch(`./data/${name}`);
  if (!res.ok) throw new Error(`Couldn't load ${name}. Run python3 scripts/export_web.py, then reload.`);
  return res.json();
}

function Legend({ mode, year, meta }: { mode: Mode; year: number; meta: Meta }) {
  if (mode === "movement") {
    const span = 25;
    const unit = "mm a year";
    return (
      <div>
        <div className="ramp" style={{ background: `linear-gradient(90deg, ${[-1, -0.66, -0.33, 0, 0.33].map((t) => movementColor(t * span, span)).join(",")})` }} />
        <div className="ramp-keys"><span>Sinking {span} {unit}</span><span>Stable</span><span>Rising</span></div>
      </div>
    );
  }
  const entries = mode === "priority"
    ? (["urgent", "high", "watch", "stable", "check"] as const).map((k) => ({ ...PRIORITY[k], n: meta.counts.priority[k] ?? 0 }))
    : (["high", "medium", "low"] as const).map((k) => ({ ...CONFIDENCE[k], n: meta.counts.confidence[k] ?? 0 }));
  return (
    <ul className="keys">{entries.map((e) => <li key={e.name} title={e.meaning}><span className="sw" style={{ background: e.color }} /><span><b>{e.name}</b><small>{e.meaning}</small></span><em>{e.n.toLocaleString()}</em></li>)}</ul>
  );
}

export default function App() {
  const [cells, setCells] = useState<Cell[] | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [sites, setSites] = useState<Sites | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("map");
  const [mode, setMode] = useState<Mode>("movement");
  const [year] = useState(2035);
  const [layers, setLayers] = useState<Layers>({ sensors: true, gps: false, ext: false, wells: false, flood: false });
  const [selected, setSelected] = useState<string | null>(null);
  const [focus, setFocus] = useState<{ lon: number; lat: number; key: number } | null>(null);

  useEffect(() => {
    Promise.all([getJSON<Cell[]>("cells.json"), getJSON<Meta>("meta.json"), getJSON<Sites>("sites.json")])
      .then(([c, m, s]) => { setCells(c); setMeta(m); setSites(s); })
      .catch((e: Error) => setError(e.message));
  }, []);
  useEffect(() => { if (tab === "map") window.dispatchEvent(new Event("resize")); }, [tab]);

  const byId = useMemo(() => new Map((cells ?? []).map((c) => [c.id, c])), [cells]);
  const stats = useMemo(() => {
    if (!cells) return null;
    const measured = cells.filter((c) => c.rate !== null && c.pri !== "no_data" && c.pri !== "check");
    const fast = measured.filter((c) => (c.rate ?? 0) <= -10).length;
    return { measured: measured.length, fast };
  }, [cells]);

  if (error) return <div className="loading">{error}</div>;
  if (!cells || !meta || !sites || !stats) return <div className="loading">Loading Houston…</div>;

  const cell = selected ? byId.get(selected) ?? null : null;
  const sensorFor = (id: string) => meta.sensors.find((s) => s.id === id);
  const pick = (id: string) => { const c = byId.get(id); if (!c) return; setSelected(id); setFocus({ lon: c.lon, lat: c.lat, key: Date.now() }); };
  const toggle = (k: keyof Layers) => setLayers((l) => ({ ...l, [k]: !l[k] }));
  const q = MODES.find((m) => m.key === mode)!;

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="14" fill="#B8862B" /><path d="M6 19c4-5 7 2 10-3s7 1 10-3" fill="none" stroke="#14201F" strokeWidth="2.6" strokeLinecap="round" /></svg>
          <div><h1>TerraGauge</h1><p>Where is Houston's ground sinking?</p></div>
        </div>
        <nav aria-label="Pages">
          {([["map", "Map"], ["how", "How we know"], ["sensor", "Our $74 sensor"]] as const).map(([k, name]) => (
            <button key={k} className={tab === k ? "tab on" : "tab"} aria-current={tab === k ? "page" : undefined} onClick={() => setTab(k)}>{name}</button>
          ))}
        </nav>
      </header>

      <main className={tab === "map" ? "stage" : "stage hidden"}>
        <MapView cells={cells} sites={sites} sensors={meta.sensors} mode={mode} year={year} layers={layers} selected={selected} focus={focus} onSelect={setSelected} />

        <div className="controls">
          <div className="box">
            <p className="box-label">Color the map by</p>
            <div className="seg" role="radiogroup" aria-label="Color the map by">
              {MODES.map((m) => <button key={m.key} role="radio" aria-checked={mode === m.key} className={mode === m.key ? "on" : ""} onClick={() => setMode(m.key)}>{m.name}</button>)}
            </div>
            <p className="question">{q.question}</p>
            <Legend mode={mode} year={year} meta={meta} />
          </div>
          <details className="box layers">
            <summary>Show on map</summary>
            {([["sensors", "Suggested sensor sites"], ["gps", "GPS stations"], ["ext", "Soil compaction gauges"], ["wells", "Groundwater wells"], ["flood", "FEMA high-risk flood zones"]] as const).map(([k, name]) => (
              <label key={k}><input type="checkbox" checked={layers[k]} onChange={() => toggle(k)} />{name}</label>
            ))}
          </details>
        </div>

        <section className={cell ? "panel open" : "panel"} aria-live="polite">
          {cell ? <Card cell={cell} meta={meta} sensor={sensorFor(cell.id)} onClose={() => setSelected(null)} /> : (
            <div className="summary">
              <h2>Houston at a glance</h2>
              <p className="fine">{meta.record.start.slice(0, 4)}–{meta.record.end.slice(0, 4)} satellite record combined with GPS, wells, compaction gauges, and flood zones. Click any square for its full story.</p>
              <button className="answer" onClick={() => setMode("movement")}>
                <span className="q">Where is the ground moving?</span>
                <span className="a"><strong>{stats.fast.toLocaleString()}</strong> of {stats.measured.toLocaleString()} measured squares sank 1 cm a year or more. The darkest purple areas are sinking fastest.</span>
              </button>
              <button className="answer" onClick={() => setMode("confidence")}>
                <span className="q">How sure are we?</span>
                <span className="a">The satellite matches {meta.validation.stations} GPS stations to within about <strong>{num(meta.validation.typical_diff_mm_year)} mm a year</strong>. Each square gets its own confidence level.</span>
              </button>
              <div className="answer">
                <span className="q">Can TerraGauge predict floods or future sinking?</span>
                <span className="a">No. {meta.forecast.reason ?? "Future projections are withheld until the evidence supports them."} TerraGauge directs investigation and monitoring; it does not forecast damage.</span>
              </div>
              <button className="answer" onClick={() => setMode("priority")}>
                <span className="q">Where should we act first?</span>
                <span className="a"><strong>{(meta.counts.priority.urgent ?? 0).toLocaleString()}</strong> urgent squares. Below are the top {meta.sensors.length} places to add a GPS sensor.</span>
              </button>
              <h3>Suggested sensor sites</h3>
              <ol className="sensor-list">
                {meta.sensors.map((s) => (
                  <li key={s.id}><button onClick={() => pick(s.id)}>
                    <span className="rank">{s.rank}</span>
                    <span><b>Area sinking about {num(Math.abs(s.areaRate / 10))} cm a year</b><small>{num(s.gpsKm)} km from the nearest GPS{s.sfha ? ", high-risk flood zone" : ""}, {CONFIDENCE[s.conf].name.toLowerCase()} confidence</small></span>
                  </button></li>
                ))}
              </ol>
            </div>
          )}
        </section>
      </main>
      {tab === "how" && <HowWeKnow meta={meta} />}
      {tab === "sensor" && <SensorPage />}
      {meta.status !== "reviewed" && <footer className="foot">Draft for NASA Space Apps 2026 (Dancing with the SARs). Not a flood forecast or a property assessment.</footer>}
    </div>
  );
}
