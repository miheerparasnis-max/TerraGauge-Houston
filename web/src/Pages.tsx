import { useEffect, useMemo, useState, type ReactNode } from "react";
import type { Cell, Meta } from "./types";
import { ACTION, CONFIDENCE, num } from "./labels";
import { CONFIDENCE_COLORS, CONTEXT_BAR, MUTED_BAR, UI } from "./palette";
import { ColumnChart, HBarChart, Scatter } from "./Charts";
import { MapFigure, type FigurePin } from "./MapFigure";
import { SquareTrend } from "./Card";
import { usePlaceName } from "./places";

/* The two reading pages, set like a newspaper: masthead, a ticker of key
   numbers, columns of text with figures and captions, and boxed sidebars. */

/** Plain names for the forecast methods we tested. */
const METHOD_NAMES: Record<string, string> = {
  seasonal_area: "Seasonal trend + neighborhood (ours)", robust_theil_sen: "Trend that ignores odd readings", area_smoothed: "Trend averaged with neighbors",
  long_term: "Ten-year trend", seasonal: "Trend allowing for seasons", recent_5yr: "Last five years only", recency_weighted: "Recent years count more",
  no_motion: "Assume no motion", ml_gradient_boosting: "Machine learning",
};

const longMonth = (d: string) => new Date(`${d.slice(0, 10)}T12:00:00Z`).toLocaleDateString("en-US", { month: "long", year: "numeric", timeZone: "UTC" });

function Ticker({ items }: { items: string[] }) {
  const run = (key: string) => <span className="ticker-run" key={key} aria-hidden="true">{items.map((t) => <span key={t}>{t}<i className="ticker-sep" /></span>)}</span>;
  return (
    <div className="ticker" role="marquee" aria-label={items.join(". ")}>
      <div className="ticker-track">{run("a")}{run("b")}</div>
      <p className="ticker-still">{items.join(" · ")}</p>
    </div>
  );
}

function Masthead({ section, title, deck, date, ticker }: { section: string; title: string; deck: string; date: string; ticker: string[] }) {
  return (
    <header className="masthead">
      <div className="mast-rule"><span>TerraGauge Houston</span><span>{section}</span><span>{date}</span></div>
      <h1 className="mast-title">{title}</h1>
      <p className="mast-deck">{deck}</p>
      <Ticker items={ticker} />
    </header>
  );
}

function Fig({ n, title, children, caption, wide }: { n: number; title: string; children: ReactNode; caption: ReactNode; wide?: boolean }) {
  return (
    <figure className={wide ? "figure span" : "figure"}>
      <p className="fig-title"><b>Figure {n}.</b> {title}</p>
      {children}
      <figcaption>{caption}</figcaption>
    </figure>
  );
}

function Gauge({ signal, noise, label }: { signal: number; noise: number; label: string }) {
  const pct = (v: number) => `${Math.max(0.8, (v / (noise * 1.05)) * 100)}%`;
  return (
    <div className="gauge">
      <p className="gauge-label">{label}</p>
      <div className="gauge-track" aria-hidden="true"><div className="gauge-noise" style={{ width: pct(noise) }} /><div className="gauge-signal" style={{ width: pct(signal) }} /></div>
      <div className="gauge-keys"><span><i className="k-signal" />Real ground movement in that time: {num(signal)} mm</span><span><i className="k-noise" />How much single readings wobble: {num(noise, 0)} mm</span></div>
    </div>
  );
}

