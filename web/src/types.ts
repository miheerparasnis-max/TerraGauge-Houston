export type Priority = "urgent" | "high" | "watch" | "stable" | "check" | "no_data";
export type Confidence = "high" | "medium" | "low";
export type Mode = "movement" | "confidence" | "priority";

export interface Projection { center_mm: number; low_mm: number; high_mm: number } // values are in cm (exported /10)

export interface Cell {
  id: string;
  lon: number;
  lat: number;
  rate: number | null;          // mm/yr, negative = sinking
  se: number | null;            // mm/yr
  src: ("satellite" | "gps")[];
  sig: boolean;
  conf: Confidence | null;
  confWhy: string[];
  pri: Priority;
  priWhy: string;
  needsSensor: boolean;
  future: Record<string, Projection> | null;
  series: number[] | null;      // cumulative mm along the satellite line of sight
  gps: { id: string; km: number; up: number; y0: number | null; y1: number | null };
  check: { id: string; km: number; diff: number } | null;
  flood: { zone: string | null; sub: string | null; sfha: boolean };
  well: { km: number; dd: number | null } | null;
  ext: { km: number; c: number | null } | null;
  nisar: { d: number | null; ok: boolean };
  nasadem?: { elevation_m?: number };
  dswx?: { water_fraction?: number };
  dist?: { disturbed_fraction?: number };
}

export interface SensorSite { rank: number; id: string; lon: number; lat: number; rate: number; areaRate: number; conf: Confidence; gpsKm: number; sfha: boolean; zone: string | null; future2035: Projection | null }

export interface Meta {
  status: string;
  record: { start: string; end: string; dates: string[]; products: number; extendedThroughOpera2026: boolean };
  thresholds: { stable_mm_year: number; gps_covered_km: number };
  counts: { priority: Record<string, number>; confidence: Record<string, number> };
  validation: { stations: number; r: number; typical_diff_mm_year: number; points: { id: string; gps: number; sat: number }[] };
  forecast: {
    mode: "tested" | "scenario" | "withheld"; reason?: string; damping: number; model_error_mm_year: number; base: string; years: number[];
    backtest: { train: string[]; test: string[]; cells: number; correlation: number; mae_persistence_mm_year: number; mae_no_motion_mm_year: number; best_damping: number; fast_cells: number; fast_median_before_mm_year: number | null; fast_median_after_mm_year: number | null; beats_no_motion: boolean };
  };
  nisar: { pair: { cells: number; noise_mm: number | null; signal_mm: number | null; r: number | null; status: string }; chain: { cells: number; noise_mm: number | null; signal_mm: number | null; r: number | null; status: string }; detect: { rate: number; passes: number | null; years: number | null }[]; sigma_mm: number };
  reference: { method: string; reference_stations: string[]; held_out_stable_stations: string[] };
  sensors: SensorSite[];
  nasaLayers: Record<string, string>;
}

export interface Sites {
  gps: { id: string; lon: number; lat: number; up: number; y0: number; y1: number }[];
  ext: { id: string; name: string; lon: number; lat: number; c: number; d0: string; d1: string }[];
  wells: { id: string; name: string; lon: number; lat: number; dd: number | null; t0: string; t1: string }[];
}
