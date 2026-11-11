export type Priority = "urgent" | "high" | "watch" | "stable" | "check" | "no_data";
export type Confidence = "high" | "medium" | "low";
export type Mode = "movement" | "confidence" | "priority";

export interface Cell {
  id: string;
  lon: number;
  lat: number;
  rate: number | null;          // mm/yr, up/down equivalent, negative = moved down, relative to the reference GPS stations
  se: number | null;            // mm/yr
  src: ("satellite" | "gps")[];
  sig: boolean;
  conf: Confidence | null;
  confWhy: string[];
  pri: Priority;
  priWhy: string;
  needsSensor: boolean;
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

export interface SensorSite { rank: number; id: string; lon: number; lat: number; rate: number; areaRate: number; conf: Confidence; gpsKm: number; sfha: boolean; zone: string | null }

interface NisarCheck { cells: number; days: number; noise_mm: number; signal_mm: number; r: number }

export interface Meta {
  status: string;
  record: { start: string; end: string; dates: string[]; products: number };
  geometry: { incidence_deg: number; assumption: string };
  thresholds: { stable_mm_year: number; gps_covered_km: number; gps_blend_km: number };
  counts: { priority: Record<string, number>; confidence: Record<string, number> };
  validation: { stations: number; r: number; typical_diff_mm_year: number; points: { id: string; gps: number; sat: number }[] };
  nisar: { pair: NisarCheck; chain: NisarCheck };
  nisarArchive: { passes: number; pairs: number; first: string; last: string; processedPairs: number; retrieved: string; inventory: string };
  reference: { method: string; reference_stations: string[]; held_out_stable_stations: string[] };
  sensors: SensorSite[];
  nasaLayers: Record<string, string>;
  provenance: { manifest: string };
}

export interface Sites {
  gps: { id: string; lon: number; lat: number; up: number; y0: number; y1: number }[];
  ext: { id: string; name: string; lon: number; lat: number; c: number; d0: string; d1: string }[];
  wells: { id: string; name: string; lon: number; lat: number; dd: number | null; t0: string; t1: string }[];
}
