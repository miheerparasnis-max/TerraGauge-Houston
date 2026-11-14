import type { Cell, Meta, SensorSite } from "./types";
import { CONFIDENCE, PRIORITY, headline, num } from "./labels";

function Row({ k, v, note }: { k: string; v: string; note?: string }) {
  return <div className="row"><dt>{k}</dt><dd>{v}{note && <span className="note">{note}</span>}</dd></div>;
}

export function Card({ cell, meta, sensor, onClose }: { cell: Cell; meta: Meta; sensor?: SensorSite; onClose: () => void }) {
  const p = PRIORITY[cell.pri];
  const sources = cell.src[0] === "gps" ? "GPS station" : "Satellite (OPERA)";
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
          <li>It does not predict future sinking or flood damage; those outputs are deliberately withheld.</li>
        </ul>
      </details>
      <p className="fine">Square {cell.id} at {cell.lat.toFixed(4)}, {cell.lon.toFixed(4)}</p>
    </article>
  );
}
