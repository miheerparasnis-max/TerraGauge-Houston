import type { LabelCode, ViewKey } from "./types";

export const LABELS: Record<LabelCode, { name: string; color: string; action: string }> = {
  I: { name: "Investigate signal", color: "#5B2A86", action: "Review this signal first: it passes the quality and noise tests and a GPS station is nearby to confirm it." },
  A: { name: "Add ground monitoring", color: "#B8862B", action: "The signal passes the tests, but no permanent GPS station is within 2 km to confirm it." },
  C: { name: "Context only", color: "#9DB0AA", action: "Data exists here, but the signal is not strong enough to recommend action." },
  R: { name: "Review mismatch", color: "#B23A48", action: "Time-matched GPS and radar disagree. Reserved; not used until a time-matched comparison exists." },
  X: { name: "Insufficient evidence", color: "transparent", action: "Radar quality checks failed or coverage is too sparse to say anything." },
};

export const VIEWS: Record<ViewKey, { short: string; long: string }> = {
  o: { short: "OPERA 2016–2021", long: "Multi-year OPERA Sentinel-1 motion, checked against GPS" },
  p: { short: "NISAR 12-day", long: "One NISAR pair, 2 to 14 Nov 2025" },
  c: { short: "NISAR 60-day", long: "Five NISAR pairs summed, 2 Nov 2025 to 1 Jan 2026" },
};

/** Diverging scale: violet = moving away from satellite (sinking), teal = toward. */
export function motionColor(value: number | null, span: number): string {
  if (value === null || Number.isNaN(value)) return "rgba(0,0,0,0)";
  const t = Math.max(-1, Math.min(1, value / span));
  const neutral = [236, 239, 233];
  const sink = [74, 25, 120];
  const rise = [20, 110, 112];
  const end = t < 0 ? sink : rise;
  const k = Math.pow(Math.abs(t), 0.8);
  const c = neutral.map((n, i) => Math.round(n + (end[i] - n) * k));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

export const fmt = (v: number | null | undefined, digits = 1, unit = "") =>
  v === null || v === undefined || Number.isNaN(v) ? "—" : `${v.toFixed(digits).replace(/^-/, "−")}${unit ? " " + unit : ""}`;
