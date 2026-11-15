import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Cell, ColorBy, Hazard, Meta, Mode, Sites } from "./types";
import { MapView, type Layers } from "./MapView";
import { Card } from "./Card";
import { HardwarePage, HowWeKnow } from "./Pages";
import { Search } from "./Search";
import { Tour, tourSteps } from "./Tour";
import { usePlaceName } from "./places";
import { cellIdAt } from "./geo";
import { readHash, writeHash, type Tab } from "./url";
import { Landing, type Story } from "./Landing";
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
      if (hazard === "flood") { const f = floodExtra(c, meta); if (f.cls) add(f.cls === "1pct" && (f.total ?? 0) >= 3 ? "deeper" : f.cls === "levee" ? "0.2pct" : f.cls); }
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
        <div className="ramp-keys"><span>Sinking {span}+ {unit}</span><span>No clear motion</span><span>Rising</span></div>
        <KeyList items={[noData]} note={mode === "future"
          ? <>Each square's 2016–2026 trend, allowing for seasons and averaged with its neighborhood, carried forward. It tied for most accurate of {meta.forecast?.benchmark.table.length ?? 9} methods we tested on past years, including machine learning. Lighter squares are estimated from their neighbors.</>
          : <>Measured by NASA satellite radar, 2016–2026, and combined with GPS where a station sits inside the square. Lighter squares are estimated from their neighbors.</>} />
      </div>
    );
  }
  if (mode === "hazards") {
    const table: Record<string, { name: string; color: string; meaning: string }> = hazard === "flood" ? FLOOD : hazard === "drought" ? DROUGHT : BEND;
    const keys = hazard === "flood" ? ["deeper", "1pct", "0.2pct", "minimal"] : ["high", "medium", "low"];
    const t = meta.hazards?.tests;
    const note = hazard === "flood"
      ? <>FEMA's flood zones give the odds of a big flood. The satellite measured how much the ground has dropped since 2016, and the same flood now stands that much deeper. This is measured, not forecast.{meta.hazards?.harvey?.by_class["1pct"] && meta.hazards.harvey.by_class.minimal ? <> Checked against Hurricane Harvey: in northeast Houston, {num(meta.hazards.harvey.by_class["1pct"].mean_flooded_share_pct, 0)}% of high-risk squares' area flooded, versus {num(meta.hazards.harvey.by_class.minimal.mean_flooded_share_pct, 0)}% of low-risk squares'.</> : null}</>
      : hazard === "drought" && t ? <>Tested: using only data from before 2023, the squares flagged from the 2018 drought typically dropped {num(t.drought.flagged_median_drop_mm, 0)} mm in the 2023 drought, against {num(t.drought.others_median_drop_mm, 0)} mm for the rest.</>
      : t ? <>Tested: the sharpest-bending squares in 2016–2021 were still bending about {num(t.bending.hotspot_later_median / t.bending.others_later_median, 0)}× more than the rest in 2021–2026.</> : undefined;
    const items: Key[] = keys.map((k) => ({ key: k, ...table[k], n: counts.get(k) ?? 0 }));
    if (hazard !== "flood") items.push({ key: "indirect", name: "No direct record", color: NOT_DIRECT, meaning: "Estimated or unmeasured squares: drought and bending need a square's own satellite record.", n: cells.length - items.reduce((t, i) => t + i.n, 0) });
    return <KeyList items={items} note={note} />;
  }
  const items: Key[] = mode === "priority"
    ? (["investigate_first", "add_monitoring", "review_disagreement", "observe", "no_clear_motion"] as const).map((k) => ({ key: k, ...ACTION[k], n: meta.counts.action[k] ?? 0 }))
    : (["high", "medium", "low"] as const).map((k) => ({ key: k, ...CONFIDENCE[k], n: meta.counts.confidence[k] ?? 0 }));
  return <KeyList items={[...items, noData]} note={mode === "priority" ? <>Rules are checked in this order, and the first that fits decides. Numbered pins are suggested permanent GPS stations, orange diamonds are suggested low-cost sensors, and white diamonds are sensors for land nothing measures yet. Every "Add monitoring here" square has a suggested sensor within 6 km.</> : undefined} />;
}

function detailTile(id: string): string | null {
  const m = /(-?\d+)-(-?\d+)$/.exec(id);
  return m ? `${Math.floor(Number(m[1]) / 16)}_${Math.floor(Number(m[2]) / 16)}` : null;
}

