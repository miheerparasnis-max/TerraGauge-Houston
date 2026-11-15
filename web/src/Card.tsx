import { useEffect, useRef, useState } from "react";
import { usePlaceName } from "./places";
import type { Cell, Meta, SensorSite } from "./types";
import { ACTION, BEND, CONFIDENCE, DROUGHT, FLOOD, chanceOver, duration, floodExtra, headline, num, plain } from "./labels";
import { TrendChart, monthLabel, yearOf } from "./Charts";

/** Measured ground level since 2016 plus the tested forecast range, for one square. */
export function SquareTrend({ cell, meta, height }: { cell: Cell; meta: Meta; height?: number }) {
  if (!cell.series) return null;
  const cos = Math.cos((meta.thresholds.incidence_deg * Math.PI) / 180);
  const x = meta.record.dates.map(yearOf);
  const past = cell.series.map((v) => v / cos / 10);
  const t0 = x[x.length - 1];
  const future = cell.future && meta.forecast ? meta.forecast.years.map((y) => ({ t: y + (t0 % 1), label: `${y}`, ...cell.future!.by[String(y)] })) : [];
  return <TrendChart x={x} labels={meta.record.dates.map(monthLabel)} past={past} future={future} height={height} />;
}

function Row({ k, v, note }: { k: string; v: string; note?: string }) {
  return <div className="row"><dt>{k}</dt><dd>{v}{note && <span className="note">{note}</span>}</dd></div>;
}

function Section({ title, peek, open, children }: { title: string; peek?: string; open?: boolean; children: React.ReactNode }) {
  return (
    <details className="sec" open={open}>
      <summary><span className="sec-title">{title}</span>{peek && <span className="peek">{peek}</span>}</summary>
      <div className="sec-body">{children}</div>
    </details>
  );
}

/** Share of directly measured squares sinking slower than this one (0-100). */
function fasterThan(rate: number, sorted: number[]): number {
  let lo = 0, hi = sorted.length;
  while (lo < hi) { const mid = (lo + hi) >> 1; if (sorted[mid] <= rate) lo = mid + 1; else hi = mid; }
  return Math.round(100 * (1 - lo / sorted.length));
}

