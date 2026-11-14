import type { Action, Cell, ColorBy, Confidence, Hazard, Level, Meta, Mode } from "./types";

export const MODES: { key: Mode; name: string; question: string }[] = [
  { key: "movement", name: "Movement", question: "Where is the ground moving?" },
  { key: "confidence", name: "Confidence", question: "How sure are we?" },
  { key: "future", name: "Future", question: "How much will it sink?" },
  { key: "priority", name: "Priority", question: "What should Houston do here?" },
  { key: "hazards", name: "Hazards", question: "If a disaster hit, what would the moving ground do?" },
];

export const HAZARDS: { key: Hazard; name: string; question: string }[] = [
  { key: "flood", name: "Flood", question: "Where has sinking already made floods deeper?" },
  { key: "drought", name: "Drought", question: "Where would the next drought crack foundations and pipes?" },
  { key: "bending", name: "Ground bending", question: "Where is the ground bending, and maybe faulting?" },
];

export type FloodClass = "1pct" | "0.2pct" | "levee" | "minimal";
export const FLOOD: Record<FloodClass | "deeper", { name: string; color: string; meaning: string }> = {
  deeper: { name: "High-risk zone, already deeper", color: "#0B3C6E", meaning: "FEMA 1-in-100-year flood zone where the ground has measurably dropped at least 3 cm since 2016, so the same flood now stands at least that much deeper." },
  "1pct": { name: "High-risk flood zone", color: "#4A86C5", meaning: "FEMA 1-in-100-year flood zone: a 1% chance of a flood this big every year, about 26% over 30 years." },
  "0.2pct": { name: "Moderate-risk zone", color: "#A9CBEA", meaning: "FEMA 1-in-500-year zone (0.2% a year), or protected by a levee." },
  levee: { name: "Moderate-risk zone", color: "#A9CBEA", meaning: "Protected by a levee; floods if the levee is overtopped or fails." },
  minimal: { name: "Low flood risk", color: "#EEF1EC", meaning: "Outside FEMA's mapped flood zones. Harvey still flooded many such areas." },
};

export const DROUGHT: Record<Level, { name: string; color: string; meaning: string }> = {
  high: { name: "Drought hotspot", color: "#8A3B12", meaning: "Among the 10% of squares that dropped most in the 2018 and 2023 droughts." },
  medium: { name: "Drought sensitive", color: "#D99A4E", meaning: "Dropped more than most squares in those droughts (next 20%)." },
  low: { name: "Normal", color: "#F1ECE2", meaning: "Typical drought response." },
};

export const BEND: Record<Level, { name: string; color: string; meaning: string }> = {
  high: { name: "Sharp bending", color: "#B3261E", meaning: "Sinking speed changes by 10 mm a year or more within 1 km." },
  medium: { name: "Some bending", color: "#E8A33D", meaning: "Sinking speed changes by 5–10 mm a year within 1 km." },
  low: { name: "Even", color: "#EEF1EC", meaning: "The ground sinks evenly here." },
};

export function floodClass(cell: Cell): FloodClass | null {
  const z = cell.flood.zone, sub = cell.flood.sub ?? "";
  if (z && ["A", "AE", "AO", "AH", "VE", "V"].includes(z)) return "1pct";
  if (z === "X") return sub.includes("0.2 PCT") || sub.includes("1 PCT DEPTH") ? "0.2pct" : sub.includes("LEVEE") ? "levee" : "minimal";
  return null;
}

/** How much deeper the same flood already is because the ground here dropped
 *  since the satellite record began (measured, not forecast; cm). Only for
 *  squares the satellite measures (or fills from touching measured squares)
 *  and whose sinking is clear of noise. */