function AtRisk({ c, rank, onPick }: { c: Cell; rank: number; onPick: (id: string) => void }) {
  const name = usePlaceName(c.id, c.lon, c.lat);
  const by = c.future ? Object.values(c.future.by) : [];
  const last = by.length ? by[by.length - 1].c : null;
  return (
    <li><button onClick={() => onPick(c.id)}>
      <span className="rank">{rank}</span>
      <span><b>{name ?? `${c.lat.toFixed(3)}°N, ${Math.abs(c.lon).toFixed(3)}°W`}</b><small>Sinking {num(Math.abs(c.rate ?? 0))} mm a year in a high-risk flood zone, {num(last)} cm more by {c.future ? Object.keys(c.future.by).slice(-1)[0] : ""}</small></span>
    </button></li>
  );
}

const LAYER_NAMES: [keyof Layers, string][] = [["sensors", "Suggested GPS stations (numbered)"], ["nodes", "Suggested low-cost sensors (diamonds)"], ["gaps", "Sensors where nothing measures yet (white diamonds)"], ["gps", "Existing GPS stations"], ["ext", "Soil compaction gauges"], ["wells", "Groundwater wells"], ["flood", "FEMA high-risk flood zone outlines"]];

const COPYRIGHT = "© 2026 TerraGauge by Aaron Qin, Miheer Parasnis, and Reyansh Maheshwari · Built for the NASA Space Apps Challenge";

/** The story intro shows on a fresh visit; any #map / #how / #hardware link goes straight to the app. */
const startsInApp = () => /^#(map|how|hardware)/.test(window.location.hash);

