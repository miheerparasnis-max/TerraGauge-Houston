import type { Action, Cell, ColorBy, Confidence, Hazard, Level, Meta, Mode } from "./types";
import { BEND_COLORS, CONFIDENCE_COLORS, DROUGHT_COLORS, FLOOD_COLORS, NO_DATA, NOT_DIRECT as NOT_DIRECT_COLOR, PRIORITY_COLORS, divergingColor } from "./palette";

export const MODES: { key: Mode; name: string; question: string }[] = [
  { key: "movement", name: "Movement", question: "Where is the ground moving?" },
  { key: "confidence", name: "Confidence", question: "How sure are we?" },
  { key: "future", name: "Future", question: "How much more will it sink?" },
  { key: "priority", name: "Priority", question: "What should Houston do here?" },
  { key: "hazards", name: "Hazards", question: "What does the moving ground do in a disaster?" },
];

export const HAZARDS: { key: Hazard; name: string; question: string }[] = [
  { key: "flood", name: "Flood", question: "Where has sinking already made floods deeper?" },
  { key: "drought", name: "Drought", question: "Where do droughts crack foundations and pipes?" },
  { key: "bending", name: "Bending", question: "Where is the ground bending, and maybe faulting?" },
];

export type FloodClass = "1pct" | "0.2pct" | "levee" | "minimal";
export const FLOOD: Record<FloodClass | "deeper", { name: string; color: string; meaning: string }> = {
  deeper: { name: "High risk, already deeper", color: FLOOD_COLORS.deeper, meaning: "A FEMA high-risk flood zone where the ground has dropped at least 3 cm since 2016, so the same flood now stands at least that much deeper." },
  "1pct": { name: "High flood risk", color: FLOOD_COLORS["1pct"], meaning: "FEMA's 1-in-100-year flood zone: a 1% chance of a flood this big every year, about 26% over a 30-year mortgage." },
  "0.2pct": { name: "Moderate flood risk", color: FLOOD_COLORS["0.2pct"], meaning: "FEMA's 1-in-500-year zone (0.2% a year), or land protected by a levee." },
  levee: { name: "Moderate flood risk", color: FLOOD_COLORS["0.2pct"], meaning: "Protected by a levee; it floods if the levee is overtopped or fails." },
  minimal: { name: "Low flood risk", color: FLOOD_COLORS.minimal, meaning: "Outside FEMA's mapped flood zones. Hurricane Harvey still flooded many places like this." },
};

export const DROUGHT: Record<Level, { name: string; color: string; meaning: string }> = {
  high: { name: "Drought hotspot", color: DROUGHT_COLORS.high, meaning: "Among the 10% of squares whose ground dropped most in the 2018 and 2023 droughts." },
  medium: { name: "Drought sensitive", color: DROUGHT_COLORS.medium, meaning: "Dropped more than most squares in those droughts (the next 20%)." },
  low: { name: "Typical", color: DROUGHT_COLORS.low, meaning: "Behaved like most of Houston in those droughts." },
};

