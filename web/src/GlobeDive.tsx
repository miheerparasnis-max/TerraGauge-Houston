import { useEffect, useRef } from "react";
import maplibregl, { type StyleSpecification } from "maplibre-gl";
import type { Cell, Meta } from "./types";
import { cellsGeoJSON, loadStyle } from "./MapView";

/** Downtown Houston. */
export const HOUSTON: [number, number] = [-95.37, 29.76];

// NASA Black Marble night lights (VIIRS, 2016 composite) served by NASA GIBS. No key needed.
const BLACK_MARBLE = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/VIIRS_Black_Marble/default/2016-01-01/GoogleMapsCompatible_Level8/{z}/{y}/{x}.png";

/** Globe radius in screen px at a camera, MapLibre's own formula (512·2^zoom / 2π / cos latitude). */
export const globeRadius = (zoom: number, lat: number) => (512 * Math.pow(2, zoom)) / (2 * Math.PI) / Math.cos((lat * Math.PI) / 180);
/** Zoom at which the globe has radius `r` px. */
export const zoomForRadius = (r: number, lat: number) => Math.log2((r * 2 * Math.PI * Math.cos((lat * Math.PI) / 180)) / 512);

// MapLibre's camera is a perspective camera (36.87° field of view, so the focal length is
// 1.5 × the viewport height). The globe's visible edge is farther from the camera than the
// point under the crosshair, so it looks smaller than the radius above: by about 15% at full-Earth size.
const focal = () => 1.5 * window.innerHeight;
/** Visible (silhouette) radius on screen of a globe whose radius is `R` px. */
export const visibleRadius = (R: number) => { const f = focal(); return (f * R) / Math.sqrt(f * f + 2 * f * R); };
/** Globe radius that gives a visible radius of `r` px. */
export const radiusForVisible = (r: number) => { const f = focal(); return (r * r + r * Math.sqrt(r * r + f * f)) / f; };

export interface Camera { lon: number; lat: number; zoom: number }

/**
 * The night-side Earth the evidence decagon turns into. The page's scroll drives
 * the camera: it spins to the Gulf Coast and dives into Houston. Night lights
 * fade out by zoom 8 while TerraGauge's 1 km squares fade in on the same dark
 * basemap the map uses, so the last frame already looks like the map itself.
 */
export function GlobeDive({ camera, cells, meta, active, pixelRatio, path }: { camera: Camera; cells: Cell[] | null; meta: Meta | null; active: boolean; pixelRatio: number; path: (t: number) => Camera }) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const loaded = useRef(false);
  const latest = useRef({ camera, active, path });
  latest.current = { camera, active, path };

  useEffect(() => {
    let live = true;
    loadStyle().then((base) => {
      if (!live || !box.current) return;
      const style = base as StyleSpecification;
      style.projection = { type: "globe" };
      style.sky = { "atmosphere-blend": ["interpolate", ["linear"], ["zoom"], 0, 1, 5, 0.8, 8, 0] };
      style.sources = { ...style.sources, night: { type: "raster", tiles: [BLACK_MARBLE], tileSize: 256, maxzoom: 8 } };
      // Place names only once we're over Texas; at globe scale they would show through the night lights.
      style.layers = [...style.layers.map((l) => (l.type === "symbol" ? { ...l, minzoom: Math.max(l.minzoom ?? 0, 6) } : l)),
        { id: "night", type: "raster", source: "night", paint: { "raster-opacity": ["interpolate", ["linear"], ["zoom"], 5, 1, 8, 0], "raster-fade-duration": 0 } }];
      const c = latest.current.camera;
      let m: maplibregl.Map;
      try {
        m = new maplibregl.Map({ container: box.current, style, center: [c.lon, c.lat], zoom: c.zoom, interactive: false, attributionControl: false, fadeDuration: 0 });
      } catch { return; } // no WebGL: the page still opens the map at the end
      map.current = m;
      m.setPixelRatio(pixelRatio);
      m.on("styleimagemissing", (e) => { if (!m.hasImage(e.id)) m.addImage(e.id, { width: 1, height: 1, data: new Uint8Array(4) }); });
      m.on("load", () => {
        loaded.current = true;
        addSquares(m);
        const k = latest.current.camera;
        m.jumpTo({ center: [k.lon, k.lat], zoom: k.zoom });
        rehearse(m);
      });
    });
    return () => { live = false; map.current?.remove(); map.current = null; loaded.current = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /** While still hidden, fly the dive once so every tile on the way is cached before anyone scrolls there. */
  const rehearse = async (m: maplibregl.Map) => {
    const settle = () => new Promise<void>((done) => { const t = window.setTimeout(done, 2500); m.once("idle", () => { clearTimeout(t); done(); }); });
    for (const t of [0, 0.25, 0.45, 0.6, 0.72, 0.82, 0.9, 0.96, 1]) {
      if (latest.current.active || !map.current) return;
      const c = latest.current.path(t);
      m.jumpTo({ center: [c.lon, c.lat], zoom: c.zoom });
      await settle();
    }
    if (!latest.current.active && map.current) { const c = latest.current.camera; m.jumpTo({ center: [c.lon, c.lat], zoom: c.zoom }); }
  };

  const addSquares = (m: maplibregl.Map) => {
    if (!cells || !meta || m.getSource("cells")) return;
    const firstLabel = m.getStyle().layers.find((l) => l.type === "symbol")?.id;
    m.addSource("cells", { type: "geojson", data: cellsGeoJSON(cells, "movement", 0, meta) });
    m.addLayer({ id: "cells", type: "fill", source: "cells", paint: { "fill-color": ["get", "fill"], "fill-opacity": ["interpolate", ["linear"], ["zoom"], 6, 0, 8.6, ["get", "op"]] } }, firstLabel);
  };
  useEffect(() => { if (loaded.current && map.current) addSquares(map.current); }, [cells, meta]);

  // Built early and parked while hidden: the camera only moves (and the map only redraws) once it's on screen.
  useEffect(() => {
    if (active && loaded.current) map.current?.jumpTo({ center: [camera.lon, camera.lat], zoom: camera.zoom });
  }, [active, camera.lon, camera.lat, camera.zoom]);
  useEffect(() => { map.current?.setPixelRatio(pixelRatio); }, [pixelRatio]);

  const r = visibleRadius(globeRadius(camera.zoom, camera.lat));
  const fit = Math.min(window.innerWidth, window.innerHeight);
  const corona = Math.max(0, Math.min(1, (fit * 0.85 - r) / (fit * 0.35)));
  return (
    <div className="globe-dive" aria-hidden="true">
      <div className="corona" style={{ ["--r" as string]: `${r.toFixed(1)}px`, opacity: corona }} />
      <div ref={box} className="globe-map" />
      <p className="globe-credit" style={{ opacity: Math.max(0, Math.min(1, 7.5 - camera.zoom)) }}>Earth at night, NASA Black Marble</p>
    </div>
  );
}
