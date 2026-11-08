import { useEffect, useRef } from "react";
import maplibregl, { type GeoJSONSource, type Map as MLMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Cell, Sites, ViewKey } from "./types";
import { cellRing } from "./geo";
import { LABELS, motionColor } from "./labels";

export type ColorMode = "label" | "value";
export interface Layers { flood: boolean; gps: boolean; ext: boolean; wells: boolean }

interface Props {
  cells: Cell[];
  sites: Sites;
  view: ViewKey;
  mode: ColorMode;
  layers: Layers;
  selected: string | null;
  onSelect: (id: string | null) => void;
}

const CARTO = (style: string) => ["a", "b", "c", "d"].map((s) => `https://${s}.basemaps.cartocdn.com/${style}/{z}/{x}/{y}@2x.png`);

export function valueFor(cell: Cell, view: ViewKey): number | null {
  if (view === "o") return cell.o ? cell.o.v : null;
  if (view === "p") return cell.n.d;
  return cell.ch.d;
}

function cellsGeoJSON(cells: Cell[], view: ViewKey, mode: ColorMode) {
  const span = view === "o" ? 18 : 40;
  return {
    type: "FeatureCollection" as const,
    features: cells.flatMap((c) => {
      const ring = cellRing(c.id);
      if (!ring) return [];
      const code = c.L[view];
      const value = valueFor(c, view);
      const fill = mode === "label" ? LABELS[code].color : code === "X" ? "rgba(0,0,0,0)" : motionColor(value, span);
      return [{ type: "Feature" as const, id: undefined, properties: { id: c.id, fill, code, flood: c.f.x === true }, geometry: { type: "Polygon" as const, coordinates: [ring] } }];
    }),
  };
}

function pointsGeoJSON(rows: { id: string; lon: number; lat: number; [k: string]: unknown }[]) {
  return { type: "FeatureCollection" as const, features: rows.map((r) => ({ type: "Feature" as const, properties: { ...r }, geometry: { type: "Point" as const, coordinates: [r.lon, r.lat] } })) };
}

