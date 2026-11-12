import { useEffect, useRef, useState } from "react";
import { usePlaceName } from "./places";
import type { Cell, Meta, SensorSite } from "./types";
import { ACTION, BEND, CONFIDENCE, DROUGHT, FLOOD, chanceOver, duration, floodExtra, headline, num } from "./labels";

const yearOf = (d: string) => Number(d.slice(0, 4)) + (Number(d.slice(5, 7)) - 1) / 12 + (Number(d.slice(8, 10)) - 1) / 365;

/** Measured ground level since 2016 plus the tested forecast range. */
function TrendChart({ cell, meta }: { cell: Cell; meta: Meta }) {
  if (!cell.series) return null;
  const cos = Math.cos((meta.thresholds.incidence_deg * Math.PI) / 180);
  const past = cell.series.map((v, i) => ({ t: yearOf(meta.record.dates[i]), cm: v / cos / 10 }));
  const t0 = past[past.length - 1].t, base = past[past.length - 1].cm;
  const fut = cell.future && meta.forecast ? meta.forecast.years.map((y) => ({ t: y + (t0 % 1), ...cell.future!.by[String(y)] })) : [];
  const w = 340, h = 150, padL = 34, padR = 20, padT = 14, padB = 22;
  const xs = [past[0].t, fut.length ? fut[fut.length - 1].t : t0];
  const vals = [...past.map((p) => p.cm), ...fut.flatMap((f) => [base + f.lo, base + f.hi]), 0];
  const lo = Math.min(...vals), hi = Math.max(...vals);
  const sx = (t: number) => padL + ((t - xs[0]) / (xs[1] - xs[0] || 1)) * (w - padL - padR);
  const sy = (v: number) => padT + (1 - (v - lo) / (hi - lo || 1)) * (h - padT - padB);
  const pastPath = past.map((p, i) => `${i ? "L" : "M"}${sx(p.t).toFixed(1)},${sy(p.cm).toFixed(1)}`).join("");
  const cone = fut.length ? [`M${sx(t0)},${sy(base)}`, ...fut.map((f) => `L${sx(f.t)},${sy(base + f.hi)}`), ...fut.slice().reverse().map((f) => `L${sx(f.t)},${sy(base + f.lo)}`), "Z"].join("") : "";
  const mid = fut.length ? [`M${sx(t0)},${sy(base)}`, ...fut.map((f) => `L${sx(f.t)},${sy(base + f.c)}`)].join("") : "";
  const span = hi - lo, step = span > 60 ? 20 : span > 30 ? 10 : span > 12 ? 5 : 2;
  const ticks: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) ticks.push(v);
  const xticks = [2016, 2020, 2024, ...(fut.length ? [Math.round(xs[1])] : [])].filter((t) => t >= xs[0] - 0.5 && t <= xs[1] + 0.5);
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="trend" role="img" aria-label="Measured ground level since 2016 and the forecast range">
      {ticks.map((v) => <g key={v}><line x1={padL} x2={w - padR} y1={sy(v)} y2={sy(v)} className="grid" /><text x={padL - 4} y={sy(v) + 3} textAnchor="end" className="tick">{v}</text></g>)}
      {cone && <path d={cone} className="cone" />}
      {mid && <path d={mid} className="mid" />}
      <path d={pastPath} className="past" />
      <line x1={sx(t0)} x2={sx(t0)} y1={padT} y2={h - padB} className="now" />
      {xticks.map((t) => <text key={t} x={sx(t)} y={h - 6} textAnchor="middle" className="tick">{t}</text>)}
      <text x={2} y={9} className="tick">cm</text>
    </svg>
  );
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
  const sources = estimated ? (cell.estFrom === "gps" ? `an estimate from ${cell.est} GPS stations nearby (outside the satellite's coverage)` : `an estimate from ${cell.est} measured squares nearby`) : cell.src.length === 2 ? "satellite and a GPS station inside the square, combined" : cell.src[0] === "gps" ? "a GPS station inside the square" : "satellite (NASA OPERA)";
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
      <p className="why">{cell.actWhy}</p>

      <div className="headline-stats">
        <div><strong>{measured ? `${num(cell.rate)}` : "—"}</strong><span>mm a year{measured ? (cell.rate! < 0 ? ", sinking" : ", rising") : ""}</span></div>
        {yv && <div><strong>{num(yv.c)}</strong><span>cm change by {year}, likely {num(yv.lo)} to {num(yv.hi)}</span></div>}
        {cell.conf && <div><strong className="conf"><i style={{ background: CONFIDENCE[cell.conf].color }} />{CONFIDENCE[cell.conf].name}</strong><span>confidence</span></div>}
      </div>
      {pctile !== null && <p className="pctile">Sinking faster than <b>{pctile}%</b> of measured Houston squares.</p>}
      <div className="chips">
        {sensor && <span className="chip pin-chip">GPS station site #{sensor.rank}</span>}
        {cell.nodeRank && <span className="chip">Low-cost node site #{cell.nodeRank}</span>}
        {cell.gapRank && <span className="chip">Fill-the-gap node #{cell.gapRank}</span>}
        {estimated && <span className="chip">Estimated, not measured</span>}
      </div>
      <div className="matters"><h3>Why it matters here</h3><p>{a.why}</p></div>

      <Section title={headline(cell, th.stable_mm_year)} peek={measured ? `${num(cell.rate)} ± ${num(cell.se)} mm/yr` : undefined} open>
        {measured ? (
          <dl>
            <Row k="Up and down" v={`${num(cell.rate)} ± ${num(cell.se)} mm/yr`} note={`${meta.record.start.slice(0, 4)}–${meta.record.end.slice(0, 4)}, from ${sources}`} />
            {cell.raw !== null && cell.raw !== undefined && <Row k="This square's own reading" v={`${num(cell.raw)} mm/yr`} note="Its satellite record is noisy, so the map combines it with the squares around it, weighting each by how precise it is. In tests this matched GPS stations better than the raw readings." />}
            {!estimated && cell.los !== null && <Row k="Satellite's slanted view" v={`${num(cell.los)} mm/yr`} note={`What the radar measures directly. Converted to up/down assuming the ground moves vertically (${th.incidence_deg}° viewing angle).`} />}
          </dl>
        ) : <p className="muted">{cell.actWhy}</p>}
      </Section>

      {cell.future && f && (
        <Section title="How much will it sink?" peek={yv ? `${num(yv.c)} cm by ${year}` : undefined} open>
          <TrendChart cell={cell} meta={meta} />
          <p className="legend-line"><span className="k-past" />Measured <span className="k-mid" />Forecast <span className="k-cone" />Likely range (80%)</p>
          <dl>{f.years.map((y) => { const v = cell.future!.by[String(y)]; return <Row key={y} k={`By ${y}`} v={`${num(v.c)} cm`} note={`likely ${num(v.lo)} to ${num(v.hi)} cm`} />; })}</dl>
          <p className="fine">Change in ground level since {f.base.slice(0, 7)}, at {num(cell.future.rate)} mm a year: the square's season-aware trend averaged with its neighborhood{cell.future.recent !== null ? `. The last 5 years alone were ${num(cell.future.recent)} mm a year` : ""}.</p>
          <details className="fine"><summary>Why a straight line?</summary>We tested {f.benchmark.table.length} forecasting methods, including machine learning, by pretending it was an earlier date and predicting 1 to 5 years ahead, {f.benchmark.test_cases} tests each. The winner continues each square's season-aware trend, averaged with its neighborhood. Real ground wiggles around the line (dry years shrink Houston's clay, wet years swell it), and nobody can predict those years ahead, so the shaded range comes from the real errors in those tests.</details>
        </Section>
      )}

      <Hazards cell={cell} meta={meta} year={year} />

      {cell.conf && (
        <Section title="How sure are we?" peek={CONFIDENCE[cell.conf].name}>
          <ul className="reasons">{cell.confWhy.map((r) => <li key={r}>{r}</li>)}</ul>
          <dl>
            {cell.check && <Row k="GPS cross-check" v={`${num(Math.abs(cell.check.diff))} mm/yr apart`} note={`Station ${cell.check.id}, ${num(cell.check.km)} km away`} />}
            {cell.quality.periods !== null && <Row k="Satellite periods used" v={`${cell.quality.periods} of ${cell.quality.periodsTotal}`} note="Periods with a clear view of the ground" />}
            {cell.quality.fitSe !== null && <Row k="Trend fit error" v={`± ${num(cell.quality.fitSe)} mm/yr`} />}
          </dl>
        </Section>
      )}

      {cell.detect && (
        <Section title="How long to confirm it?" peek={cell.detect.gpsWeeks !== null ? `GPS: ~${Math.max(1, cell.detect.gpsWeeks)} weeks` : undefined}>
          <dl>
            <Row k="NASA's NISAR satellite" v={duration(cell.detect.nisarMonths)} note="of passes every 12 days, based on NISAR's measured noise over Houston" />
            <Row k="A permanent GPS station" v={cell.detect.gpsWeeks === null ? "—" : `about ${Math.max(1, cell.detect.gpsWeeks)} weeks`} note={`assuming ${th.gps_daily_sigma_mm} mm of daily noise`} />
            <Row k="A low-cost GPS node" v={cell.detect.nodeWeeks === null ? "more than 4 years" : `about ${Math.max(1, cell.detect.nodeWeeks)} weeks`} note={`assuming ${meta.hardware.node_daily_sigma_mm} mm of daily noise until our hardware test measures it`} />
          </dl>
          <p className="fine">Best-case estimates. Real atmospheric and site noise make the wait longer.</p>
        </Section>
      )}

      <Section title="Sensors" peek={`nearest GPS ${num(cell.gps.km)} km`}>
        <dl><Row k="Nearest active GPS" v={`${num(cell.gps.km)} km away`} note={`Station ${cell.gps.id}: ${num(cell.gps.up)} mm/yr${cell.gps.y0 ? ` over ${cell.gps.y0}–${cell.gps.y1}` : ""}`} /></dl>
        {sensor ? <p className="good">Suggested permanent GPS station site #{sensor.rank} of {meta.sensors.length}: the area around it is sinking about {num(Math.abs(sensor.areaRate))} mm/yr in a high-risk flood zone, and the nearest GPS is {num(sensor.gpsKm)} km away.</p>
          : cell.gapRank ? <p className="good">Fill-the-gap node site #{cell.gapRank} of {meta.gaps.length}: no satellite coverage here and the nearest GPS is {num(cell.gps.km)} km away, so nothing measures this ground directly. A low-cost node gives the first reading.</p>
          : cell.nodeRank ? <p className="good">Suggested low-cost node site #{cell.nodeRank} of {meta.nodes.length}: sinking fast enough that a cheap node could confirm it in about {cell.detect?.nodeWeeks} weeks, and no GPS within {th.gps_covered_km} km.</p>
          : cell.act === "add_monitoring" ? <p className="good">Needs a sensor: no GPS within {th.gps_covered_km} km. Faster-sinking areas rank higher on the sensor list.</p>
          : cell.gps.km <= th.gps_covered_km ? <p className="muted">Covered: a GPS station is within {th.gps_covered_km} km.</p>
          : <p className="muted">Not a sensor priority right now: no clear sinking here.</p>}
      </Section>

      <Section title="Other evidence" peek={cell.flood.zone ? `flood zone ${cell.flood.zone}` : undefined}>
        <dl>
          <Row k="Flood zone (FEMA)" v={cell.flood.sfha ? `${cell.flood.zone}: high risk` : cell.flood.zone ?? "Not mapped"} note={[cell.flood.sub, cell.flood.share !== undefined && cell.flood.share !== null ? `${Math.round(cell.flood.share * 100)}% of the square is in the 1-in-100-year zone` : null].filter(Boolean).join(". ") || undefined} />
          {cell.well && <Row k="Groundwater well" v={`${num(cell.well.km)} km away`} note={cell.well.dd === null ? undefined : `Water ${cell.well.dd >= 0 ? `${num(cell.well.dd)} ft deeper` : `${num(-cell.well.dd)} ft shallower`}, Jan 2025 to Nov 2026 (USGS)`} />}
          {cell.ext && <Row k="Soil compaction gauge" v={`${num(cell.ext.km)} km away`} note={cell.ext.c === null ? undefined : `Squeezed ${num(cell.ext.c, 2)} ft over its record (USGS extensometer)`} />}
          {cell.quality.nisarCoh !== null && <Row k="NISAR pass, Nov 2025" v={cell.quality.nisarOk ? "Good quality" : "Poor quality"} note={`coherence ${num(cell.quality.nisarCoh, 2)}, ${cell.quality.nisarValid === null ? "—" : Math.round(cell.quality.nisarValid * 100)}% valid pixels`} />}
          {cell.nasadem?.elevation_m !== undefined && <Row k="Elevation (NASADEM)" v={`${num(cell.nasadem.elevation_m)} m`} />}
          {cell.dswx?.water_fraction !== undefined && <Row k="Surface water (OPERA DSWx)" v={`${Math.round(cell.dswx.water_fraction * 100)}% of passes`} />}
          {cell.dist?.disturbed_fraction !== undefined && <Row k="Construction or clearing (OPERA DIST)" v={`${Math.round(cell.dist.disturbed_fraction * 100)}% of the square`} />}
        </dl>
      </Section>

      <Section title="What we can't conclude">
        <ul className="reasons">
          <li>This is a 1 km average. It says nothing about any single building or property.</li>
          <li>It does not tell you whether this spot floods, or exactly why the ground is moving.</li>
          <li>Up-and-down rates assume the ground moves vertically; the radar measures at a slant.</li>
          <li>The forecast assumes the next five years behave like the last ten, with no big change in groundwater pumping.</li>
        </ul>
      </Section>
      <p className="fine">Square {cell.id} at {cell.lat.toFixed(4)}, {cell.lon.toFixed(4)}</p>
    </article>
  );
}


/** What the measured ground does to floods, droughts and bending here. */
function Hazards({ cell, meta, year }: { cell: Cell; meta: Meta; year: number }) {
  const fl = floodExtra(cell, year, meta);
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
              ? <>By {year} the same flood would be about <b>{num(fl.total)} cm deeper</b>{fl.ocean > 0 ? <> ({num(fl.sink)} cm from the ground sinking, {num(fl.ocean)} cm from ocean rise)</> : <>, because the ground here is forecast to sink that much</>}.</>
              : fl.total !== null ? <>The ground here isn't forecast to sink much, so floods shouldn't get deeper by {year}.</> : null}
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
      <p className="fine">These don't predict when a storm or drought comes, only what the moving ground does when one does. Flood odds are FEMA's; depth changes are our forecast.</p>
    </Section>
  );
}
