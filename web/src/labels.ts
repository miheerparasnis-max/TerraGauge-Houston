import type { Action, Cell, Confidence, Mode } from "./types";

export const MODES: { key: Mode; name: string; question: string }[] = [
  { key: "movement", name: "Movement", question: "Where is the ground moving?" },
  { key: "confidence", name: "Confidence", question: "How sure are we?" },
  { key: "future", name: "Future", question: "How much will it sink?" },
  { key: "priority", name: "Priority", question: "What should Houston do here?" },
];

/** The plan's action labels. Order = rule order (first match wins). */
export const ACTION: Record<Action, { name: string; color: string; meaning: string }> = {
  investigate_first: { name: "Investigate first", color: "#7A1F3D", meaning: "Clearly sinking in a FEMA high-risk flood zone, and a nearby GPS station confirms it." },
  add_monitoring: { name: "Add monitoring here", color: "#B8862B", meaning: "Clearly sinking in a FEMA high-risk flood zone, but no GPS station within 2 km to confirm it. The numbered pins are the top sites." },
  review_disagreement: { name: "Review disagreement", color: "#2F6FB0", meaning: "The satellite and a GPS station within 2 km disagree by more than 5 mm a year." },
  observe: { name: "Observe", color: "#D9C7E8", meaning: "Clearly sinking, but outside FEMA's high-risk flood zone." },
  no_clear_motion: { name: "No clear motion", color: "#EEF1EC", meaning: "No sinking beyond what our measurements can tell apart from noise." },
  insufficient_data: { name: "No measurement", color: "rgba(110,120,116,0.32)", meaning: "Trees, fields, or water block the satellite here, so there's no reliable reading." },
};

export const CONFIDENCE: Record<Confidence, { name: string; color: string; meaning: string }> = {
  high: { name: "High", color: "#1F5F5B", meaning: "Steady satellite record, confirmed by a nearby GPS station." },
  medium: { name: "Medium", color: "#7FA8A0", meaning: "Steady satellite record, but no GPS station close enough to confirm it." },
  low: { name: "Low", color: "#DCE5E1", meaning: "Noisy record, it doesn't match the squares around it, or a GPS station disagrees." },
};

export const NO_MEASUREMENT = ACTION.insufficient_data.color;

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

export function cellColor(cell: Cell, mode: Mode, year: number): string {
  if (cell.act === "insufficient_data") return NO_MEASUREMENT;
  if (mode === "priority") return ACTION[cell.act].color;
  if (mode === "confidence") return cell.conf ? CONFIDENCE[cell.conf].color : NO_MEASUREMENT;
  if (mode === "future") return cell.future ? movementColor(cell.future.by[String(year)]?.c ?? null, 12) : NO_MEASUREMENT;
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
