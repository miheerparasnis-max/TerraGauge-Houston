import { useMemo, useState } from "react";
import type { Meta } from "./types";
import { ACTION, CONFIDENCE, num } from "./labels";

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

function Gauge({ signal, noise, label }: { signal: number; noise: number; label: string }) {
  const pct = (v: number) => `${Math.max(0.8, (v / (noise * 1.05)) * 100)}%`;
  return (
    <figure className="gauge">
      <figcaption>{label}</figcaption>
      <div className="gauge-track" aria-hidden="true"><div className="gauge-noise" style={{ width: pct(noise) }} /><div className="gauge-signal" style={{ width: pct(signal) }} /></div>
      <div className="gauge-keys"><span><i className="k-signal" />Real ground movement in that time: {num(signal)} mm</span><span><i className="k-noise" />Measurement noise: {num(noise, 0)} mm</span></div>
    </figure>
  );
}

const BASELINE_NAMES: Record<string, string> = {
  model: "Machine-learning model",
  past_rate_continues: "The past rate continues",
  area_rate: "The surrounding area's rate",
  damped_past_rate: "The past rate, scaled down",
  no_motion: "No motion",
};

export function HowWeKnow({ meta }: { meta: Meta }) {
  const v = meta.validation, n = meta.nisar, f = meta.forecast, th = meta.thresholds;
  return (
    <div className="page">
      <h2 className="page-title">How we know</h2>
      <p className="lede">TerraGauge puts every dataset onto one map of 1 km squares, then answers four questions for each square. Here is how each answer is made, and how far to trust it.</p>

      <h3>One map, every dataset</h3>
      <table className="table">
        <thead><tr><th>Data</th><th>What it tells us</th><th>How we use it</th></tr></thead>
        <tbody>
          <tr><td>NASA OPERA satellite radar, {meta.record.start.slice(0, 4)}–{meta.record.end.slice(0, 4)} ({meta.record.products} time periods)</td><td>How much each square moved</td><td>Main movement measurement and the forecast's training data</td></tr>
          <tr><td>HoustonNet GPS, 257 stations</td><td>Very precise movement at single points</td><td>Blended in where a station is inside a square; checks the satellite; defines sensor coverage</td></tr>
          <tr><td>NASA/ISRO NISAR, Nov 2025–Jan 2026</td><td>The newest radar satellite</td><td>Quality check and "how long to confirm" in every square</td></tr>
          <tr><td>USGS groundwater wells</td><td>Whether water levels are dropping</td><td>Context in each square's card</td></tr>
          <tr><td>USGS extensometers</td><td>How much soil is squeezing underground</td><td>Context in each square's card</td></tr>
          <tr><td>FEMA flood zones</td><td>Official high-risk flood areas</td><td>Part of the priority rules</td></tr>
          {Object.entries(meta.nasaLayers).map(([k, src]) => <tr key={k}><td>{src}</td><td>{k === "nasadem" ? "Ground elevation" : k === "dswx" ? "Standing water" : "Construction and clearing"}</td><td>{k === "dswx" ? "Marks water squares as no measurement" : "Context in each square's card"}</td></tr>)}
        </tbody>
      </table>

      <h3>Does the satellite match the ground?</h3>
      <div className="split">
        <Scatter meta={meta} />
        <div>
          <p className="big"><strong>{v.r.toFixed(2)}</strong> correlation with {v.stations} GPS stations we did not use to calibrate the satellite.</p>
          <p>Typical difference: <strong>{num(v.typical_diff_mm_year)} mm a year</strong>. Points near the dashed line mean the satellite and the GPS station agree.</p>
          <p className="small">GPS station records cover different years than the satellite, so some difference is expected.</p>
        </div>
      </div>

      <h3>How the forecast works, and how we tested it</h3>
      {f ? (
        <>
          <p>A machine-learning model (gradient-boosted trees) learns how each square's future rate relates to its past: its overall rate, whether it was speeding up or slowing down, how steady its record was, what the squares around it were doing, and where it is. Groundwater, compaction, and GPS rates are left out because their records overlap the years being predicted.</p>
          <p>To test it honestly, we trained it only on {f.train_window[0].slice(0, 4)}–{f.train_window[1].slice(0, 4)} data and asked it to predict each square's rate for {f.test_window[0].slice(0, 4)}–{f.test_window[1].slice(0, 4)}. We scored it on parts of the city it never trained on (10 km blocks), and compared it with simpler guesses:</p>
          <table className="table">
            <thead><tr><th>Method</th><th>Typical error, mm/yr</th><th>In fast-sinking areas</th></tr></thead>
            <tbody>{(["model", "past_rate_continues", "area_rate", "damped_past_rate", "no_motion"] as const).map((k) => <tr key={k} className={k === "model" ? "win" : ""}><td>{BASELINE_NAMES[k]}</td><td>{num(f.scores[k].median_abs_error)}</td><td>{num(f.scores[k].fast_median_abs_error)}</td></tr>)}</tbody>
          </table>
          <p>{f.passes ? `The model beats every simpler method, so the Future view uses it.` : "The model did not clearly beat the simpler methods, so no forecast is shown."} The ranges are calibrated so that {Math.round(f.interval_coverage_10_90 * 100)}% of test squares fell inside them. We tested about {f.tested_horizon_years.toFixed(0)} years ahead, so the forecast stops at {f.years[f.years.length - 1]}.</p>
          <ul className="small">{f.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
        </>
      ) : <p>No forecast has been built yet. Run scripts/build_forecast.py.</p>}

      <h3>NASA's newest satellite: NISAR</h3>
      <p>NISAR started imaging Houston in late 2025. Houston sinks a few millimetres over a few weeks, but the atmosphere shifts a single radar reading by centimetres, so one pass can't measure Houston's slow sinking yet.</p>
      <Gauge signal={n.pair.signal_mm} noise={n.pair.noise_mm} label="One 12-day NISAR pair" />
      <Gauge signal={n.chain.signal_mm} noise={n.chain.noise_mm} label="Five pairs combined, 60 days" />
      <p>That's why every square's card says how long NISAR needs to confirm it. Using NISAR's measured noise over Houston ({num(n.sigma_mm)} mm per pass) and one pass every 12 days:</p>
      <table className="table">
        <thead><tr><th>If the ground sinks</th><th>NISAR passes needed</th><th>Time</th></tr></thead>
        <tbody>{n.detect.map((d) => <tr key={d.rate}><td>{d.rate} mm a year</td><td>{d.passes ?? "—"}</td><td>{d.years !== null ? `about ${d.years} years` : "—"}</td></tr>)}</tbody>
      </table>
      <p className="small">Best case. Real atmospheric noise is correlated from pass to pass, so the true wait is longer.</p>

      <h3>How each answer is decided</h3>
      <h4>Movement</h4>
      <p>The satellite rate (converted from its slanted view to up and down, assuming vertical motion at a {th.incidence_deg}° viewing angle) is blended with a GPS station's rate when one sits within {th.gps_blend_km} km. Changes smaller than {num(th.stable_mm_year)} mm a year count as no clear motion: that's twice the wobble at GPS stations that aren't moving.</p>
      <h4>Confidence</h4>
      <ul>{(["high", "medium", "low"] as const).map((k) => <li key={k}><b>{CONFIDENCE[k].name}:</b> {CONFIDENCE[k].meaning}</li>)}</ul>
      <h4>Priority (first rule that matches wins)</h4>
      <ol>{(["insufficient_data", "review_disagreement", "investigate_first", "add_monitoring", "observe", "no_clear_motion"] as const).map((k) => <li key={k}><b>{ACTION[k].name}:</b> {ACTION[k].meaning}</li>)}</ol>
      <h4>Sensor sites</h4>
      <p>The numbered pins are the "Add monitoring here" squares in the fastest-sinking areas, ranked by the median rate of squares within 3 km (so one noisy square can't top the list) and kept at least {th.sensor_spacing_km} km apart.</p>

      <h3>Still provisional</h3>
      <p className="small">Satellite radar measures movement relative to a reference. We used {meta.reference.reference_stations.length} long-running GPS stations that barely move as that reference and held out {meta.reference.held_out_stable_stations.length} similar stations for checking. The team still needs to review this choice.</p>

      <h3>Sources</h3>
      <ul className="small">
        <li>NASA JPL OPERA DISP-S1 surface displacement, frame F38238, {meta.record.start} to {meta.record.end}, via the Alaska Satellite Facility.</li>
        <li>NASA/ISRO NISAR L2 GUNW, track 062 frame 016, five pairs, 2 Nov 2025 to 1 Jan 2026.</li>
        <li>HoustonNet GPS 2024 release, University of Houston and Harris-Galveston Subsidence District.</li>
        <li>USGS groundwater daily values and the 2023 Houston extensometer release.</li>
        <li>FEMA National Flood Hazard Layer. Basemap © OpenFreeMap, © OpenMapTiles, © OpenStreetMap contributors.</li>
      </ul>
    </div>
  );
}

const rateUncertainty = (sigma: number, days: number, n: number) => (sigma / (days / 365.25)) * Math.sqrt(12 / (n * (n * n - 1)));

export function HardwarePage({ meta, onShow }: { meta: Meta; onShow: (id: string) => void }) {
  const hw = meta.hardware;
  const [heights, setHeights] = useState("");
  const [rate, setRate] = useState(10);
  const [gap, setGap] = useState(1);
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
      <h2 className="page-title">Hardware</h2>
      <p className="lede">Satellites show where Houston is sinking. A GPS sensor on the ground confirms it. TerraGauge suggests two kinds of sensors and exactly where each would help most.</p>

      <h3>What a ground sensor does</h3>
      <p>A GPS receiver bolted to the ground measures its own height every day against NOAA's reference stations. If the ground under it sinks, the daily heights slowly drift down. After enough days, the drift stands out from the daily wobble and the sinking is confirmed. Faster sinking and a quieter sensor mean a shorter wait.</p>

      <div className="tier">
        <div>
          <h4>Basic: low-cost GPS node</h4>
          <dl>
            <div className="row"><dt>What it is</dt><dd>A small dual-band GPS board and antenna on a fixed post, with power and a data link</dd></div>
            <div className="row"><dt>Cost</dt><dd>About $74 (our Waveshare LC29H prototype) to about $350–500 for a u-blox ZED-F9P kit with a better antenna</dd></div>
            <div className="row"><dt>Daily noise</dt><dd>~{hw.node_daily_sigma_mm} mm (planning guess until our test measures it)</dd></div>
            <div className="row"><dt>Time to confirm 10 mm/yr</dt><dd>about {hw.node_weeks_10} weeks (best case)</dd></div>
            <div className="row"><dt>Time to confirm 5 mm/yr</dt><dd>about {hw.node_weeks_5} weeks (best case)</dd></div>
            <div className="row"><dt>Best for</dt><dd>Covering many sinking areas cheaply, especially squares the satellite can only estimate</dd></div>
          </dl>
        </div>
        <div>
          <h4>Advanced: permanent GPS station</h4>
          <dl>
            <div className="row"><dt>What it is</dt><dd>A survey-grade receiver and antenna on a deep, stable mount, like the 257 HoustonNet stations</dd></div>
            <div className="row"><dt>Cost</dt><dd>About $20,000–30,000 per station</dd></div>
            <div className="row"><dt>Daily noise</dt><dd>~{hw.gps_daily_sigma_mm} mm</dd></div>
            <div className="row"><dt>Time to confirm 10 mm/yr</dt><dd>about {hw.gps_weeks_10} weeks (best case)</dd></div>
            <div className="row"><dt>Time to confirm 5 mm/yr</dt><dd>about {hw.gps_weeks_5} weeks (best case)</dd></div>
            <div className="row"><dt>Best for</dt><dd>Long-term anchors in the most important flood-zone sinking areas</dd></div>
          </dl>
        </div>
      </div>
      <p className="small">"Best case" assumes the daily wobble is random. Real GPS noise has seasonal and slow drifts, so agencies usually wait a few years before trusting a station's long-term rate. Low-cost costs and performance are from a published test of u-blox ZED-F9P receivers for deformation monitoring (Hohensinn et al., 2022), which found centimetre-level precision and called them an excellent way to add stations to existing networks.</p>

      <h3>Where we'd put them</h3>
      <h4>{meta.sensors.length} permanent GPS stations (numbered pins on the map)</h4>
      <p className="small">Rule: measured squares that are clearly sinking inside a FEMA high-risk flood zone with no GPS station within {meta.thresholds.gps_covered_km} km ("Add monitoring here"), ranked by how fast the surrounding area is sinking, kept {meta.thresholds.sensor_spacing_km} km apart.</p>
      <ol className="site-list">{meta.sensors.map((s) => <li key={s.id}><button className="link" onClick={() => onShow(s.id)}>Area sinking {num(Math.abs(s.areaRate))} mm/yr</button> <small>, zone {s.zone}, {num(s.gpsKm)} km from GPS</small></li>)}</ol>
      <h4>{meta.nodes.length} low-cost nodes (diamonds on the map)</h4>
      <p className="small">Rule: squares that are clearly sinking ("Add monitoring here" or "Observe", measured or estimated) with no GPS within {meta.thresholds.gps_covered_km} km, where a node could confirm the sinking within {hw.node_max_years} years, ranked by sinking speed, kept {hw.node_spacing_km} km apart and away from the permanent-station sites.</p>
      <ol className="site-list">{meta.nodes.map((n) => <li key={n.id}><button className="link" onClick={() => onShow(n.id)}>Sinking {num(Math.abs(n.areaRate))} mm/yr</button> <small>, about {n.weeks} weeks to confirm{n.est ? ", estimated square" : ""}</small></li>)}</ol>

      <h3>Our hackathon test</h3>
      <p>During the event we test the basic node ourselves: the antenna is fixed to a metal sheet in a backyard and never moved, so any change in its readings is pure noise. That measured noise replaces the {hw.node_daily_sigma_mm} mm planning guess above.</p>
      <div className="status-box"><p><strong>Status: no recordings yet.</strong> We report a result only with three good sessions checked against NOAA's NETP reference station. The node measures its own noise, not Houston's sinking.</p></div>
      <h4>Try the calculator</h4>
      <label className="field">Heights from each session, in mm<input value={heights} onChange={(e) => setHeights(e.target.value)} placeholder="for example 11.2, 8.9, 10.4" inputMode="decimal" /></label>
      <div className="field-row">
        <label className="field">Sinking to detect, mm a year<input type="number" min={1} value={rate} onChange={(e) => setRate(Number(e.target.value))} /></label>
        <label className="field">Days between sessions<input type="number" min={1} value={gap} onChange={(e) => setGap(Number(e.target.value))} /></label>
      </div>
      {sigma !== null
        ? <p className="result">Noise between sessions: <strong>{sigma.toFixed(1)} mm</strong>. To spot {rate} mm a year you'd need about <strong>{needed ?? "20,000+"}</strong> sessions{needed ? `, roughly ${Math.round(((needed - 1) * gap) / 7)} weeks` : ""}.</p>
        : <p className="muted">Enter at least three heights to see an estimate.</p>}

      <h3>Sources</h3>
      <ul className="small">
        <li>Hohensinn, R. et al. (2022), Low-cost GNSS and real-time PPP: assessing the precision of the u-blox ZED-F9P for kinematic monitoring applications, Remote Sensing 14(20), 5100.</li>
        <li>Harris-Galveston Subsidence District, Subsidence FAQs.</li>
      </ul>
    </div>
  );
}
