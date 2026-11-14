import { useMemo, useState } from "react";
import type { Meta } from "./types";
import { CONFIDENCE, PRIORITY, num } from "./labels";

function Scatter({ meta }: { meta: Meta }) {
  const pts = meta.validation.points;
  const w = 320, h = 250, pad = 36;
  const vals = pts.flatMap((p) => [p.gps, p.sat]);
  const lo = Math.min(-30, ...vals), hi = Math.max(6, ...vals);
  const sx = (v: number) => pad + ((v - lo) / (hi - lo)) * (w - pad - 10);
  const sy = (v: number) => h - pad - ((v - lo) / (hi - lo)) * (h - pad - 10);
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="scatter" role="img" aria-label={`Satellite versus GPS at ${pts.length} stations, correlation ${meta.validation.r.toFixed(2)}`}>
      <line x1={sx(lo)} y1={sy(lo)} x2={sx(hi)} y2={sy(hi)} className="diag" />
      {[-30, -20, -10, 0].filter((t) => t >= lo).map((t) => <g key={t}><text x={sx(t)} y={h - 18} textAnchor="middle" className="tick">{t}</text><text x={pad - 6} y={sy(t) + 3} textAnchor="end" className="tick">{t}</text></g>)}
      {pts.map((p) => <circle key={p.id} cx={sx(p.gps)} cy={sy(p.sat)} r={3.2} className="pt"><title>{`${p.id}: GPS ${p.gps}, satellite ${p.sat} mm/yr`}</title></circle>)}
      <text x={(w + pad) / 2} y={h - 3} textAnchor="middle" className="axis">GPS station, mm a year</text>
      <text transform={`translate(11 ${(h - pad) / 2}) rotate(-90)`} textAnchor="middle" className="axis">Satellite, mm a year</text>
    </svg>
  );
}

function Gauge({ signal, noise, label }: { signal: number | null; noise: number | null; label: string }) {
  if (signal === null || noise === null) return <figure className="gauge"><figcaption>{label}</figcaption><p className="small">Not enough overlapping high-quality cells to estimate signal versus noise.</p></figure>;
  const pct = (v: number) => `${Math.max(0.8, (v / (noise * 1.05)) * 100)}%`;
  return (
    <figure className="gauge">
      <figcaption>{label}</figcaption>
      <div className="gauge-track" aria-hidden="true"><div className="gauge-noise" style={{ width: pct(noise) }} /><div className="gauge-signal" style={{ width: pct(signal) }} /></div>
      <div className="gauge-keys"><span><i className="k-signal" />Real ground movement in that time: {num(signal)} mm</span><span><i className="k-noise" />Measurement noise: {num(noise, 0)} mm</span></div>
    </figure>
  );
}