export function floodExtra(cell: Cell, meta: Meta) {
  const cls = floodClass(cell);
  const dates = meta.timelapse?.dates;
  const yr = (d: string) => Number(d.slice(0, 4)) + (Number(d.slice(5, 7)) - 1) / 12;
  const span = dates && dates.length > 1 ? yr(dates[dates.length - 1]) - yr(dates[0]) : 9.7;
  const measured = cell.rate !== null && (!cell.src.includes("estimated") || !!cell.adj);
  const sink = !measured ? null : cell.sig && cell.rate! < 0 ? (-cell.rate! * span) / 10 : 0;
  return { cls, sink, total: sink, since: dates ? dates[0].slice(0, 4) : "2016" };
}

export const chanceOver = (annual: number, years: number) => 1 - Math.pow(1 - annual, years);

/** The plan's action labels. Order = rule order (first match wins). */
export const ACTION: Record<Action, { name: string; color: string; meaning: string; why: string }> = {
  investigate_first: { name: "Investigate first", color: "#7A1F3D", meaning: "Clearly sinking in a FEMA high-risk flood zone, and a nearby GPS station confirms it.", why: "Land that sinks in a flood zone gets closer to the water that floods it, so the same storm can flood it deeper over time, and drainage and levees designed for the old ground level work less well. Because GPS confirms it, flood planners and the Subsidence District can act on this with confidence." },
  add_monitoring: { name: "Add monitoring here", color: "#B8862B", meaning: "Clearly sinking in a FEMA high-risk flood zone, but no GPS station within 2 km to confirm it. The numbered pins are the top sites.", why: "Same flood concern as Investigate first, but only the satellite sees it. A sensor here turns a satellite reading into proof before anyone spends money on drainage or flood fixes." },
  review_disagreement: { name: "Review disagreement", color: "#2F6FB0", meaning: "The satellite and a GPS station within 2 km disagree by more than 5 mm a year.", why: "When two measurements disagree, one of them is missing something: a GPS station that has shifted, local construction, or a radar glitch. Checking these keeps bad numbers out of flood and planning decisions." },
  observe: { name: "Observe", color: "#D9C7E8", meaning: "Clearly sinking, but outside FEMA's high-risk flood zone.", why: "Sinking outside today's flood zones still strains pipes, roads, and foundations, and flood maps are drawn on today's ground level. Keep watching so these areas aren't a surprise later." },
  no_clear_motion: { name: "No clear motion", color: "#EEF1EC", meaning: "No sinking beyond what our measurements can tell apart from noise.", why: "Knowing where the ground is stable is useful too: it tells the city where it doesn't need to spend limited monitoring money." },
  insufficient_data: { name: "No measurement", color: "rgba(120,130,126,0.16)", meaning: "Open water, outside the satellite's coverage, or too far from measured squares to estimate.", why: "We'd rather show a gap than guess. Where nothing measures the ground, the white diamonds mark low-cost sensor sites that would give the first reading." },
};

export const CONFIDENCE: Record<Confidence, { name: string; color: string; meaning: string }> = {
  high: { name: "High", color: "#1F5F5B", meaning: "Steady satellite record, confirmed by a nearby GPS station." },
  medium: { name: "Medium", color: "#7FA8A0", meaning: "Steady satellite record, but no GPS station close enough to confirm it." },
  low: { name: "Low", color: "#DCE5E1", meaning: "Noisy record, it doesn't match the squares around it, or a GPS station disagrees." },
};

export const NO_MEASUREMENT = ACTION.insufficient_data.color;
/** Estimated squares in views that need a direct satellite record (drought, bending). */
export const NOT_DIRECT = "rgba(150,160,156,0.30)";

const NEUTRAL = [236, 239, 233];
const SINK = [74, 25, 120];
const RISE = [20, 110, 112];

