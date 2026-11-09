import type { Cell, Meta, SensorSite } from "./types";
import { ACTION, CONFIDENCE, duration, headline, num } from "./labels";

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

export function Card({ cell, meta, sensor, onClose }: { cell: Cell; meta: Meta; sensor?: SensorSite; onClose: () => void }) {
  const a = ACTION[cell.act];
  const th = meta.thresholds;
  const f = meta.forecast;
  const measured = cell.act !== "insufficient_data" && cell.rate !== null;
  const estimated = cell.src.includes("estimated");
  const sources = estimated ? `an estimate from ${cell.est} measured squares nearby` : cell.src.length === 2 ? "satellite and a GPS station inside the square, combined" : cell.src[0] === "gps" ? "a GPS station inside the square" : "satellite (NASA OPERA)";
  return (
    <article className="card" aria-labelledby="card-title">
      <button className="close" onClick={onClose} aria-label="Close">×</button>
      <p className="eyebrow-label">Priority</p>
      <h2 id="card-title"><span className="badge" style={{ background: a.color }} />{a.name}</h2>
      <p className="why">{cell.actWhy}</p>
      <div className="matters"><h3>Why it matters here</h3><p>{a.why}</p></div>
      <div className="chips">
        {cell.conf && <span className="chip" style={{ ["--c" as string]: CONFIDENCE[cell.conf].color }}><i />Confidence: {CONFIDENCE[cell.conf].name}</span>}
        {sensor && <span className="chip pin-chip">GPS station site #{sensor.rank}</span>}
        {cell.nodeRank && <span className="chip">Low-cost node site #{cell.nodeRank}</span>}
        {estimated && <span className="chip">Estimated, not measured</span>}
      </div>

      <section className="block">
        <h3>{headline(cell, th.stable_mm_year)}</h3>
        {measured ? (
          <dl>
            <Row k="Up and down" v={`${num(cell.rate)} ± ${num(cell.se)} mm/yr`} note={`${meta.record.start.slice(0, 4)}–${meta.record.end.slice(0, 4)}, from ${sources}`} />
            {!estimated && cell.los !== null && <Row k="Satellite's slanted view" v={`${num(cell.los)} mm/yr`} note={`What the radar measures directly. Converted to up/down assuming the ground moves vertically (${th.incidence_deg}° viewing angle).`} />}
          </dl>
        ) : <p className="muted">The satellite couldn't get a reliable reading here, and no GPS station is inside the square.</p>}
      </section>

      {cell.conf && (
        <section className="block">
          <h3>How sure are we?</h3>
          <ul className="reasons">{cell.confWhy.map((r) => <li key={r}>{r}</li>)}</ul>
          <dl>
            {cell.check && <Row k="GPS cross-check" v={`${num(Math.abs(cell.check.diff))} mm/yr apart`} note={`Station ${cell.check.id}, ${num(cell.check.km)} km away`} />}
            {cell.quality.periods !== null && <Row k="Satellite periods used" v={`${cell.quality.periods} of ${cell.quality.periodsTotal}`} note="Periods with a clear view of the ground" />}
            {cell.quality.fitSe !== null && <Row k="Trend fit error" v={`± ${num(cell.quality.fitSe)} mm/yr`} />}
          </dl>
        </section>
      )}

      {cell.future && f && (
        <section className="block">
          <h3>How much will it sink?</h3>
          <TrendChart cell={cell} meta={meta} />
          <p className="legend-line"><span className="k-past" />Measured <span className="k-mid" />Forecast <span className="k-cone" />Likely range (80%)</p>
          <dl>
            <Row k={`Rate, ${f.base.slice(0, 4)}–${f.years[f.years.length - 1]}`} v={`${num(cell.future.rate)} mm/yr`} note={`likely ${num(cell.future.low)} to ${num(cell.future.high)}; it was ${num(cell.future.recent)} mm/yr over the last 5 years`} />
          </dl>
          <details className="fine"><summary>Why is the forecast line straight?</summary>The model predicts this square's average speed for the next five years, so the forecast is a straight line at that speed. We tested a bending path (speed changing smoothly) and it was less accurate every year. Real ground wiggles around any line, for example when dry years shrink Houston's clay, and nobody can predict those years ahead, so the shaded range is built from the real wiggles we saw in testing.</details>
          <p className="fine">Change in ground level since {f.base.slice(0, 7)}</p>
          <dl>{f.years.map((y) => { const v = cell.future!.by[String(y)]; return <Row key={y} k={`By ${y}`} v={`${num(v.c)} cm`} note={`likely ${num(v.lo)} to ${num(v.hi)} cm`} />; })}</dl>
        </section>
      )}

      {cell.detect && (
        <section className="block">
          <h3>How long to confirm it?</h3>
          <dl>
            <Row k="NASA's NISAR satellite" v={duration(cell.detect.nisarMonths)} note="of passes every 12 days, based on NISAR's measured noise over Houston" />
            <Row k="A permanent GPS station" v={cell.detect.gpsWeeks === null ? "—" : `about ${Math.max(1, cell.detect.gpsWeeks)} weeks`} note={`assuming ${th.gps_daily_sigma_mm} mm of daily noise`} />
            <Row k="A low-cost GPS node" v={cell.detect.nodeWeeks === null ? "more than 4 years" : `about ${Math.max(1, cell.detect.nodeWeeks)} weeks`} note={`assuming ${meta.hardware.node_daily_sigma_mm} mm of daily noise until our hardware test measures it`} />
          </dl>
          <p className="fine">Best-case estimates. Real atmospheric and site noise make the wait longer.</p>
        </section>
      )}

      <section className="block">
        <h3>Sensors</h3>
        <dl><Row k="Nearest active GPS" v={`${num(cell.gps.km)} km away`} note={`Station ${cell.gps.id}: ${num(cell.gps.up)} mm/yr${cell.gps.y0 ? ` over ${cell.gps.y0}–${cell.gps.y1}` : ""}`} /></dl>
        {sensor ? <p className="good">Suggested permanent GPS station site #{sensor.rank} of {meta.sensors.length}: the area around it is sinking about {num(Math.abs(sensor.areaRate))} mm/yr in a high-risk flood zone, and the nearest GPS is {num(sensor.gpsKm)} km away.</p>
          : cell.nodeRank ? <p className="good">Suggested low-cost node site #{cell.nodeRank} of {meta.nodes.length}: sinking fast enough that a cheap node could confirm it in about {cell.detect?.nodeWeeks} weeks, and no GPS within {th.gps_covered_km} km.</p>
          : cell.act === "add_monitoring" ? <p className="good">Needs a sensor: no GPS within {th.gps_covered_km} km. Faster-sinking areas rank higher on the sensor list.</p>
          : cell.gps.km <= th.gps_covered_km ? <p className="muted">Covered: a GPS station is within {th.gps_covered_km} km.</p>
          : <p className="muted">Not a sensor priority right now: no clear sinking here.</p>}
      </section>

      <section className="block">
        <h3>Other evidence</h3>
        <dl>
          <Row k="Flood zone (FEMA)" v={cell.flood.sfha ? `${cell.flood.zone}: high risk` : cell.flood.zone ?? "Not mapped"} note={cell.flood.sub ?? undefined} />
          {cell.well && <Row k="Groundwater well" v={`${num(cell.well.km)} km away`} note={cell.well.dd === null ? undefined : `Water ${cell.well.dd >= 0 ? `${num(cell.well.dd)} ft deeper` : `${num(-cell.well.dd)} ft shallower`}, Jan 2025 to Nov 2026 (USGS)`} />}
          {cell.ext && <Row k="Soil compaction gauge" v={`${num(cell.ext.km)} km away`} note={cell.ext.c === null ? undefined : `Squeezed ${num(cell.ext.c, 2)} ft over its record (USGS extensometer)`} />}
          <Row k="NISAR pass, Nov 2025" v={cell.quality.nisarOk ? "Good quality" : "Poor quality"} note={`coherence ${num(cell.quality.nisarCoh, 2)}, ${cell.quality.nisarValid === null ? "—" : Math.round(cell.quality.nisarValid * 100)}% valid pixels`} />
          {cell.nasadem?.elevation_m !== undefined && <Row k="Elevation (NASADEM)" v={`${num(cell.nasadem.elevation_m)} m`} />}
          {cell.dswx?.water_fraction !== undefined && <Row k="Surface water (OPERA DSWx)" v={`${Math.round(cell.dswx.water_fraction * 100)}% of passes`} />}
          {cell.dist?.disturbed_fraction !== undefined && <Row k="Construction or clearing (OPERA DIST)" v={`${Math.round(cell.dist.disturbed_fraction * 100)}% of the square`} />}
        </dl>
      </section>

      <details className="block">
        <summary>What we can't conclude</summary>
        <ul className="reasons">
          <li>This is a 1 km average. It says nothing about any single building or property.</li>
          <li>It does not say this spot will flood, or why the ground is moving.</li>
          <li>Up-and-down rates assume the ground moves vertically; the radar measures at a slant.</li>
          <li>The forecast assumes the next five years behave like the last ten, with no big change in groundwater pumping.</li>
        </ul>
      </details>
      <p className="fine">Square {cell.id} at {cell.lat.toFixed(4)}, {cell.lon.toFixed(4)}</p>
    </article>
  );
}