export function HowWeKnow({ meta }: { meta: Meta }) {
  const v = meta.validation, b = meta.forecast.backtest, n = meta.nisar;
  return (
    <div className="page">
      <h2 className="page-title">How we know</h2>
      <p className="lede">TerraGauge puts every dataset onto one map of 1 km squares, then answers four questions for each square. Here is how each answer is made, and how far to trust it.</p>

      <h3>One map, every dataset</h3>
      <table className="table">
        <thead><tr><th>Data</th><th>What it tells us</th><th>How we use it</th></tr></thead>
        <tbody>
          <tr><td>NASA OPERA satellite radar, {meta.record.start.slice(0, 4)}–{meta.record.end.slice(0, 4)}</td><td>How much each square moved, every few months</td><td>Main movement measurement</td></tr>
          <tr><td>HoustonNet GPS, 257 stations</td><td>Very precise movement at single points</td><td>Checks satellite trends and defines monitoring coverage; never blended into a different-time-window satellite trend</td></tr>
          <tr><td>NASA/ISRO NISAR, Nov 2025–Jan 2026</td><td>The newest radar satellite</td><td>Quality check; too new to measure slow sinking (see below)</td></tr>
          <tr><td>USGS groundwater wells</td><td>Whether water levels are dropping</td><td>Context in each square's evidence</td></tr>
          <tr><td>USGS extensometers</td><td>How much soil is squeezing underground</td><td>Context in each square's evidence</td></tr>
          <tr><td>FEMA flood zones</td><td>Official high-risk flood areas</td><td>Raises priority for sinking squares</td></tr>
          {Object.entries(meta.nasaLayers).map(([k, s]) => <tr key={k}><td>{s}</td><td>{k === "nasadem" ? "Ground elevation" : k === "dswx" ? "Standing water" : "Construction and clearing"}</td><td>{k === "dswx" ? "Removes water squares from rankings" : "Context in each square's evidence"}</td></tr>)}
        </tbody>
      </table>

      <h3>Does the satellite match the ground?</h3>
      <div className="split">
        <Scatter meta={meta} />
        <div>
          <p className="big"><strong>{v.r.toFixed(2)}</strong> correlation with {v.stations} GPS stations we did not use to calibrate the satellite.</p>
          <p>Typical difference: <strong>{num(v.typical_diff_mm_year)} mm a year</strong>. Points near the dashed line mean the satellite and the GPS station agree.</p>
          <p className="small">GPS stations cover longer time spans than the satellite record, so some difference is expected.</p>
        </div>
      </div>

      <h3>Can we predict where it will go?</h3>
      <p>We tested it. Using only {b.train[0].slice(0, 4)}–{b.train[1].slice(0, 4)} data, we predicted each square's rate for {b.test[0].slice(0, 4)}–{b.test[1].slice(0, 4)}, then checked against what actually happened.</p>
      <div className="facts">
        <div><strong>{num(b.fast_median_before_mm_year)} → {num(b.fast_median_after_mm_year)}</strong><span>mm a year: the fastest-sinking areas before and after {b.test[0].slice(0, 4)}. Sinking slowed down.</span></div>
        <div><strong>{b.correlation.toFixed(2)}</strong><span>correlation between earlier and later rates. Two years of satellite data per side is too short and noisy to predict reliably.</span></div>
      </div>
      <p><strong>We withhold future projections.</strong> Earlier rates did not predict later rates reliably enough, and the historical satellite reference region is still awaiting scientific review. A map that invents a precise future would be less useful than an honest monitoring-priority map.</p>
      {!meta.record.extendedThroughOpera2026 && <p className="note-block">With OPERA data through 2026 (11 more files, about 3.7 GB), we can test five years against the next five years, which is long enough for a real forecast. Run <code>scripts/fetch_opera_extension.py</code> and the site updates itself.</p>}

      <h3>Why doesn't NASA's newest satellite (NISAR) change the map yet?</h3>
      <p>NISAR started imaging Houston in late 2025. Houston sinks a few millimetres over a few weeks, and the atmosphere alone shifts a single radar reading by centimetres.</p>
      <Gauge signal={n.pair.signal_mm} noise={n.pair.noise_mm} label="One 12-day NISAR pair" />
      <Gauge signal={n.chain.signal_mm} noise={n.chain.noise_mm} label="Five pairs combined, 60 days" />
      <p>At one pass every 12 days, NISAR needs about {n.detect.find((d) => d.rate === 10)?.years ?? "—"} years of passes to detect 10 mm a year, and about {n.detect.find((d) => d.rate === 5)?.years ?? "—"} years for 5 mm a year (best case). Until then, TerraGauge uses it as a quality check.</p>

      <h3>How each answer is decided</h3>
      <h4>Movement</h4>
      <p>Each square's movement rate comes from the historical satellite record, converted from the satellite's slanted view to up and down. GPS remains a separate point-scale check and coverage signal, because most station records do not share the satellite's exact time window. Changes smaller than {num(meta.thresholds.stable_mm_year)} mm a year count as stable: that's twice the wobble we see at GPS stations that aren't moving.</p>
      <h4>Confidence</h4>
      <ul>{(["high", "medium", "low"] as const).map((k) => <li key={k}><b>{CONFIDENCE[k].name}:</b> {CONFIDENCE[k].meaning}</li>)}</ul>
      <h4>Priority</h4>
      <ul>{(["urgent", "high", "watch", "stable", "check", "no_data"] as const).map((k) => <li key={k}><b>{PRIORITY[k].name}:</b> {PRIORITY[k].meaning}</li>)}</ul>
      <h4>Suggested sensor sites</h4>
      <p>Squares that are sinking and have no GPS station within {meta.thresholds.gps_covered_km} km, ranked by how fast they sink, how sure we are, how far the nearest station is, and whether they're in a high-risk flood zone. Sites are kept at least 4 km apart so the list covers different areas.</p>

      <h3>Still provisional</h3>
      <p className="small">Satellite radar measures movement relative to a reference. We used {meta.reference.reference_stations.length} long-running GPS stations that barely move as that reference and held out {meta.reference.held_out_stable_stations.length} similar stations for checking. The team still needs to review this choice.</p>

      <h3>Sources</h3>
      <ul className="small">
        <li>NASA JPL OPERA DISP-S1 surface displacement, frame F38238, via the Alaska Satellite Facility.</li>
        <li>NASA/ISRO NISAR L2 GUNW, track 062 frame 016, five pairs, 2 Nov 2025 to 1 Jan 2026.</li>
        <li>HoustonNet GPS 2024 release, University of Houston and Harris-Galveston Subsidence District.</li>
        <li>USGS groundwater daily values and the 2023 Houston extensometer release.</li>
        <li>FEMA National Flood Hazard Layer. Basemap © OpenFreeMap, © OpenMapTiles, © OpenStreetMap contributors.</li>
      </ul>
    </div>
  );
}