export const BEND: Record<Level, { name: string; color: string; meaning: string }> = {
  high: { name: "Sharp bending", color: BEND_COLORS.high, meaning: "The sinking speed changes by 10 mm a year or more within 1 km." },
  medium: { name: "Some bending", color: BEND_COLORS.medium, meaning: "The sinking speed changes by 5 to 10 mm a year within 1 km." },
  low: { name: "Even", color: BEND_COLORS.low, meaning: "The ground sinks evenly here." },
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
  investigate_first: { name: "Investigate first", color: PRIORITY_COLORS.investigate_first, meaning: "Clearly sinking inside a FEMA high-risk flood zone, and a GPS station nearby confirms it.", why: "Land that sinks in a flood zone gets closer to the water that floods it, so the same storm floods it deeper, and drains and levees built for the old ground level work less well. A GPS station confirms the sinking, so flood planners can act on it with confidence." },
  add_monitoring: { name: "Add monitoring here", color: PRIORITY_COLORS.add_monitoring, meaning: "Clearly sinking inside a FEMA high-risk flood zone, but no GPS station within 2 km to confirm it. Numbered pins mark the best sites.", why: "The same flood concern as Investigate first, but only the satellite sees it. A sensor here turns a satellite reading into proof before anyone spends money on drainage or flood fixes." },
  review_disagreement: { name: "Check the readings", color: PRIORITY_COLORS.review_disagreement, meaning: "The satellite and a GPS station within 2 km disagree by more than 5 mm a year.", why: "When two measurements disagree, one is missing something: a GPS station that has shifted, nearby construction, or a radar glitch. Checking these keeps bad numbers out of flood and planning decisions." },
  observe: { name: "Keep watching", color: PRIORITY_COLORS.observe, meaning: "Clearly sinking, but outside FEMA's high-risk flood zones.", why: "Sinking outside today's flood zones still strains pipes, roads and foundations, and flood maps are drawn on today's ground. Watching these areas means they won't be a surprise later." },
  no_clear_motion: { name: "No clear motion", color: PRIORITY_COLORS.no_clear_motion, meaning: "Any movement here is too small to tell apart from the measurements' own wobble.", why: "Knowing where the ground is steady helps too: it tells the city where it doesn't need to spend limited monitoring money." },
  insufficient_data: { name: "No measurement", color: NO_DATA, meaning: "Open water, outside the satellite's view, or too far from measured squares to estimate.", why: "We would rather show a gap than guess. Where nothing measures the ground, the white diamonds mark low-cost sensor sites that would give the first reading." },
};

export const CONFIDENCE: Record<Confidence, { name: string; color: string; meaning: string }> = {
  high: { name: "High", color: CONFIDENCE_COLORS.high, meaning: "A steady satellite record, confirmed by a GPS station nearby." },
  medium: { name: "Medium", color: CONFIDENCE_COLORS.medium, meaning: "A steady satellite record, but no GPS station close enough to confirm it." },
  low: { name: "Low", color: CONFIDENCE_COLORS.low, meaning: "A shaky record, it doesn't match the squares around it, or a GPS station disagrees." },
};

export const NO_MEASUREMENT = NO_DATA;
/** Estimated squares in views that need a direct satellite record (drought, bending). */
export const NOT_DIRECT = NOT_DIRECT_COLOR;

/** Purple = sinking, green = rising, gray = no clear motion. `span` gets the full color. */
export function movementColor(value: number | null, span = 25): string {
  if (value === null || Number.isNaN(value)) return NO_MEASUREMENT;
  return divergingColor(value, span);
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

/** Plain wording for sentences that arrive inside the data files. */
export const plain = (t: string) => t
  .replace(/\(±\s?([\d.]+) mm\/yr\)/g, "(give or take $1 mm a year)")
  .replace(/±\s?([\d.]+) mm\/yr/g, "give or take $1 mm a year")
  .replace(/mm\/yr/g, "mm a year")
  .replace(/ \(NASA OPERA DIST\)/g, " (NASA satellite)")
  .replace(/neighbouring/g, "neighboring");
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
  if (mode === "drought") return cell.hz ? `${DROUGHT[cell.hz.dl].name}: ${num(cell.hz.drop, 0)} mm extra drop in droughts` : "Needs its own satellite record";
  if (mode === "bending") return cell.hz?.bl ? `${BEND[cell.hz.bl].name}: speed changes ${num(cell.hz.bend)} mm a year within 1 km` : "Needs its own satellite record";
  if (mode === "confidence") return cell.conf ? `${CONFIDENCE[cell.conf].name} confidence${est}` : "No confidence level";
  if (mode === "priority") return ACTION[cell.act].name + est;
  if (mode === "future") { const v = cell.future?.by[String(year)]; return v ? `${num(v.c)} cm by ${year}${est}` : "No forecast"; }
  return `${num(cell.rate)} mm a year${est}`;
}
