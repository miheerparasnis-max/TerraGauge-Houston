import { useMemo, useState } from "react";
import type { LedgerEntry, Meta } from "./types";
import { fmt } from "./labels";

/** The one memorable element: signal and noise drawn to the same scale. */
function Gauge({ signal, noise, label }: { signal: number; noise: number; label: string }) {
  const max = noise * 1.05;
  const pct = (v: number) => `${Math.max(0.6, (v / max) * 100)}%`;
  return (
    <figure className="gauge">
      <figcaption>{label}</figcaption>
      <div className="gauge-track" aria-hidden="true">
        <div className="gauge-noise" style={{ width: pct(noise) }} />
        <div className="gauge-signal" style={{ width: pct(signal) }} />
      </div>
      <div className="gauge-keys">
        <span><i className="k-signal" />Expected real motion {fmt(signal, 1, "mm")}</span>
        <span><i className="k-noise" />Measured NISAR noise {fmt(noise, 0, "mm")}</span>
      </div>
    </figure>
  );
}

export function SignalCheck({ meta }: { meta: Meta }) {
  const { pair, chain } = meta.signal_check;
  const d = meta.detectability;
  return (
    <div className="page">
      <h2 className="page-title">Can NISAR see Houston sinking yet?</h2>
      <p className="lede">Not from the data we have. Over 12 days, Houston's fastest-sinking ground moves a fraction of a millimetre. The NISAR pair varies by about {fmt(pair.nisar_sd_mm, 0)} mm from cell to cell, almost all of it ionosphere and atmosphere.</p>
      <Gauge signal={pair.expected_signal_sd_mm} noise={pair.nisar_sd_mm} label="12-day pair, 2–14 Nov 2025" />
      <Gauge signal={chain.expected_signal_sd_mm} noise={chain.nisar_sd_mm} label="Five pairs summed, 2 Nov 2025 to 1 Jan 2026" />
      <div className="facts">
        <div><strong>{pair.pearson_r_vs_opera.toFixed(2).replace("-", "−")}</strong><span>correlation between the 12-day NISAR pair and five years of OPERA motion ({pair.cells.toLocaleString()} cells). Zero means no shared pattern.</span></div>
        <div><strong>{chain.pearson_r_vs_opera.toFixed(2).replace("-", "−")}</strong><span>the same check for the 60-day sum. Summing pairs cancels noise from the middle dates, but the end dates still dominate.</span></div>
      </div>
      <h3>How many NISAR passes would it take?</h3>
      <p>Using the measured {fmt(d.sigma_mm, 1)} mm reference scatter and one pass every {d.interval_days} days. White-noise lower bound: real atmosphere is correlated, so the true wait is longer.</p>
      <table className="table">
        <thead><tr><th>If the ground moves</th><th>Passes needed</th><th>Time</th></tr></thead>
        <tbody>{d.rows.map((r) => <tr key={r.rate_mm_year}><td>{Math.abs(r.rate_mm_year)} mm/yr</td><td>{r.observations ?? "—"}</td><td>{r.years !== null ? `about ${r.years} ${r.years === 1 ? "year" : "years"}` : "—"}</td></tr>)}</tbody>
      </table>
      <p className="note-block">That is why the map defaults to the OPERA 2016–2021 record, which agrees with held-out GPS stations. NISAR views stay available as a quality preview and become useful as more passes arrive.</p>
    </div>
  );
}

function Scatter({ meta }: { meta: Meta }) {
  const pts = meta.gps_validation_points;
  const w = 340, h = 260, pad = 34;
  const lo = Math.min(-22, ...pts.map((p) => Math.min(p.gps_los_approx_mm_year, p.opera_los_mm_year)));
  const hi = Math.max(6, ...pts.map((p) => Math.max(p.gps_los_approx_mm_year, p.opera_los_mm_year)));
  const sx = (v: number) => pad + ((v - lo) / (hi - lo)) * (w - pad - 10);
  const sy = (v: number) => h - pad - ((v - lo) / (hi - lo)) * (h - pad - 10);
  const ticks = [-20, -10, 0];
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="scatter" role="img" aria-label={`OPERA velocity against GPS at ${pts.length} held-out stations, correlation ${meta.gps_validation.pearson_r.toFixed(2)}`}>
      <line x1={sx(lo)} y1={sy(lo)} x2={sx(hi)} y2={sy(hi)} className="one-to-one" />
      {ticks.map((t) => <g key={t}><text x={sx(t)} y={h - 14} textAnchor="middle" className="axis">{t}</text><text x={pad - 6} y={sy(t) + 4} textAnchor="end" className="axis">{t}</text></g>)}
      {pts.map((p) => <circle key={p.station_id} cx={sx(p.gps_los_approx_mm_year)} cy={sy(p.opera_los_mm_year)} r={3} className="pt"><title>{`${p.station_id}: GPS ${p.gps_los_approx_mm_year.toFixed(1)}, OPERA ${p.opera_los_mm_year.toFixed(1)} mm/yr`}</title></circle>)}
      <text x={w / 2 + 10} y={h - 1} textAnchor="middle" className="axis-title">GPS vertical rate in line of sight, mm/yr</text>
      <text transform={`translate(10 ${h / 2 - 10}) rotate(-90)`} textAnchor="middle" className="axis-title">OPERA, mm/yr</text>
    </svg>
  );
}

