import type { Cell, Meta, SensorSite } from "./types";
import { CONFIDENCE, PRIORITY, headline, num } from "./labels";

const COS = Math.cos((38 * Math.PI) / 180);
const yearOf = (d: string) => Number(d.slice(0, 4)) + (Number(d.slice(5, 7)) - 1) / 12;

/** Past (measured) and future (projected) ground level in cm, on one chart. */
function TrendChart({ cell, meta }: { cell: Cell; meta: Meta }) {
  if (!cell.series || !cell.future) return null;
  const past = cell.series.map((v, i) => ({ t: yearOf(meta.record.dates[i]), cm: v / COS / 10 }));
  const t0 = past[past.length - 1].t;
  const base = past[past.length - 1].cm;
  const fut = meta.forecast.years.map((y) => ({ t: y, ...cell.future![String(y)] }));
  const w = 340, h = 150, padL = 34, padR = 20, padT = 14, padB = 22;
  const xs = [past[0].t, fut[fut.length - 1].t];
  const all = [...past.map((p) => p.cm), ...fut.flatMap((f) => [base + f.low_mm, base + f.high_mm]), 0];
  const lo = Math.min(...all), hi = Math.max(...all);
  const sx = (t: number) => padL + ((t - xs[0]) / (xs[1] - xs[0])) * (w - padL - padR);
  const sy = (v: number) => padT + (1 - (v - lo) / (hi - lo || 1)) * (h - padT - padB);
  const pastPath = past.map((p, i) => `${i ? "L" : "M"}${sx(p.t).toFixed(1)},${sy(p.cm).toFixed(1)}`).join("");
  const cone = [`M${sx(t0)},${sy(base)}`, ...fut.map((f) => `L${sx(f.t)},${sy(base + f.high_mm)}`), ...fut.slice().reverse().map((f) => `L${sx(f.t)},${sy(base + f.low_mm)}`), "Z"].join("");
  const mid = [`M${sx(t0)},${sy(base)}`, ...fut.map((f) => `L${sx(f.t)},${sy(base + f.center_mm)}`)].join("");
  const ticks = niceTicks(lo, hi);
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="trend" role="img" aria-label="Measured ground level since 2016 and the projected range to 2040">
      {ticks.map((v) => <g key={v}><line x1={padL} x2={w - padR} y1={sy(v)} y2={sy(v)} className="grid" /><text x={padL - 4} y={sy(v) + 3} textAnchor="end" className="tick">{v}</text></g>)}
      <path d={cone} className="cone" />
      <path d={mid} className="mid" />
      <path d={pastPath} className="past" />
      <line x1={sx(t0)} x2={sx(t0)} y1={padT} y2={h - padB} className="now" />
      {[past[0].t, t0, ...meta.forecast.years].map((t) => <text key={t} x={sx(t)} y={h - 6} textAnchor="middle" className="tick">{Math.round(t)}</text>)}
      <text x={2} y={9} className="tick">cm</text>
    </svg>
  );
}

function niceTicks(lo: number, hi: number) {
  const span = hi - lo;
  const step = span > 60 ? 20 : span > 30 ? 10 : span > 12 ? 5 : 2;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) out.push(v);
  return out;
}

function Row({ k, v, note }: { k: string; v: string; note?: string }) {
  return <div className="row"><dt>{k}</dt><dd>{v}{note && <span className="note">{note}</span>}</dd></div>;
}