function toCSV(cells: Cell[], meta: Meta): string {
  const years = meta.forecast?.years ?? [];
  const head = ["square_id", "longitude", "latitude", "rate_mm_per_year", "give_or_take_mm_per_year", "source", "confidence", "action", "flood_zone", "high_risk_flood_zone", ...years.map((y) => `forecast_${y}_cm`), "drought_level", "bending_level", "elevation_m"];
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

/** The full record of one square, from its details tile. */
function useDetailedCell(id: string | undefined) {
  const [cell, setCell] = useState<Cell | null>(null);
  useEffect(() => {
    const m = id ? /(-?\d+)-(-?\d+)$/.exec(id) : null;
    if (!id || !m) return;
    let live = true;
    fetch(`./data/details/${Math.floor(Number(m[1]) / 16)}_${Math.floor(Number(m[2]) / 16)}.json`).then((r) => r.json()).then((rows: Record<string, Cell>) => { if (live && rows[id]) setCell(rows[id]); }).catch(() => undefined);
    return () => { live = false; };
  }, [id]);
  return cell;
}

const pinsNear = (meta: Meta, lon: number, lat: number, km: number): FigurePin[] =>
  meta.sensors.filter((s) => Math.hypot((s.lon - lon) * 96.5, (s.lat - lat) * 111) < km).map((s) => ({ lon: s.lon, lat: s.lat, label: String(s.rank), kind: "station" }));

export function HowWeKnow({ meta, cells, onShow }: { meta: Meta; cells: Cell[]; onShow: (id: string) => void }) {
  const v = meta.validation, n = meta.nisar, f = meta.forecast, th = meta.thresholds, h = meta.hazards?.harvey, t = meta.hazards?.tests;
  const direct = cells.filter((c) => c.act !== "insufficient_data" && !c.src.includes("estimated")).length;
  const est = cells.filter((c) => c.src.includes("estimated")).length;
  const site = meta.sensors[0];
  const siteCell = useDetailedCell(site?.id);
  const place = usePlaceName(site ? `site-${site.rank}` : "none", site?.lon ?? 0, site?.lat ?? 0);
  const agree = v.points.filter((p) => Math.abs(p.sat - p.gps) <= 2).length;
  const years = `${meta.record.start.slice(0, 4)}–${meta.record.end.slice(0, 4)}`;
  const horizon = f ? String(Math.round(f.tested_horizon_years)) : "5";
  const bench = f ? [...f.benchmark.table].sort((a, b) => a.by_horizon_cm[horizon] - b.by_horizon_cm[horizon]) : [];
  const best = bench[0]?.by_horizon_cm[horizon];
  const ticker = [
    `${cells.length.toLocaleString()} squares mapped`, `${direct.toLocaleString()} measured directly`, `${v.stations} GPS stations checked`,
    `${num(v.typical_diff_mm_year)} mm a year typical gap`, ...(f ? [`${f.benchmark.table.length} forecast methods tested`] : []),
    `${meta.nisarArchive.processedPairs} NISAR image pairs`, ...(h ? [`${h.squares.toLocaleString()} squares checked against Hurricane Harvey`] : []),
  ];
  return (
    <div className="page paper">
      <Masthead section="How we know" title="How we know" date={longMonth(meta.nisarArchive.retrieved ?? meta.nisarArchive.last)}
        deck="Ten datasets, one map of 1 km squares, and every answer checked against the real world." ticker={ticker} />

      <article className="story">
        <h2 className="head">Measuring a sinking city from orbit</h2>
        <div className="cols three">
          <p className="dropcap">Radar satellites pass over Houston every few days and time how long their signal takes to bounce back from the ground. When the ground drops even a few millimeters, the echo returns a little later. NASA turns those tiny delays into maps of how far the ground moved, and has done so for Houston every few months since July 2016.</p>
          <p>TerraGauge cuts the region into {cells.length.toLocaleString()} squares, each one kilometer wide, from Katy to Baytown and from Spring to Pearland. For every square it gathers ten datasets and answers five questions: is the ground moving, how sure are we, how much more will it sink, what should Houston do here, and what would a flood or drought do.</p>
          <p>Where the satellite can't see the ground, such as lakes, bays and thick woods, the square says so. {est.toLocaleString()} squares with no reading of their own are estimated from measured neighbors, drawn lighter, and always marked low confidence. Nothing is filled in silently.</p>
          <p>The ten datasets come from NASA, NISAR, the U.S. Geological Survey, FEMA and the region's GPS network. Each answers a different part of the question, and none of them alone can say both where the ground is moving and how much to trust it.</p>
        </div>
        {site && <MapFigure cells={cells} meta={meta} mode="priority" year={0} center={[site.lon, site.lat]} zoom={11.2} pins={pinsNear(meta, site.lon, site.lat, 9)} height={340} onOpen={() => onShow(site.id)}
          caption={<><b>Figure 1. An urgent corner of {place ?? "west Houston"}.</b> Each square is 1 km wide. Pink squares are sinking inside a FEMA high-risk flood zone with a GPS station confirming it; amber squares are sinking there with no GPS within 2 km, and pin {site.rank} marks the best site for a new station. The area around it is sinking about {num(Math.abs(site.areaRate / 10))} cm a year.</>} />}
        <table className="table fact-table">
          <caption>Table 1. The datasets and what each one does</caption>
          <thead><tr><th>Data</th><th>Tells us</th><th>Used for</th></tr></thead>
          <tbody>
            <tr><td>NASA satellite radar, {years}</td><td>How far each square moved, every few months</td><td>Movement and the forecast</td></tr>
            <tr><td>NISAR, from {longMonth(meta.nisarArchive.first)}</td><td>The same, every 12 days, from NASA and India's new satellite</td><td>An independent check of the pattern</td></tr>
            <tr><td>HoustonNet GPS, {meta.stations.total} stations</td><td>Very precise movement at single points</td><td>Checking the satellite, and confidence</td></tr>
            <tr><td>FEMA flood zones</td><td>Official flood odds</td><td>Priority and the flood view</td></tr>
            <tr><td>USGS Harvey flood maps</td><td>Where Harvey's water reached</td><td>Checking the flood view</td></tr>
            <tr><td>USGS wells and soil gauges</td><td>Falling water levels and squeezing clay</td><td>Evidence in each square</td></tr>
            <tr><td>NASA elevation, water and land-change maps</td><td>Low ground, standing water, construction</td><td>Flood view, gaps and confidence</td></tr>
          </tbody>
        </table>
      </article>

      <article className="story">
        <h2 className="head">Does the satellite match the ground?</h2>
        <div className="spread">
          <div className="cols">
            <p className="dropcap">A satellite can be fooled by weather in the air, by construction, or by a bad reference point. So we held back {v.stations} GPS stations, each bolted to the ground and measuring its own height every day, and compared them with the satellite square they sit in. The satellite never learned from them.</p>
            <p>Typically the two are <b>{num(v.typical_diff_mm_year)} mm a year</b> apart, and they rise and fall together closely: {v.r.toFixed(2)} on a scale where 1 is a perfect match. {agree} of {v.points.length} stations agree within 2 mm a year. Where the two disagree by more than {th.disagree_mm_year} mm a year, the square is flagged for a closer look instead of hidden.</p>
            <p>GPS records cover different years than the satellite, so some difference is expected. {meta.stations.deepSeated.length} stations sit on anchors hundreds of meters underground and track deep ground, not the surface, so they are left out of this check.</p>
            <aside className="sidebar"><h3>Confidence, square by square</h3><ul>{(["high", "medium", "low"] as const).map((k) => <li key={k}><i className="key-box" style={{ background: CONFIDENCE[k].color }} /><b>{CONFIDENCE[k].name}.</b> {CONFIDENCE[k].meaning}</li>)}</ul></aside>
          </div>
          <div className="rail">
            <Fig n={2} title="Satellite against GPS, station by station" caption={<>Each dot is one GPS station: across is what the station measured, up is what the satellite saw in the same square, in mm a year. Dots on the line agree exactly. Teal dots agree within 2 mm a year, darker teal within 5, orange by more.</>}>
              <Scatter height={330} ariaLabel={`Satellite against GPS at ${v.points.length} stations`} xLabel="GPS station, mm a year" yLabel="Satellite, mm a year"
                points={v.points.map((p) => { const d = Math.abs(p.sat - p.gps); return { id: p.id, x: p.gps, y: p.sat, color: d <= 2 ? CONFIDENCE_COLORS.high : d <= 5 ? CONFIDENCE_COLORS.medium : UI.orange, note: `${num(d)} mm a year apart` }; })} />
            </Fig>
          </div>
        </div>
      </article>

      {meta.hazards && t && (
        <article className="story">
          <h2 className="head">What the moving ground does in a disaster</h2>
          <div className="spread">
            <div className="cols">
              <p className="dropcap">Nobody can say years ahead when a hurricane or drought will come. What the record can show is what Houston's moving ground does when one comes, and we tested each view on past disasters.</p>
              <h3 className="subhead">Floods</h3>
              <p>FEMA's flood maps give the odds of a big flood: a 1% chance each year in high-risk zones and 0.2% in moderate ones. Over a 30-year mortgage, 1% a year adds up to about a 26% chance. Sinking ground makes the same flood deeper by however much the ground has dropped, and the satellite measured that drop in every square since 2016. The flood view shows it directly, measured and not forecast. Real flooding also depends on drains, bayous and where the rain falls.</p>
              {h && <p>Checked against Hurricane Harvey, the flood odds hold up: high-risk squares had far more of their area flooded, and deeper, than low-risk ones. But {num(h.flooded_area_outside_high_risk_pct, 0)}% of Harvey's flooded area was outside the high-risk zones, which is why every square shows its flood zone and not just a yes or no. A square with no mapped zone counts as unknown, never as safe.</p>}
              <h3 className="subhead">Droughts</h3>
              <p>Houston's clay shrinks when it dries out. In the 2011 and 2023 droughts the city had thousands of water main breaks and widespread foundation cracks, and the satellite saw the ground drop below its normal trend. We pretended it was early 2023 and used only the 2018 drought to flag the 10% of squares most likely to drop. In the October 2023 drought, those squares typically dropped <b>{num(t.drought.flagged_median_drop_mm, 0)} mm</b>, against {num(t.drought.others_median_drop_mm, 0)} mm everywhere else. Drought damage repeats in the same places.</p>
              <h3 className="subhead">Ground bending and faults</h3>
              <p>Where one square sinks much faster than the next, the ground between them bends, straining pipes, roads and foundations. Houston's slowly slipping faults show up in radar as exactly this kind of sharp change. The squares bending most in 2016–2021 were still bending about {num(t.bending.hotspot_later_median / t.bending.others_later_median, 0)} times more than the rest in 2021–2026, so the hotspots are real and lasting. At 1 km wide, they mark zones to inspect, not exact fault lines.</p>
            </div>
            <div className="rail">
              <blockquote className="pull">Sinking doesn't change where a storm's water goes. It changes how deep the water stands once it gets there.</blockquote>
              {h && (() => { const row = (k: "1pct" | "0.2pct" | "minimal", name: string) => { const b = h.by_class[k], d = h.depth_by_class[k]; return b ? <tr key={k}><td>{name}</td><td>{b.squares.toLocaleString()}</td><td>{num(b.mean_flooded_share_pct, 0)}%</td><td>{d ? `${num(d.median_depth_ft)} ft` : "—"}</td></tr> : null; }; return (
                <table className="table">
                  <caption>Table 2. Hurricane Harvey, 2017, by FEMA zone</caption>
                  <thead><tr><th>Zone</th><th>Squares</th><th>Area flooded</th><th>Typical depth</th></tr></thead>
                  <tbody>{row("1pct", "High risk")}{row("0.2pct", "Moderate")}{row("minimal", "Low risk")}</tbody>
                </table>
              ); })()}
              {h && <p className="rail-note">From USGS maps of where Harvey's water reached, covering {h.squares.toLocaleString()} of our squares in {(h.areas ?? []).length ? (h.areas ?? []).map((a) => a.split(" (")[0]).join(" and ") : "north Houston"}.</p>}
            </div>
          </div>
        </article>
      )}

      {f && (
        <article className="story">
          <h2 className="head">How the forecast works, and how we tested it</h2>
          <div className="spread">
            <div className="cols">
              <p className="dropcap">To test a forecast honestly, we pretended it was an earlier date. Each method could only use satellite data up to that date, then had to say how far every square would sink one to five years later. We compared each answer with what really happened, from {f.benchmark.origins.length} different starting dates between {f.benchmark.origins[0].slice(0, 4)} and {f.benchmark.origins[f.benchmark.origins.length - 1].slice(0, 4)}.</p>
              <p>We tried {f.benchmark.table.length} methods, from "no motion" to a machine-learning model that learns from each square's past speed, its neighbors and its location. The winner is simple: each square's own trend, allowing for the clay's seasonal swing, averaged half and half with its neighborhood within 3 km.</p>
              <p>Machine learning came last, even behind "no motion". With ten years of data most of the error comes from weather-driven shrink and swell that no one can know years ahead, and the model learned quirks of particular years instead. With more years of radar, a model may eventually win.</p>
              <aside className="sidebar"><h3>What the forecast assumes</h3><ul>
                <li>Each square keeps its 2016–2026 trend, allowing for seasons and averaged with its neighborhood. It can't foresee changes in groundwater pumping or new rules.</li>
                <li>We tested it up to {f.tested_horizon_years.toFixed(0)} years ahead, {f.benchmark.test_cases} times, so we don't show later years.</li>
                <li>The likely range comes from the real misses in those tests: 8 in 10 squares fell inside it.</li>
                <li>Dry and wet years shrink and swell Houston's clay. Nobody can know those years ahead; the range covers them.</li>
              </ul></aside>
            </div>
            <div className="rail">
              <Fig n={3} title="How far off each method was, five years ahead" caption={<>Typical miss for one square, in cm, over every test. The method TerraGauge uses is highlighted; shorter is better.</>}>
                <HBarChart stacked ariaLabel="Typical forecast miss by method" format={(x) => `${num(x)} cm`}
                  rows={bench.map((r) => ({ label: METHOD_NAMES[r.method] ?? r.label, value: r.by_horizon_cm[horizon], color: r.method === f.method ? UI.accent : r.by_horizon_cm[horizon] === best ? UI.ink3 : MUTED_BAR }))} />
              </Fig>
              {site && siteCell && (
                <Fig n={4} title={`Ground level at suggested station site #${site.rank}`} caption={<>{place ? `${place}. ` : ""}Measured from {meta.record.start.slice(0, 4)} to {meta.record.end.slice(0, 4)}, then the forecast to {f.years[f.years.length - 1]}. The shaded range covers 8 in 10 of the misses in our tests, about ±{num(f.bands_cm[f.bands_cm.length - 1]?.half_width_cm)} cm at {f.tested_horizon_years.toFixed(0)} years. The forecast stops where the testing stops.</>}>
                  <SquareTrend cell={siteCell} meta={meta} height={210} />
                </Fig>
              )}
            </div>
          </div>
        </article>
      )}

      <article className="story">
        <h2 className="head">NISAR, NASA and India's newest radar</h2>
        <div className="spread">
          <div className="cols">
            <p className="dropcap">NISAR started imaging Houston in {longMonth(meta.nisarArchive.first)} and passes over every 12 days. We use all {meta.nisarArchive.processedPairs} of its Houston image pairs so far. Houston sinks a few millimeters over a few weeks, but the air between the satellite and the ground shifts a single reading by centimeters, so one pass can't yet measure Houston's slow sinking on its own.</p>
            <p>That's why every square says how long NISAR needs to confirm its sinking. At {n.detect[1]?.rate ?? 10} mm a year it takes about {n.detect[1]?.years ?? "—"} years of passes; faster sinking shows up sooner.</p>
            {meta.predictionTest && meta.predictionTest.status !== "scored" && <p>We also wrote down a prediction for NISAR's 2026 images before they existed. It has not been scored yet.</p>}
          </div>
          <div className="rail">
            <div className="figure">
              <p className="fig-title"><b>Figure 5.</b> Real movement against reading wobble</p>
              <Gauge signal={n.pair.signal_mm} noise={n.pair.noise_mm} label="One 12-day NISAR pair" />
              <Gauge signal={n.chain.signal_mm} noise={n.chain.noise_mm} label="Five pairs in a row, 60 days" />
            </div>
            {meta.predictionTest && (() => { const pt = meta.predictionTest; return pt.status === "scored" && pt.result && pt.verdict === "pass" ? (
              <aside className="sidebar accent"><h3>A prediction written down before the data existed</h3>
                <p>On 12 November 2026, before downloading NISAR's 2026 images, we wrote down a prediction and exactly how to score it: the areas the older radar record showed sinking fastest should also move most in NISAR's {pt.pairs} image pairs from {longMonth(pt.first)} to {longMonth(pt.last)}.</p>
                <p><b>It came true.</b> Grouped into 10 km areas, NISAR ranked them in nearly the same order ({num(Math.abs(pt.result.spearman_rho_block_medians), 2)}, where 1 is identical), and in 10,000 random shuffles chance never matched it. NISAR sees the same pattern, not yet the same speeds, so its speeds stay off the map for now.</p>
              </aside>
            ) : null; })()}
          </div>
        </div>
      </article>

      <article className="story">
        <h2 className="head">How each answer is decided</h2>
        <div className="boxes">
          <section><h3>Movement</h3><p>The satellite looks at the ground at a {th.incidence_deg}° slant, so we turn its reading into straight up-and-down movement, then blend in a GPS station when one sits within {th.gps_blend_km} km. Changes smaller than {num(th.stable_mm_year)} mm a year count as no clear motion: twice the wobble of GPS stations that aren't moving.</p></section>
          <section><h3>Priority, first rule that fits</h3><ol>{(["insufficient_data", "review_disagreement", "investigate_first", "add_monitoring", "observe", "no_clear_motion"] as const).map((k) => <li key={k}><b>{ACTION[k].name}.</b> {ACTION[k].meaning}</li>)}</ol></section>
          <section><h3>Sensor sites</h3><p>The numbered pins are "Add monitoring here" squares in the fastest-sinking areas, ranked by the typical rate within 3 km so one odd square can't top the list, and kept at least {th.sensor_spacing_km} km apart. Low-cost sensors are added until every such square has one within 6 km.</p></section>
          <section><h3>Shaky and missing squares</h3><p>About 1 in 10 squares has a shaky record. Each square's own rate is blended with its neighborhood, trusting steadier squares more; against GPS this cut the typical gap from 1.9 to 1.7 mm a year. Squares with no reading are estimated from at least {meta.estimates.min_neighbors} measured squares within {meta.estimates.radius_km} km; hidden-square tests put the typical error at {num(meta.estimates.median_error_mm_year)} mm a year.</p></section>
          <section><h3>Still to sign off</h3><p>Radar measures movement against a reference. We used {meta.reference.reference_stations.length} long-running GPS stations that barely move, and held {meta.reference.held_out_stable_stations.length} more back as a check. The team still has to review that choice.</p></section>
          <section><h3>Downloads</h3><p>Everything on the map, free to reuse.</p><div className="downloads">
            <button onClick={() => save("terragauge-houston-squares.csv", toCSV(cells, meta), "text/csv")}>All squares (CSV)</button>
            <a href="./data/cells.json" download>Squares (JSON)</a><a href="./data/meta.json" download>Tests and settings (JSON)</a><a href="./data/sites.json" download>GPS, wells, gauges (JSON)</a>
          </div></section>
        </div>
      </article>

      <footer className="sources">
        <h2>Sources</h2>
        <ul>
          <li>NASA JPL OPERA surface displacement products from Copernicus Sentinel-1 (frames F38238 and F38239), {meta.record.start} to {meta.record.end}, via the Alaska Satellite Facility.</li>
          <li>NASA/ISRO NISAR interferogram products, track 062 frame 016, {meta.nisarArchive.processedPairs} pairs, {meta.nisarArchive.first} to {meta.nisarArchive.last}.</li>
          <li>HoustonNet GPS 2024 release, University of Houston and the Harris-Galveston Subsidence District. Wang et al. (2022), J. Surv. Eng. 148(4): 04022008, for the deep-anchor stations.</li>
          <li>USGS groundwater daily values and the 2023 Houston extensometer release. Garvin, K.M. (2018), Hurricane Harvey flood inundation data, USGS, doi:10.5066/F7VH5N3N.</li>
          <li>FEMA National Flood Hazard Layer. NASA NASADEM elevation; NASA JPL OPERA surface water and land disturbance products.</li>
          <li>Address search and place names by OpenStreetMap Nominatim. Basemap © OpenFreeMap, © OpenMapTiles, © OpenStreetMap contributors.</li>
        </ul>
      </footer>
    </div>
  );
}

const rateUncertainty = (sigma: number, days: number, n: number) => (sigma / (days / 365.25)) * Math.sqrt(12 / (n * (n * n - 1)));
const utcTime = (iso: string) => iso.slice(11, 16);

/** Live status of our fixed-antenna test, from meta.groundtruth (scripts/export_web.py). */
const DIRECTIONS: [string, string][] = [["N", "North"], ["NE", "Northeast"], ["E", "East"], ["SE", "Southeast"], ["S", "South"], ["SW", "Southwest"], ["W", "West"], ["NW", "Northwest"]];
const signed = (v: number | null) => (v === null ? "—" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${num(Math.abs(v))} m`);

/** Recorded but too weak for a result: show what the sensor saw, and the rough heights with their limits. */
function GroundTruthData({ gt, note }: { gt: NonNullable<Meta["groundtruth"]>; note: string }) {
  const sig = gt.signal ?? [];
  const clear = gt.clearSkyDbHz ?? 40;
  const bars = DIRECTIONS.map(([k, name]) => {
    const vals = sig.map((s) => s.byDirection[k]).filter((v): v is number => typeof v === "number");
    const v = vals.length ? Math.round(vals.reduce((a, b) => a + b, 0) / vals.length) : 0;
    return { label: k, value: v, color: v >= clear ? UI.accent : CONTEXT_BAR, note: `${name}: ${vals.join(", ")} in sessions ${sig.filter((s) => typeof s.byDirection[k] === "number").map((s) => s.id.replace("session", "")).join(", ")}` };
  });
  const rough = gt.roughHeights;
  const spread = rough ? Math.max(...rough.methods.flatMap((m) => m.offsetsM.filter((v): v is number => v !== null))) - Math.min(...rough.methods.flatMap((m) => m.offsetsM.filter((v): v is number => v !== null))) : null;
  return (
    <>
      <div className="status-box">
        <p><b>Recorded: here is everything the sensor saw. No steadiness result.</b> {gt.reason ?? ""} {note}</p>
        <p>Nothing is corrupted: the sensor logged every second, and the files run through the whole processing chain. What fell short was the signal. Satellites to the north and east came in weak and kept losing track.</p>
      </div>
      <div className="table-scroll"><table className="table">
        <thead><tr><th>Session</th><th>Time (UTC)</th><th>Recorded</th><th>Satellites seen</th><th>Held steadily at once</th><th>Seconds with a lost signal</th></tr></thead>
        <tbody>{gt.sessions.map((x) => {
          const s = sig.find((y) => y.id === x.id);
          return (
            <tr key={x.id}>
              <td>{x.id.replace("session", "")}</td>
              <td>{x.window ? `${x.window[0].slice(0, 10)}, ${utcTime(x.window[0])}–${utcTime(x.window[1])}` : "—"}</td>
              <td>{s ? `${s.seconds.toLocaleString()} s` : x.hours === null ? "—" : `${num(x.hours)} h`}</td>
              <td>{s ? s.tracked : "—"}</td>
              <td>{s ? `About ${Math.round(s.steady)}` : "—"}</td>
              <td>{s?.breakShare != null ? `${Math.round(s.breakShare * 100)}%` : "—"}</td>
            </tr>
          );
        })}</tbody>
      </table></div>
      <p className="gt-note">"Held steadily" counts satellites tracked without a break for 10 minutes or more. Precise height needs many of those, spread all around the sky. A lost signal is a sudden jump between the sensor's two radio frequencies.</p>

      {sig.length > 0 && (
        <figure className="figure">
          <h3 className="fig-title">GPS signal strength by direction in the sky</h3>
          <ColumnChart bars={bars} height={190} ariaLabel="Average GPS signal strength by compass direction across the three sessions" format={(v) => `${v}`} />
          <figcaption>Average of the three sessions, satellites at least 15° above the horizon. Teal bars reach the open-sky level of about {clear}; gray bars fall short. The weak side was the same in every session, and even satellites high overhead averaged only {sig.map((s) => s.high).filter((v) => v !== null).join(", ")} in sessions 1–3.</figcaption>
        </figure>
      )}

      {rough && rough.methods.length > 0 && (
        <>
          <h3 className="fig-title gt-gap">Rough heights from each method we tried</h3>
          <div className="table-scroll"><table className="table">
            <thead><tr><th>Method</th>{gt.sessions.map((x) => <th key={x.id}>Session {x.id.replace("session", "")}</th>)}</tr></thead>
            <tbody>{rough.methods.map((m) => (
              <tr key={m.label}><td>{m.label}</td>{m.offsetsM.map((v, i) => <td key={i}>{v === null ? "Too few satellites" : signed(v)}</td>)}</tr>
            ))}</tbody>
          </table></div>
          <p className="gt-note">Heights are relative to each method's own average. The antenna never moved, so with good data every row would agree to within a few millimetres. Instead they differ by up to {spread === null ? "several" : num(spread)} m depending on the method, which is why none of them is a result and the sensor's daily wobble above stays a planning guess.</p>
        </>
      )}
    </>
  );
}

function GroundTruthStatus({ gt }: { gt: Meta["groundtruth"] }) {
  const note = "The sensor measures its own wobble with the antenna standing still, not Houston's sinking.";
  if (!gt || gt.status === "none") return <div className="status-box"><p><b>No recordings yet.</b> We report a result only after three good sessions checked against NOAA's reference station in Houston. {note}</p></div>;
  if (gt.status === "inconclusive") return <GroundTruthData gt={gt} note={note} />;
  if (gt.status === "recorded") return <div className="status-box"><p><b>{gt.recorded} session{gt.recorded === 1 ? "" : "s"} recorded, waiting on NOAA.</b> Each two-hour recording is checked against NOAA's reference station in Houston, whose data NOAA posts a few hours after each day ends. {note}</p></div>;
  return (
    <>
      <div className="status-box">
        {gt.pass && gt.scatterMm !== null
          ? <p><b>Result: between sessions, the sensor's height varied by {num(gt.scatterMm)} mm</b> across {gt.processed} sessions. {note} The planning guess stays until the team reviews this result.</p>
          : <p><b>{gt.processed} of {gt.recorded} sessions solved.</b> A result needs at least three good sessions. {note}</p>}
        {gt.days === 1 && <p>All sessions were on the same day, so this shows how steady the sensor is over a few hours. Sessions on different days would show its day-to-day steadiness, which is what tracking sinking depends on.</p>}
      </div>
      <table className="table">
        <thead><tr><th>Session</th><th>Time (UTC)</th><th>Length</th><th>Height vs. average</th><th>Solution</th></tr></thead>
        <tbody>{gt.sessions.map((x) => (
          <tr key={x.id}>
            <td>{x.id.replace("session", "")}</td>
            <td>{x.window ? `${x.window[0].slice(0, 10)}, ${utcTime(x.window[0])}–${utcTime(x.window[1])}` : "—"}</td>
            <td>{x.hours === null ? "—" : `${num(x.hours)} h`}</td>
            <td>{x.offsetMm === null ? "—" : `${x.offsetMm > 0 ? "+" : ""}${num(x.offsetMm)} mm`}</td>
            <td>{x.quality === "fixed" ? "Precise" : x.quality === "float" ? "Rough" : "—"}{x.fixedShare !== null ? ` (precise ${Math.round(x.fixedShare * 100)}% of the time)` : ""}</td>
          </tr>
        ))}</tbody>
      </table>
    </>
  );
}

export function HardwarePage({ meta, cells, onShow }: { meta: Meta; cells: Cell[]; onShow: (id: string) => void }) {
  const hw = meta.hardware;
  const gt = meta.groundtruth;
  const ours = gt && gt.pass && gt.processed >= 3 ? gt.sessions.map((x) => x.offsetMm ?? 0).join(", ") : "";
  const [heights, setHeights] = useState(ours);
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
    for (let k = 3; k < 20000; k++) if (rateUncertainty(sigma, gap, k) <= rate / 2) return k;
    return null;
  }, [sigma, rate, gap]);
  const center: [number, number] = [-95.42, 29.82];
  const pins: FigurePin[] = [...meta.nodes.map((x) => ({ lon: x.lon, lat: x.lat, kind: "node" as const })), ...meta.sensors.map((x) => ({ lon: x.lon, lat: x.lat, label: String(x.rank), kind: "station" as const }))];
  const ticker = [`${meta.sensors.length} permanent GPS station sites`, `${meta.nodes.length} low-cost sensor sites`, `${meta.gaps.length} sites where nothing measures yet`, "Prototype sensor: $74", `About ${hw.gps_weeks_10} weeks to confirm 1 cm a year`];
  return (
    <div className="page paper">
      <Masthead section="Hardware" title="Hardware" date={longMonth(meta.nisarArchive.retrieved ?? meta.nisarArchive.last)} deck="Satellites find the sinking. Sensors on the ground confirm it, and TerraGauge says exactly where each one would help most." ticker={ticker} />

      <article className="story">
        <h2 className="head">Why put a sensor on the ground?</h2>
        <div className="spread">
          <div className="cols">
            <p className="dropcap">A GPS receiver bolted to the ground measures its own height every day against NOAA's reference stations. If the ground under it sinks, the daily heights slowly drift down. After enough days the drift stands out from the daily wobble, and the sinking is confirmed. Faster sinking and a steadier sensor mean a shorter wait.</p>
            <p>The satellite already sees where Houston is sinking. A sensor turns that reading into proof at the exact spots where a city would spend money on drainage, levees or pumping rules, which is why TerraGauge suggests sites instead of spreading sensors evenly.</p>
            <p>A permanent station is steadier and confirms sinking faster, but costs hundreds of times more. A low-cost sensor can cover many more places for the same money, which matters in a region where {meta.counts.action.add_monitoring?.toLocaleString() ?? "many"} flood-zone squares are sinking with no GPS nearby.</p>
          </div>
          <div className="rail">
            <Fig n={1} title="Weeks to confirm sinking, best case" caption={<>Fewer weeks is better. Best case assumes the daily wobble is random; real readings also drift with the seasons, so agencies usually wait a few years before trusting a long-term rate.</>}>
              <ul className="chart-legend"><li><i className="key-box" style={{ background: UI.accent }} />Permanent GPS station</li><li><i className="key-box" style={{ background: UI.orange }} />Low-cost sensor</li></ul>
              <HBarChart ariaLabel="Weeks to confirm sinking" labelWidth={150} format={(x) => `${x} weeks`} rows={[
                { label: "1 cm a year", value: hw.gps_weeks_10, color: UI.accent },
                { label: "1 cm a year", value: hw.node_weeks_10, color: UI.orange },
                { label: "5 mm a year", value: hw.gps_weeks_5, color: UI.accent },
                { label: "5 mm a year", value: hw.node_weeks_5, color: UI.orange },
              ].map((r, i) => ({ ...r, label: `${r.label}${i % 2 ? ", low-cost" : ", station"}` }))} />
            </Fig>
          </div>
        </div>
        <div className="tier">
          <section>
            <h3>Basic: low-cost GPS sensor</h3>
            <dl>
              <div className="row"><dt>What it is</dt><dd>A small dual-band GPS board and antenna on a fixed post, with power and a data link</dd></div>
              <div className="row"><dt>Cost</dt><dd>About $74 for our prototype, up to $350–500 for a kit with a better antenna</dd></div>
              <div className="row"><dt>Daily wobble</dt><dd>About {hw.node_daily_sigma_mm} mm, a planning guess until our test measures it</dd></div>
              <div className="row"><dt>Best for</dt><dd>Covering many sinking areas cheaply</dd></div>
            </dl>
          </section>
          <section>
            <h3>Advanced: permanent GPS station</h3>
            <dl>
              <div className="row"><dt>What it is</dt><dd>A survey-grade receiver on a deep, stable mount, like the {meta.stations.total} HoustonNet stations</dd></div>
              <div className="row"><dt>Cost</dt><dd>About $20,000–30,000</dd></div>
              <div className="row"><dt>Daily wobble</dt><dd>About {hw.gps_daily_sigma_mm} mm</dd></div>
              <div className="row"><dt>Best for</dt><dd>Long-term anchors in the most important flood-zone areas</dd></div>
            </dl>
          </section>
        </div>
      </article>

      <article className="story">
        <h2 className="head">Where we would put them</h2>
        <MapFigure cells={cells} meta={meta} mode="priority" year={0} center={center} zoom={9.1} pins={pins} height={380}
          caption={<><b>Figure 2. Every suggested site.</b> Numbered pins are the {meta.sensors.length} permanent GPS station sites; orange diamonds are the {meta.nodes.length} low-cost sensor sites. Squares are colored by what each one needs, as on the main map.</>} />
        <div className="spread">
          <div className="cols">
            <p><b>Permanent stations</b> go to measured squares clearly sinking inside a FEMA high-risk flood zone with no GPS within {meta.thresholds.gps_covered_km} km, ranked by how fast the surrounding area sinks and kept {meta.thresholds.sensor_spacing_km} km apart.</p>
            <p><b>Low-cost sensors</b> go where the sinking is clear and fast enough for a cheap sensor to confirm within {hw.node_max_years} years, kept {hw.node_spacing_km} km apart, and then wherever a flagged flood-zone square still has no suggested site within 6 km.</p>
            <p><b>Sensors where nothing measures</b> go to land the satellite doesn't cover, at least 4 km from any working GPS, high-risk flood zones first. Their first job is simply to give a reading.</p>
          </div>
          <div className="rail">
            <aside className="sidebar"><h3>Top permanent station sites</h3><ol className="site-list">{meta.sensors.slice(0, 6).map((x) => <li key={x.id}><button className="text-btn" onClick={() => onShow(x.id)}>Site {x.rank}: sinking {num(Math.abs(x.areaRate / 10))} cm a year</button><small>{num(x.gpsKm)} km from the nearest GPS, flood zone {x.zone}</small></li>)}</ol></aside>
            <aside className="sidebar"><h3>Where nothing measures yet</h3><ol className="site-list">{meta.gaps.slice(0, 5).map((g) => <li key={g.id}><button className="text-btn" onClick={() => onShow(g.id)}>Site {g.rank}: {num(g.gpsKm)} km from any GPS</button><small>Flood zone {g.zone ?? "not mapped"}{g.sfha ? ", high risk" : ""}</small></li>)}</ol></aside>
          </div>
        </div>
      </article>

      <article className="story">
        <h2 className="head">Our own sensor test</h2>
        <div className="spread">
          <div className="cols one">
            <p className="dropcap">During the challenge we tested the basic sensor ourselves. The antenna is fixed to a metal sheet in a backyard and never moved, so any change in its readings is the sensor's own wobble. Once that wobble is measured, we compare it with the {hw.node_daily_sigma_mm} mm planning guess above.</p>
            <GroundTruthStatus gt={gt} />
          </div>
          <div className="rail">
            <aside className="sidebar calc">
              <h3>Try the calculator</h3>
              <label className="field">Heights from each session, in mm{ours ? ", filled in with ours" : ""}<input value={heights} onChange={(e) => setHeights(e.target.value)} placeholder="for example 11.2, 8.9, 10.4" inputMode="decimal" /></label>
              <div className="field-row">
                <label className="field">Sinking to spot, mm a year<input type="number" min={1} value={rate} onChange={(e) => setRate(Number(e.target.value))} /></label>
                <label className="field">Days between sessions<input type="number" min={1} value={gap} onChange={(e) => setGap(Number(e.target.value))} /></label>
              </div>
              {sigma !== null
                ? <p className="result">Wobble between sessions: <b>{sigma.toFixed(1)} mm</b>. To spot {rate} mm a year you'd need about <b>{needed ?? "20,000+"}</b> sessions{needed ? `, roughly ${Math.round(((needed - 1) * gap) / 7)} weeks` : ""}.</p>
                : <p className="muted">Enter at least three heights to see an estimate.</p>}
            </aside>
          </div>
        </div>
      </article>

      <footer className="sources">
        <h2>Sources</h2>
        <ul>
          <li>Hohensinn, R. et al. (2022), low-cost GPS receivers for ground-movement monitoring, Remote Sensing 14(20), 5100.</li>
          <li>Harris-Galveston Subsidence District, subsidence FAQs and GPS records.</li>
          <li>NOAA Continuously Operating Reference Stations (stations NETP and ZHU1), open data bucket noaa-cors-pds.</li>
          <li>CNES real-time multi-GNSS orbits, clocks and signal biases (ppp-wizard.net, file cnt24446), used for the satellites-only rough heights.</li>
        </ul>
      </footer>
    </div>
  );
}