export default function App() {
  const initial = useMemo(readHash, []);
  const [landing, setLanding] = useState(() => !startsInApp());
  const [dashMounted, setDashMounted] = useState(() => startsInApp());
  const firstVisit = useRef(!startsInApp());
  const appRef = useRef<HTMLDivElement>(null);
  const [cells, setCells] = useState<Cell[] | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [sites, setSites] = useState<Sites | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>(initial.tab ?? "map");
  const [mode, setMode] = useState<Mode>(initial.mode ?? "movement");
  const [hazard, setHazard] = useState<Hazard>(initial.hazard ?? "flood");
  const [year, setYear] = useState<number>(initial.year ?? 0);
  const [layers, setLayers] = useState<Layers>({ sensors: true, nodes: true, gaps: true, gps: false, ext: false, wells: false, flood: false });
  const [selected, setSelected] = useState<string | null>(initial.cell ?? null);
  const [focus, setFocus] = useState<{ lon: number; lat: number; key: number } | null>(null);
  const [sheet, setSheet] = useState(false);
  const [found, setFound] = useState<string | null>(null);
  const [mapSeen, setMapSeen] = useState(tab === "map");
  const [details, setDetails] = useState<Map<string, Cell>>(new Map());
  const [frame, setFrame] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const [tourAt, setTourAt] = useState<number | null>(null);
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
  useEffect(() => { if (meta && !landing) writeHash({ tab, mode, hazard, year, cell: selected }); }, [meta, tab, mode, hazard, year, selected, landing]);
  useEffect(() => { if ("scrollRestoration" in window.history) window.history.scrollRestoration = "manual"; }, []);
  useEffect(() => { appRef.current?.toggleAttribute("inert", landing); }, [landing, dashMounted, cells]);
  const warm = useCallback(() => setDashMounted(true), []);
  const enter = useCallback(() => {
    setDashMounted(true);
    setLanding(false);
    firstVisit.current = false;
    setTab("map");
    window.scrollTo(0, 0);
    requestAnimationFrame(() => window.dispatchEvent(new Event("resize")));
  }, []);
  const backToStart = () => {
    setLanding(true);
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
    window.scrollTo(0, 0);
  };
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

  // Full record for the opened square, from its details tile.
  useEffect(() => {
    if (!selected || details.has(selected)) return;
    const tile = detailTile(selected);
    if (!tile) return;
    let live = true;
    getJSON<Record<string, Cell>>(`details/${tile}.json`).then((rows) => {
      if (!live) return;
      setDetails((d) => { const n = new Map(d); for (const [k, v] of Object.entries(rows)) n.set(k, { ...v, detailed: true }); return n; });
    }).catch(() => undefined);
    return () => { live = false; };
  }, [selected, details]);

  // Time-lapse playback.
  const frames = meta?.timelapse?.dates.length ?? 0;
  useEffect(() => {
    if (!playing || frame === null) return;
    if (frame >= frames - 1) { setPlaying(false); return; }
    const t = setTimeout(() => setFrame((f) => (f === null ? null : f + 1)), 380);
    return () => clearTimeout(t);
  }, [playing, frame, frames]);
  useEffect(() => { if (mode !== "movement") { setFrame(null); setPlaying(false); } }, [mode]);

  const byId = useMemo(() => new Map((cells ?? []).map((c) => [c.id, c])), [cells]);
  const stats = useMemo(() => {
    if (!cells) return null;
    const measured = cells.filter((c) => c.rate !== null && c.act !== "insufficient_data");
    const direct = measured.filter((c) => !c.src.includes("estimated"));
    const sorted = direct.map((c) => c.rate as number).sort((a, b) => a - b);
    // Most at-risk: directly measured, high-risk flood zone, fastest forecast sinking, 5 km apart.
    const risky = direct.filter((c) => c.flood.sfha && c.future && c.sig && c.act !== "review_disagreement").sort((a, b) => (a.future!.rate - b.future!.rate));
    const top: Cell[] = [];
    for (const c of risky) {
      if (top.every((t) => Math.hypot((t.lon - c.lon) * 96.5, (t.lat - c.lat) * 111) >= 5)) top.push(c);
      if (top.length >= 10) break;
    }
    const harvey = direct.filter((c) => c.harvey && c.harvey.wet >= 0.5 && c.flood.sfha && (c.rate ?? 0) < -5).sort((a, b) => (a.rate ?? 0) - (b.rate ?? 0))[0];
    return { total: cells.length, measured: measured.length, direct: direct.length, fast: measured.filter((c) => (c.rate ?? 0) <= -10).length, sorted, top, harveyPick: harvey?.id };
  }, [cells]);

  const story = useMemo<Story | null>(() => {
    if (!cells || !meta?.timelapse) return null;
    const dates = meta.timelapse.dates;
    const median = (xs: number[]) => { const a = [...xs].sort((p, q) => p - q); const m = a.length >> 1; return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2; };
    const measured = cells.filter((c) => c.rate !== null && c.act !== "insufficient_data");
    const direct = measured.filter((c) => !c.src.includes("estimated"));
    const withTl = direct.filter((c) => c.tl && c.tl.length === dates.length).sort((a, b) => (a.rate ?? 0) - (b.rate ?? 0));
    const tenth = withTl.slice(0, Math.max(1, Math.round(withTl.length / 10)));
    const curve = (group: Cell[]) => dates.map((_, i) => Math.round(median(group.map((c) => c.tl![i])) / 10 * 10) / 10);
    const r = (c: Cell) => c.rate as number;
    const bins = [
      { label: "Rising\n2+", mid: 3, n: measured.filter((c) => r(c) >= 2).length },
      { label: "Steady\n±2", mid: 0, n: measured.filter((c) => r(c) > -2 && r(c) < 2).length },
      { label: "Sinking\n2–5", mid: -3.5, n: measured.filter((c) => r(c) <= -2 && r(c) > -5).length },
      { label: "Sinking\n5–10", mid: -7.5, n: measured.filter((c) => r(c) <= -5 && r(c) > -10).length },
      { label: "Sinking\n10–20", mid: -15, n: measured.filter((c) => r(c) <= -10 && r(c) > -20).length },
      { label: "Sinking\n20+", mid: -25, n: measured.filter((c) => r(c) <= -20).length },
    ];
    const fast = measured.filter((c) => r(c) <= -10);
    return { measured: measured.length, direct: direct.length, fast: fast.length, fastInFlood: fast.filter((c) => c.flood.sfha).length, fastest: Math.min(...direct.map(r)), dates, fastCurve: curve(tenth), typicalCurve: curve(withTl), bins };
  }, [cells, meta]);

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

  const enterAt = (lon: number, lat: number) => {
    enter();
    if (!cells) return;
    let id = cellIdAt(lon, lat);
    if (!byId.has(id)) { let best: Cell | null = null, d = Infinity; for (const c of cells) { const dd = (c.lon - lon) ** 2 + (c.lat - lat) ** 2; if (dd < d) { d = dd; best = c; } } if (best) id = best.id; }
    setMode("movement"); setSelected(id); setFocus({ lon, lat, key: Date.now() });
  };
  const landingView = landing && <Landing meta={meta} sites={sites} story={story} playIntro={firstVisit.current} onWarm={warm} onEnter={enter} onEnterAt={enterAt} />;
  if (!dashMounted && landing) return <>{landingView}</>;
  if (error) return <>{landingView}<div className={landing ? "app under loading" : "loading"}>{error}</div></>;
  if (!cells || !meta || !sites || !stats) return <>{landingView}<div className={landing ? "app under loading" : "loading"}><span className="spinner" aria-hidden="true" />Loading Houston's ground record…</div></>;

  const slimCell = selected ? byId.get(selected) ?? null : null;
  const cell = selected ? details.get(selected) ?? null : null;
  const steps = tourSteps(meta, stats, { fastest: meta.sensors[0]?.id, harvey: stats.harveyPick });
  const goTour = (i: number) => {
    if (i < 0 || i >= steps.length) return;
    const s = steps[i];
    setTourAt(i); setTab("map"); setMode(s.mode); if (s.hazard) setHazard(s.hazard);
    if (s.cell) pick(s.cell); else setSelected(null);
    if (s.history) { setFrame(0); setPlaying(true); } else { setFrame(null); setPlaying(false); }
  };
  const history = mode === "movement" && frame !== null;
  const dates = meta.timelapse?.dates ?? [];
  const fc = meta.forecast;
  const lastYear = fc ? fc.years[fc.years.length - 1] : 2031;
  const question = mode === "hazards" ? HAZARDS.find((h) => h.key === hazard)!.question : MODES.find((m) => m.key === mode)!.question;
  const showYear = mode === "future" && fc;
  const goMode = (m: Mode, h?: Hazard) => { setMode(m); if (h) setHazard(h); setSheet(false); };
  const shareUrl = () => writeHash({ tab, mode, hazard, year, cell: selected });
  const test5 = fc?.benchmark.table.find((t) => t.method === fc.method)?.by_horizon_cm[String(Math.round(fc.tested_horizon_years))];
  const ht = meta.hazards?.tests;

  return (
    <>
    {landingView}
    <div ref={appRef} className={landing ? "app under" : "app"}>
      <header className="top">
        <button className="brand" onClick={backToStart} title="Back to the start">
          <img src="./logo.png" alt="" width={34} height={34} />
          <div><h1>TerraGauge</h1><p>Houston's moving ground, measured from space</p></div>
        </button>
        <nav aria-label="Pages">
          <button className="tab tour-btn" onClick={() => goTour(0)}>Take the tour</button>
          {([["map", "Map"], ["how", "How we know"], ["hardware", "Hardware"]] as const).map(([k, name]) => (
            <button key={k} className={tab === k ? "tab on" : "tab"} aria-current={tab === k ? "page" : undefined} onClick={() => setTab(k)}>{name}</button>
          ))}
        </nav>
      </header>

      <main className={`stage${tab === "map" ? "" : " hidden"}${cell ? " has-card" : ""}`}>
        {mapSeen && <MapView cells={cells} sites={sites} sensors={meta.sensors} nodes={meta.nodes} gaps={meta.gaps} mode={(history ? "history" : mode === "hazards" ? hazard : mode) as ColorBy} meta={meta} year={history ? frame! : year} layers={layers} selected={selected} focus={focus} onSelect={(id) => { setSelected(id); setFound(null); }} />}

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
            <p className="question">{question}</p>
            {showYear && (
              <div className="seg years" role="radiogroup" aria-label="Forecast year" style={{ gridTemplateColumns: `repeat(${fc!.years.length}, 1fr)` }}>
                {fc!.years.map((y) => <button key={y} role="radio" aria-checked={year === y} className={year === y ? "on" : ""} onClick={() => setYear(y)}>{y}</button>)}
              </div>
            )}
            {history ? (
              <div className="timelapse">
                <div className="ramp" style={{ background: `linear-gradient(90deg, ${[-1, -0.66, -0.33, 0, 0.33].map((t) => movementColor(t * 20, 20)).join(",")})` }} />
                <div className="ramp-keys"><span>Sunk 20+ cm</span><span>No change</span><span>Rose</span></div>
                <div className="tl-row">
                  <button className="tl-play" onClick={() => { if (frame! >= frames - 1) setFrame(0); setPlaying((p) => !p); }} aria-label={playing ? "Pause" : "Play"}>{playing ? "Pause" : "Play"}</button>
                  <input type="range" min={0} max={frames - 1} value={frame!} onChange={(e) => { setPlaying(false); setFrame(Number(e.target.value)); }} aria-label="Date" />
                  <span className="tl-date">{new Date(dates[frame!]).toLocaleDateString("en-US", { month: "short", year: "numeric" })}</span>
                </div>
                <p className="legend-note">How far the ground has dropped or risen since July 2016, from NASA satellite radar. Squares with shaky records show their trend.</p>
                <button className="link small-link" onClick={() => { setFrame(null); setPlaying(false); }}>Back to the yearly rate</button>
              </div>
            ) : (
              <>
                <Legend mode={mode} hazard={hazard} year={year} meta={meta} cells={cells} />
                {mode === "movement" && frames > 0 && <button className="watch" onClick={() => { setFrame(0); setPlaying(true); }}>Watch 2016–2026</button>}
              </>
            )}
          </div>
          <details className="box layers">
            <summary>Show on map</summary>
            {LAYER_NAMES.map(([k, name]) => (
              <label key={k}><input type="checkbox" checked={layers[k]} onChange={() => setLayers((l) => ({ ...l, [k]: !l[k] }))} />{name}</label>
            ))}
          </details>
        </div>

        <section className={`panel${cell ? " open" : ""}${sheet ? " expanded" : ""}`} aria-live="polite">
          {selected && !cell ? (
            <div className="card loading-card"><span className="spinner" aria-hidden="true" />Loading this square{slimCell ? "" : "…"}</div>
          ) : cell ? <Card key={cell.id} cell={cell} meta={meta} sensor={meta.sensors.find((s) => s.id === cell.id)} year={year} ranks={stats.sorted} onShare={shareUrl} onClose={() => setSelected(null)} /> : (
            <div className="summary">
              <button className="sheet-handle" onClick={() => setSheet((s) => !s)} aria-expanded={sheet}><span>Houston at a glance</span><i aria-hidden="true">{sheet ? "▾" : "▴"}</i></button>
              <h2>Houston at a glance</h2>
              <p className="lead-in">Pumping groundwater squeezes Houston's clay and the land sinks, and sinking ground floods deeper. TerraGauge maps it one square kilometer at a time from NASA satellite radar and the new NISAR mission, checked against GPS on the ground.</p>
              <div className="tiles">
                <div className="tile"><small>Movement</small><strong>{stats.fast.toLocaleString()}</strong><span>squares sinking 1 cm or more a year</span></div>
                <div className="tile"><small>Confidence</small><strong>{num(meta.validation.typical_diff_mm_year)}<em> mm a year</em></strong><span>typical gap from {meta.validation.stations} GPS stations</span></div>
                <div className="tile"><small>Future</small><strong>±{num(test5 ?? null)}<em> cm</em></strong><span>typical miss five years ahead, tested on past years</span></div>
                <div className="tile"><small>Priority</small><strong>{(meta.counts.action.add_monitoring ?? 0).toLocaleString()}</strong><span>flood-zone squares sinking with no GPS nearby</span></div>
                <div className="tile wide"><small>Hazards</small><strong>{ht ? `${num(ht.drought.flagged_median_drop_mm / ht.drought.others_median_drop_mm, 0)}×` : "—"}</strong><span>more ground drop in the 2023 drought where we flagged it from 2018 alone</span></div>
              </div>
              <p className="fine">{stats.total.toLocaleString()} squares: {stats.direct.toLocaleString()} measured directly and {(stats.measured - stats.direct).toLocaleString()} estimated from their neighbors. Click any square, or search an address, for its full story.</p>

              {stats.top.length > 0 && (
                <details className="list-block" open>
                  <summary>Most at-risk areas <span>{stats.top.length}</span></summary>
                  <p className="fine">The fastest sinking inside FEMA high-risk flood zones, measured directly and at least 5 km apart, with the forecast to {lastYear}.</p>
                  <ol className="sensor-list">{stats.top.map((c, i) => <AtRisk key={c.id} c={c} rank={i + 1} onPick={pick} />)}</ol>
                </details>
              )}
              <details className="list-block">
                <summary>Suggested permanent GPS stations <span>{meta.sensors.length}</span></summary>
                <ol className="sensor-list">
                  {meta.sensors.map((s) => (
                    <li key={s.id}><button onClick={() => pick(s.id)}>
                      <span className="rank">{s.rank}</span>
                      <span><b>Area sinking {num(Math.abs(s.areaRate))} mm a year</b><small>{num(s.gpsKm)} km from the nearest GPS, in a high-risk flood zone</small></span>
                    </button></li>
                  ))}
                </ol>
              </details>
              <p className="sheet-credit">{COPYRIGHT}</p>
            </div>
          )}
        </section>
      </main>
      {tab === "how" && <HowWeKnow meta={meta} cells={cells} onShow={(id) => { setTab("map"); setMode("priority"); pick(id); }} />}
      {tab === "hardware" && <HardwarePage meta={meta} cells={cells} onShow={(id) => { setTab("map"); setMode("priority"); setLayers((l) => ({ ...l, sensors: true, nodes: true, gaps: true })); pick(id); }} />}
      {tourAt !== null && tab === "map" && <Tour steps={steps} index={tourAt} onGo={goTour} onClose={() => { setTourAt(null); setPlaying(false); }} />}
      <footer className={tab === "map" ? "foot on-map" : "foot"}>{COPYRIGHT}</footer>
    </div>
    </>
  );
}
