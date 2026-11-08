import { useEffect, useMemo, useState } from "react";
import type { Cell, LabelCode, LedgerEntry, Meta, Sites, ViewKey } from "./types";
import { MapView, type ColorMode, type Layers } from "./MapView";
import { EvidenceCard } from "./EvidenceCard";
import { GroundTruth, Ledger, Methods, SignalCheck } from "./Panels";
import { LABELS, VIEWS, fmt, motionColor } from "./labels";

type Tab = "map" | "signal" | "node" | "methods" | "ledger";
const TABS: { key: Tab; name: string }[] = [
  { key: "map", name: "Map" },
  { key: "signal", name: "Signal check" },
  { key: "node", name: "GroundTruth Node" },
  { key: "methods", name: "Methods and limits" },
  { key: "ledger", name: "Data ledger" },
];
const COUNT_KEY: Record<LabelCode, string> = { I: "investigate_satellite_signal", A: "add_ground_monitoring", C: "context_only", R: "review_time_matched_mismatch", X: "insufficient_radar_evidence" };
const VIEW_META = { o: "opera", p: "pair", c: "chain" } as const;

async function getJSON<T>(name: string): Promise<T> {
  const res = await fetch(`./data/${name}`);
  if (!res.ok) throw new Error(`Could not load ${name} (${res.status}). Run scripts/export_web.py, then reload.`);
  return res.json();
}

