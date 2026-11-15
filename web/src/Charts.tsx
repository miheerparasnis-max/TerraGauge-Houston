import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { num } from "./labels";
import { UI } from "./palette";

/* Small, dependency-free SVG charts that share one look: 2px lines, hairline
   solid grids, bars no thicker than 24px with rounded data ends, direct end
   labels, a hover/focus tooltip on every mark, and a screen-reader table. */

export function useWidth<T extends HTMLElement>(fallback = 480) {
  const ref = useRef<T>(null);
  const [w, setW] = useState(fallback);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const set = () => setW(Math.max(160, Math.round(el.getBoundingClientRect().width)));
    set();
    const ro = new ResizeObserver(set);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

function niceStep(span: number, target = 4) {
  const raw = span / target;
  const p = Math.pow(10, Math.floor(Math.log10(raw)));
  const f = raw / p;
  return (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * p;
}

function niceTicks(lo: number, hi: number, target = 4) {
  const step = niceStep(hi - lo || 1, target);
  const a = Math.floor(lo / step) * step, b = Math.ceil(hi / step) * step;
  const out: number[] = [];
  for (let v = a; v <= b + step / 2; v += step) out.push(Math.round(v * 1e6) / 1e6);
  return out;
}

interface Tip { x: number; y: number; body: ReactNode }

function Tooltip({ tip, width }: { tip: Tip | null; width: number }) {
  if (!tip) return null;
  const left = Math.min(Math.max(tip.x, 8), width - 8);
  const flip = tip.x > width * 0.62;
  return (
    <div className="chart-tip" style={{ left, top: tip.y, transform: `translate(${flip ? "calc(-100% - 12px)" : "12px"}, -50%)` }} role="status">
      {tip.body}
    </div>
  );
}

export interface LineSeries { name: string; color: string; values: (number | null)[]; emphasis?: boolean }

/** Lines over time with a crosshair that snaps to the nearest date. */
export function LineChart({ x, labels, series, unit, height = 190, xTicks, ariaLabel, format = (v: number) => num(v) }: {
  x: number[]; labels: string[]; series: LineSeries[]; unit: string; height?: number; xTicks: number[]; ariaLabel: string; format?: (v: number) => string;
}) {
  const [box, width] = useWidth<HTMLDivElement>();
  const [at, setAt] = useState<number | null>(null);
  const pad = { l: 38, r: 64, t: 22, b: 24 };
  const all = series.flatMap((s) => s.values.filter((v): v is number => v !== null));
  const ticks = niceTicks(Math.min(0, ...all), Math.max(0, ...all));
  const lo = ticks[0], hi = ticks[ticks.length - 1];
  const sx = (t: number) => pad.l + ((t - x[0]) / (x[x.length - 1] - x[0] || 1)) * (width - pad.l - pad.r);
  const sy = (v: number) => pad.t + (1 - (v - lo) / (hi - lo || 1)) * (height - pad.t - pad.b);
  const path = (vals: (number | null)[]) => vals.map((v, i) => (v === null ? "" : `${i && vals[i - 1] !== null ? "L" : "M"}${sx(x[i]).toFixed(1)},${sy(v).toFixed(1)}`)).join("");
  // End labels: nudge apart when two would overlap, keeping order.
  const ends = series.map((s) => { const last = [...s.values].reverse().find((v) => v !== null) ?? 0; return { s, v: last, y: sy(last) }; }).sort((a, b) => a.y - b.y);
  for (let i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 15) ends[i].y = ends[i - 1].y + 15;
  const onMove = (e: React.PointerEvent<SVGRectElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - r.left + pad.l;
    let best = 0, d = Infinity;
    x.forEach((t, i) => { const dd = Math.abs(sx(t) - px); if (dd < d) { d = dd; best = i; } });
    setAt(best);
  };
  const tip: Tip | null = at === null ? null : {
    x: sx(x[at]), y: pad.t + 30,
    body: <><b className="tip-head">{labels[at]}</b>{series.map((s) => s.values[at] === null ? null : <span key={s.name} className="tip-row"><i style={{ background: s.color }} /><strong>{format(s.values[at]!)} {unit}</strong><em>{s.name}</em></span>)}</>,
  };
  return (
    <div className="chart" ref={box}>
      {series.length > 1 && <ul className="chart-legend">{series.map((s) => <li key={s.name}><i className="key-line" style={{ background: s.color }} />{s.name}</li>)}</ul>}
      <div className="chart-plot">
        <svg width={width} height={height} role="img" aria-label={ariaLabel}>
          {ticks.map((v) => <g key={v}><line x1={pad.l} x2={width - pad.r} y1={sy(v)} y2={sy(v)} className={v === 0 ? "axis" : "grid"} /><text x={pad.l - 6} y={sy(v) + 4} textAnchor="end" className="tick">{v}</text></g>)}
          {xTicks.map((t) => <text key={t} x={sx(t)} y={height - 6} textAnchor="middle" className="tick">{t}</text>)}
          <text x={pad.l - 6} y={9} textAnchor="end" className="tick unit">{unit}</text>
          {series.map((s) => <path key={s.name} d={path(s.values)} className="line" style={{ stroke: s.color, opacity: s.emphasis === false ? 0.85 : 1 }} />)}
          {ends.map(({ s, v, y }) => (
            <g key={s.name}>
              <circle cx={sx(x[x.length - 1])} cy={sy(v)} r={4.5} className="end-dot" style={{ fill: s.color }} />
              <text x={sx(x[x.length - 1]) + 9} y={y + 4} className="end-label">{format(v)}</text>
            </g>
          ))}
          {at !== null && <line x1={sx(x[at])} x2={sx(x[at])} y1={pad.t} y2={height - pad.b} className="crosshair" />}
          {at !== null && series.map((s) => s.values[at] === null ? null : <circle key={s.name} cx={sx(x[at])} cy={sy(s.values[at]!)} r={4.5} className="end-dot" style={{ fill: s.color }} />)}
          <rect x={pad.l} y={pad.t} width={Math.max(0, width - pad.l - pad.r)} height={height - pad.t - pad.b} fill="transparent" onPointerMove={onMove} onPointerLeave={() => setAt(null)}
            tabIndex={0} aria-label={`${ariaLabel}. Use the arrow keys to read each date.`}
            onKeyDown={(e) => { if (e.key === "ArrowRight") setAt((a) => Math.min(x.length - 1, (a ?? -1) + 1)); if (e.key === "ArrowLeft") setAt((a) => Math.max(0, (a ?? x.length) - 1)); }}
            onBlur={() => setAt(null)} />
        </svg>
        <Tooltip tip={tip} width={width} />
      </div>
      <div className="sr-only"><table><caption>{ariaLabel}</caption><thead><tr><th>Date</th>{series.map((s) => <th key={s.name}>{s.name} ({unit})</th>)}</tr></thead>
        <tbody>{labels.map((l, i) => <tr key={l}><td>{l}</td>{series.map((s) => <td key={s.name}>{s.values[i] === null ? "—" : format(s.values[i]!)}</td>)}</tr>)}</tbody></table></div>
    </div>
  );
}

export interface Bar { label: string; value: number; color: string; note?: string }

/** Vertical columns with the value on each cap. */
export function ColumnChart({ bars, height = 170, ariaLabel, format = (v: number) => v.toLocaleString() }: { bars: Bar[]; height?: number; ariaLabel: string; format?: (v: number) => string }) {
  const [box, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const pad = { l: 4, r: 4, t: 20, b: 36 };
  const max = Math.max(...bars.map((b) => b.value), 1);
  const slot = (width - pad.l - pad.r) / bars.length;
  const bw = Math.min(24, slot * 0.56);
  const sy = (v: number) => pad.t + (1 - v / max) * (height - pad.t - pad.b);
  const base = height - pad.b;
  const tip: Tip | null = hover === null ? null : { x: pad.l + slot * (hover + 0.5), y: sy(bars[hover].value), body: <><strong className="tip-head">{format(bars[hover].value)}</strong><span className="tip-sub">{bars[hover].label}</span>{bars[hover].note && <span className="tip-sub">{bars[hover].note}</span>}</> };
  return (
    <div className="chart" ref={box}>
      <div className="chart-plot">
        <svg width={width} height={height} role="img" aria-label={ariaLabel}>
          <line x1={pad.l} x2={width - pad.r} y1={base} y2={base} className="axis" />
          {bars.map((b, i) => {
            const cx = pad.l + slot * (i + 0.5), y = sy(b.value), h = Math.max(1, base - y);
            const r = Math.min(4, h, bw / 2);
            const d = `M${cx - bw / 2},${base} V${y + r} Q${cx - bw / 2},${y} ${cx - bw / 2 + r},${y} H${cx + bw / 2 - r} Q${cx + bw / 2},${y} ${cx + bw / 2},${y + r} V${base} Z`;
            return (
              <g key={b.label} className={hover === i ? "mark on" : "mark"}>
                <path d={d} style={{ fill: b.color }} />
                <text x={cx} y={y - 6} textAnchor="middle" className="cap">{format(b.value)}</text>
                <text x={cx} y={base + 15} textAnchor="middle" className="tick">{b.label.split("\n")[0]}</text>
                {b.label.includes("\n") && <text x={cx} y={base + 28} textAnchor="middle" className="tick">{b.label.split("\n")[1]}</text>}
                <rect x={cx - slot / 2} y={pad.t - 16} width={slot} height={base - pad.t + 16} fill="transparent" tabIndex={0} aria-label={`${b.label.replace("\n", " ")}: ${format(b.value)}`}
                  onPointerEnter={() => setHover(i)} onPointerLeave={() => setHover(null)} onFocus={() => setHover(i)} onBlur={() => setHover(null)} />
              </g>
            );
          })}
        </svg>
        <Tooltip tip={tip} width={width} />
      </div>
    </div>
  );
}

/** Horizontal bars: label on the left, value at the tip. */
export function HBarChart({ rows, ariaLabel, format = (v: number) => v.toLocaleString(), labelWidth = 150, stacked = false }: { rows: Bar[]; ariaLabel: string; format?: (v: number) => string; labelWidth?: number; stacked?: boolean }) {
  const [box, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  if (stacked) return <StackedBars rows={rows} ariaLabel={ariaLabel} format={format} width={width} box={box} hover={hover} setHover={setHover} />;
  const rowH = 30, bw = 16, valueRoom = 64;
  const lw = Math.min(labelWidth, width * 0.42);
  const max = Math.max(...rows.map((r) => r.value), 1);
  const sx = (v: number) => (v / max) * (width - lw - valueRoom);
  const height = rows.length * rowH + 4;
  const tip: Tip | null = hover === null || !rows[hover].note ? null : { x: lw + sx(rows[hover].value), y: hover * rowH + rowH / 2, body: <><strong className="tip-head">{rows[hover].label}</strong><span className="tip-sub">{rows[hover].note}</span></> };
  return (
    <div className="chart" ref={box}>
      <div className="chart-plot">
        <svg width={width} height={height} role="img" aria-label={ariaLabel}>
          <line x1={lw} x2={lw} y1={0} y2={height} className="axis" />
          {rows.map((r, i) => {
            const y = i * rowH + (rowH - bw) / 2, w = Math.max(2, sx(r.value)), rr = Math.min(4, w);
            const d = `M${lw},${y} H${lw + w - rr} Q${lw + w},${y} ${lw + w},${y + rr} V${y + bw - rr} Q${lw + w},${y + bw} ${lw + w - rr},${y + bw} H${lw} Z`;
            return (
              <g key={r.label} className={hover === i ? "mark on" : "mark"}>
                <text x={lw - 10} y={y + bw / 2 + 4.5} textAnchor="end" className="row-label">{r.label}</text>
                <path d={d} style={{ fill: r.color }} />
                <text x={lw + w + 8} y={y + bw / 2 + 4.5} className="cap">{format(r.value)}</text>
                <rect x={0} y={i * rowH} width={width} height={rowH} fill="transparent" tabIndex={r.note ? 0 : -1} aria-label={`${r.label}: ${format(r.value)}${r.note ? `. ${r.note}` : ""}`}
                  onPointerEnter={() => setHover(i)} onPointerLeave={() => setHover(null)} onFocus={() => setHover(i)} onBlur={() => setHover(null)} />
              </g>
            );
          })}
        </svg>
        <Tooltip tip={tip} width={width} />
      </div>
    </div>
  );
}

/** Bars with their label on a line above: for narrow columns and long names. */
function StackedBars({ rows, ariaLabel, format, width, box, hover, setHover }: { rows: Bar[]; ariaLabel: string; format: (v: number) => string; width: number; box: React.RefObject<HTMLDivElement>; hover: number | null; setHover: (i: number | null) => void }) {
  const rowH = 38, bw = 12, valueRoom = 60;
  const max = Math.max(...rows.map((r) => r.value), 1);
  const sx = (v: number) => (v / max) * (width - valueRoom);
  const height = rows.length * rowH;
  return (
    <div className="chart" ref={box}>
      <svg width={width} height={height} role="img" aria-label={ariaLabel}>
        {rows.map((r, i) => {
          const y = i * rowH + 18, w = Math.max(2, sx(r.value)), rr = Math.min(4, w);
          const d = `M0,${y} H${w - rr} Q${w},${y} ${w},${y + rr} V${y + bw - rr} Q${w},${y + bw} ${w - rr},${y + bw} H0 Z`;
          return (
            <g key={r.label} className={hover === i ? "mark on" : "mark"}>
              <text x={0} y={y - 5} className="row-label">{r.label}</text>
              <path d={d} style={{ fill: r.color }} />
              <text x={w + 8} y={y + bw / 2 + 4.5} className="cap">{format(r.value)}</text>
              <rect x={0} y={i * rowH} width={width} height={rowH} fill="transparent" onPointerEnter={() => setHover(i)} onPointerLeave={() => setHover(null)} />
            </g>
          );
        })}
      </svg>
    </div>
  );
}

/** One whole split into parts: a tall bar with shares inside and a legend below. */
export function SegmentedBar({ parts, ariaLabel }: { parts: Bar[]; ariaLabel: string }) {
  const [box, width] = useWidth<HTMLDivElement>();
  const total = parts.reduce((t, p) => t + p.value, 0) || 1;
  const gap = 2;
  let x = 0;
  const blocks = parts.filter((p) => p.value > 0).map((p) => { const w = (p.value / total) * (width - gap * (parts.length - 1)); const b = { ...p, x, w }; x += w + gap; return b; });
  return (
    <div className="chart" ref={box} role="img" aria-label={`${ariaLabel}: ${parts.map((p) => `${p.label} ${p.value}`).join(", ")}`}>
      <div className="seg-bar" aria-hidden="true">
        {blocks.map((b) => (
          <span key={b.label} style={{ left: b.x, width: b.w, background: b.color }} title={`${b.label}: ${b.value} (${Math.round((b.value / total) * 100)}%)`}>
            {b.w > 44 && <em style={{ color: luminance(b.color) > 0.42 ? UI.surface : UI.ink }}>{Math.round((b.value / total) * 100)}%</em>}
          </span>
        ))}
      </div>
      <ul className="chart-legend under">{parts.map((p) => <li key={p.label}><i className="key-box" style={{ background: p.color }} />{p.label}<b>{p.value}</b></li>)}</ul>
    </div>
  );
}

function luminance(color: string) {
  const m = color.startsWith("#") ? [1, 3, 5].map((i) => parseInt(color.slice(i, i + 2), 16)) : (color.match(/\d+/g) ?? ["0", "0", "0"]).slice(0, 3).map(Number);
  const [r, g, b] = m.map((v) => { const c = v / 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export interface ScatterPoint { id: string; x: number; y: number; color: string; note?: string }

/** Two measurements of the same thing; the diagonal is perfect agreement. */
export function Scatter({ points, xLabel, yLabel, ariaLabel, height = 300 }: { points: ScatterPoint[]; xLabel: string; yLabel: string; ariaLabel: string; height?: number }) {
  const [box, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const pad = { l: 44, r: 12, t: 12, b: 40 };
  const vals = points.flatMap((p) => [p.x, p.y]);
  const ticks = niceTicks(Math.min(...vals), Math.max(...vals, 0), 5);
  const lo = ticks[0], hi = ticks[ticks.length - 1];
  const size = Math.min(width - pad.l - pad.r, height - pad.t - pad.b);
  const sx = (v: number) => pad.l + ((v - lo) / (hi - lo)) * size;
  const sy = (v: number) => pad.t + (1 - (v - lo) / (hi - lo)) * size;
  const onMove = (e: React.PointerEvent<SVGRectElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - r.left + pad.l, py = e.clientY - r.top + pad.t;
    let best = -1, d = 24 * 24;
    points.forEach((p, i) => { const dd = (sx(p.x) - px) ** 2 + (sy(p.y) - py) ** 2; if (dd < d) { d = dd; best = i; } });
    setHover(best < 0 ? null : best);
  };
  const p = hover === null ? null : points[hover];
  const tip: Tip | null = p ? { x: sx(p.x), y: sy(p.y), body: <><b className="tip-head">{p.id}</b><span className="tip-row"><strong>{num(p.x)} mm a year</strong><em>GPS</em></span><span className="tip-row"><strong>{num(p.y)} mm a year</strong><em>satellite</em></span>{p.note && <span className="tip-sub">{p.note}</span>}</> } : null;
  const h = size + pad.t + pad.b;
  return (
    <div className="chart" ref={box}>
      <div className="chart-plot">
        <svg width={width} height={h} role="img" aria-label={ariaLabel}>
          {ticks.map((v) => <g key={v}><line x1={pad.l} x2={pad.l + size} y1={sy(v)} y2={sy(v)} className={v === 0 ? "axis" : "grid"} /><line x1={sx(v)} x2={sx(v)} y1={pad.t} y2={pad.t + size} className={v === 0 ? "axis" : "grid"} /><text x={pad.l - 6} y={sy(v) + 4} textAnchor="end" className="tick">{v}</text><text x={sx(v)} y={pad.t + size + 15} textAnchor="middle" className="tick">{v}</text></g>)}
          <line x1={sx(lo)} y1={sy(lo)} x2={sx(hi)} y2={sy(hi)} className="diag" />
          {points.map((q, i) => <circle key={q.id} cx={sx(q.x)} cy={sy(q.y)} r={hover === i ? 6 : 4} className="dot" style={{ fill: q.color }} />)}
          <text x={pad.l + size / 2} y={h - 4} textAnchor="middle" className="axis-label">{xLabel}</text>
          <text transform={`translate(12 ${pad.t + size / 2}) rotate(-90)`} textAnchor="middle" className="axis-label">{yLabel}</text>
          <rect x={pad.l} y={pad.t} width={size} height={size} fill="transparent" onPointerMove={onMove} onPointerLeave={() => setHover(null)} />
        </svg>
        <Tooltip tip={tip} width={width} />
      </div>
      <div className="sr-only"><table><caption>{ariaLabel}</caption><thead><tr><th>Station</th><th>{xLabel}</th><th>{yLabel}</th></tr></thead><tbody>{points.map((q) => <tr key={q.id}><td>{q.id}</td><td>{q.x}</td><td>{q.y}</td></tr>)}</tbody></table></div>
    </div>
  );
}

/** Measured ground level and the tested forecast range for one square. */
export function TrendChart({ x, labels, past, future, height = 200 }: {
  x: number[]; labels: string[]; past: number[]; future: { t: number; label: string; c: number; lo: number; hi: number }[]; height?: number;
}) {
  const [box, width] = useWidth<HTMLDivElement>();
  const [at, setAt] = useState<number | null>(null);
  const pad = { l: 38, r: 60, t: 22, b: 24 };
  const t0 = x[x.length - 1], base = past[past.length - 1];
  const all = [...past, ...future.flatMap((f) => [base + f.lo, base + f.hi]), 0];
  const ticks = niceTicks(Math.min(...all), Math.max(...all));
  const lo = ticks[0], hi = ticks[ticks.length - 1];
  const xs = [x[0], future.length ? future[future.length - 1].t : t0];
  const sx = (t: number) => pad.l + ((t - xs[0]) / (xs[1] - xs[0] || 1)) * (width - pad.l - pad.r);
  const sy = (v: number) => pad.t + (1 - (v - lo) / (hi - lo || 1)) * (height - pad.t - pad.b);
  const pts = useMemo(() => [...x.map((t, i) => ({ t, label: labels[i], v: past[i], band: null as null | [number, number] })), ...future.map((f) => ({ t: f.t, label: f.label, v: base + f.c, band: [base + f.lo, base + f.hi] as [number, number] }))], [x, labels, past, future, base]);
  const pastPath = past.map((v, i) => `${i ? "L" : "M"}${sx(x[i]).toFixed(1)},${sy(v).toFixed(1)}`).join("");
  const cone = future.length ? [`M${sx(t0)},${sy(base)}`, ...future.map((f) => `L${sx(f.t)},${sy(base + f.hi)}`), ...future.slice().reverse().map((f) => `L${sx(f.t)},${sy(base + f.lo)}`), "Z"].join("") : "";
  const mid = future.length ? [`M${sx(t0)},${sy(base)}`, ...future.map((f) => `L${sx(f.t)},${sy(base + f.c)}`)].join("") : "";
  const yearTicks = Array.from(new Set([2016, 2019, 2022, 2025, ...(future.length ? [Math.round(xs[1])] : [])])).filter((t) => t >= xs[0] - 0.3 && t <= xs[1] + 0.3);
  const onMove = (e: React.PointerEvent<SVGRectElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - r.left + pad.l;
    let best = 0, d = Infinity;
    pts.forEach((p, i) => { const dd = Math.abs(sx(p.t) - px); if (dd < d) { d = dd; best = i; } });
    setAt(best);
  };
  const p = at === null ? null : pts[at];
  const tip: Tip | null = p ? { x: sx(p.t), y: pad.t + 30, body: <><b className="tip-head">{p.label}</b><span className="tip-row"><i style={{ background: "var(--violet)" }} /><strong>{num(p.v)} cm</strong><em>{p.band ? "forecast" : "measured"}</em></span>{p.band && <span className="tip-sub">likely {num(p.band[0])} to {num(p.band[1])} cm</span>}</> } : null;
  const last = future.length ? future[future.length - 1] : null;
  return (
    <div className="chart" ref={box}>
      <ul className="chart-legend"><li><i className="key-line" style={{ background: "var(--violet)" }} />Measured</li>{future.length > 0 && <><li><i className="key-line dashed" />Forecast</li><li><i className="key-box" style={{ background: "color-mix(in srgb, var(--violet) 22%, transparent)" }} />Likely range</li></>}</ul>
      <div className="chart-plot">
        <svg width={width} height={height} role="img" aria-label="Ground level since 2016 and the forecast range, in centimeters">
          {ticks.map((v) => <g key={v}><line x1={pad.l} x2={width - pad.r} y1={sy(v)} y2={sy(v)} className={v === 0 ? "axis" : "grid"} /><text x={pad.l - 6} y={sy(v) + 4} textAnchor="end" className="tick">{v}</text></g>)}
          {yearTicks.map((t) => <text key={t} x={sx(t)} y={height - 6} textAnchor="middle" className="tick">{t}</text>)}
          <text x={pad.l - 6} y={9} textAnchor="end" className="tick unit">cm</text>
          {cone && <path d={cone} className="cone" />}
          {mid && <path d={mid} className="line dashed" />}
          <path d={pastPath} className="line" style={{ stroke: "var(--violet)" }} />
          <line x1={sx(t0)} x2={sx(t0)} y1={pad.t} y2={height - pad.b} className="today" />
          <circle cx={sx(t0)} cy={sy(base)} r={4.5} className="end-dot" style={{ fill: "var(--violet)" }} />
          {last && <text x={sx(last.t) + 8} y={sy(base + last.c) + 4} className="end-label">{num(base + last.c)}</text>}
          {at !== null && p && <><line x1={sx(p.t)} x2={sx(p.t)} y1={pad.t} y2={height - pad.b} className="crosshair" /><circle cx={sx(p.t)} cy={sy(p.v)} r={4.5} className="end-dot" style={{ fill: "var(--violet)" }} /></>}
          <rect x={pad.l} y={pad.t} width={Math.max(0, width - pad.l - pad.r)} height={height - pad.t - pad.b} fill="transparent" onPointerMove={onMove} onPointerLeave={() => setAt(null)} tabIndex={0}
            aria-label="Ground level chart. Use the arrow keys to read each date." onBlur={() => setAt(null)}
            onKeyDown={(e) => { if (e.key === "ArrowRight") setAt((a) => Math.min(pts.length - 1, (a ?? -1) + 1)); if (e.key === "ArrowLeft") setAt((a) => Math.max(0, (a ?? pts.length) - 1)); }} />
        </svg>
        <Tooltip tip={tip} width={width} />
      </div>
      <div className="sr-only"><table><caption>Ground level in centimeters</caption><thead><tr><th>Date</th><th>Level</th><th>Likely range</th></tr></thead><tbody>{pts.map((q) => <tr key={q.label + q.t}><td>{q.label}</td><td>{num(q.v)}</td><td>{q.band ? `${num(q.band[0])} to ${num(q.band[1])}` : ""}</td></tr>)}</tbody></table></div>
    </div>
  );
}

/** Decimal year of an ISO date. */
export const yearOf = (d: string) => Number(d.slice(0, 4)) + (Number(d.slice(5, 7)) - 1) / 12 + (Number(d.slice(8, 10)) - 1) / 365;
export const monthLabel = (d: string) => new Date(`${d.slice(0, 10)}T12:00:00Z`).toLocaleDateString("en-US", { month: "short", year: "numeric", timeZone: "UTC" });

/** Run `fn` once the element scrolls near the viewport. */
export function useNearView<T extends HTMLElement>(margin = "300px") {
  const ref = useRef<T>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || seen) return;
    const io = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) { setSeen(true); io.disconnect(); } }, { rootMargin: margin });
    io.observe(el);
    return () => io.disconnect();
  }, [seen, margin]);
  return [ref, seen] as const;
}
