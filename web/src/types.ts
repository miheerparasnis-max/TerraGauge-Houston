export type ViewKey = "o" | "p" | "c";
export type LabelCode = "I" | "A" | "C" | "R" | "X";

export interface Cell {
  id: string;
  lon: number;
  lat: number;
  L: Record<ViewKey, LabelCode>;
  R: Record<ViewKey, number[]>;
  n: { d: number | null; raw: number | null; coh: number | null; vf: number | null; main: boolean };
  ch: { d: number | null; coh: number | null; vf: number | null };
  o: { v: number; se: number; cum: number; s: number[] } | null;
  f: { z: string | null; sub: string | null; x: boolean | null };
  g: { id: string | null; km: number | null; up: number | null; y0: number | null; y1: number | null };
  w: { id: string | null; km: number | null; dd: number | null };
  e: { id: string | null; km: number | null; c: number | null };
  nasadem?: Record<string, number | string | null>;
  dswx?: Record<string, number | string | null>;
  dist?: Record<string, number | string | null>;
}

export interface CheckStats { cells: number; days: number; nisar_sd_mm: number; expected_signal_sd_mm: number; pearson_r_vs_opera: number }

export interface Meta {
  generated: string;
  status: string;
  reasons: string[];
  thresholds: { coherence_min: number; valid_fraction_min: number; sigma_multiplier: number; gps_nearby_km: number };
  views: {
    opera: { title: string; dates: string[]; dates_all: string[]; products: number; noise_floor_mm_year: number; threshold_mm_year: number; counts: Record<string, number> };
    pair: { title: string; dates: string[]; reference_scatter_mm: number; reference_median_mm: number; threshold_mm: number; counts: Record<string, number> };
    chain: { title: string; dates: string[]; reference_scatter_mm: number; reference_median_mm: number; threshold_mm: number; counts: Record<string, number> };
  };
  reference: { method: string; reference_stations: string[]; held_out_stable_stations: string[] };
  signal_check: { pair: CheckStats; chain: CheckStats };
  detectability: { sigma_mm: number; interval_days: number; rows: { rate_mm_year: number; observations: number | null; years: number | null }[] };
  gps_validation: { station_count: number; pearson_r: number; median_abs_residual_mm_year: number; median_residual_mm_year: number; incidence_deg_assumed: number; method: string; limitations: string[] };
  gps_validation_points: { station_id: string; gps_los_approx_mm_year: number; opera_los_mm_year: number; residual_mm_year: number; distance_km: number }[];
  nasa_layers: Record<string, Record<string, unknown>>;
  limitations: { opera: string[]; nisar: string[] };
}

export interface Sites {
  gps: { id: string; lon: number; lat: number; up: number; y0: number; y1: number; ref: boolean }[];
  ext: { id: string; name: string; lon: number; lat: number; c: number; d0: string; d1: string; interval: string }[];
  wells: { id: string; name: string; lon: number; lat: number; dd: number | null; t0: string; t1: string }[];
}

export interface LedgerEntry { manifest: string; record: Record<string, unknown> }