export function Methods({ meta }: { meta: Meta }) {
  const g = meta.gps_validation;
  const v = meta.views;
  return (
    <div className="page">
      <h2 className="page-title">Methods and limits</h2>
      <p className="lede">Every label comes from published rules in the TerraGauge backend. The website only displays results computed in Python.</p>
      <h3>Does the OPERA record match GPS?</h3>
      <div className="split">
        <Scatter meta={meta} />
        <div>
          <p><strong>{g.station_count}</strong> HoustonNet stations that were not used for the reference. Correlation <strong>{g.pearson_r.toFixed(2)}</strong>; typical difference <strong>{fmt(g.median_abs_residual_mm_year, 1, "mm/yr")}</strong>; median bias {fmt(g.median_residual_mm_year, 1, "mm/yr")}.</p>
          <p className="small">{g.method} Incidence assumed {g.incidence_deg_assumed}°.</p>
          <ul className="small">{g.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
        </div>
      </div>
      <h3>Processing steps</h3>
      <ol className="steps">
        <li><b>Quality mask.</b> NISAR pixels need finite phase, coherence ≥ {meta.thresholds.coherence_min.toFixed(2)}, and the product's main connected component; a 1 km cell needs ≥ {Math.round(meta.thresholds.valid_fraction_min * 100)}% valid pixels. OPERA cells must pass the recommended mask and be mostly land in all {v.opera.products} products.</li>
        <li><b>Ramp removal.</b> A best-fit plane is removed from each NISAR pair. This cuts frame-wide ionospheric and atmospheric ramps from 13–43 mm to 3–10 mm of scatter, and would also remove any real motion that is planar across the whole city.</li>
        <li><b>Reference.</b> {meta.reference.method}. {meta.reference.reference_stations.length} reference stations; {meta.reference.held_out_stable_stations.length} stable stations held out. Radar results are relative to these stations.</li>
        <li><b>Noise threshold.</b> A candidate must exceed {meta.thresholds.sigma_multiplier}× the scatter at the reference stations: {fmt(v.opera.threshold_mm_year, 1, "mm/yr")} for OPERA, {fmt(v.pair.threshold_mm, 1, "mm")} for the NISAR 12-day pair.</li>
        <li><b>OPERA velocity.</b> {v.opera.products} chained OPERA DISP-S1 products ({v.opera.dates[0]} to {v.opera.dates[1]}), each re-referenced, then a least-squares line per cell.</li>
        <li><b>Monitoring gap.</b> Distance to the nearest permanent HoustonNet GPS station; under {meta.thresholds.gps_nearby_km} km counts as covered.</li>
      </ol>
      <h3>Limitations</h3>
      <ul className="limits">{[...meta.limitations.opera, ...meta.limitations.nisar].map((l) => <li key={l}>{l}</li>)}</ul>
      <h3>Label counts</h3>
      <table className="table">
        <thead><tr><th>View</th><th>Investigate</th><th>Add monitoring</th><th>Context</th><th>Insufficient</th></tr></thead>
        <tbody>{(["opera", "pair", "chain"] as const).map((k) => { const c = v[k].counts; return <tr key={k}><td>{v[k].title}</td><td>{c.investigate_satellite_signal ?? 0}</td><td>{c.add_ground_monitoring ?? 0}</td><td>{c.context_only ?? 0}</td><td>{c.insufficient_radar_evidence ?? 0}</td></tr>; })}</tbody>
      </table>
    </div>
  );
}

const rateUncertainty = (sigma: number, days: number, n: number) => (sigma / (days / 365.25)) * Math.sqrt(12 / (n * (n * n - 1)));

export function GroundTruth() {
  const [heights, setHeights] = useState("");
  const [rate, setRate] = useState(10);
  const [interval, setInterval] = useState(7);
  const values = heights.split(/[\s,]+/).map(Number).filter((n) => Number.isFinite(n) && heights.trim() !== "");
  const sigma = useMemo(() => {
    if (values.length < 3) return null;
    const m = values.reduce((a, b) => a + b, 0) / values.length;
    return Math.sqrt(values.reduce((a, b) => a + (b - m) ** 2, 0) / (values.length - 1));
  }, [values.join(",")]);
  const needed = useMemo(() => {
    if (!sigma || rate <= 0) return null;
    for (let n = 3; n < 20000; n++) if (rateUncertainty(sigma, interval, n) <= rate / 2) return n;
    return null;
  }, [sigma, rate, interval]);
  return (
    <div className="page">
      <h2 className="page-title">GroundTruth Node</h2>
      <p className="lede">A $74 Waveshare LC29H(BS) receiver with its antenna fixed on a metal sheet. It measures its own noise while standing still, so we can estimate how long a cheap node would need to confirm motion in a monitoring gap. It does not measure Houston subsidence.</p>
      <div className="status-box">
        <p><strong>Status: no sessions recorded yet.</strong> Logging starts at hour 0 of the hackathon. A result is reported only with a raw log, a RINEX file, overlapping NOAA NETP data, at least three static solutions, and an antenna that never moved.</p>
      </div>
      <h3>Try the planning calculator</h3>
      <label className="field">Static-session heights in mm, one per session
        <input value={heights} onChange={(e) => setHeights(e.target.value)} placeholder="e.g. 11.2, 8.9, 10.4" inputMode="decimal" />
      </label>
      <div className="field-row">
        <label className="field">Motion to detect, mm/yr<input type="number" min={1} value={rate} onChange={(e) => setRate(Number(e.target.value))} /></label>
        <label className="field">Days between sessions<input type="number" min={1} value={interval} onChange={(e) => setInterval(Number(e.target.value))} /></label>
      </div>
      {sigma !== null ? (
        <p className="result">Session scatter {sigma.toFixed(1)} mm. To resolve {rate} mm/yr at 2σ you would need about <strong>{needed ?? "more than 20,000"}</strong> sessions{needed ? `, roughly ${((needed - 1) * interval / 7).toFixed(0)} weeks` : ""}.</p>
      ) : <p className="empty">Enter at least three session heights to see an estimate.</p>}
      <p className="small">Lower-bound planning estimate. Atmospheric effects, multipath, and site conditions can increase real uncertainty. Example values are not results.</p>
    </div>
  );
}

export function Ledger({ ledger, meta }: { ledger: LedgerEntry[]; meta: Meta }) {
  const extra = [
    { key: "nasadem", name: "NASA NASADEM elevation" },
    { key: "dswx", name: "NASA JPL OPERA DSWx-S1 surface water" },
    { key: "dist", name: "NASA JPL OPERA DIST-ALERT land disturbance" },
  ];
  return (
    <div className="page">
      <h2 className="page-title">Data ledger</h2>
      <p className="lede">Every source file the map was built from, with its manifest.</p>
      <ul className="sources">
        <li><b>NASA/ISRO NISAR L2 GUNW</b>, track 062 frame 016, five pairs 2 Nov 2025 to 1 Jan 2026, via ASF. Product wet/hydrostatic tropospheric and ionospheric corrections already applied.</li>
        <li><b>NASA JPL OPERA DISP-S1</b>, frame F38238, 2016–2021, via ASF DAAC.</li>
        <li><b>HoustonNet GPS</b>, 2024 data release, University of Houston and Harris-Galveston Subsidence District.</li>
        <li><b>USGS</b> groundwater daily values (NWIS) and the 2023 Houston extensometer compaction release.</li>
        <li><b>FEMA</b> National Flood Hazard Layer, flood hazard zones.</li>
        {extra.map((x) => <li key={x.key}><b>{x.name}</b>{meta.nasa_layers[x.key] ? `, ${String(meta.nasa_layers[x.key].value)}.` : ": not loaded yet. Run scripts/fetch_nasa_layers.py with an Earthdata login, then scripts/export_web.py."}</li>)}
      </ul>
      {ledger.map((e) => (
        <details key={e.manifest} className="block">
          <summary>{e.manifest}</summary>
          <pre>{JSON.stringify(e.record, null, 2).slice(0, 4000)}</pre>
        </details>
      ))}
    </div>
  );
}
