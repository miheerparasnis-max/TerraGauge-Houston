import type { Cell, Confidence, Mode, Priority } from "./types";

export const MODES: { key: Mode; name: string; question: string }[] = [
  { key: "movement", name: "Movement", question: "Where did the ground move in the satellite record?" },
  { key: "confidence", name: "Confidence", question: "How sure are we?" },
  { key: "priority", name: "Priority", question: "Where should we look first?" },
];

export const PRIORITY: Record<Priority, { name: string; color: string; meaning: string }> = {
  urgent: { name: "Urgent", color: "#7A1F3D", meaning: "Moved down at least 1 cm a year in the satellite record, or 5 mm a year inside a FEMA high-risk flood zone, clearly above noise." },
  high: { name: "High", color: "#B8862B", meaning: "Moved down at least 5 mm a year in the satellite record, clearly above noise." },
  watch: { name: "Watch", color: "#E6CF8F", meaning: "Some sign of downward motion in the satellite record, but the evidence is weaker. Worth a closer look." },
  stable: { name: "Stable", color: "#CBD6D1", meaning: "No up-or-down motion we can tell apart from noise in the satellite record." },
  check: { name: "Check data", color: "#6B7280", meaning: "The reading is faster than anything ever measured in Houston, so it's probably a glitch." },
  no_data: { name: "No reliable reading", color: "transparent", meaning: "Trees, fields, or water block the satellite here, and no GPS station is inside the square." },
};

export const CONFIDENCE: Record<Confidence, { name: string; color: string; meaning: string }> = {
  high: { name: "High", color: "#1F5F5B", meaning: "Steady satellite record, confirmed by a nearby GPS station." },
  medium: { name: "Medium", color: "#7FA8A0", meaning: "Steady satellite record, but no GPS station close enough to confirm it." },
  low: { name: "Low", color: "#DCE5E1", meaning: "Noisy record, or a nearby GPS station disagrees." },
};

const NEUTRAL = [236, 239, 233];
const DOWN = [74, 25, 120];
const UP = [20, 110, 112];

function mix(a: number[], b: number[], k: number) {
  const c = a.map((v, i) => Math.round(v + (b[i] - v) * k));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

/** Violet = moved down, teal = moved up. `span` is the value that gets full color. */
export function movementColor(value: number | null, span = 25): string {
  if (value === null || Number.isNaN(value)) return "rgba(0,0,0,0)";
  const t = Math.max(-1, Math.min(1, value / span));
  return mix(NEUTRAL, t < 0 ? DOWN : UP, Math.pow(Math.abs(t), 0.75));
}

export function cellColor(cell: Cell, mode: Mode): string {
  if (cell.pri === "no_data") return "rgba(0,0,0,0)";
  if (mode === "priority") return PRIORITY[cell.pri].color;
  if (cell.pri === "check") return PRIORITY.check.color;
  if (mode === "confidence") return cell.conf ? CONFIDENCE[cell.conf].color : "rgba(0,0,0,0)";
  return movementColor(cell.rate);
}

const minus = (s: string) => s.replace(/^-/, "−");
export const num = (v: number | null | undefined, digits = 1) => (v === null || v === undefined || Number.isNaN(v) ? "—" : minus(v.toFixed(digits)));

/** "Moved down about 1.2 cm a year" style headline, describing the past record. */
export function headline(cell: Cell): string {
  if (cell.pri === "no_data" || cell.rate === null) return "No reliable reading here";
  if (cell.pri === "check") return "Reading looks like a glitch";
  if (cell.pri === "stable") return "No clear up-or-down motion";
  const mm = Math.abs(cell.rate);
  const amount = mm >= 10 ? `${(mm / 10).toFixed(1)} cm` : `${mm.toFixed(0)} mm`;
  return cell.rate < 0 ? `Moved down about ${amount} a year` : `Moved up about ${amount} a year`;
}
