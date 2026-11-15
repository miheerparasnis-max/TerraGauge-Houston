/**
 * TerraGauge colors: the one place they are defined.
 *
 * UI colors are written to CSS custom properties at startup (applyPalette), so
 * styles.css reads the same values as the map and the charts. Data scales were
 * stepped in OKLCH and checked with the dataviz palette validator against the
 * dark map surface: every ramp is one hue with lightness rising with severity,
 * so the brightest squares are always the ones that matter most.
 */

export const UI = {
  space: "#030817",
  ground: "#050B1F",
  surface: "#0B1532",
  paper: "#0E1A3A",
  paper2: "#132449",
  ink: "#E8F0FA",
  ink2: "#AFC0D8",
  ink3: "#8EA3C2",
  line: "rgba(140, 180, 230, 0.16)",
  line2: "rgba(140, 180, 230, 0.30)",
  accent: "#62D8C6",
  blue: "#6899E2",
  orange: "#EDAB61",
  violet: "#C1A9EE",
  green: "#8EC899",
  warn: "#EDB97A",
} as const;

/** "Nothing here": no motion, low risk, normal. Sits just above the map surface. */
export const NEUTRAL = "#393D45";
export const NO_DATA = "rgba(150, 170, 200, 0.10)";
export const NOT_DIRECT = "rgba(150, 170, 200, 0.16)";

/** Diverging movement scale: purple arm for sinking, green arm for rising, gray midpoint. */
export const SINK = ["#6B578F", "#9379C2", "#C1A9EE"] as const;
export const RISE = ["#456F4E", "#60996C", "#8EC899"] as const;
/** Beyond the end of the sinking arm, for the fastest bin in charts. */
export const SINK_EXTREME = "#DCCDF8";
/** Bars that are context, not the story: a step above NEUTRAL so they read on the panels. */
export const CONTEXT_BAR = "#5B6270";
export const MUTED_BAR = "#4A5262";
/** Star tints for the starfield behind the story. */
export const STARS = ["#FFFFFF", "#CFE3F7"] as const;

/** Priority: one warm ramp for urgency (brighter = act sooner) plus a separate blue for "check". */
export const PRIORITY_COLORS = {
  investigate_first: "#F4A39B",
  add_monitoring: "#CE7B31",
  observe: "#856136",
  review_disagreement: "#5D8ECE",
  no_clear_motion: NEUTRAL,
} as const;

export const CONFIDENCE_COLORS = { high: "#7DD8C8", medium: "#499990", low: "#355D5D" } as const;
export const FLOOD_COLORS = { deeper: "#A1D1F4", "1pct": "#5E97CD", "0.2pct": "#406690", minimal: "#2F3945" } as const;
export const DROUGHT_COLORS = { high: "#E7B369", medium: "#A57E4F", low: NEUTRAL } as const;
export const BEND_COLORS = { high: "#F49383", medium: "#B06B60", low: NEUTRAL } as const;

/** Points and outlines drawn on the map. */
export const MAP = {
  gps: UI.ink,
  ext: UI.accent,
  wells: UI.blue,
  floodLine: "#7FB4E8",
  selected: "#FFFFFF",
  grid: "#C9DCF5",
  stroke: UI.surface,
} as const;

const hexToRgb = (h: string) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const mix = (a: number[], b: number[], k: number) => a.map((v, i) => Math.round(v + (b[i] - v) * k));

/** Diverging color for a value; `span` is the magnitude that gets the end color. */
export function divergingColor(value: number, span: number): string {
  const t = Math.max(-1, Math.min(1, value / span));
  const k = Math.pow(Math.abs(t), 0.75);
  const arm = (t < 0 ? SINK : RISE).map(hexToRgb);
  const stops = [hexToRgb(NEUTRAL), ...arm];
  const pos = k * (stops.length - 1);
  const i = Math.min(stops.length - 2, Math.floor(pos));
  const c = mix(stops[i], stops[i + 1], pos - i);
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

/** Write UI colors to CSS custom properties (--space, --ink-2, --accent, ...). */
export function applyPalette(root: HTMLElement = document.documentElement) {
  const names: Record<keyof typeof UI, string> = {
    space: "--space", ground: "--ground", surface: "--surface", paper: "--paper", paper2: "--paper-2",
    ink: "--ink", ink2: "--ink-2", ink3: "--ink-3", line: "--line", line2: "--line-2",
    accent: "--accent", blue: "--blue", orange: "--orange", violet: "--violet", green: "--green", warn: "--warn",
  };
  for (const [k, v] of Object.entries(UI)) root.style.setProperty(names[k as keyof typeof UI], v);
  root.style.setProperty("--neutral", NEUTRAL);
}
