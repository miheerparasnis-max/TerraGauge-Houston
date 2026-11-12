import { useCallback, useEffect, useMemo, useState } from "react";
import type { Cell, ColorBy, Hazard, Meta, Mode, Sites } from "./types";
import { MapView, type Layers } from "./MapView";
import { Card } from "./Card";
import { HardwarePage, HowWeKnow } from "./Pages";
import { Search } from "./Search";
import { cellIdAt } from "./geo";
import { readHash, writeHash, type Tab } from "./url";
import { ACTION, BEND, CONFIDENCE, DROUGHT, FLOOD, HAZARDS, MODES, NOT_DIRECT, NO_MEASUREMENT, floodExtra, movementColor, num } from "./labels";

async function getJSON<T>(name: string): Promise<T> {
  const res = await fetch(`./data/${name}`);
  if (!res.ok) throw new Error(`Couldn't load ${name}. Run python3 scripts/export_web.py, then reload.`);
  return res.json();
}

interface Key { key: string; name: string; color: string; meaning: string; n: number }

function KeyList({ items, note }: { items: Key[]; note?: React.ReactNode }) {
  return (
    <>
      <ul className="keys">{items.map((e) => <li key={e.key} title={e.meaning}><span className="sw" style={{ background: e.color }} /><b>{e.name}</b><em>{e.n.toLocaleString()}</em></li>)}</ul>
      <details className="explain">
        <summary>What do these mean?</summary>
        <dl>{items.map((e) => <div key={e.key}><dt>{e.name}</dt><dd>{e.meaning}</dd></div>)}</dl>
        {note && <p>{note}</p>}
      </details>
    </>
  );
}

