export type Action = "investigate_first" | "add_monitoring" | "review_disagreement" | "observe" | "no_clear_motion" | "insufficient_data";
export type Confidence = "high" | "medium" | "low";
export type Mode = "movement" | "confidence" | "future" | "priority" | "hazards";
export type Hazard = "flood" | "drought" | "bending";
export type ColorBy = Exclude<Mode, "hazards"> | Hazard;
export type Level = "high" | "medium" | "low";

export interface Cell {
  id: string;
  lon: number;
  lat: number;
  rate: number | null;          // vertical mm/yr, negative = sinking (satellite + GPS combined)
  se: number | null;
  los: number | null;           // satellite line-of-sight mm/yr
  src: ("satellite" | "gps" | "estimated")[];
  est?: number;                 // number of neighbours used when estimated
  sig: boolean;
  conf: Confidence | null;
  confWhy: string[];
  act: Action;
  actWhy: string;
  sensorRank?: number;
  nodeRank?: number;
  future: { rate: number; low: number; high: number; recent: number; by: Record<string, { c: number; lo: number; hi: number }> } | null;
  detect: { nisarMonths: number | null; gpsWeeks: number | null; nodeWeeks: number | null } | null;
  series: number[] | null;      // cumulative LOS mm
  quality: { periods: number | null; periodsTotal: number; fitSe: number | null; nisarCoh: number | null; nisarValid: number | null; nisarOk: boolean };
  gps: { id: string; km: number; up: number; y0: number | null; y1: number | null };
  check: { id: string; km: number; diff: number } | null;
  flood: { zone: string | null; sub: string | null; sfha: boolean };
  well: { km: number; dd: number | null } | null;
  ext: { km: number; c: number | null } | null;
  nasadem?: { elevation_m?: number };
  dswx?: { water_fraction?: number };
  dist?: { disturbed_fraction?: number };
  hz?: { drop: number; dl: Level; bend: number | null; bl: Level | null };
}

export interface SensorSite { rank: number; id: string; lon: number; lat: number; areaRate: number; rate: number; gpsKm: number; conf: Confidence | null; zone: string | null; weeks: number | null }
export interface NodeSite { rank: number; id: string; lon: number; lat: number; areaRate: number; weeks: number; act: Action; zone: string | null; est: boolean }

interface Score { median_abs_error: number; mean_abs_error: number; correlation: number | null; fast_median_abs_error: number | null }

export interface Meta {
  status: string;
  record: { start: string; end: string; dates: string[]; products: number };
  thresholds: { stable_mm_year: number; gps_covered_km: number; gps_blend_km: number; disagree_mm_year: number; sensor_spacing_km: number; incidence_deg: number; gps_daily_sigma_mm: number };
  counts: { action: Record<string, number>; confidence: Record<string, number> };
  hazards: null | {
    tests: { drought: { flagged_median_drop_mm: number; others_median_drop_mm: number; flagged_share_in_worst10_pct: number; auc: number; cells: number }; bending: { r: number; hotspot_later_median: number; others_later_median: number; cells: number } };
    drought: { epochs: string[]; high_mm: number; medium_mm: number };
    bend: { high: number; medium: number };
    flood: { ocean_rise_mm_year: number; coastal_elevation_m: number };
  };
  validation: { stations: number; r: number; typical_diff_mm_year: number; points: { id: string; gps: number; sat: number }[] };
  forecast: null | {
    method: string; base: string; years: number[]; tested_horizon_years: number; ml_tested: boolean;
    bands_cm: { years_ahead: number; half_width_cm: number }[];
    benchmark: { test_cases: number; origins: string[]; table: { method: string; label: string; overall_cm: number; by_horizon_cm: Record<string, number> }[] };
    limitations: string[];
    backtest: { cutoff: string; predict_to: string; years_ahead: number; ml_typical_error_cm: number | null; long_term_rate_typical_error_cm: number; past_rate_typical_error_cm: number; no_motion_typical_error_cm: number; long_term_within_2cm_pct: number; fast_actual_median_cm: number; fast_long_term_predicted_median_cm: number }[];
  };
  nisar: { pair: { cells: number; noise_mm: number; signal_mm: number; r: number }; chain: { cells: number; noise_mm: number; signal_mm: number; r: number }; detect: { rate: number; passes: number | null; years: number | null }[]; sigma_mm: number };
  reference: { method: string; reference_stations: string[]; held_out_stable_stations: string[] };
  sensors: SensorSite[];
  nodes: NodeSite[];
  estimates: { count: number; radius_km: number; min_neighbors: number; median_error_mm_year: number; p80_error_mm_year: number; tested: number };
  hardware: { node_daily_sigma_mm: number; node_max_years: number; node_spacing_km: number; gps_daily_sigma_mm: number; node_weeks_10: number; gps_weeks_10: number; node_weeks_5: number; gps_weeks_5: number };
  nasaLayers: Record<string, string>;
}

export interface Sites {
  gps: { id: string; lon: number; lat: number; up: number; y0: number; y1: number }[];
  ext: { id: string; name: string; lon: number; lat: number; c: number; d0: string; d1: string }[];
  wells: { id: string; name: string; lon: number; lat: number; dd: number | null; t0: string; t1: string }[];
}
