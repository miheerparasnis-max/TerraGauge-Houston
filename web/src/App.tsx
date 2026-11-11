import { useEffect, useMemo, useState } from "react";
import type { Cell, Meta, Mode, Sites } from "./types";
import { MapView, type Layers } from "./MapView";
import { Card } from "./Card";
import { HardwarePage, HowWeKnow } from "./Pages";
import { ACTION, CONFIDENCE, MODES, NO_MEASUREMENT, movementColor, num } from "./labels";

type Tab = "map" | "how" | "hardware";

async function getJSON<T>(name: string): Promise<T> {
  const res = await fetch(`./data/${name}`);
  if (!res.ok) throw new Error(`Couldn't load ${name}. Run python3 scripts/export_web.py, then reload.`);
  return res.json();
}

function Legend({ mode, year, meta }: { mode: Mode; year: number; meta: Meta }) {
  const noData = <li><span className="sw" style={{ background: NO_MEASUREMENT }} /><span><b>No measurement</b><small>{ACTION.insufficient_data.meaning}</small></span><em>{(meta.counts.action.insufficient_data ?? 0).toLocaleString()}</em></li>;
  if (mode === "movement" || mode === "future") {
    const span = mode === "movement" ? 25 : 12;
    const unit = mode === "movement" ? "mm a year" : `cm by ${year}`;
    return (
      <div>
        <div className="ramp" style={{ background: `linear-gradient(90deg, ${[-1, -0.66, -0.33, 0, 0.33].map((t) => movementColor(t * span, span)).join(",")})` }} />
        <div className="ramp-keys"><span>Sinking {span} {unit}</span><span>None</span><span>Rising</span></div>
        {mode === "future" && meta.forecast && <p className="legend-note">Each square's season-aware 2016–2026 trend, averaged with its neighborhood, continued. The most accurate of 9 methods tested on past years, including machine learning.</p>}
        <ul className="keys" style={{ marginTop: 8 }}>{noData}</ul>
      </div>
    );
  }
  const entries = mode === "priority"
    ? (["investigate_first", "add_monitoring", "review_disagreement", "observe", "no_clear_motion"] as const).map((k) => ({ ...ACTION[k], n: meta.counts.action[k] ?? 0 }))
    : (["high", "medium", "low"] as const).map((k) => ({ ...CONFIDENCE[k], n: meta.counts.confidence[k] ?? 0 }));
  return (
    <ul className="keys">{entries.map((e) => <li key={e.name} title={e.meaning}><span className="sw" style={{ background: e.color }} /><span><b>{e.name}</b><small>{e.meaning}</small></span><em>{e.n.toLocaleString()}</em></li>)}{noData}</ul>
  );
}

export default function App() {
  const [cells, setCells] = useState<Cell[] | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [sites, setSites] = useState<Sites | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("map");
  const [mode, setMode] = useState<Mode>("movement");
  const [year, setYear] = useState(2035);
  const [layers, setLayers] = useState<Layers>({ sensors: true, nodes: true, gps: false, ext: false, wells: false, flood: false });
  const [selected, setSelected] = useState<string | null>(null);
  const [focus, setFocus] = useState<{ lon: number; lat: number; key: number } | null>(null);

  useEffect(() => {
    Promise.all([getJSON<Cell[]>("cells.json"), getJSON<Meta>("meta.json"), getJSON<Sites>("sites.json")])
      .then(([c, m, s]) => { setCells(c); setMeta(m); setSites(s); if (m.forecast?.years.length) setYear(m.forecast.years[m.forecast.years.length - 1]); })
      .catch((e: Error) => setError(e.message));
  }, []);
  useEffect(() => { if (tab === "map") window.dispatchEvent(new Event("resize")); }, [tab]);

  const byId = useMemo(() => new Map((cells ?? []).map((c) => [c.id, c])), [cells]);
  const stats = useMemo(() => {
    if (!cells) return null;
    const measured = cells.filter((c) => c.rate !== null && c.act !== "insufficient_data");
    const fast = measured.filter((c) => (c.rate ?? 0) <= -10).length;
    return { measured: measured.length, fast };
  }, [cells]);

  if (error) return <div className="loading">{error}</div>;
  if (!cells || !meta || !sites || !stats) return <div className="loading">Loading Houston…</div>;

  const cell = selected ? byId.get(selected) ?? null : null;
  const sensorFor = (id: string) => meta.sensors.find((s) => s.id === id);
  const fc = meta.forecast;
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
          {([["map", "Map"], ["how", "How we know"], ["hardware", "Hardware"]] as const).map(([k, name]) => (
            <button key={k} className={tab === k ? "tab on" : "tab"} aria-current={tab === k ? "page" : undefined} onClick={() => setTab(k)}>{name}</button>
          ))}
        </nav>
      </header>

      <main className={tab === "map" ? "stage" : "stage hidden"}>
        <MapView cells={cells} sites={sites} sensors={meta.sensors} nodes={meta.nodes} mode={mode} year={year} layers={layers} selected={selected} focus={focus} onSelect={setSelected} />

        <div className="controls">
          <div className="box">
            <p className="box-label">Color the map by</p>
            <div className="seg" role="radiogroup" aria-label="Color the map by">
              {MODES.map((m) => <button key={m.key} role="radio" aria-checked={mode === m.key} className={mode === m.key ? "on" : ""} onClick={() => setMode(m.key)}>{m.name}</button>)}
            </div>
            <p className="question">{q.question}</p>
            {mode === "future" && fc && (
              <label className="year-select">By the year
                <select value={year} onChange={(e) => setYear(Number(e.target.value))}>
                  {fc.years.map((y) => <option key={y} value={y}>{y}</option>)}
                </select>
              </label>
            )}
            <Legend mode={mode} year={year} meta={meta} />
          </div>
          <details className="box layers">
            <summary>Show on map</summary>
            {([["sensors", "Suggested GPS stations (numbered)"], ["nodes", "Suggested low-cost nodes (diamonds)"], ["gps", "Existing GPS stations"], ["ext", "Soil compaction gauges"], ["wells", "Groundwater wells"], ["flood", "FEMA high-risk flood zones"]] as const).map(([k, name]) => (
              <label key={k}><input type="checkbox" checked={layers[k]} onChange={() => toggle(k)} />{name}</label>
            ))}
          </details>
        </div>

        <section className={cell ? "panel open" : "panel"} aria-live="polite">
          {cell ? <Card cell={cell} meta={meta} sensor={sensorFor(cell.id)} onClose={() => setSelected(null)} /> : (
            <div className="summary">
              <h2>Houston at a glance</h2>
              <div className="matters">
                <h3>Why this matters</h3>
                <p>Pumping groundwater makes Houston's clay soils squeeze and the land sink. Some areas sank over 9 feet in four decades, and sinking ground adds to flood risk, because land that sinks gets closer to the water that floods it and drainage stops working as designed (Harris-Galveston Subsidence District).</p>
                <p>TerraGauge uses NASA satellites to show where that's still happening, how sure we are, how much more is likely by {fc ? fc.years[fc.years.length - 1] : "2031"}, and where new sensors would do the most good.</p>
              </div>
              <p className="fine">NASA satellite record {meta.record.start.slice(0, 4)}–{meta.record.end.slice(0, 4)} combined with GPS, NISAR, wells, compaction gauges, and flood zones on one map. Click any square for its full story.</p>
              <button className="answer" onClick={() => setMode("movement")}>
                <span className="q">Where is the ground moving?</span>
                <span className="a"><strong>{stats.fast.toLocaleString()}</strong> of {stats.measured.toLocaleString()} squares sank 10 mm a year or more from {meta.record.start.slice(0, 4)} to {meta.record.end.slice(0, 4)}. Lighter squares are estimated from their neighbors; gray squares have no reading.</span>
              </button>
              <button className="answer" onClick={() => setMode("confidence")}>
                <span className="q">How sure are we?</span>
                <span className="a">The satellite matches {meta.validation.stations} GPS stations to within about <strong>{num(meta.validation.typical_diff_mm_year)} mm a year</strong>. Each square gets its own confidence level.</span>
              </button>
              <button className="answer" onClick={() => setMode("future")}>
                <span className="q">How much will it sink?</span>
                <span className="a">{fc ? (() => { const t = fc.benchmark.table; const k = String(Math.round(fc.tested_horizon_years)); const row = (m: string) => t.find((x) => x.method === m); const ch = row(fc.method), ml = row("ml_gradient_boosting"), nm = row("no_motion"); return <>Each square's season-aware trend, averaged with its neighborhood, continued to {fc.years[fc.years.length - 1]}. In {fc.benchmark.test_cases} tests on past years, predicting {k} years ahead it was off by a typical <strong>{ch ? num(ch.by_horizon_cm[k]) : "—"} cm</strong>, versus {nm ? num(nm.by_horizon_cm[k]) : "—"} cm for "no motion"{ml ? ` and ${num(ml.by_horizon_cm[k])} cm for a machine-learning model` : ""}.</>; })() : "No tested forecast yet."}</span>
              </button>
              <button className="answer" onClick={() => setMode("priority")}>
                <span className="q">What should Houston do here?</span>
                <span className="a"><strong>{(meta.counts.action.investigate_first ?? 0).toLocaleString()}</strong> squares to investigate first, <strong>{(meta.counts.action.add_monitoring ?? 0).toLocaleString()}</strong> that need a sensor, and <strong>{(meta.counts.action.review_disagreement ?? 0).toLocaleString()}</strong> where satellite and GPS disagree. Numbered pins: permanent GPS stations. Diamonds: low-cost nodes.</span>
              </button>
              <h3>Suggested permanent GPS stations</h3>
              <p className="fine">The measured "Add monitoring here" squares in the fastest-sinking areas, at least {meta.thresholds.sensor_spacing_km} km apart. {meta.nodes.length} more low-cost node sites (diamonds) are on the Hardware page.</p>
              <ol className="sensor-list">
                {meta.sensors.map((s) => (
                  <li key={s.id}><button onClick={() => pick(s.id)}>
                    <span className="rank">{s.rank}</span>
                    <span><b>Area sinking {num(Math.abs(s.areaRate))} mm a year</b><small>{num(s.gpsKm)} km from the nearest GPS, flood zone {s.zone}{s.conf ? `, ${CONFIDENCE[s.conf].name.toLowerCase()} confidence` : ""}</small></span>
                  </button></li>
                ))}
              </ol>
            </div>
          )}
        </section>
      </main>
      {tab === "how" && <HowWeKnow meta={meta} />}
      {tab === "hardware" && <HardwarePage meta={meta} onShow={(id) => { setTab("map"); setMode("priority"); setLayers((l) => ({ ...l, sensors: true, nodes: true })); pick(id); }} />}
      {meta.status !== "reviewed" && <footer className="foot">Draft for NASA Space Apps 2026 (Dancing with the SARs). Not a flood forecast or a property assessment.</footer>}
    </div>
  );
}
