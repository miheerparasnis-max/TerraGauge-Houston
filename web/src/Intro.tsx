import { useEffect, useRef } from "react";
import maplibregl, { type StyleSpecification } from "maplibre-gl";

/** Downtown Houston: the dive ends here, at the centre of the screen, where the hero radar opens. */
export const HOUSTON: [number, number] = [-95.37, 29.76];

// NASA Black Marble night lights (VIIRS, 2016 composite) served by NASA GIBS. No key needed.
const BLACK_MARBLE = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/VIIRS_Black_Marble/default/2016-01-01/GoogleMapsCompatible_Level8/{z}/{y}/{x}.png";

const STYLE: StyleSpecification = {
  version: 8,
  projection: { type: "globe" },
  sky: { "atmosphere-blend": ["interpolate", ["linear"], ["zoom"], 0, 1, 4, 0.9, 7, 0] },
  sources: { night: { type: "raster", tiles: [BLACK_MARBLE], tileSize: 256, maxzoom: 8 } },
  layers: [{ id: "night", type: "raster", source: "night", paint: { "raster-fade-duration": 0, "raster-brightness-max": 1, "raster-saturation": -0.1 } }],
};

const easeInOut = (t: number) => 0.5 - Math.cos(Math.PI * t) / 2;
/** Length of the combined spin-and-dive. */
const SPIN_ZOOM_MS = 3400;

/** Zoom at which the globe is about `share` of the shorter screen side across (globe diameter = 512·2^z / π px). */
const fitZoom = (share: number) => Math.log2((share * Math.min(window.innerWidth, window.innerHeight) * Math.PI) / 512);

interface Props {
  /** Set to true to cut the animation short (Skip button, scroll, key press). */
  skip: boolean;
  /** Called once when the globe has arrived over Houston (or was skipped / failed). */
  onDone: () => void;
}

/**
 * Intro: a night-side globe turns from the Atlantic to the Gulf Coast and dives into Houston.
 * Transparent outside the globe so the Galaxy starfield behind it shows through.
 */
export function Intro({ skip, onDone }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const done = useRef(false);
  const latest = useRef(onDone);
  latest.current = onDone;

  const finish = () => {
    if (done.current) return;
    done.current = true;
    latest.current();
  };

  useEffect(() => {
    if (!ref.current) return;
    let m: maplibregl.Map;
    try {
      m = new maplibregl.Map({
        container: ref.current,
        style: STYLE,
        center: [-20, 18],
        zoom: fitZoom(0.5),
        interactive: false,
        attributionControl: false,
        fadeDuration: 0,
      });
    } catch {
      finish(); // no WebGL: go straight to the hero
      return;
    }
    map.current = m;
    const timers: number[] = [];
    // Never hold the visitor on a blank screen if tiles are slow.
    timers.push(window.setTimeout(finish, 9000));
    let started = false;
    const start = () => {
      if (started || done.current) return;
      started = true;
      // One move: the globe turns from the Atlantic to Houston while the camera
      // zooms in, both on the same clock, so the spin and the dive happen together.
      // Black Marble is a 500 m composite: stop at zoom 5.4, before it turns blocky.
      m.easeTo({ center: HOUSTON, zoom: 5.4, duration: SPIN_ZOOM_MS, easing: easeInOut, essential: true });
      m.once("moveend", finish);
    };
    m.once("load", () => {
      // Give the first tiles a moment so the globe isn't blank, but don't wait long.
      m.once("idle", start);
      timers.push(window.setTimeout(start, 900));
    });
    m.on("error", () => { /* tile hiccups are fine; the timeout above still ends the intro */ });
    return () => { timers.forEach(clearTimeout); m.remove(); map.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!skip) return;
    map.current?.stop();
    finish();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skip]);

  return (
    <div className="intro-globe" aria-hidden="true">
      <div ref={ref} className="intro-map" />
      <p className="intro-credit">Earth at night: NASA Black Marble</p>
    </div>
  );
}