/** Violet = sinking, teal = rising. `span` is the value that gets full color. */
export function movementColor(value: number | null, span = 25): string {
  if (value === null || Number.isNaN(value)) return NO_MEASUREMENT;
  const t = Math.max(-1, Math.min(1, value / span));
  const end = t < 0 ? SINK : RISE;
  const k = Math.pow(Math.abs(t), 0.75);
  const c = NEUTRAL.map((n, i) => Math.round(n + (end[i] - n) * k));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

export function cellColor(cell: Cell, mode: ColorBy, year: number, meta?: Meta): string {
  if (mode === "history") return cell.tl ? movementColor(cell.tl[year] / 10, 20) : NO_MEASUREMENT;
  if (mode === "flood") {
    const f = meta ? floodExtra(cell, meta) : null;
    if (!f || !f.cls) return NO_MEASUREMENT;
    return f.cls === "1pct" && (f.total ?? 0) >= 3 ? FLOOD.deeper.color : FLOOD[f.cls].color;
  }
  if (cell.act === "insufficient_data") return NO_MEASUREMENT;
  if (mode === "drought") return cell.hz ? DROUGHT[cell.hz.dl].color : NOT_DIRECT;
  if (mode === "bending") return cell.hz?.bl ? BEND[cell.hz.bl].color : NOT_DIRECT;
  if (mode === "priority") return ACTION[cell.act].color;
  if (mode === "confidence") return cell.conf ? CONFIDENCE[cell.conf].color : NO_MEASUREMENT;
  if (mode === "future") return cell.future ? movementColor(cell.future.by[String(year)]?.c ?? null, 12) : NO_MEASUREMENT;
  // estimated squares use the same colors; MapView draws them lighter
  return movementColor(cell.rate);
}

const minus = (s: string) => s.replace(/^-/, "−");
export const num = (v: number | null | undefined, digits = 1) => (v === null || v === undefined || Number.isNaN(v) ? "—" : minus(v.toFixed(digits)));

export function headline(cell: Cell, stable: number): string {
  if (cell.act === "insufficient_data" || cell.rate === null) return "No measurement here";
  if (Math.abs(cell.rate) < stable || !cell.sig) return "No clear motion";
  return cell.rate < 0 ? `Sinking ${num(Math.abs(cell.rate))} mm a year` : `Rising ${num(cell.rate)} mm a year`;
}

export function duration(months: number | null): string {
  if (months === null) return "more than 80 years";
  if (months < 12) return `about ${Math.max(1, Math.round(months))} months`;
  return `about ${(months / 12).toFixed(1)} years`;
}


/** One-line hover text for a square in the current view. */
export function cellSummary(cell: Cell, mode: ColorBy, year: number, meta: Meta): string {
  if (mode === "history") return cell.tl ? `${num(cell.tl[year] / 10)} cm since July 2016` : "No measurement";
  if (mode === "flood") {
    const f = floodExtra(cell, meta);
    if (!f.cls) return "No flood zone data";
    const base = FLOOD[f.cls === "1pct" && (f.total ?? 0) >= 3 ? "deeper" : f.cls].name;
    return f.total !== null && f.total > 0.5 ? `${base}: floods ${num(f.total)} cm deeper than in ${f.since}` : base;
  }
  if (cell.act === "insufficient_data" || cell.rate === null) return "No measurement";
  const est = cell.src.includes("estimated") ? " (estimated)" : "";
  if (mode === "drought") return cell.hz ? `${DROUGHT[cell.hz.dl].name}: ${num(cell.hz.drop, 0)} mm extra drop in droughts` : "Needs a direct satellite record";
  if (mode === "bending") return cell.hz?.bl ? `${BEND[cell.hz.bl].name}: ${num(cell.hz.bend)} mm/yr change within 1 km` : "Needs a direct satellite record";
  if (mode === "confidence") return cell.conf ? `${CONFIDENCE[cell.conf].name} confidence${est}` : "No confidence level";
  if (mode === "priority") return ACTION[cell.act].name + est;
  if (mode === "future") { const v = cell.future?.by[String(year)]; return v ? `${num(v.c)} cm by ${year}${est}` : "No forecast"; }
  return `${num(cell.rate)} mm a year${est}`;
}
