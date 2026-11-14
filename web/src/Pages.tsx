import { Fragment, useMemo, useState } from "react";
import type { Cell, Meta } from "./types";
import { ACTION, CONFIDENCE, num } from "./labels";
import { Marquee } from "./Marquee";

function Scatter({ meta }: { meta: Meta }) {
  const pts = meta.validation.points;
  const w = 320, h = 250, pad = 36;
  const vals = pts.flatMap((p) => [p.gps, p.sat]);
  const lo = Math.min(-30, ...vals), hi = Math.max(6, ...vals);
  const sx = (v: number) => pad + ((v - lo) / (hi - lo)) * (w - pad - 10);
  const sy = (v: number) => h - pad - ((v - lo) / (hi - lo)) * (h - pad - 10);
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="scatter" role="img" aria-label={`Satellite versus GPS at ${pts.length} stations`}>
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
      <div className="gauge-keys"><span><i className="k-signal" />Real ground movement in that time: {num(signal)} mm</span><span><i className="k-noise" />How much the readings wobble: {num(noise, 0)} mm</span></div>
    </figure>
  );
}

function toCSV(cells: Cell[], meta: Meta): string {
  const years = meta.forecast?.years ?? [];
  const head = ["square_id", "longitude", "latitude", "rate_mm_per_year", "uncertainty_mm_per_year", "source", "confidence", "priority", "flood_zone", "high_risk_flood", ...years.map((y) => `forecast_${y}_cm`), "drought_level", "bending_level", "elevation_m"];
  const esc = (v: unknown) => (v === null || v === undefined ? "" : /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v));
  const rows = cells.map((c) => [c.id, c.lon, c.lat, c.rate, c.se, c.src.join("+") || "none", c.conf, c.act, c.flood.zone, c.flood.sfha, ...years.map((y) => c.future?.by[String(y)]?.c), c.hz?.dl, c.hz?.bl, c.elev ?? c.nasadem?.elevation_m].map(esc).join(","));
  return [head.join(","), ...rows].join("\n");
}

function save(name: string, text: string, type: string) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type }));
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

