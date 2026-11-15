import { useEffect, useRef, type ReactNode } from "react";
import maplibregl from "maplibre-gl";
import type { Cell, ColorBy, Meta } from "./types";
import { cellsGeoJSON, loadStyle } from "./MapView";
import { useNearView } from "./Charts";

export interface FigurePin { lon: number; lat: number; label?: string; kind: "station" | "node" | "focus" }

/** A still, real map of one part of Houston: the same squares and colors as the main map. */
export function MapFigure({ cells, meta, mode, year, center, zoom, pins = [], height = 300, caption, onOpen }: {
  cells: Cell[]; meta: Meta; mode: ColorBy; year: number; center: [number, number]; zoom: number; pins?: FigurePin[]; height?: number; caption: ReactNode; onOpen?: () => void;
}) {
  const [wrap, near] = useNearView<HTMLElement>();
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!near || !box.current) return;
    let m: maplibregl.Map | null = null;
    let live = true;
    loadStyle().then((style) => {
      if (!live || !box.current) return;
      m = new maplibregl.Map({ container: box.current, style, center, zoom, interactive: false, attributionControl: false, fadeDuration: 0 });
      m.on("styleimagemissing", (e) => { if (m && !m.hasImage(e.id)) m.addImage(e.id, { width: 1, height: 1, data: new Uint8Array(4) }); });
      m.on("load", () => {
        if (!m) return;
        const firstLabel = m.getStyle().layers.find((l) => l.type === "symbol")?.id;
        m.addSource("cells", { type: "geojson", data: cellsGeoJSON(cells, mode, year, meta) });
        m.addLayer({ id: "cells", type: "fill", source: "cells", paint: { "fill-color": ["get", "fill"], "fill-opacity": ["get", "op"] } }, firstLabel);
        for (const p of pins) {
          const el = document.createElement("div");
          el.className = p.kind === "station" ? "pin" : p.kind === "node" ? "node-pin" : "focus-ring";
          if (p.kind === "station" && p.label) el.textContent = p.label;
          new maplibregl.Marker({ element: el }).setLngLat([p.lon, p.lat]).addTo(m);
        }
      });
    });
    return () => { live = false; m?.remove(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [near]);
  return (
    <figure className="figure map-figure" ref={wrap}>
      <div className="map-still" style={{ height }} ref={box} role="img" aria-label="Map of part of Houston" />
      {onOpen && <button className="figure-open" onClick={onOpen}>Open in the map</button>}
      <figcaption>{caption}</figcaption>
    </figure>
  );
}