export default function App() {
  const [cells, setCells] = useState<Cell[] | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [sites, setSites] = useState<Sites | null>(null);
  const [ledger, setLedger] = useState<LedgerEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("map");
  const [view, setView] = useState<ViewKey>("o");
  const [mode, setMode] = useState<ColorMode>("label");
  const [layers, setLayers] = useState<Layers>({ flood: false, gps: true, ext: true, wells: false });
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getJSON<Cell[]>("cells.json"), getJSON<Meta>("meta.json"), getJSON<Sites>("sites.json"), getJSON<LedgerEntry[]>("ledger.json")])
      .then(([c, m, s, l]) => { setCells(c); setMeta(m); setSites(s); setLedger(l); })
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => { if (tab === "map") window.dispatchEvent(new Event("resize")); }, [tab]);
  const byId = useMemo(() => new Map((cells ?? []).map((c) => [c.id, c])), [cells]);
  const cell = selected ? byId.get(selected) ?? null : null;

  if (error) return <div className="loading"><p>{error}</p></div>;
  if (!cells || !meta || !sites) return <div className="loading"><p>Loading Houston evidence cells…</p></div>;

  const counts = meta.views[VIEW_META[view]].counts;
  const toggle = (k: keyof Layers) => setLayers((l) => ({ ...l, [k]: !l[k] }));

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <svg width="26" height="26" viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="13" fill="#B8862B" /><circle cx="16" cy="16" r="9" fill="none" stroke="#1D2B2A" strokeWidth="1.5" /><path d="M7 16h18M16 7v18" stroke="#1D2B2A" strokeWidth="2.5" /></svg>
          <div><h1>TerraGauge</h1><p>Houston ground-motion triage</p></div>
        </div>
        <nav aria-label="Sections">
          {TABS.map((t) => <button key={t.key} className={tab === t.key ? "tab on" : "tab"} aria-current={tab === t.key ? "page" : undefined} onClick={() => setTab(t.key)}>{t.name}</button>)}
        </nav>
      </header>
      {meta.status !== "reviewed" && <div className="banner" role="status">Provisional build: reference stations and processing choices are not yet team-reviewed. Labels are monitoring priorities, not findings.</div>}

      <main className={tab === "map" ? "stage" : "stage hidden"} aria-hidden={tab !== "map"}>
        <MapView cells={cells} sites={sites} view={view} mode={mode} layers={layers} selected={selected} onSelect={setSelected} />
        <div className="controls">
          <fieldset className="seg">
            <legend>Motion evidence</legend>
            {(Object.keys(VIEWS) as ViewKey[]).map((k) => (
              <label key={k} className={view === k ? "on" : ""}><input type="radio" name="view" checked={view === k} onChange={() => setView(k)} />{VIEWS[k].short}</label>
            ))}
          </fieldset>
          <fieldset className="seg small">
            <legend>Color by</legend>
            <label className={mode === "label" ? "on" : ""}><input type="radio" name="mode" checked={mode === "label"} onChange={() => setMode("label")} />Priority</label>
            <label className={mode === "value" ? "on" : ""}><input type="radio" name="mode" checked={mode === "value"} onChange={() => setMode("value")} />Motion</label>
          </fieldset>
          <fieldset className="checks">
            <legend>Show</legend>
            <label><input type="checkbox" checked={layers.gps} onChange={() => toggle("gps")} />GPS stations</label>
            <label><input type="checkbox" checked={layers.ext} onChange={() => toggle("ext")} />Extensometers</label>
            <label><input type="checkbox" checked={layers.wells} onChange={() => toggle("wells")} />Groundwater wells</label>
            <label><input type="checkbox" checked={layers.flood} onChange={() => toggle("flood")} />FEMA flood zones</label>
          </fieldset>
        </div>

        <aside className="legend" aria-label="Legend">
          <p className="legend-title">{VIEWS[view].long}</p>
          {mode === "label" ? (
            <ul>{(["I", "A", "C", "X"] as LabelCode[]).map((c) => <li key={c}><span className={`swatch badge-${c}`} />{LABELS[c].name}<b>{(counts[COUNT_KEY[c]] ?? 0).toLocaleString()}</b></li>)}</ul>
          ) : (
            <div className="ramp">
              <div className="ramp-bar" style={{ background: `linear-gradient(90deg, ${[-1, -0.5, 0, 0.5, 1].map((t) => motionColor(t * (view === "o" ? 18 : 40), view === "o" ? 18 : 40)).join(",")})` }} />
              <div className="ramp-keys"><span>{view === "o" ? "−18 mm/yr" : "−40 mm"} away (sinking)</span><span>toward</span></div>
            </div>
          )}
          <ul className="site-keys">
            <li><span className="dot gps-ref" />Reference GPS station</li>
            <li><span className="dot gps" />GPS station</li>
            <li><span className="dot ext" />Extensometer</li>
          </ul>
          {view !== "o" && <p className="legend-warn">NISAR noise is about {fmt(meta.signal_check.pair.nisar_sd_mm, 0)} mm here; most labels in this view are noise. See Signal check.</p>}
        </aside>

        <section className={cell ? "panel open" : "panel"} aria-live="polite">
          {cell ? <EvidenceCard cell={cell} view={view} meta={meta} onClose={() => setSelected(null)} /> : (
            <div className="intro">
              <h2>Where should Houston look first?</h2>
              <p>Each square is about 1 km. TerraGauge checks whether the radar there is trustworthy, compares it with nearby GPS, wells, compaction records, and flood zones, and then sorts it into one of four priorities.</p>
              <p className="big-stat"><strong>{(meta.views.opera.counts.add_ground_monitoring ?? 0).toLocaleString()}</strong> cells show significant 2016–2021 motion with no permanent GPS station within 2 km.</p>
              <p className="big-stat"><strong>{meta.gps_validation.pearson_r.toFixed(2)}</strong> correlation between the OPERA record and {meta.gps_validation.station_count} independent GPS stations.</p>
              <p className="hint">Click any colored square to open its evidence card.</p>
            </div>
          )}
        </section>
      </main>

      {tab === "signal" && <SignalCheck meta={meta} />}
      {tab === "node" && <GroundTruth />}
      {tab === "methods" && <Methods meta={meta} />}
      {tab === "ledger" && <Ledger ledger={ledger} meta={meta} />}
      <footer className="foot">NASA Space Apps Challenge 2026, Dancing with the SARs. Data: NASA/ISRO NISAR, NASA JPL OPERA, HoustonNet, USGS, FEMA. Not a flood forecast, property assessment, or diagnosis of cause.</footer>
    </div>
  );
}