const rateUncertainty = (sigma: number, days: number, n: number) => (sigma / (days / 365.25)) * Math.sqrt(12 / (n * (n * n - 1)));

export function SensorPage() {
  const [heights, setHeights] = useState("");
  const [rate, setRate] = useState(10);
  const [gap, setGap] = useState(7);
  const values = heights.split(/[\s,]+/).filter(Boolean).map(Number).filter(Number.isFinite);
  const sigma = useMemo(() => {
    if (values.length < 3) return null;
    const m = values.reduce((a, b) => a + b, 0) / values.length;
    return Math.sqrt(values.reduce((a, b) => a + (b - m) ** 2, 0) / (values.length - 1));
  }, [values.join(",")]);
  const needed = useMemo(() => {
    if (!sigma || rate <= 0 || gap <= 0) return null;
    for (let n = 3; n < 20000; n++) if (rateUncertainty(sigma, gap, n) <= rate / 2) return n;
    return null;
  }, [sigma, rate, gap]);
  return (
    <div className="page">
      <h2 className="page-title">Our $74 sensor</h2>
      <p className="lede">Professional GPS stations cost thousands of dollars. We're testing whether a $74 GPS board (Waveshare LC29H) could fill the gaps on the map.</p>
      <h3>The test</h3>
      <p>We bolt the antenna to a metal sheet in a backyard and never move it. Because it isn't moving, any change in its readings is pure measurement noise. Knowing the noise tells us how long a cheap sensor would need to spot real sinking.</p>
      <div className="status-box"><p><strong>Status: no recordings yet.</strong> Recording starts in the first hour of the hackathon. We'll report a result only if we get three good sessions compared against NOAA's NETP reference station.</p></div>
      <h3>Try it</h3>
      <p className="small">Enter the height from each recording session. The numbers below are just an example until real data comes in.</p>
      <label className="field">Heights from each session, in mm<input value={heights} onChange={(e) => setHeights(e.target.value)} placeholder="for example 11.2, 8.9, 10.4" inputMode="decimal" /></label>
      <div className="field-row">
        <label className="field">Sinking to detect, mm a year<input type="number" min={1} value={rate} onChange={(e) => setRate(Number(e.target.value))} /></label>
        <label className="field">Days between sessions<input type="number" min={1} value={gap} onChange={(e) => setGap(Number(e.target.value))} /></label>
      </div>
      {sigma !== null
        ? <p className="result">Noise between sessions: <strong>{sigma.toFixed(1)} mm</strong>. To spot {rate} mm a year you'd need about <strong>{needed ?? "20,000+"}</strong> sessions{needed ? `, roughly ${Math.round(((needed - 1) * gap) / 7)} weeks` : ""}.</p>
        : <p className="muted">Enter at least three heights to see an estimate.</p>}
      <p className="small">Best-case estimate. Weather, nearby buildings, and the site itself can make the real wait longer. The sensor measures its own noise, not Houston's sinking.</p>
    </div>
  );
}