export function MapView({ cells, sites, view, mode, layers, selected, onSelect }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const map = useRef<MLMap | null>(null);
  const ready = useRef(false);
  const latest = useRef({ cells, view, mode });
  latest.current = { cells, view, mode };

  useEffect(() => {
    if (!ref.current) return;
    const m = new maplibregl.Map({
      container: ref.current,
      center: [-95.37, 29.78],
      zoom: 9.1,
      minZoom: 7,
      maxZoom: 15,
      attributionControl: { compact: true },
      style: {
        version: 8,
        sources: {
          base: { type: "raster", tiles: CARTO("light_nolabels"), tileSize: 256, attribution: "© OpenStreetMap contributors © CARTO" },
          names: { type: "raster", tiles: CARTO("light_only_labels"), tileSize: 256 },
        },
        layers: [
          { id: "bg", type: "background", paint: { "background-color": "#E6EBE5" } },
          { id: "base", type: "raster", source: "base", paint: { "raster-saturation": -0.6, "raster-opacity": 0.9 } },
        ],
      },
    });
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    m.on("load", () => {
      const { cells: c, view: v, mode: md } = latest.current;
      m.addSource("cells", { type: "geojson", data: cellsGeoJSON(c, v, md) });
      m.addLayer({ id: "cells-fill", type: "fill", source: "cells", paint: { "fill-color": ["get", "fill"], "fill-opacity": 0.82 } });
      m.addLayer({ id: "cells-flood", type: "line", source: "cells", filter: ["==", ["get", "flood"], true], paint: { "line-color": "#2B6CB0", "line-width": 0.8, "line-opacity": 0.75 }, layout: { visibility: "none" } });
      m.addLayer({ id: "cells-selected", type: "line", source: "cells", filter: ["==", ["get", "id"], ""], paint: { "line-color": "#1D2B2A", "line-width": 2.5 } });
      m.addLayer({ id: "names", type: "raster", source: "names", paint: { "raster-opacity": 0.85 } });
      m.addSource("wells", { type: "geojson", data: pointsGeoJSON(sites.wells) });
      m.addSource("ext", { type: "geojson", data: pointsGeoJSON(sites.ext) });
      m.addSource("gps", { type: "geojson", data: pointsGeoJSON(sites.gps) });
      m.addLayer({ id: "wells", type: "circle", source: "wells", paint: { "circle-radius": 4, "circle-color": "#2B6CB0", "circle-stroke-color": "#fff", "circle-stroke-width": 1.2 } });
      m.addLayer({ id: "ext", type: "circle", source: "ext", paint: { "circle-radius": 6, "circle-color": "#1D2B2A", "circle-stroke-color": "#F2E3BC", "circle-stroke-width": 2 } });
      m.addLayer({ id: "gps", type: "circle", source: "gps", paint: { "circle-radius": ["case", ["get", "ref"], 5, 3.5], "circle-color": ["case", ["get", "ref"], "#B8862B", "#FFFFFF"], "circle-stroke-color": "#1D2B2A", "circle-stroke-width": 1.2 } });
      ready.current = true;
      m.on("click", (e) => {
        const site = m.queryRenderedFeatures(e.point, { layers: ["gps", "ext", "wells"].filter((l) => m.getLayoutProperty(l, "visibility") !== "none") })[0];
        if (site) {
          const p = site.properties as Record<string, unknown>;
          const html = site.layer.id === "gps"
            ? `<b>HoustonNet ${p.id}</b><br>${Number(p.up).toFixed(1)} mm/yr vertical, ${Number(p.y0).toFixed(1)}–${Number(p.y1).toFixed(1)}${p.ref ? "<br><i>Used as provisional reference</i>" : ""}`
            : site.layer.id === "ext"
            ? `<b>${p.name}</b><br>Extensometer, ${p.interval}<br>${Number(p.c).toFixed(2)} ft compaction ${p.d0} to ${p.d1}`
            : `<b>${p.name}</b><br>USGS well ${p.id}<br>Water level ${p.dd === null ? "—" : Number(p.dd).toFixed(2) + " ft deeper"}, ${p.t0} to ${p.t1}`;
          new maplibregl.Popup({ closeButton: true, maxWidth: "260px" }).setLngLat(e.lngLat).setHTML(html).addTo(m);
          return;
        }
        const cell = m.queryRenderedFeatures(e.point, { layers: ["cells-fill"] })[0];
        onSelect(cell ? String(cell.properties.id) : null);
      });
      for (const layer of ["cells-fill", "gps", "ext", "wells"]) {
        m.on("mouseenter", layer, () => (m.getCanvas().style.cursor = "pointer"));
        m.on("mouseleave", layer, () => (m.getCanvas().style.cursor = ""));
      }
      m.fire("tg-ready");
    });
    map.current = m;
    return () => m.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const apply = () => (m.getSource("cells") as GeoJSONSource).setData(cellsGeoJSON(cells, view, mode));
    if (ready.current) apply(); else m.once("tg-ready", apply);
  }, [cells, view, mode]);

  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const apply = () => {
      m.setLayoutProperty("cells-flood", "visibility", layers.flood ? "visible" : "none");
      m.setLayoutProperty("gps", "visibility", layers.gps ? "visible" : "none");
      m.setLayoutProperty("ext", "visibility", layers.ext ? "visible" : "none");
      m.setLayoutProperty("wells", "visibility", layers.wells ? "visible" : "none");
    };
    if (ready.current) apply(); else m.once("tg-ready", apply);
  }, [layers]);

  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const apply = () => m.setFilter("cells-selected", ["==", ["get", "id"], selected ?? ""]);
    if (ready.current) apply(); else m.once("tg-ready", apply);
  }, [selected]);

  return <div ref={ref} className="map" role="region" aria-label="Houston evidence map" />;
}
