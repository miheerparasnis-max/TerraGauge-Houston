import { useEffect, useRef } from "react";
import maplibregl, { type GeoJSONSource, type Map as MLMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Cell, ColorBy, GapSite, Meta, NodeSite, SensorSite, Sites } from "./types";
import { cellRing } from "./geo";
import { cellColor, cellSummary } from "./labels";

export interface Layers { sensors: boolean; nodes: boolean; gaps: boolean; gps: boolean; ext: boolean; wells: boolean; flood: boolean }

interface Props {
  cells: Cell[];
  sites: Sites;
  sensors: SensorSite[];
  nodes: NodeSite[];
  gaps: GapSite[];
  mode: ColorBy;
  meta: Meta;
  year: number;
  layers: Layers;
  selected: string | null;
  focus: { lon: number; lat: number; key: number } | null;
  onSelect: (id: string | null) => void;
}

// OpenFreeMap: free vector basemap, no API key. If it can't be reached, the
// map still works on a plain background.
const BASEMAP = "https://tiles.openfreemap.org/styles/positron";
const FALLBACK: maplibregl.StyleSpecification = { version: 8, sources: {}, layers: [{ id: "bg", type: "background", paint: { "background-color": "#E6EBE5" } }] };

async function loadStyle(): Promise<string | maplibregl.StyleSpecification> {
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 6000);
    const res = await fetch(BASEMAP, { signal: controller.signal });
    clearTimeout(timer);
    if (!res.ok) throw new Error(String(res.status));
    return (await res.json()) as maplibregl.StyleSpecification;
  } catch {
    return FALLBACK;
  }
}

function cellsGeoJSON(cells: Cell[], mode: ColorBy, year: number, meta: Meta) {
  return {
    type: "FeatureCollection" as const,
    features: cells.flatMap((c) => {
      const ring = cellRing(c.id);
      return ring ? [{ type: "Feature" as const, properties: { id: c.id, fill: cellColor(c, mode, year, meta), sfha: c.flood.sfha, op: c.src.includes("estimated") ? 0.45 : 0.82 }, geometry: { type: "Polygon" as const, coordinates: [ring] } }] : [];
    }),
  };
}

const points = (rows: { lon: number; lat: number }[]) => ({
  type: "FeatureCollection" as const,
  features: rows.map((r) => ({ type: "Feature" as const, properties: { ...r }, geometry: { type: "Point" as const, coordinates: [r.lon, r.lat] } })),
});