function download(cell: Cell) {
  const blob = new Blob([JSON.stringify(cell, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `terragauge-${cell.id}.json`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

export function Card({ cell, meta, sensor, year, ranks, onShare, onClose }: { cell: Cell; meta: Meta; sensor?: SensorSite; year: number; ranks: number[]; onShare: () => string; onClose: () => void }) {
  const a = ACTION[cell.act];
  const th = meta.thresholds;
  const f = meta.forecast;
  const measured = cell.act !== "insufficient_data" && cell.rate !== null;
  const estimated = cell.src.includes("estimated");
  const sources = estimated && cell.adj ? `the ${cell.adj} measured squares touching it (it falls between the satellite's grid blocks)` : estimated ? (cell.estFrom === "gps" ? `an estimate from ${cell.est} GPS stations nearby (outside the satellite's coverage)` : `an estimate from ${cell.est} measured squares nearby`) : cell.src.length === 2 ? "satellite and a GPS station inside the square, combined" : cell.src[0] === "gps" ? "a GPS station inside the square" : "NASA satellite radar";
  const [copied, setCopied] = useState(false);
  const ref = useRef<HTMLElement>(null);
  useEffect(() => { ref.current?.closest(".panel")?.scrollTo({ top: 0 }); }, [cell.id]);
  const pctile = measured && cell.sig && cell.rate !== null && cell.rate < 0 && ranks.length ? fasterThan(cell.rate, ranks) : null;
  const share = async () => {
    const url = onShare();
    try { await navigator.clipboard.writeText(url); setCopied(true); setTimeout(() => setCopied(false), 1800); } catch { window.prompt("Copy this link", url); }
  };
  const yv = cell.future?.by[String(year)];
  const place = usePlaceName(cell.id, cell.lon, cell.lat);
  return (
    <article className="card" aria-labelledby="card-title" ref={ref}>
      <div className="card-head">
        <div className="actions">
          <button onClick={share}>{copied ? "Link copied" : "Copy link"}</button>
          <button onClick={() => download(cell)}>Download</button>
          <button onClick={() => { document.querySelectorAll<HTMLDetailsElement>(".card details").forEach((d) => (d.open = true)); window.print(); }}>Print</button>
          <button className="close" onClick={onClose} aria-label="Close">×</button>
        </div>
        <h2 id="card-title"><span className="badge" style={{ background: a.color }} />{a.name}</h2>
        {place && <p className="place">Near {place}</p>}
      </div>
      <p className="why">{plain(cell.actWhy)}</p>

      <div className="headline-stats">
        <div><strong>{measured ? `${num(cell.rate)}` : "—"}</strong><span>mm a year{measured ? (!cell.sig ? ", too small to call" : cell.rate! < 0 ? ", sinking" : ", rising") : ""}</span></div>
        {yv && <div><strong>{num(yv.c)}</strong><span>cm change by {year}, likely {num(yv.lo)} to {num(yv.hi)}</span></div>}
        {cell.conf && <div><strong className="conf"><i style={{ background: CONFIDENCE[cell.conf].color }} />{CONFIDENCE[cell.conf].name}</strong><span>confidence</span></div>}
      </div>
      {pctile !== null && <p className="pctile">{pctile >= 99 ? <>Among the <b>fastest-sinking 1%</b> of measured Houston squares.</> : <>Sinking faster than <b>{pctile}%</b> of measured Houston squares.</>}</p>}
      <div className="chips">
        {sensor && <span className="chip pin-chip">GPS station site #{sensor.rank}</span>}
        {cell.nodeRank && <span className="chip">Low-cost sensor site #{cell.nodeRank}</span>}
        {cell.gapRank && <span className="chip">Sensor where nothing measures #{cell.gapRank}</span>}
        {estimated && <span className="chip">{cell.adj ? "Filled from touching squares" : "Estimated, not measured"}</span>}
      </div>
      <div className="matters"><h3>Why it matters here</h3><p>{a.why}</p></div>

      <Section title={headline(cell, th.stable_mm_year)} peek={measured ? `${num(cell.rate)} mm a year` : undefined} open>
        {measured ? (
          <dl>
            <Row k="Up and down" v={`${num(cell.rate)} mm a year`} note={`Give or take ${num(cell.se)} mm. ${meta.record.start.slice(0, 4)}–${meta.record.end.slice(0, 4)}, from ${sources}.`} />
            {cell.raw !== null && cell.raw !== undefined && <Row k="This square on its own" v={`${num(cell.raw)} mm a year`} note="Its own satellite record is shaky, so the map blends it with the squares around it, trusting the steadier ones more. Checked against GPS stations, the blend was closer than the raw readings." />}
            {!estimated && cell.los !== null && <Row k="What the radar sees" v={`${num(cell.los)} mm a year`} note={`The satellite looks at the ground at a ${th.incidence_deg}° slant. We turn that into straight up-and-down movement.`} />}
          </dl>
        ) : <p className="muted">{plain(cell.actWhy)}</p>}
      </Section>

      {cell.future && f && (
        <Section title="How much more will it sink?" peek={yv ? `${num(yv.c)} cm by ${year}` : undefined} open>
          <SquareTrend cell={cell} meta={meta} height={170} />
          <dl>{f.years.map((y) => { const v = cell.future!.by[String(y)]; return <Row key={y} k={`By ${y}`} v={`${num(v.c)} cm`} note={`likely ${num(v.lo)} to ${num(v.hi)} cm`} />; })}</dl>
          <p className="fine">Change in ground level since {monthLabel(f.base)}, at {num(cell.future.rate)} mm a year: this square's own trend, allowing for seasons, averaged with its neighborhood{cell.future.recent !== null ? `. The last five years alone ran ${num(cell.future.recent)} mm a year` : ""}. The likely range covers 8 in 10 of the misses in our tests.</p>
          <details className="fine"><summary>Why a straight line?</summary>We tested {f.benchmark.table.length} ways to forecast, including machine learning, by pretending it was an earlier date and predicting 1 to 5 years ahead, {f.benchmark.test_cases.toLocaleString()} times each. The winner carries each square's trend forward, allowing for seasons and averaged with its neighborhood. Real ground wiggles around the line (dry years shrink Houston's clay, wet years swell it), and nobody can know those years in advance, so the shaded range comes from the real misses in those tests.</details>
        </Section>
      )}

      <Hazards cell={cell} meta={meta} year={year} />

      {cell.conf && (
        <Section title="How sure are we?" peek={CONFIDENCE[cell.conf].name}>
          <ul className="reasons">{cell.confWhy.map((r) => <li key={r}>{plain(r)}</li>)}</ul>
          <dl>
            {cell.check && <Row k="GPS check" v={`${num(Math.abs(cell.check.diff))} mm a year apart`} note={`Station ${cell.check.id}, ${num(cell.check.km)} km away`} />}
            {cell.quality.periods !== null && <Row k="Clear radar snapshots" v={`${cell.quality.periods} of ${cell.quality.periodsTotal}`} note="Snapshots where the satellite could see the ground clearly" />}
            {cell.quality.fitSe !== null && <Row k="How steady the trend is" v={`give or take ${num(cell.quality.fitSe)} mm a year`} />}
          </dl>
        </Section>
      )}

      {cell.detect && (
        <Section title="How long to confirm it?" peek={cell.detect.gpsWeeks !== null ? `GPS: ~${Math.max(1, cell.detect.gpsWeeks)} weeks` : undefined}>
          <dl>
            <Row k="NISAR, NASA and India's new satellite" v={duration(cell.detect.nisarMonths)} note="of passes every 12 days, given how much its readings over Houston wobble" />
            <Row k="A permanent GPS station" v={cell.detect.gpsWeeks === null ? "—" : `about ${Math.max(1, cell.detect.gpsWeeks)} weeks`} note={`assuming its height wobbles ${th.gps_daily_sigma_mm} mm a day`} />
            <Row k="A low-cost GPS sensor" v={cell.detect.nodeWeeks === null ? "more than 4 years" : `about ${Math.max(1, cell.detect.nodeWeeks)} weeks`} note={`assuming ${meta.hardware.node_daily_sigma_mm} mm a day until our own sensor test measures it`} />
          </dl>
          <p className="fine">Best case. Weather and the site itself usually make the wait longer.</p>
        </Section>
      )}

      <Section title="Sensors" peek={`nearest GPS ${num(cell.gps.km)} km`}>
        <dl><Row k="Nearest working GPS" v={`${num(cell.gps.km)} km away`} note={`Station ${cell.gps.id}: ${num(cell.gps.up)} mm a year${cell.gps.y0 ? ` over ${cell.gps.y0}–${cell.gps.y1}` : ""}`} /></dl>
        {sensor ? <p className="good">Suggested permanent GPS station site #{sensor.rank} of {meta.sensors.length}. Why here: the area around it is sinking about {num(Math.abs(sensor.areaRate))} mm a year in a high-risk flood zone, the nearest GPS is {num(sensor.gpsKm)} km away, and our confidence here is only {cell.conf ? CONFIDENCE[cell.conf].name.toLowerCase() : "low"}. A station turns that uncertain satellite reading into a firm one where it matters most for flooding.</p>
          : cell.gapRank ? <p className="good">Sensor site #{cell.gapRank} of {meta.gaps.length} for places nothing measures: no satellite coverage here and the nearest GPS is {num(cell.gps.km)} km away. A low-cost sensor gives the first reading.</p>
          : cell.nodeRank ? <p className="good">Suggested low-cost sensor site #{cell.nodeRank} of {meta.nodes.length}: {cell.detect?.nodeWeeks ? `sinking fast enough that a cheap sensor could confirm it in about ${cell.detect.nodeWeeks} weeks, ` : ""}with no GPS within {th.gps_covered_km} km.</p>
          : cell.act === "add_monitoring" && cell.near ? <p className="good">Needs a sensor: no GPS within {th.gps_covered_km} km. The nearest suggested site is {cell.near.kind === "gps" ? `permanent GPS station #${cell.near.rank}` : `low-cost sensor #${cell.near.rank}`}, {num(cell.near.km)} km away.</p>
          : cell.act === "add_monitoring" ? <p className="good">Needs a sensor: no GPS within {th.gps_covered_km} km.</p>
          : cell.gps.km <= th.gps_covered_km ? <p className="muted">Covered: a GPS station is within {th.gps_covered_km} km.</p>
          : <p className="muted">Not a sensor priority right now: no clear sinking here.</p>}
      </Section>

      <Section title="Other evidence" peek={cell.flood.zone ? `flood zone ${cell.flood.zone}` : undefined}>
        <dl>
          <Row k="Flood zone (FEMA)" v={cell.flood.sfha ? `${cell.flood.zone}: high risk` : cell.flood.zone ?? "Not mapped"} note={[cell.flood.sub, cell.flood.share !== undefined && cell.flood.share !== null ? `${Math.round(cell.flood.share * 100)}% of the square is in the 1-in-100-year zone` : null].filter(Boolean).join(". ") || undefined} />
          {cell.well && <Row k="Groundwater well" v={`${num(cell.well.km)} km away`} note={cell.well.dd === null ? undefined : `Water ${cell.well.dd >= 0 ? `${num(cell.well.dd)} ft lower` : `${num(-cell.well.dd)} ft higher`}, Jan 2025 to Nov 2026 (USGS)`} />}
          {cell.ext && <Row k="Soil compaction gauge" v={`${num(cell.ext.km)} km away`} note={cell.ext.c === null ? undefined : `Clay squeezed ${num(cell.ext.c, 2)} ft over its record (USGS)`} />}
          {cell.quality.nisarCoh !== null && <Row k="NISAR, Nov 2025" v={cell.quality.nisarOk ? "Clear view of the ground" : "Blurry view of the ground"} note={`${cell.quality.nisarValid === null ? "—" : Math.round(cell.quality.nisarValid * 100)}% of the square was readable`} />}
          {cell.nasadem?.elevation_m !== undefined && <Row k="Elevation (NASA)" v={`${num(cell.nasadem.elevation_m)} m`} />}
          {cell.dswx?.water_fraction !== undefined && <Row k="Standing water (NASA satellite)" v={`${Math.round(cell.dswx.water_fraction * 100)}% of passes`} />}
          {cell.dist?.disturbed_fraction !== undefined && <Row k="Construction or clearing (NASA satellite)" v={`${Math.round(cell.dist.disturbed_fraction * 100)}% of the square`} />}
        </dl>
      </Section>

      <Section title="What we can't conclude">
        <ul className="reasons">
          <li>This is a 1 km average. It says nothing about any single building or property.</li>
          <li>It does not tell you whether this spot floods, or exactly why the ground is moving.</li>
          <li>The radar looks at the ground at a slant; we assume the ground moves straight up and down.</li>
          <li>The forecast assumes the next five years behave like the last ten, with no big change in groundwater pumping.</li>
        </ul>
      </Section>
      <p className="fine">Square centered at {cell.lat.toFixed(4)}°N, {Math.abs(cell.lon).toFixed(4)}°W</p>
    </article>
  );
}


/** What the measured ground does to floods, droughts and bending here. */
function Hazards({ cell, meta, year }: { cell: Cell; meta: Meta; year: number }) {
  const fl = floodExtra(cell, meta);
  const hz = cell.hz;
  if (!fl.cls && !hz) return null;
  const odds = fl.cls === "1pct" ? 0.01 : fl.cls === "0.2pct" || fl.cls === "levee" ? 0.002 : 0;
  const pct = (p: number) => `${Math.round(p * 100)}%`;
  return (
    <Section title="If a disaster hit here" open>
      {fl.cls && (
        <div className="hazard">
          <h4><span className="badge" style={{ background: fl.cls === "1pct" && (fl.total ?? 0) >= 3 ? FLOOD.deeper.color : FLOOD[fl.cls].color }} />Flood: {FLOOD[fl.cls].name.toLowerCase()}</h4>
          <p>{odds > 0
            ? <>A flood this big has about a <b>{odds * 100}% chance each year</b> here ({pct(chanceOver(odds, 5))} over 5 years, {pct(chanceOver(odds, 30))} over a 30-year mortgage). </>
            : <>FEMA rates this area as low flood risk, though Hurricane Harvey flooded many areas like it. </>}
            {fl.total !== null && fl.total > 0.5
              ? <>The ground here has dropped about <b>{num(fl.total)} cm</b> since {fl.since}, so the same flood now stands about {num(fl.total)} cm deeper than it would have then.</>
              : fl.total !== null ? <>The ground here hasn't clearly dropped since {fl.since}, so floods here aren't deeper because of sinking.</> : null}
          </p>
          {cell.harvey && <p className="harvey">{cell.harvey.wet > 0
            ? <>In <b>Hurricane Harvey</b> (2017), about {Math.round(cell.harvey.wet * 100)}% of this square flooded{cell.harvey.ft !== null ? <>, on average {num(cell.harvey.ft)} ft deep where it was wet</> : null} (USGS flood maps).</>
            : <>USGS flood maps show this square stayed dry in <b>Hurricane Harvey</b> (2017).</>}</p>}
        </div>
      )}
      {hz && (
        <div className="hazard">
          <h4><span className="badge" style={{ background: DROUGHT[hz.dl].color }} />Drought: {DROUGHT[hz.dl].name.toLowerCase()}</h4>
          <p>{hz.drop > 2
            ? <>In the 2018 and 2023 droughts this ground dropped about <b>{num(hz.drop, 0)} mm more</b> than a typical Houston square as its clay dried out. </>
            : <>In the 2018 and 2023 droughts this ground behaved like most of Houston. </>}
            {hz.dl === "high" ? "Places like this are where the next drought is most likely to crack foundations, driveways and water mains." : hz.dl === "medium" ? "Expect more drought damage here than in most of Houston." : ""}
          </p>
        </div>
      )}
      {hz?.bl && (
        <div className="hazard">
          <h4><span className="badge" style={{ background: BEND[hz.bl].color }} />Ground bending: {BEND[hz.bl].name.toLowerCase()}</h4>
          <p>The sinking speed changes by <b>{num(hz.bend)} mm a year</b> between this square and the next one over. {hz.bl === "high" ? "Uneven sinking like this bends pipes, roads and slabs, and in Houston it often marks one of the city's slowly slipping faults." : hz.bl === "medium" ? "Some uneven sinking; worth watching for cracks in roads and pipes." : "The ground sinks evenly here, which is easier on buildings and pipes."}</p>
        </div>
      )}
      <p className="fine">These say nothing about when a storm or drought comes, only what the moving ground does when one does. Flood odds are FEMA's; how far the ground dropped is measured by satellite.</p>
    </Section>
  );
}