function Legend({ mode, hazard, year, meta, cells }: { mode: Mode; hazard: Hazard; year: number; meta: Meta; cells: Cell[] }) {
  const noData: Key = { key: "none", name: "No measurement", color: NO_MEASUREMENT, meaning: ACTION.insufficient_data.meaning, n: meta.counts.action.insufficient_data ?? 0 };
  const counts = useMemo(() => {
    const m = new Map<string, number>();
    if (mode !== "hazards") return m;
    const add = (k: string) => m.set(k, (m.get(k) ?? 0) + 1);
    for (const c of cells) {
      if (hazard === "flood") { const f = floodExtra(c, year, meta); if (f.cls) add(f.cls === "1pct" && (f.total ?? 0) >= 3 ? "deeper" : f.cls === "levee" ? "0.2pct" : f.cls); }
      else if (c.hz && c.act !== "insufficient_data") { const v = hazard === "drought" ? c.hz.dl : c.hz.bl; if (v) add(v); }
    }
    return m;
  }, [mode, hazard, year, meta, cells]);

  if (mode === "movement" || mode === "future") {
    const span = mode === "movement" ? 25 : 12;
    const unit = mode === "movement" ? "mm a year" : `cm by ${year}`;
    return (
      <div>
        <div className="ramp" style={{ background: `linear-gradient(90deg, ${[-1, -0.66, -0.33, 0, 0.33].map((t) => movementColor(t * span, span)).join(",")})` }} />
        <div className="ramp-keys"><span>Sinking {span}+ {unit}</span><span>None</span><span>Rising</span></div>
        <KeyList items={[noData]} note={mode === "future"
          ? <>Each square's season-aware 2016–2026 trend, averaged with its neighborhood, continued. It was the most accurate of {meta.forecast?.benchmark.table.length ?? 9} methods tested on past years, including machine learning. Lighter squares are estimated from their neighbors.</>
          : <>Measured by NASA's OPERA satellite product, 2016–2026, converted to up-and-down movement and blended with GPS where a station is inside the square. Lighter squares are estimated from their neighbors.</>} />
      </div>
    );
  }
  if (mode === "hazards") {
    const table: Record<string, { name: string; color: string; meaning: string }> = hazard === "flood" ? FLOOD : hazard === "drought" ? DROUGHT : BEND;
    const keys = hazard === "flood" ? ["deeper", "1pct", "0.2pct", "minimal"] : ["high", "medium", "low"];
    const t = meta.hazards?.tests;
    const note = hazard === "flood"
      ? <>FEMA's flood zones give the odds of a big flood. Our forecast gives how much the ground sinks by {year}, which makes the same flood that much deeper. Coastal squares also get about 1 cm a year of Gulf rise.</>
      : hazard === "drought" && t ? <>Tested: using only data from before 2023, the squares flagged from the 2018 drought dropped a median {num(t.drought.flagged_median_drop_mm, 0)} mm in the 2023 drought, versus {num(t.drought.others_median_drop_mm, 0)} mm for the rest.</>
      : t ? <>Tested: the sharpest-bending squares in 2016–2021 were still bending about {num(t.bending.hotspot_later_median / t.bending.others_later_median, 0)}× more than the rest in 2021–2026.</> : undefined;
    const items: Key[] = keys.map((k) => ({ key: k, ...table[k], n: counts.get(k) ?? 0 }));
    if (hazard !== "flood") items.push({ key: "indirect", name: "No direct record", color: NOT_DIRECT, meaning: "Estimated or unmeasured squares: drought and bending need a square's own satellite record.", n: cells.length - items.reduce((t, i) => t + i.n, 0) });
    return <KeyList items={items} note={note} />;
  }
  const items: Key[] = mode === "priority"
    ? (["investigate_first", "add_monitoring", "review_disagreement", "observe", "no_clear_motion"] as const).map((k) => ({ key: k, ...ACTION[k], n: meta.counts.action[k] ?? 0 }))
    : (["high", "medium", "low"] as const).map((k) => ({ key: k, ...CONFIDENCE[k], n: meta.counts.confidence[k] ?? 0 }));
  return <KeyList items={[...items, noData]} note={mode === "priority" ? <>Rules are checked in this order; the first that fits decides. Numbered pins are suggested permanent GPS stations; diamonds are suggested low-cost nodes.</> : undefined} />;
}

const LAYER_NAMES: [keyof Layers, string][] = [["sensors", "Suggested GPS stations (numbered)"], ["nodes", "Suggested low-cost nodes (diamonds)"], ["gps", "Existing GPS stations"], ["ext", "Soil compaction gauges"], ["wells", "Groundwater wells"], ["flood", "FEMA high-risk flood zones"]];

export default function App() {
  const initial = useMemo(readHash, []);
  const [cells, setCells] = useState<Cell[] | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [sites, setSites] = useState<Sites | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>(initial.tab ?? "map");
  const [mode, setMode] = useState<Mode>(initial.mode ?? "movement");
  const [hazard, setHazard] = useState<Hazard>(initial.hazard ?? "flood");
  const [year, setYear] = useState<number>(initial.year ?? 0);
  const [layers, setLayers] = useState<Layers>({ sensors: true, nodes: true, gps: false, ext: false, wells: false, flood: false });
  const [selected, setSelected] = useState<string | null>(initial.cell ?? null);
  const [focus, setFocus] = useState<{ lon: number; lat: number; key: number } | null>(null);
  const [sheet, setSheet] = useState(false);
  const [found, setFound] = useState<string | null>(null);
  const [mapSeen, setMapSeen] = useState(tab === "map");
  useEffect(() => { if (tab === "map") setMapSeen(true); }, [tab]);

  useEffect(() => {
    Promise.all([getJSON<Cell[]>("cells.json"), getJSON<Meta>("meta.json"), getJSON<Sites>("sites.json")])
      .then(([c, m, s]) => {
        setCells(c); setMeta(m); setSites(s);
        const ys = m.forecast?.years ?? [];
        setYear((y) => (ys.includes(y) ? y : ys[ys.length - 1] ?? 2031));
        if (initial.cell) { const hit = c.find((x) => x.id === initial.cell); if (hit) setFocus({ lon: hit.lon, lat: hit.lat, key: Date.now() }); }
      })
      .catch((e: Error) => setError(e.message));
  }, [initial.cell]);
  useEffect(() => { if (tab === "map") requestAnimationFrame(() => window.dispatchEvent(new Event("resize"))); }, [tab]);
  useEffect(() => { if (meta) writeHash({ tab, mode, hazard, year, cell: selected }); }, [meta, tab, mode, hazard, year, selected]);
  useEffect(() => {
    const onHash = () => {
      const h = readHash();
      if (h.tab) setTab(h.tab);
      if (h.mode) setMode(h.mode);
      if (h.hazard) setHazard(h.hazard);
      if (h.year) setYear(h.year);
      setSelected(h.cell ?? null);
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  useEffect(() => {
    if (!selected || !cells) return;
    const c = cells.find((x) => x.id === selected);
    if (c) setFocus((f) => (f && Math.abs(f.lon - c.lon) < 1e-6 && Math.abs(f.lat - c.lat) < 1e-6 ? f : { lon: c.lon, lat: c.lat, key: Date.now() }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected, cells]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setSelected(null); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const byId = useMemo(() => new Map((cells ?? []).map((c) => [c.id, c])), [cells]);
  const stats = useMemo(() => {
    if (!cells) return null;
    const measured = cells.filter((c) => c.rate !== null && c.act !== "insufficient_data");
    const direct = measured.filter((c) => !c.src.includes("estimated"));
    const sorted = direct.map((c) => c.rate as number).sort((a, b) => a - b);
    return { total: cells.length, measured: measured.length, direct: direct.length, fast: measured.filter((c) => (c.rate ?? 0) <= -10).length, sorted };
  }, [cells]);

  const pick = useCallback((id: string) => { const c = byId.get(id); if (!c) return; setSelected(id); setFocus({ lon: c.lon, lat: c.lat, key: Date.now() }); }, [byId]);
  const pickPoint = useCallback((lon: number, lat: number, label: string) => {
    let id = cellIdAt(lon, lat);
    if (!byId.has(id) && cells) {
      let best: Cell | null = null, d = Infinity;
      for (const c of cells) { const dd = (c.lon - lon) ** 2 + (c.lat - lat) ** 2; if (dd < d) { d = dd; best = c; } }
      if (!best || d > 0.0004) { setFound(`${label} is outside the Houston study area.`); return; }
      id = best.id;
    }
    setFound(label); setSelected(id); setFocus({ lon, lat, key: Date.now() });
  }, [byId, cells]);

  if (error) return <div className="loading">{error}</div>;
  if (!cells || !meta || !sites || !stats) return <div className="loading"><span className="spinner" aria-hidden="true" />Loading Houston's ground record…</div>;

  const cell = selected ? byId.get(selected) ?? null : null;
  const fc = meta.forecast;
  const lastYear = fc ? fc.years[fc.years.length - 1] : 2031;
  const question = mode === "hazards" ? HAZARDS.find((h) => h.key === hazard)!.question : MODES.find((m) => m.key === mode)!.question;
  const showYear = (mode === "future" || (mode === "hazards" && hazard === "flood")) && fc;
  const goMode = (m: Mode, h?: Hazard) => { setMode(m); if (h) setHazard(h); setSheet(false); };
  const shareUrl = () => writeHash({ tab, mode, hazard, year, cell: selected });
  const test5 = fc?.benchmark.table.find((t) => t.method === fc.method)?.by_horizon_cm[String(Math.round(fc.tested_horizon_years))];
  const ht = meta.hazards?.tests;

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

      <main className={`stage${tab === "map" ? "" : " hidden"}${cell ? " has-card" : ""}`}>
        {mapSeen && <MapView cells={cells} sites={sites} sensors={meta.sensors} nodes={meta.nodes} mode={(mode === "hazards" ? hazard : mode) as ColorBy} meta={meta} year={year} layers={layers} selected={selected} focus={focus} onSelect={(id) => { setSelected(id); setFound(null); }} />}

        <div className="controls">
          <div className="box">
            <Search onPick={pickPoint} />
            {found && <p className="found">{found}</p>}
            <div className="seg modes" role="radiogroup" aria-label="Color the map by">
              {MODES.map((m) => <button key={m.key} role="radio" aria-checked={mode === m.key} className={mode === m.key ? "on" : ""} onClick={() => goMode(m.key)}>{m.name}</button>)}
            </div>
            {mode === "hazards" && (
              <div className="seg sub" role="radiogroup" aria-label="Hazard">
                {HAZARDS.map((h) => <button key={h.key} role="radio" aria-checked={hazard === h.key} className={hazard === h.key ? "on" : ""} onClick={() => setHazard(h.key)}>{h.name}</button>)}
              </div>
            )}
            <div className="q-row">
              <p className="question">{question}</p>
              {showYear && (
                <label className="year-select"><span className="sr-only">Year</span>
                  <select value={year} onChange={(e) => setYear(Number(e.target.value))} aria-label="Year">
                    {fc!.years.map((y) => <option key={y} value={y}>{y}</option>)}
                  </select>
                </label>
              )}
            </div>
            <Legend mode={mode} hazard={hazard} year={year} meta={meta} cells={cells} />
          </div>
          <details className="box layers">
            <summary>Show on map</summary>
            {LAYER_NAMES.map(([k, name]) => (
              <label key={k}><input type="checkbox" checked={layers[k]} onChange={() => setLayers((l) => ({ ...l, [k]: !l[k] }))} />{name}</label>
            ))}
          </details>
        </div>

        <section className={`panel${cell ? " open" : ""}${sheet ? " expanded" : ""}`} aria-live="polite">
          {cell ? <Card key={cell.id} cell={cell} meta={meta} sensor={meta.sensors.find((s) => s.id === cell.id)} year={year} ranks={stats.sorted} onShare={shareUrl} onClose={() => setSelected(null)} /> : (
            <div className="summary">
              <button className="sheet-handle" onClick={() => setSheet((s) => !s)} aria-expanded={sheet}><span>Houston at a glance</span><i aria-hidden="true">{sheet ? "▾" : "▴"}</i></button>
              <h2>Houston at a glance</h2>
              <p className="intro">Pumping groundwater squeezes Houston's clay and the land sinks. Some areas dropped over 9 feet in four decades, and sinking ground floods deeper. TerraGauge maps it from NASA satellites, square kilometer by square kilometer.</p>
              <div className="tiles">
                <button className={`tile${mode === "movement" ? " on" : ""}`} onClick={() => goMode("movement")}>
                  <strong>{stats.fast.toLocaleString()}</strong><span>squares sinking 10+ mm a year</span><small>Movement</small>
                </button>
                <button className={`tile${mode === "confidence" ? " on" : ""}`} onClick={() => goMode("confidence")}>
                  <strong>±{num(meta.validation.typical_diff_mm_year)}<em>mm/yr</em></strong><span>typical gap from {meta.validation.stations} GPS stations</span><small>Confidence</small>
                </button>
                <button className={`tile${mode === "future" ? " on" : ""}`} onClick={() => goMode("future")}>
                  <strong>±{num(test5 ?? null)}<em>cm</em></strong><span>typical error forecasting 5 years ahead, tested</span><small>Future</small>
                </button>
                <button className={`tile${mode === "priority" ? " on" : ""}`} onClick={() => goMode("priority")}>
                  <strong>{(meta.counts.action.add_monitoring ?? 0).toLocaleString()}</strong><span>flood-zone squares sinking with no GPS nearby</span><small>Priority</small>
                </button>
                <button className={`tile wide${mode === "hazards" ? " on" : ""}`} onClick={() => goMode("hazards", "flood")}>
                  <strong>{ht ? `${num(ht.drought.flagged_median_drop_mm / ht.drought.others_median_drop_mm, 0)}×` : "—"}</strong><span>more drop in the 2023 drought where we predicted it from 2018. Flood, drought and ground-bending views.</span><small>Hazards</small>
                </button>
              </div>
              <p className="fine">{stats.total.toLocaleString()} squares of 1 km: {stats.direct.toLocaleString()} measured, {(stats.measured - stats.direct).toLocaleString()} estimated from neighbors. Click any square, or search an address, for its full story. Forecast to {lastYear}.</p>

              <details className="list-block" open>
                <summary>Suggested permanent GPS stations <span>{meta.sensors.length}</span></summary>
                <ol className="sensor-list">
                  {meta.sensors.map((s) => (
                    <li key={s.id}><button onClick={() => pick(s.id)}>
                      <span className="rank">{s.rank}</span>
                      <span><b>Area sinking {num(Math.abs(s.areaRate))} mm a year</b><small>{num(s.gpsKm)} km from the nearest GPS, flood zone {s.zone}</small></span>
                    </button></li>
                  ))}
                </ol>
                <p className="fine">{meta.nodes.length} low-cost node sites (diamonds) are listed on the <button className="link" onClick={() => setTab("hardware")}>Hardware page</button>.</p>
              </details>
            </div>
          )}
        </section>
      </main>
      {tab === "how" && <HowWeKnow meta={meta} cells={cells} />}
      {tab === "hardware" && <HardwarePage meta={meta} onShow={(id) => { setTab("map"); setMode("priority"); setLayers((l) => ({ ...l, sensors: true, nodes: true })); pick(id); }} />}
      {meta.status !== "reviewed" && <footer className="foot">Draft for NASA Space Apps 2026 (Dancing with the SARs). Not a flood forecast or a property assessment.</footer>}
    </div>
  );
}