export function MapView({ cells, sites, sensors, nodes, gaps, mode, meta, year, layers, selected, focus, onSelect }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const map = useRef<MLMap | null>(null);
  const ready = useRef<Promise<void> | null>(null);
  const markers = useRef<maplibregl.Marker[]>([]);
  const latest = useRef({ cells, mode, year, meta, onSelect });
  latest.current = { cells, mode, year, meta, onSelect };

  useEffect(() => {
    if (!ref.current) return;
    let cancelled = false;
    let m: MLMap | null = null;
    ready.current = loadStyle().then((style) => new Promise<void>((resolve) => {
      if (cancelled || !ref.current) return;
      const created = new maplibregl.Map({ container: ref.current, style, center: [-95.4, 29.8], zoom: 9.2, minZoom: 7, maxZoom: 15, attributionControl: { compact: true } });
      created.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-left");
      map.current = m = created;
      created.on("load", () => {
        const m = created;
        const firstLabel = m.getStyle().layers.find((l) => l.type === "symbol")?.id;
        const { cells: c, mode: md, year: y, meta: mt } = latest.current;
        m.addSource("cells", { type: "geojson", data: cellsGeoJSON(c, md, y, mt) });
        m.addLayer({ id: "cells", type: "fill", source: "cells", paint: { "fill-color": ["get", "fill"], "fill-opacity": ["get", "op"] } }, firstLabel);
        m.addLayer({ id: "grid", type: "line", source: "cells", minzoom: 10.5, paint: { "line-color": "#14201F", "line-opacity": ["interpolate", ["linear"], ["zoom"], 10.5, 0, 12, 0.14], "line-width": 0.6 } }, firstLabel);
        m.addLayer({ id: "flood", type: "line", source: "cells", filter: ["==", ["get", "sfha"], true], paint: { "line-color": "#2563A8", "line-width": 1, "line-opacity": 0.7 }, layout: { visibility: "none" } }, firstLabel);
        m.addLayer({ id: "selected", type: "line", source: "cells", filter: ["==", ["get", "id"], ""], paint: { "line-color": "#14201F", "line-width": 3 } });
        m.addSource("gps", { type: "geojson", data: points(sites.gps) });
        m.addSource("ext", { type: "geojson", data: points(sites.ext) });
        m.addSource("wells", { type: "geojson", data: points(sites.wells) });
        m.addLayer({ id: "wells", type: "circle", source: "wells", paint: { "circle-radius": 4, "circle-color": "#2563A8", "circle-stroke-color": "#fff", "circle-stroke-width": 1.2 } });
        m.addLayer({ id: "ext", type: "circle", source: "ext", paint: { "circle-radius": 5.5, "circle-color": "#14201F", "circle-stroke-color": "#fff", "circle-stroke-width": 2 } });
        m.addLayer({ id: "gps", type: "circle", source: "gps", paint: { "circle-radius": 4, "circle-color": "#fff", "circle-stroke-color": "#14201F", "circle-stroke-width": 1.5 } });
        m.on("click", (e) => {
          const pointLayers = ["gps", "ext", "wells"].filter((l) => m.getLayoutProperty(l, "visibility") !== "none");
          const site = m.queryRenderedFeatures(e.point, { layers: pointLayers })[0];
          if (site) {
            const p = site.properties as Record<string, unknown>;
            const html = site.layer.id === "gps"
              ? `<b>GPS station ${p.id}</b><br>Moved ${Number(p.up).toFixed(1)} mm a year (up is positive)<br>${Number(p.y0).toFixed(0)} to ${Number(p.y1).toFixed(0)}, HoustonNet`
              : site.layer.id === "ext"
              ? `<b>${p.name}</b><br>Extensometer: measures soil squeezing underground<br>${Number(p.c).toFixed(2)} ft since ${p.d0}`
              : `<b>${p.name}</b><br>Groundwater well, USGS<br>${p.dd === null ? "No change recorded" : `Water ${Number(p.dd) >= 0 ? `${Number(p.dd).toFixed(1)} ft deeper` : `${(-Number(p.dd)).toFixed(1)} ft shallower`}`}, ${p.t0} to ${p.t1}`;
            new maplibregl.Popup({ maxWidth: "260px" }).setLngLat(e.lngLat).setHTML(html).addTo(m);
            return;
          }
          const cell = m.queryRenderedFeatures(e.point, { layers: ["cells"] })[0];
          latest.current.onSelect(cell ? String(cell.properties.id) : null);
        });
        const tip = new maplibregl.Popup({ closeButton: false, closeOnClick: false, className: "hover-tip", offset: 10 });
        const byId = () => new Map(latest.current.cells.map((x) => [x.id, x]));
        let index = byId(), indexed = latest.current.cells;
        m.on("mousemove", "cells", (e) => {
          if (matchMedia("(hover: none)").matches) return;
          const f = e.features?.[0];
          if (!f) return;
          if (indexed !== latest.current.cells) { index = byId(); indexed = latest.current.cells; }
          const c = index.get(String(f.properties.id));
          if (!c) return;
          const { mode: md, year: y, meta: mt } = latest.current;
          tip.setLngLat(e.lngLat).setText(cellSummary(c, md, y, mt)).addTo(m);
        });
        m.on("mouseleave", "cells", () => tip.remove());
        for (const layer of ["cells", "gps", "ext", "wells"]) {
          m.on("mouseenter", layer, () => (m.getCanvas().style.cursor = "pointer"));
          m.on("mouseleave", layer, () => (m.getCanvas().style.cursor = ""));
        }
        const zoomClass = () => ref.current?.classList.toggle("zoomed-out", m.getZoom() < 10);
        m.on("zoomend", zoomClass);
        const fit = () => {
          const narrow = window.innerWidth < 860;
          m.fitBounds([[-95.95, 29.4], [-94.8, 30.2]], { padding: narrow ? { top: 200, bottom: 90, left: 10, right: 10 } : { top: 20, bottom: 20, left: 370, right: 440 }, duration: 0 });
        };
        if (m.getContainer().clientWidth > 0) fit();
        else {
          // Created while its tab was hidden: fit once it has a real size.
          const once = () => { if (m.getContainer().clientWidth > 0) { m.off("resize", once); fit(); } };
          m.on("resize", once);
        }
        zoomClass();
        resolve();
      });
    }));
    return () => { cancelled = true; m?.remove(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const whenReady = (fn: (m: MLMap) => void) => { ready.current?.then(() => map.current && fn(map.current)); };

  useEffect(() => whenReady((m) => (m.getSource("cells") as GeoJSONSource).setData(cellsGeoJSON(cells, mode, year, meta))), [cells, mode, year, meta]);
  useEffect(() => whenReady((m) => m.setFilter("selected", ["==", ["get", "id"], selected ?? ""])), [selected]);
  useEffect(() => whenReady((m) => {
    m.setLayoutProperty("gps", "visibility", layers.gps ? "visible" : "none");
    m.setLayoutProperty("ext", "visibility", layers.ext ? "visible" : "none");
    m.setLayoutProperty("wells", "visibility", layers.wells ? "visible" : "none");
    m.setLayoutProperty("flood", "visibility", layers.flood ? "visible" : "none");
  }), [layers]);

  useEffect(() => whenReady((m) => {
    markers.current.forEach((mk) => mk.remove());
    markers.current = [];
    const add = (el: HTMLElement, id: string, lon: number, lat: number) => {
      el.addEventListener("click", (ev) => { ev.stopPropagation(); latest.current.onSelect(id); });
      markers.current.push(new maplibregl.Marker({ element: el }).setLngLat([lon, lat]).addTo(m));
    };
    if (layers.gaps) for (const g of gaps) {
      const el = document.createElement("button");
      el.className = "node-pin gap-pin";
      el.setAttribute("aria-label", `Fill-the-gap node site ${g.rank}`);
      el.title = `Fill-the-gap node site ${g.rank}: nothing measures this ground yet`;
      add(el, g.id, g.lon, g.lat);
    }
    if (layers.nodes) for (const n of nodes) {
      const el = document.createElement("button");
      el.className = "node-pin";
      el.setAttribute("aria-label", `Suggested low-cost node ${n.rank}`);
      el.title = `Low-cost node site ${n.rank}`;
      add(el, n.id, n.lon, n.lat);
    }
    if (layers.sensors) for (const s of sensors) {
      const el = document.createElement("button");
      el.className = "pin";
      el.textContent = String(s.rank);
      el.setAttribute("aria-label", `Suggested GPS station site ${s.rank}`);
      add(el, s.id, s.lon, s.lat);
    }
  }), [sensors, nodes, gaps, layers.sensors, layers.nodes, layers.gaps]);

  useEffect(() => { if (focus) whenReady((m) => { m.resize(); m.flyTo({ center: [focus.lon, focus.lat], zoom: Math.min(13, Math.max(m.getZoom(), 11.5)), duration: 900 }); }); }, [focus]);

  return <div ref={ref} className="map" role="region" aria-label="Map of Houston ground movement" />;
}
