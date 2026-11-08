import type { Cell, Meta, ViewKey } from "./types";
import { LABELS, VIEWS, fmt } from "./labels";

function Sparkline({ series, dates }: { series: number[]; dates: string[] }) {
  const w = 300, h = 84, pad = 6;
  const years = dates.map((d) => Number(d.slice(0, 4)) + (Number(d.slice(5, 7)) - 1) / 12);
  const x0 = years[0], x1 = years[years.length - 1];
  const lo = Math.min(0, ...series), hi = Math.max(0, ...series);
  const sx = (t: number) => pad + ((t - x0) / (x1 - x0)) * (w - 2 * pad);
  const sy = (v: number) => pad + (1 - (v - lo) / (hi - lo || 1)) * (h - 2 * pad);
  const path = series.map((v, i) => `${i ? "L" : "M"}${sx(years[i]).toFixed(1)},${sy(v).toFixed(1)}`).join("");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="spark" role="img" aria-label={`Cumulative OPERA line-of-sight displacement from ${dates[0]} to ${dates[dates.length - 1]}, ending at ${series[series.length - 1].toFixed(1)} mm`}>
      <line x1={pad} x2={w - pad} y1={sy(0)} y2={sy(0)} className="spark-zero" />
      <path d={path} className="spark-line" />
      {series.map((v, i) => <circle key={i} cx={sx(years[i])} cy={sy(v)} r={2} className="spark-dot" />)}
      <text x={pad} y={h - 1} className="spark-axis">{dates[0].slice(0, 4)}</text>
      <text x={w - pad} y={h - 1} textAnchor="end" className="spark-axis">{dates[dates.length - 1].slice(0, 4)}</text>
    </svg>
  );
}

function Row({ k, v, note }: { k: string; v: string; note?: string }) {
  return (
    <div className="row">
      <dt>{k}</dt>
      <dd>{v}{note ? <span className="note">{note}</span> : null}</dd>
    </div>
  );
}