export function Card({ cell, meta, sensor, onClose }: { cell: Cell; meta: Meta; sensor?: SensorSite; onClose: () => void }) {
  const p = PRIORITY[cell.pri];
  const f = meta.forecast;
  const lastYear = f.years[f.years.length - 1];
  const sources = cell.src.length === 2 ? "Satellite and GPS combined" : cell.src[0] === "gps" ? "GPS station" : "Satellite (OPERA)";
  return (
    <article className="card" aria-labelledby="card-title">
      <button className="close" onClick={onClose} aria-label="Close">×</button>
      <h2 id="card-title">{headline(cell)}</h2>
      {cell.rate !== null && cell.pri !== "no_data" && (
        <p className="sub">{num(cell.rate)} ± {num(cell.se)} mm a year, {meta.record.start.slice(0, 4)} to {meta.record.end.slice(0, 4)}. {sources}.</p>
      )}
      <div className="chips">
        <span className="chip" style={{ ["--c" as string]: p.color }}><i />Priority: {p.name}</span>
        {cell.conf && <span className="chip" style={{ ["--c" as string]: CONFIDENCE[cell.conf].color }}><i />Confidence: {CONFIDENCE[cell.conf].name}</span>}
        {sensor && <span className="chip pin-chip">Sensor site #{sensor.rank}</span>}
      </div>
      <p className="why">{cell.priWhy}</p>

      {cell.conf && (
        <section className="block">
          <h3>How sure are we?</h3>
          <ul className="reasons">{cell.confWhy.map((r) => <li key={r}>{r}</li>)}</ul>
        </section>
      )}

      {cell.future && (
        <section className="block">
          <h3>Where is it heading?</h3>
          <TrendChart cell={cell} meta={meta} />
          <p className="legend-line"><span className="k-past" />Measured <span className="k-mid" />If the trend continues <span className="k-cone" />Likely range</p>
          <p className="fine">Change in ground level compared with {f.base.slice(0, 4)}</p>
          <dl>{f.years.map((y) => { const v = cell.future![String(y)]; return <Row key={y} k={`By ${y}`} v={`${num(v.center_mm)} cm`} note={`likely ${num(v.low_mm)} to ${num(v.high_mm)} cm`} />; })}</dl>
          {f.mode === "scenario" && <p className="caution">This is a "what if the {meta.record.start.slice(0, 4)}–{meta.record.end.slice(0, 4)} trend continues" scenario, not a tested forecast. Our test found the fastest areas slowed after {f.backtest.test[0].slice(0, 4)}, so by {lastYear} the real change is likely smaller.</p>}
        </section>
      )}

      <section className="block">
        <h3>Sensors</h3>
        <dl>
          <Row k="Nearest permanent GPS" v={`${num(cell.gps.km)} km away`} note={`Station ${cell.gps.id}, ${num(cell.gps.up)} mm a year${cell.gps.y0 ? `, ${cell.gps.y0}–${cell.gps.y1}` : ""}`} />
        </dl>
        {sensor ? <p className="good">Suggested sensor site #{sensor.rank} of {meta.sensors.length}: the squares around it are sinking about {num(Math.abs(sensor.areaRate))} mm a year, and the closest GPS station is {num(sensor.gpsKm)} km away.</p>
          : cell.needsSensor ? <p className="good">No GPS station within {meta.thresholds.gps_covered_km} km. A sensor here would confirm what the satellite sees.</p>
          : cell.gps.km <= meta.thresholds.gps_covered_km ? <p className="muted">Already covered: a GPS station is within {meta.thresholds.gps_covered_km} km.</p>
          : <p className="muted">No sensor needed while the ground looks stable.</p>}
      </section>

      <section className="block">
        <h3>Other evidence</h3>
        <dl>
          <Row k="Flood zone (FEMA)" v={cell.flood.sfha ? `${cell.flood.zone}: high risk` : cell.flood.zone ?? "Not mapped"} note={cell.flood.sub ?? undefined} />
          {cell.well && <Row k="Groundwater well" v={`${num(cell.well.km)} km away`} note={cell.well.dd === null ? undefined : `Water ${cell.well.dd >= 0 ? `${num(cell.well.dd)} ft deeper` : `${num(-cell.well.dd)} ft shallower`}, Jan 2025 to Nov 2026 (USGS)`} />}
          {cell.ext && <Row k="Soil compaction gauge" v={`${num(cell.ext.km)} km away`} note={cell.ext.c === null ? undefined : `Squeezed ${num(cell.ext.c, 2)} ft over its record (USGS extensometer)`} />}
          {cell.check && <Row k="GPS cross-check" v={`${num(cell.check.km)} km away`} note={`Station ${cell.check.id} differs from the satellite by ${num(Math.abs(cell.check.diff))} mm a year`} />}
          <Row k="Newest satellite (NISAR)" v={cell.nisar.ok ? "Good-quality pass" : "Poor-quality pass"} note="Nov 2025. Too few passes yet to measure Houston's slow sinking." />
          {cell.nasadem?.elevation_m !== undefined && <Row k="Elevation (NASADEM)" v={`${num(cell.nasadem.elevation_m)} m`} />}
          {cell.dswx?.water_fraction !== undefined && <Row k="Surface water (OPERA DSWx)" v={`${Math.round(cell.dswx.water_fraction * 100)}% of passes`} note="Water spoils radar readings" />}
          {cell.dist?.disturbed_fraction !== undefined && <Row k="Construction or clearing (OPERA DIST)" v={`${Math.round(cell.dist.disturbed_fraction * 100)}% of the square`} note="Can look like ground movement" />}
        </dl>
      </section>

      <details className="block">
        <summary>What we can't conclude</summary>
        <ul className="reasons">
          <li>This is a 1 km average. It says nothing about any single building or property.</li>
          <li>It does not say this spot will flood, or why the ground is moving.</li>
          <li>Satellites measure motion at a slant; we convert to up and down assuming the motion is mostly vertical.</li>
          <li>The future range is a projection from past data, not a guarantee.</li>
        </ul>
      </details>
      <p className="fine">Square {cell.id} at {cell.lat.toFixed(4)}, {cell.lon.toFixed(4)}</p>
    </article>
  );
}