export function HowWeKnow({ meta, cells }: { meta: Meta; cells: Cell[] }) {
  const v = meta.validation, n = meta.nisar, f = meta.forecast, th = meta.thresholds;
  const direct = cells.filter((c) => c.act !== "insufficient_data" && !c.src.includes("estimated")).length;
  const est = cells.filter((c) => c.src.includes("estimated")).length;
  return (
    <div className="page">
      <Marquee className="page-title" text="How we know" />
      <p className="lede">TerraGauge puts every dataset onto one map of 1 km squares, then answers five questions for each square: is the ground moving, how sure are we, how much will it sink, what should Houston do, and what would a disaster do here. Here is how each answer is made, and how far to trust it.</p>
      <div className="facts">
        <div><strong>{cells.length.toLocaleString()}</strong><span>squares of 1 km cover the whole study area, from Katy to Baytown and Spring to Pearland</span></div>
        <div><strong>{direct.toLocaleString()}</strong><span>measured directly; {est.toLocaleString()} more estimated from measured neighbors; the rest are water or outside satellite coverage</span></div>
      </div>
      <nav className="toc" aria-label="On this page">
        {[["data", "Datasets"], ["match", "Satellite vs GPS"], ["hazards", "Hazards"], ["forecast", "Forecast"], ["nisar", "NISAR"], ["rules", "Rules"], ["downloads", "Downloads"]].map(([id, name]) => <a key={id} href={`#how`} onClick={(e) => { e.preventDefault(); document.getElementById(id)?.scrollIntoView({ behavior: "smooth" }); }}>{name}</a>)}
      </nav>

      <h3 id="data">One map, every dataset</h3>
      <table className="table">
        <thead><tr><th>Data</th><th>What it tells us</th><th>How we use it</th></tr></thead>
        <tbody>
          <tr><td>NASA OPERA satellite radar, {meta.record.start.slice(0, 4)}–{meta.record.end.slice(0, 4)} ({meta.record.products} time periods)</td><td>How much each square moved</td><td>Main movement measurement and the forecast's training data</td></tr>
          <tr><td>HoustonNet GPS, 257 stations</td><td>Very precise movement at single points</td><td>Blended in where a station is inside a square; checks the satellite; defines sensor coverage</td></tr>
          <tr><td>NASA/ISRO NISAR, {meta.nisarArchive.first.slice(0, 7)} to {meta.nisarArchive.last.slice(0, 7)} ({meta.nisarArchive.processedPairs} image pairs)</td><td>The newest radar satellite, a pass every 12 days</td><td>Checks the map, and "how long to confirm" in every square</td></tr>
          <tr><td>USGS groundwater wells</td><td>Whether water levels are dropping</td><td>Context in each square's card</td></tr>
          <tr><td>USGS extensometers</td><td>How much soil is squeezing underground</td><td>Context in each square's card</td></tr>
          <tr><td>FEMA flood zones</td><td>Official flood odds (1-in-100 and 1-in-500-year zones)</td><td>Priority rules and the flood hazard view; sampled at 25 points per square</td></tr>
          {Object.entries(meta.nasaLayers).map(([k, src]) => <tr key={k}><td>{src}</td><td>{k === "nasadem" ? "Ground elevation" : k === "dswx" ? "Standing water" : "Construction and clearing"}</td><td>{k === "dswx" ? "Marks water squares as no measurement" : k === "nasadem" ? "Finds low coastal squares for the flood view; context in each card" : "Lowers confidence where construction may fake movement"}</td></tr>)}
        </tbody>
      </table>

      <h3 id="match">Does the satellite match the ground?</h3>
      <div className="split">
        <Scatter meta={meta} />
        <div>
          <p className="big"><strong>{num(v.typical_diff_mm_year)} mm</strong> a year: how far the satellite and {v.stations} GPS stations it never saw are typically apart.</p>
          <p>They rise and fall together {Math.round(v.r * 100)}% of the way (a match score of {v.r.toFixed(2)}, where 1 is perfect). Dots near the dashed line mean the two agree.</p>
          <p className="small">GPS station records cover different years than the satellite, so some difference is expected.</p>
        </div>
      </div>

      {meta.hazards && (() => { const t = meta.hazards.tests; return (
        <>
          <h3 id="hazards">Hazards: what the moving ground does in a disaster</h3>
          <p>We can't predict when a hurricane or drought will come. Nobody can, years ahead. What we can do is show what Houston's moving ground does when one comes, and we tested each view on past years.</p>
          <h4>Floods</h4>
          <p>FEMA's flood maps give the odds of a big flood in each area: a 1% chance each year in high-risk zones (1-in-100-year) and 0.2% in moderate ones (1-in-500-year). Over a 30-year mortgage, 1% a year adds up to about a 26% chance. Sinking ground makes the same flood deeper by however much the ground has dropped. The satellite measured that drop in every square since 2016, so the flood view shows it directly: measured, not forecast. It is a simple, honest number, not a flood simulation: real flooding also depends on drains, bayous and where the rain falls.</p>
          {meta.hazards.harvey && (() => { const h = meta.hazards.harvey!; const row = (k: "1pct" | "0.2pct" | "minimal", name: string) => { const b = h.by_class[k], d = h.depth_by_class[k]; return b ? <tr key={k}><td>{name}</td><td>{b.squares.toLocaleString()}</td><td>{num(b.flooded_pct, 0)}%</td><td>{num(b.mean_flooded_share_pct, 0)}%</td><td>{d ? `${num(d.median_depth_ft)} ft` : "—"}</td></tr> : null; }; return (
            <>
              <p><b>Reality check, Hurricane Harvey (2017).</b> USGS mapped exactly where Harvey's water reached, and how deep, for {(h.areas ?? ["north and northeast Houston"]).join(" and ")}: {h.squares.toLocaleString()} of our squares. We compared that with each square's FEMA flood zone:</p>
              <table className="table">
                <thead><tr><th>FEMA zone</th><th>Squares</th><th>Flooded at all</th><th>Share of area flooded</th><th>Typical depth where wet</th></tr></thead>
                <tbody>{row("1pct", "High risk (1-in-100)")}{row("0.2pct", "Moderate (1-in-500)")}{row("minimal", "Low risk")}</tbody>
              </table>
              <p>The flood odds on our map hold up: high-risk squares had far more of their area flooded, and deeper, than low-risk ones. But {num(h.flooded_area_outside_high_risk_pct, 0)}% of Harvey's flooded area was outside the high-risk zones, which is why every square shows its flood zone and not just a yes/no.</p>
              {h.by_sinking.fast && h.by_sinking.stable && <p>Sinking speed alone did not predict where Harvey flooded: fast-sinking squares had {num(h.by_sinking.fast.mean_flooded_share_pct, 0)}% of their area flooded and stable ones {num(h.by_sinking.stable.mean_flooded_share_pct, 0)}%, because the most-flooded places were river floodplains, many of them stable. That's expected. Where one storm's water goes is set by terrain and drainage. What sinking changes is how deep the water stands once it gets there, by however much the ground has dropped, and that measured drop is what our flood view shows. We don't forecast flood depths. Each square's card in these areas says how much of it flooded in Harvey{h.depth_by_class["1pct"] ? " and, where USGS mapped depth, how deep" : ""}.</p>}
            </>
          ); })()}
          <h4>Droughts</h4>
          <p>Houston's clay shrinks when it dries out. In the 2011 and 2023 droughts the city had thousands of water main breaks and widespread foundation cracking. Our satellite record shows the shrinking directly: in late summer 2018 and in October 2023, many squares dropped well below their normal trend. We measured how much extra each square dropped.</p>
          <p><b>Test:</b> we pretended it was early 2023 and used only the 2018 drought to pick the 10% of squares most likely to drop. In the October 2023 drought, those squares dropped a median <b>{num(t.drought.flagged_median_drop_mm, 0)} mm</b>, versus {num(t.drought.others_median_drop_mm, 0)} mm for everywhere else, and {num(t.drought.flagged_share_in_worst10_pct, 0)}% of them landed in the worst-hit 10% (luck alone would give 10%). Drought damage repeats in the same places.</p>
          <h4>Ground bending and faults</h4>
          <p>Where one square sinks much faster than the one next to it, the ground between them bends. That strains pipes, roads and foundations. Houston also has hundreds of slowly slipping faults that crack roads and buildings, and in radar they show up as exactly this kind of sharp change. We flag squares where the sinking speed changes by 10 mm a year or more within 1 km.</p>
          <p><b>Test:</b> we split the record in half. The squares bending most in 2016–2021 were still bending about {num(t.bending.hotspot_later_median)} mm a year per km in 2021–2026, versus {num(t.bending.others_later_median)} for the rest, across {t.bending.cells.toLocaleString()} squares. Bending hotspots are real and lasting, not radar noise. Our squares are 1 km wide, so they mark zones to inspect, not exact fault lines.</p>
        </>
      ); })()}

      <h3 id="forecast">How the forecast works, and how we tested it</h3>
      {f ? (
        <>
          <p>To test a forecast honestly, we pretended it was an earlier date. Each method could only use satellite data up to that date, then had to predict how much every square would sink 1, 2, 3, 4 and 5 years later. We compared each prediction with what really happened. We repeated this from {f.benchmark.origins.length} different starting dates between {f.benchmark.origins[0].slice(0, 4)} and {f.benchmark.origins[f.benchmark.origins.length - 1].slice(0, 4)}: {f.benchmark.test_cases} tests per method.</p>
          <p>We tried {f.benchmark.table.length} methods, from "no motion" to a machine-learning model that learns from each square's past speed, whether it is speeding up or slowing down, its neighbors and its location, retrained for every test.</p>
          {(() => { const hs = Object.keys(f.benchmark.table[0].by_horizon_cm); const best = (k: string | null) => Math.min(...f.benchmark.table.map((t) => k ? t.by_horizon_cm[k] : t.overall_cm)); const cell = (v: number, k: string | null) => <td className={v === best(k) ? "best" : ""}>{num(v)} cm</td>; return (
          <table className="table">
            <thead><tr><th>Method</th><th>Overall</th>{hs.map((h) => <th key={h}>{h} yr ahead</th>)}</tr></thead>
            <tbody>{f.benchmark.table.map((t) => <tr key={t.method}><td>{t.label}</td>{cell(t.overall_cm, null)}{hs.map((h) => <Fragment key={h}>{cell(t.by_horizon_cm[h], h)}</Fragment>)}</tr>)}</tbody>
          </table>); })()}
          <p className="small">How far off a typical square was, over all tests. Bold = most accurate.</p>
          <p><b>Result:</b> a <b>trend that allows for seasons, averaged with its neighborhood</b> tied for most accurate (with a trend that ignores odd one-off readings), so the Future view uses it. "Allows for seasons" means it fits each square's trend while allowing for the yearly swing of Houston's clay (it shrinks in dry summers and swells back in wet winters), so a square measured in a dry season isn't mistaken for one sinking faster. "Neighborhood" means each square's rate is averaged 50/50 with the typical rate within 3 km, which smooths out radar wobble; ground sinks over whole areas, not single squares.</p>
          <p>The machine-learning model was the least accurate of all, even worse than assuming "no motion". With ten years of data, most of the error comes from weather-driven shrink and swell that no model can know years in advance, and the model learned quirks of particular years instead. With more years of NISAR and OPERA data, a model may eventually win.</p>
          <h4>How wide are the ranges?</h4>
          <p>Each year's shaded range is how far off 80% of squares stayed within in these tests, at that many years ahead: about ±{num(f.bands_cm[0]?.half_width_cm)} cm one year out and ±{num(f.bands_cm[f.bands_cm.length - 1]?.half_width_cm)} cm {f.tested_horizon_years.toFixed(0)} years out. We tested up to about {f.tested_horizon_years.toFixed(0)} years ahead, so the forecast stops at {f.years[f.years.length - 1]}.</p>
          <ul className="small">{f.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
        </>
      ) : <p>No forecast test has been run yet. Run scripts/forecast_benchmark.py.</p>}

      <h3 id="nisar">NASA's newest satellite: NISAR</h3>
      <p>NISAR, built by NASA and India's space agency, started imaging Houston in November 2025 and passes over every 12 days. We have all {meta.nisarArchive.processedPairs} of its Houston image pairs so far, {meta.nisarArchive.first.slice(0, 7)} to {meta.nisarArchive.last.slice(0, 7)}. Houston sinks a few millimetres over a few weeks, but the air between the satellite and the ground shifts a single radar reading by centimetres, so one pass can't measure Houston's slow sinking yet.</p>
      <Gauge signal={n.pair.signal_mm} noise={n.pair.noise_mm} label="One 12-day NISAR pair" />
      <Gauge signal={n.chain.signal_mm} noise={n.chain.noise_mm} label="Five pairs in a row, 60 days" />
      <p>That's why every square's card says how long NISAR needs to confirm it. Using how much NISAR's readings over Houston wobble ({num(n.sigma_mm)} mm per pass) and one pass every 12 days:</p>
      <table className="table">
        <thead><tr><th>If the ground sinks</th><th>NISAR passes needed</th><th>Time</th></tr></thead>
        <tbody>{n.detect.map((d) => <tr key={d.rate}><td>{d.rate} mm a year</td><td>{d.passes ?? "—"}</td><td>{d.years !== null ? `about ${d.years} years` : "—"}</td></tr>)}</tbody>
      </table>
      <p className="small">Best case. The air's effect carries over from one pass to the next, so the true wait is longer.</p>

      <h3 id="rules">How each answer is decided</h3>
      <h4>Movement</h4>
      <p>The satellite looks at the ground at a {th.incidence_deg}° slant, so we turn its reading into straight up-and-down movement, then combine it with a GPS station's rate when one sits within {th.gps_blend_km} km. Changes smaller than {num(th.stable_mm_year)} mm a year count as no clear motion: that's twice the wobble at GPS stations that aren't moving.</p>
      <h4>Confidence</h4>
      <ul>{(["high", "medium", "low"] as const).map((k) => <li key={k}><b>{CONFIDENCE[k].name}:</b> {CONFIDENCE[k].meaning}</li>)}</ul>
      <h4>Priority (first rule that matches wins)</h4>
      <ol>{(["insufficient_data", "review_disagreement", "investigate_first", "add_monitoring", "observe", "no_clear_motion"] as const).map((k) => <li key={k}><b>{ACTION[k].name}:</b> {ACTION[k].meaning}</li>)}</ol>
      <h4>Sensor sites</h4>
      <p>The numbered pins are the "Add monitoring here" squares in the fastest-sinking areas, ranked by the typical rate of squares within 3 km (so one odd square can't top the list) and kept at least {th.sensor_spacing_km} km apart. Low-cost sensors (diamonds) are then added until every "Add monitoring here" square has a suggested site within 6 km.</p>

      <h4>Squares between the satellite's grid blocks</h4>
      <p>The satellite data comes in blocks about 990 m wide, slightly bigger than our 1 km squares, so about every seventh row and column of squares gets no block of its own. Those {(meta.estimates as { stripeFilled?: number }).stripeFilled?.toLocaleString() ?? ""} squares are filled from the measured squares touching them. We tested this on 5,735 measured squares: the fill was typically within 0.65 mm a year, and 80% of the time within 1.9, which is better than a typical single satellite measurement. So they take the lowest confidence of the squares they are filled from, instead of being marked low across the board.</p>
      <h4>Squares without a measurement</h4>
      <p>Where the satellite has no reliable reading but at least {meta.estimates.min_neighbors} measured squares lie within {meta.estimates.radius_km} km, we estimate the rate from them (closer squares count more). We tested this by hiding {meta.estimates.tested.toLocaleString()} measured squares and estimating them: typical error {num(meta.estimates.median_error_mm_year)} mm a year, 80% within {num(meta.estimates.p80_error_mm_year)}. Estimated squares are drawn lighter and always get low confidence.</p>
      <p>South of the satellite product's coverage, we estimate from GPS stations instead: at least {meta.gpsEstimates.min_stations} stations with 5+ years of record within {meta.gpsEstimates.radius_km} km. Tested by predicting {meta.gpsEstimates.tested.toLocaleString()} satellite-measured squares from GPS alone: typical error {num(meta.gpsEstimates.median_error_mm_year)} mm a year, 80% within {num(meta.gpsEstimates.p80_error_mm_year)}. Squares with too few stations stay blank and get fill-the-gap sensor sites.</p>
      <h4>Shaky squares</h4>
      <p>About 1 in 10 squares has a shaky satellite record (its trend could be off by 15 mm a year or more), which made isolated squares look wildly different from their neighbors. The map now combines each square's own rate with the typical rate within 3 km, weighting each by how precise it is: precise squares keep their own value, noisy ones are pulled toward their neighborhood. Against GPS stations, this cut the typical gap from 1.9 to 1.7 mm a year and the worst 10% from 7.6 to 6.5. Squares with clean records keep their own value. Each card still shows the square's own reading.</p>

      <h3>Still provisional</h3>
      <p className="small">Satellite radar measures movement relative to a reference. We used {meta.reference.reference_stations.length} long-running GPS stations that barely move as that reference and held out {meta.reference.held_out_stable_stations.length} similar stations for checking. The team still needs to review this choice.</p>

      <h3 id="downloads">Downloads</h3>
      <p>Everything on the map, free to reuse. The CSV has one row per square; the JSON files are exactly what this site loads.</p>
      <div className="downloads">
        <button onClick={() => save("terragauge-houston-squares.csv", toCSV(cells, meta), "text/csv")}>All squares (CSV)</button>
        <a href="./data/cells.json" download>Squares (JSON)</a>
        <a href="./data/meta.json" download>Tests and settings (JSON)</a>
        <a href="./data/sites.json" download>GPS, wells, gauges (JSON)</a>
      </div>

      <h3>Sources</h3>
      <ul className="small">
        <li>NASA JPL OPERA DISP-S1 surface displacement products, generated from Copernicus Sentinel-1 data (frames F38238 and F38239), {meta.record.start} to {meta.record.end}, via the Alaska Satellite Facility.</li>
        <li>Wang et al. (2022), Houston GNSS Network for Subsidence and Faulting Monitoring, J. Surv. Eng. 148(4): 04022008. Used to exclude five GPS antennas mounted on deep borehole anchors.</li>
        <li>NASA/ISRO NISAR L2 GUNW, track 062 frame 016, {meta.nisarArchive.processedPairs} pairs, {meta.nisarArchive.first} to {meta.nisarArchive.last}.</li>
        <li>HoustonNet GPS 2024 release, University of Houston and Harris-Galveston Subsidence District.</li>
        <li>USGS groundwater daily values and the 2023 Houston extensometer release.</li>
                <li>USGS Flood Event Viewer high-water marks, Hurricane Harvey (2017), when downloaded.</li>
        <li>Garvin, K.M. (2018), Flood inundation geospatial data for the August and September 2017 flood event in Texas (Hurricane Harvey), USGS data release, doi:10.5066/F7VH5N3N. San Jacinto River basin flooded area, depth and high-water marks.</li>
        <li>Address search by OpenStreetMap Nominatim.</li>
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
      <Marquee className="page-title" text="Hardware" />
      <p className="lede">Satellites show where Houston is sinking. A GPS sensor on the ground confirms it. TerraGauge suggests two kinds of sensors and exactly where each would help most.</p>

      <h3>What a ground sensor does</h3>
      <p>A GPS receiver bolted to the ground measures its own height every day against NOAA's reference stations. If the ground under it sinks, the daily heights slowly drift down. After enough days, the drift stands out from the daily wobble and the sinking is confirmed. Faster sinking and a quieter sensor mean a shorter wait.</p>

      <div className="tier">
        <div>
          <h4>Basic: low-cost GPS sensor</h4>
          <dl>
            <div className="row"><dt>What it is</dt><dd>A small dual-band GPS board and antenna on a fixed post, with power and a data link</dd></div>
            <div className="row"><dt>Cost</dt><dd>About $74 (our Waveshare LC29H prototype) to about $350–500 for a u-blox ZED-F9P kit with a better antenna</dd></div>
            <div className="row"><dt>Daily wobble</dt><dd>~{hw.node_daily_sigma_mm} mm (planning guess until our test measures it)</dd></div>
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
            <div className="row"><dt>Daily wobble</dt><dd>~{hw.gps_daily_sigma_mm} mm</dd></div>
            <div className="row"><dt>Time to confirm 10 mm/yr</dt><dd>about {hw.gps_weeks_10} weeks (best case)</dd></div>
            <div className="row"><dt>Time to confirm 5 mm/yr</dt><dd>about {hw.gps_weeks_5} weeks (best case)</dd></div>
            <div className="row"><dt>Best for</dt><dd>Long-term anchors in the most important flood-zone sinking areas</dd></div>
          </dl>
        </div>
      </div>
      <p className="small">"Best case" assumes the daily wobble is random. Real GPS readings also drift with the seasons, so agencies usually wait a few years before trusting a station's long-term rate. Low-cost prices and performance come from a published test of u-blox ZED-F9P receivers for tracking ground movement (Hohensinn et al., 2022), which found centimetre-level precision and called them an excellent way to add stations to existing networks.</p>

      <h3>Where we'd put them</h3>
      <h4>{meta.sensors.length} permanent GPS stations (numbered pins on the map)</h4>
      <p className="small">Rule: measured squares that are clearly sinking inside a FEMA high-risk flood zone with no GPS station within {meta.thresholds.gps_covered_km} km ("Add monitoring here"), skipping any square we are already highly confident about, ranked by how fast the surrounding area is sinking with less certain squares first, kept {meta.thresholds.sensor_spacing_km} km apart.</p>
      <ol className="site-list">{meta.sensors.map((s) => <li key={s.id}><button className="link" onClick={() => onShow(s.id)}>Area sinking {num(Math.abs(s.areaRate))} mm/yr</button> <small>, zone {s.zone}, {num(s.gpsKm)} km from GPS</small></li>)}</ol>
      <h4>{meta.nodes.length} low-cost sensors (diamonds on the map)</h4>
      <p className="small">Rule: squares that are clearly sinking ("Add monitoring here" or "Observe"), not already high confidence, with no GPS within {meta.thresholds.gps_covered_km} km, where a sensor could confirm the sinking within {hw.node_max_years} years, ranked by sinking speed, kept {hw.node_spacing_km} km apart and away from the permanent-station sites. Then more are added until every "Add monitoring here" square has a suggested site within 6 km.</p>
      <ol className="site-list">{meta.nodes.map((n) => <li key={n.id}><button className="link" onClick={() => onShow(n.id)}>Sinking {num(Math.abs(n.areaRate))} mm/yr</button> <small>{n.weeks ? `, about ${n.weeks} weeks to confirm` : ""}{n.est ? ", estimated square" : ""}{n.cover ? ", covers nearby flood-zone sinking" : ""}</small></li>)}</ol>
      <h4>{meta.gaps.length} sensors where nothing measures yet (white diamonds on the map)</h4>
      <p className="small">Rule: land squares the satellite doesn't cover, at least 4 km from any working GPS, high-risk flood zones first, then the most isolated, kept 6 km apart. Nothing measures the ground there, so the first job of a sensor is simply to give a reading.</p>
      <ol className="site-list">{meta.gaps.map((g) => <li key={g.id}><button className="link" onClick={() => onShow(g.id)}>{num(g.gpsKm)} km from the nearest GPS</button> <small>, flood zone {g.zone ?? "not mapped"}{g.sfha ? " (high risk)" : ""}</small></li>)}</ol>

      <h3>Our hackathon test</h3>
      <p>During the event we test the basic sensor ourselves: the antenna is fixed to a metal sheet in a backyard and never moved, so any change in its readings is pure noise. That measured noise replaces the {hw.node_daily_sigma_mm} mm planning guess above.</p>
      <div className="status-box"><p><strong>Status: no recordings yet.</strong> We report a result only with three good sessions checked against NOAA's NETP reference station. The sensor measures its own wobble, not Houston's sinking.</p></div>
      <h4>Try the calculator</h4>
      <label className="field">Heights from each session, in mm<input value={heights} onChange={(e) => setHeights(e.target.value)} placeholder="for example 11.2, 8.9, 10.4" inputMode="decimal" /></label>
      <div className="field-row">
        <label className="field">Sinking to detect, mm a year<input type="number" min={1} value={rate} onChange={(e) => setRate(Number(e.target.value))} /></label>
        <label className="field">Days between sessions<input type="number" min={1} value={gap} onChange={(e) => setGap(Number(e.target.value))} /></label>
      </div>
      {sigma !== null
        ? <p className="result">Wobble between sessions: <strong>{sigma.toFixed(1)} mm</strong>. To spot {rate} mm a year you'd need about <strong>{needed ?? "20,000+"}</strong> sessions{needed ? `, roughly ${Math.round(((needed - 1) * gap) / 7)} weeks` : ""}.</p>
        : <p className="muted">Enter at least three heights to see an estimate.</p>}

      <h3>Sources</h3>
      <ul className="small">
        <li>Hohensinn, R. et al. (2022), Low-cost GNSS and real-time PPP: assessing the precision of the u-blox ZED-F9P for kinematic monitoring applications, Remote Sensing 14(20), 5100.</li>
        <li>Harris-Galveston Subsidence District, Subsidence FAQs.</li>
      </ul>
    </div>
  );
}