export function EvidenceCard({ cell, view, meta, onClose }: { cell: Cell; view: ViewKey; meta: Meta; onClose: () => void }) {
  const code = cell.L[view];
  const label = LABELS[code];
  const reasons = cell.R[view].map((i) => meta.reasons[i]);
  const t = meta.thresholds;
  const v = meta.views;
  return (
    <article className="card" aria-labelledby="card-title">
      <header className="card-head">
        <div>
          <p className="card-view">{VIEWS[view].short}</p>
          <h2 id="card-title"><span className={`badge badge-${code}`} />{label.name}</h2>
        </div>
        <button className="close" onClick={onClose} aria-label="Close evidence card">×</button>
      </header>
      <p className="action">{label.action}</p>
      <ul className="reasons">{reasons.map((r) => <li key={r}>{r}</li>)}</ul>
      {meta.status !== "reviewed" && <p className="provisional">Provisional: the reference stations and processing choices have not yet been reviewed by the team.</p>}

      <section className={view === "o" ? "block focus" : "block"}>
        <h3>Historic motion, OPERA {v.opera.dates[0].slice(0, 4)}–{v.opera.dates[1].slice(0, 4)}</h3>
        {cell.o ? (
          <>
            <dl>
              <Row k="Line-of-sight velocity" v={`${fmt(cell.o.v, 1, "mm/yr")} ± ${fmt(cell.o.se, 1)}`} note={Math.abs(cell.o.v) < v.opera.threshold_mm_year ? "Within the noise threshold: no clear motion" : cell.o.v < 0 ? "Away from satellite, consistent with sinking" : "Toward satellite, consistent with uplift"} />
              <Row k="Total over the record" v={fmt(cell.o.cum, 1, "mm")} />
            </dl>
            <Sparkline series={cell.o.s} dates={v.opera.dates_all} />
          </>
        ) : <p className="empty">No OPERA velocity: this cell failed the valid-pixel or water check in at least one of {v.opera.products} products, usually because of vegetation or water.</p>}
      </section>

      <section className={view !== "o" ? "block focus" : "block"}>
        <h3>New observation, NISAR</h3>
        <dl>
          <Row k="12-day change, 2–14 Nov 2025" v={fmt(cell.n.d, 1, "mm")} note={cell.n.raw !== null ? `before reference and ramp removal ${fmt(cell.n.raw, 1, "mm")}` : undefined} />
          <Row k="60-day change, 2 Nov–1 Jan" v={fmt(cell.ch.d, 1, "mm")} />
          <Row k="Coherence (12-day)" v={fmt(cell.n.coh, 2)} note={`needs ≥ ${t.coherence_min.toFixed(2)}`} />
          <Row k="Valid pixels (12-day)" v={cell.n.vf === null ? "—" : `${Math.round(cell.n.vf * 100)}%`} note={`needs ≥ ${Math.round(t.valid_fraction_min * 100)}%`} />
          <Row k="Main connected component" v={cell.n.main ? "Yes" : "No"} />
        </dl>
        <p className="caution">Real Houston motion over 12 days is about {fmt(meta.signal_check.pair.expected_signal_sd_mm, 1, "mm")}; NISAR noise here is about {fmt(meta.signal_check.pair.nisar_sd_mm, 0, "mm")}. Treat NISAR values as a quality preview, not a motion measurement.</p>
      </section>

      <section className="block">
        <h3>Ground evidence</h3>
        <dl>
          <Row k="Nearest GPS station" v={cell.g.id ? `${cell.g.id}, ${fmt(cell.g.km, 1, "km")}` : "—"} note={cell.g.up !== null ? `${fmt(cell.g.up, 1, "mm/yr")} vertical, ${cell.g.y0?.toFixed(0)}–${cell.g.y1?.toFixed(0)}; historic context, not time-matched` : undefined} />
          <Row k="Nearest groundwater well" v={cell.w.id ? `${fmt(cell.w.km, 1, "km")}` : "—"} note={cell.w.dd !== null ? `water ${cell.w.dd >= 0 ? `${cell.w.dd.toFixed(2)} ft deeper` : `${(-cell.w.dd).toFixed(2)} ft shallower`}, Jan 2025–Nov 2026` : undefined} />
          <Row k="Nearest extensometer" v={cell.e.id ? `${fmt(cell.e.km, 1, "km")}` : "—"} note={cell.e.c !== null ? `${cell.e.c.toFixed(2)} ft cumulative compaction` : undefined} />
          <Row k="FEMA flood zone" v={cell.f.z ?? "Not mapped"} note={cell.f.sub ?? undefined} />
          {cell.nasadem && <Row k="Elevation (NASADEM)" v={fmt(cell.nasadem.elevation_m as number, 1, "m")} />}
          {cell.dswx && <Row k="Surface water (OPERA DSWx)" v={`${Math.round((cell.dswx.water_fraction as number) * 100)}%`} note="Nov 2025 to Jan 2026; water spoils radar readings" />}
          {cell.dist && <Row k="Land disturbance (OPERA DIST)" v={`${Math.round((cell.dist.disturbed_fraction as number) * 100)}%`} note="construction or clearing can mimic motion" />}
        </dl>
      </section>

      <details className="block">
        <summary>Decision rule</summary>
        <ol className="rule">
          <li>Insufficient evidence if radar quality fails (coherence below {t.coherence_min.toFixed(2)}, under {Math.round(t.valid_fraction_min * 100)}% valid pixels, or outside the main connected component). For OPERA, if any product fails.</li>
          <li>A candidate signal must exceed {t.sigma_multiplier}× the noise measured at reference GPS stations{view === "o" ? ` (${fmt(v.opera.threshold_mm_year, 1, "mm/yr")}) and twice its own fit error` : ` (${fmt(view === "p" ? v.pair.threshold_mm : v.chain.threshold_mm, 1, "mm")})`}.</li>
          <li>Candidate with no permanent GPS station within {t.gps_nearby_km} km: Add ground monitoring.</li>
          <li>Candidate with a station nearby: Investigate signal.</li>
          <li>Everything else: Context only. Flood zones are reported but never create a label on their own.</li>
        </ol>
      </details>

      <details className="block">
        <summary>What TerraGauge cannot conclude</summary>
        <ul className="limits">
          <li>Radar measures line-of-sight motion, not vertical sinking.</li>
          <li>A label is a monitoring priority, not a finding about any property.</li>
          <li>Groundwater and compaction records are context; they do not prove what caused a signal.</li>
          <li>A FEMA zone is not flood depth, flood probability, or a forecast.</li>
          <li>Historic GPS rates are not time-matched to the NISAR dates.</li>
        </ul>
      </details>
      <p className="cell-id">Cell {cell.id}, {cell.lat.toFixed(4)}, {cell.lon.toFixed(4)}</p>
    </article>
  );
}
