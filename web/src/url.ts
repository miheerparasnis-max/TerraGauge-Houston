import type { Hazard, Mode } from "./types";

export type Tab = "map" | "how" | "hardware";
export interface ViewState { tab: Tab; mode: Mode; hazard: Hazard; year: number | null; cell: string | null }

const TABS: Tab[] = ["map", "how", "hardware"];
const MODES: Mode[] = ["movement", "confidence", "future", "priority", "hazards"];
const HAZARDS: Hazard[] = ["flood", "drought", "bending"];

/** Read the view from the address bar, e.g. #map?mode=future&year=2030&cell=epsg3857-1km--10600-3480 */
export function readHash(): Partial<ViewState> {
  const raw = window.location.hash.replace(/^#/, "");
  const [path, query = ""] = raw.split("?");
  const q = new URLSearchParams(query);
  const out: Partial<ViewState> = {};
  if (TABS.includes(path as Tab)) out.tab = path as Tab;
  const mode = q.get("mode"), hazard = q.get("hazard"), year = Number(q.get("year")), cell = q.get("cell");
  if (mode && MODES.includes(mode as Mode)) out.mode = mode as Mode;
  if (hazard && HAZARDS.includes(hazard as Hazard)) out.hazard = hazard as Hazard;
  if (Number.isFinite(year) && year > 2000) out.year = year;
  if (cell && /^epsg3857-1km--?\d+--?\d+$/.test(cell)) out.cell = cell;
  return out;
}

export function writeHash(v: ViewState): string {
  const q = new URLSearchParams();
  if (v.tab === "map") {
    if (v.mode !== "movement") q.set("mode", v.mode);
    if (v.mode === "hazards") q.set("hazard", v.hazard);
    if (v.year && (v.mode === "future" || (v.mode === "hazards" && v.hazard === "flood"))) q.set("year", String(v.year));
    if (v.cell) q.set("cell", v.cell);
  }
  const s = q.toString();
  const hash = `#${v.tab}${s ? `?${s}` : ""}`;
  if (window.location.hash !== hash) window.history.replaceState(null, "", hash);
  return `${window.location.origin}${window.location.pathname}${hash}`;
}
