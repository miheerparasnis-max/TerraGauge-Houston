import { memo, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import Galaxy from "./reactbits/Galaxy";
import Topography from "./reactbits/Topography";
import Radar from "./reactbits/Radar";
import PolygonRadar from "./reactbits/PolygonRadar";
import { GlobeDive, HOUSTON, radiusForVisible, zoomForRadius } from "./GlobeDive";
import { dashCamera } from "./MapView";
import type { Cell } from "./types";
import type { Meta, Sites } from "./types";
import { ACTION, num } from "./labels";
import { CONFIDENCE_COLORS, CONTEXT_BAR, PRIORITY_COLORS, RISE, SINK, SINK_EXTREME, STARS, UI } from "./palette";
import { ColumnChart, HBarChart, LineChart, SegmentedBar, monthLabel, yearOf } from "./Charts";
import { Marquee } from "./Marquee";
import { usePlaceName } from "./places";

const TAU = Math.PI * 2;
const clamp01 = (v: number) => Math.max(0, Math.min(1, v));
const ramp = (s: number, a: number, b: number) => clamp01((s - a) / (b - a));
/** 0 before a, up to 1 at b, 1 until c, down to 0 at d. */
const win = (s: number, a: number, b: number, c: number, d: number) => Math.min(ramp(s, a, b), 1 - ramp(s, c, d));
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const smooth = (t: number) => t * t * (3 - 2 * t);
const gapBehind = (sweep: number, bearing: number) => (((sweep - bearing) % TAU) + TAU) % TAU;

// Scroll story. On wide screens each section is `len` screens tall and its panel stays
// pinned for (len - 1) screens; on phones sections flow at their natural height. Either
// way the scene reads section positions measured from the page.
const SECTIONS = [["hero", 1.15], ["move", 2.4], ["sure", 2.6], ["first", 2.4], ["sources", 2.9], ["portal", 3.8]] as const;
type SectionId = (typeof SECTIONS)[number][0];
const DEFAULT_LEN = Object.fromEntries(SECTIONS) as Record<SectionId, number>;

const WORD = "TERRAGAUGE";

export interface Story {
  measured: number; direct: number; fast: number; fastInFlood: number; fastest: number;
  dates: string[]; fastCurve: number[]; typicalCurve: number[];
  bins: { label: string; n: number; mid: number }[];
}

interface Props {
  meta: Meta | null;
  sites: Sites | null;
  cells: Cell[] | null;
  story: Story | null;
  playIntro: boolean;
  /** Mount the dashboard underneath so the portal can reveal it. */
  onWarm: () => void;
  onEnter: () => void;
  /** Open the map at a place. */
  onEnterAt: (lon: number, lat: number) => void;
}

function useViewport() {
  const [vp, setVp] = useState({ w: window.innerWidth, h: window.innerHeight });
  useEffect(() => {
    const on = () => setVp({ w: window.innerWidth, h: window.innerHeight });
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, []);
  return vp;
}

function useScrollY() {
  const [y, setY] = useState(() => window.scrollY);
  useEffect(() => {
    let raf = 0;
    const on = () => { if (!raf) raf = requestAnimationFrame(() => { raf = 0; setY(window.scrollY); }); };
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => { window.removeEventListener("scroll", on); cancelAnimationFrame(raf); };
  }, []);
  return y;
}

const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** GPS stations' agreement with the satellite, in three bands. */
const band = (diff: number): "a" | "b" | "c" => (diff <= 2 ? "a" : diff <= 5 ? "b" : "c");
const BAND_COLOR = { a: CONFIDENCE_COLORS.high, b: CONFIDENCE_COLORS.medium, c: UI.orange } as const;

interface Blip { id: string; gps: number; sat: number; lon: number; lat: number; x: number; y: number; bearing: number; band: "a" | "b" | "c" }

function StationInspector({ blip, onPrev, onNext, onOpen }: { blip: Blip | null; onPrev: () => void; onNext: () => void; onOpen: (b: Blip) => void }) {
  const place = usePlaceName(blip ? `gps-${blip.id}` : "none", blip?.lon ?? 0, blip?.lat ?? 0);
  if (!blip) return <div className="inspector empty"><p>Tap any dot on the scope to see that station: what the GPS measured, what the satellite saw, and whether they agree.</p><div className="inspector-nav"><button onClick={onNext}>Show me one</button></div></div>;
  const diff = Math.abs(blip.sat - blip.gps);
  const span = Math.max(4, Math.abs(blip.gps), Math.abs(blip.sat));
  const bar = (v: number) => `${(Math.abs(v) / span) * 100}%`;
  const word = (v: number) => (v < 0 ? `sinking ${num(Math.abs(v))}` : `rising ${num(v)}`);
  return (
    <div className="inspector" aria-live="polite">
      <div className="inspector-head">
        <div><h3>Station {blip.id}</h3>{place && <p>{place}</p>}</div>
        <div className="inspector-nav"><button onClick={onPrev} aria-label="Previous station">‹</button><button onClick={onNext} aria-label="Next station">›</button></div>
      </div>
      <dl className="compare">
        <div><dt>GPS on the ground</dt><dd><span className="cmp-bar"><i style={{ width: bar(blip.gps), background: UI.ink2 }} /></span><b>{word(blip.gps)}</b> mm a year</dd></div>
        <div><dt>Satellite overhead</dt><dd><span className="cmp-bar"><i style={{ width: bar(blip.sat), background: BAND_COLOR[blip.band] }} /></span><b>{word(blip.sat)}</b> mm a year</dd></div>
      </dl>
      <p className="verdict" style={{ borderColor: BAND_COLOR[blip.band] }}>{blip.band === "a" ? `They agree within ${num(diff)} mm a year.` : blip.band === "b" ? `Close: ${num(diff)} mm a year apart.` : `They differ by ${num(diff)} mm a year. A GPS station measures one spot, while the satellite averages the whole square kilometer around it.`}</p>
      <button className="text-btn" onClick={() => onOpen(blip)}>See this place on the map →</button>
    </div>
  );
}

function SiteRow({ rank, lon, lat, rate, km, onOpen }: { rank: number; lon: number; lat: number; rate: number; km: number; onOpen: () => void }) {
  const place = usePlaceName(`site-${rank}`, lon, lat);
  return (
    <li><button onClick={onOpen}>
      <span className="rank">{rank}</span>
      <span><b>{place ?? "Suggested station site"}</b><small>Area sinking {num(Math.abs(rate / 10))} cm a year · {num(km)} km from the nearest GPS</small></span>
      <span className="go" aria-hidden="true">→</span>
    </button></li>
  );
}

/** The GPS stations on the card 02 scope; positions are fixed, so scrolling never re-renders them. */
const BlipDots = memo(function BlipDots({ blips, station, setStation, refs }: { blips: Blip[]; station: number | null; setStation: (i: number) => void; refs: React.MutableRefObject<(HTMLButtonElement | null)[]> }) {
  return (
    <>
      {blips.map((b, i) => (
        <button key={b.id} ref={(el) => { refs.current[i] = el; }} className={station === i ? "blip on" : "blip"} style={{ left: `${50 + b.x * 50}%`, top: `${50 - b.y * 50}%`, ["--c" as string]: BAND_COLOR[b.band] }}
          onClick={() => setStation(i)} tabIndex={-1} aria-label={`Station ${b.id}`} />
      ))}
    </>
  );
});

/* Card contents are memoized: scrolling only moves and fades each card, it never rebuilds its charts. */

const ProblemCard = memo(function ProblemCard({ story: st, chartH }: { story: Story | null; chartH: number }) {
  return (
    <>
    <div className="col">
      <p className="kicker">01 · The problem</p>
      <h2 id="b-move">Houston is sinking, and sinking land floods deeper</h2>
      <p className="lede">Much of Houston sits on thick clay. Pumping water out of the sand between the clay layers lets the clay squeeze, and the land above drops for good. Lower ground means the same storm brings deeper water, and drains and levees were built for the old ground level.</p>
      <ul className="facts-list">
        <li><strong>10+ ft</strong><span>of sinking near Pasadena between 1906 and 1995. About 3,200 square miles of greater Houston dropped at least a foot.<cite>USGS</cite></span></li>
        <li><strong>~10 ft</strong><span>Baytown's Brownwood neighborhood sank so far that Hurricane Alicia wiped it out in 1983. It is a nature center today.<cite>Houston History Magazine</cite></span></li>
        <li><strong>28 in</strong><span>dropped at a GPS station in Jersey Village over 26 years, as pumping moved northwest.<cite>Harris-Galveston Subsidence District</cite></span></li>
        <li><strong>$125B</strong><span>in damage from Hurricane Harvey in 2017, after almost 34 inches of rain fell on Harris County in four days.<cite>NOAA, Harris County Flood Control District</cite></span></li>
      </ul>
      <p className="hope">It can be slowed. Where pumping was cut in the late 1970s, sinking along the Ship Channel largely stopped. Knowing exactly where the ground moves now tells the region where to act next.<cite>USGS</cite></p>
    </div>
    <div className="col">
      <figure className="fig">
        <figcaption><b>Ten years of sinking, seen from space</b><span>Ground change since July 2016. Middle value of the fastest-sinking tenth of measured squares, and of all measured squares.</span></figcaption>
        {st && <LineChart x={st.dates.map(yearOf)} labels={st.dates.map(monthLabel)} xTicks={[2017, 2019, 2021, 2023, 2025]} unit="cm" height={chartH} ariaLabel="Ground change since 2016, in centimeters"
          series={[{ name: "Fastest-sinking tenth", color: SINK[2], values: st.fastCurve }, { name: "Typical square", color: UI.ink3, values: st.typicalCurve, emphasis: false }]} />}
      </figure>
      <figure className="fig">
        <figcaption><b>How fast each square is moving</b><span>{st ? st.measured.toLocaleString() : "—"} squares of 1 km, in mm a year</span></figcaption>
        {st && <ColumnChart height={Math.round(chartH * 0.85)} ariaLabel="Number of squares by speed of movement" bars={st.bins.map((b, i) => ({ label: b.label, value: b.n, color: [RISE[1], CONTEXT_BAR, SINK[0], SINK[1], SINK[2], SINK_EXTREME][i] }))} />}
      </figure>
      <p className="punch"><strong>{st ? st.fast.toLocaleString() : "—"}</strong> squares sink 1 cm or more a year. <strong>{st ? st.fastInFlood.toLocaleString() : "—"}</strong> of them sit inside FEMA high-risk flood zones.</p>
    </div>
    </>
  );
});

const ConfidenceCard = memo(function ConfidenceCard({ meta, blips, station, setStation, openAt }: { meta: Meta | null; blips: Blip[]; station: number | null; setStation: (i: number | null) => void; openAt: (lon: number, lat: number) => void }) {
  const bands = { a: blips.filter((b) => b.band === "a").length, b: blips.filter((b) => b.band === "b").length, c: blips.filter((b) => b.band === "c").length };
  const pickBlip = (i: number) => setStation(((i % blips.length) + blips.length) % blips.length);
  return (
    <>
    <p className="kicker">02 · Confidence</p>
    <h2 id="b-sure">How sure are we?</h2>
    <p className="lede">We compared the satellite with {meta?.validation.stations ?? "—"} GPS stations it never learned from. Each dot on the scope is one of them, drawn where it stands around Houston.</p>
    <div className="trio">
      <p><strong>{meta ? num(meta.validation.typical_diff_mm_year) : "—"}</strong><span>mm a year: the typical gap between them</span></p>
      <p><strong>{meta ? meta.validation.r.toFixed(2) : "—"}</strong><span>out of 1: how closely they rise and fall together</span></p>
      <p><strong>{meta ? (meta.counts.confidence.high ?? 0).toLocaleString() : "—"}</strong><span>squares confirmed by a GPS station nearby</span></p>
    </div>
    {blips.length > 0 && <SegmentedBar ariaLabel="How far apart the satellite and each GPS station are" parts={[
      { label: "Within 2 mm a year", value: bands.a, color: BAND_COLOR.a },
      { label: "2 to 5 mm", value: bands.b, color: BAND_COLOR.b },
      { label: "More than 5 mm", value: bands.c, color: BAND_COLOR.c },
    ]} />}
    <StationInspector blip={station === null ? null : blips[station] ?? null} onPrev={() => pickBlip((station ?? 0) - 1)} onNext={() => pickBlip(station === null ? blips.findIndex((b) => b.band === "a") : station + 1)} onOpen={(b) => openAt(b.lon, b.lat)} />
    </>
  );
});

const PriorityCard = memo(function PriorityCard({ meta, openAt }: { meta: Meta | null; openAt: (lon: number, lat: number) => void }) {
  const counts = meta?.counts.action ?? {};
  const hw = meta?.hardware;
  return (
    <>
    <div className="col">
      <p className="kicker">03 · Priority</p>
      <h2 id="b-first">Where should Houston look first?</h2>
      <p className="lede">Sinking matters most where floods already reach. Every square gets one action, from rules checked in order, and the map suggests exactly where a new sensor would turn a satellite reading into proof.</p>
      <ul className="facts-list keyed">
        {(["investigate_first", "add_monitoring", "review_disagreement"] as const).map((k) => (
          <li key={k}><strong>{(counts[k] ?? 0).toLocaleString()}</strong><span><i className="key-box" style={{ background: ACTION[k].color }} /><b>{ACTION[k].name}.</b> {ACTION[k].meaning}</span></li>
        ))}
      </ul>
      {hw && meta && (
        <div className="kit">
          <div><strong>{meta.sensors.length}</strong><span>permanent GPS stations, about $20,000–30,000 each. One confirms 1 cm a year of sinking in about {hw.gps_weeks_10} weeks.</span></div>
          <div><strong>{meta.nodes.length}</strong><span>low-cost sensors, from $74. About {hw.node_weeks_10} weeks to confirm the same, and every flagged flood-zone square gets one within 6 km.</span></div>
          <div><strong>{meta.gaps.length}</strong><span>sensors for land nothing measures yet.</span></div>
        </div>
      )}
    </div>
    <div className="col">
      <figure className="fig">
        <figcaption><b>What each measured square needs</b><span>Number of 1 km squares in each action</span></figcaption>
        <HBarChart ariaLabel="Squares in each action" labelWidth={170} rows={(["investigate_first", "add_monitoring", "review_disagreement", "observe", "no_clear_motion"] as const).map((k) => ({ label: ACTION[k].name, value: counts[k] ?? 0, color: k === "no_clear_motion" ? CONTEXT_BAR : PRIORITY_COLORS[k], note: ACTION[k].meaning }))} />
      </figure>
      {meta && (
        <figure className="fig">
          <figcaption><b>Top sites for a new GPS station</b><span>Fastest-sinking flood-zone areas with no station nearby</span></figcaption>
          <ol className="site-rows">{meta.sensors.slice(0, 3).map((x) => <SiteRow key={x.id} rank={x.rank} lon={x.lon} lat={x.lat} rate={x.areaRate} km={x.gpsKm} onOpen={() => openAt(x.lon, x.lat)} />)}</ol>
        </figure>
      )}
    </div>
    </>
  );
});

interface Source { short: string; name: string; what: string; use: string }
const EvidenceCard = memo(function EvidenceCard({ sources, active }: { sources: Source[]; active: number }) {
  const src = sources[active];
  return (
    <>
    <p className="kicker">04 · Evidence</p>
    <h2 id="b-sources">{sources.length} datasets, one map</h2>
    <p className="lede">Every square kilometer gets the same {sources.length} checks. Each sonar ping moves to the next one; tap a corner to jump to it.</p>
    {src && (
      <div className="readout" aria-live="polite">
        <p className="readout-step">{active + 1} of {sources.length}</p>
        <h3>{src.name}</h3>
        <p>{src.what}</p>
        <p className="use">{src.use}</p>
      </div>
    )}
    </>
  );
});

/**
 * Rendering quality for the animated backgrounds. Starts sharp; if the page can't hold
 * roughly 50 frames a second it steps the resolution down (never back up, so it can't flicker).
 */
const QUALITY = [
  { galaxy: 1, topo: 1.25, radar: 1.25, globe: 1.5 },
  { galaxy: 0.85, topo: 1, radar: 1, globe: 1.2 },
  { galaxy: 0.7, topo: 0.85, radar: 0.85, globe: 1 },
] as const;

function useQualityTier() {
  const [tier, setTier] = useState(0);
  useEffect(() => {
    let raf = 0, last = 0, from = performance.now() + 2500; // let shaders compile first
    const gaps: number[] = [];
    const loop = (t: number) => {
      if (last && t > from) gaps.push(t - last);
      last = t;
      if (gaps.length >= 90) {
        const median = [...gaps].sort((a, b) => a - b)[gaps.length >> 1];
        if (median > 20.5) setTier((x) => Math.min(QUALITY.length - 1, x + 1));
        gaps.length = 0;
        from = t + 1500;
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    const reset = () => { last = 0; gaps.length = 0; from = performance.now() + 1000; };
    document.addEventListener("visibilitychange", reset);
    return () => { cancelAnimationFrame(raf); document.removeEventListener("visibilitychange", reset); };
  }, []);
  return tier;
}

/** Build the heavy layers one at a time in idle moments while the hero is on screen, not mid-scroll. */
function useIdleStages(count: number) {
  const [stage, setStage] = useState(0);
  useEffect(() => {
    if (stage >= count) return;
    const idle = (window as Window & { requestIdleCallback?: (cb: () => void, o?: { timeout: number }) => number }).requestIdleCallback;
    const t = window.setTimeout(() => { if (idle) idle(() => setStage((x) => x + 1), { timeout: 1500 }); else setStage((x) => x + 1); }, stage === 0 ? 1200 : 1300);
    return () => clearTimeout(t);
  }, [stage, count]);
  return stage;
}

export function Landing({ meta, sites, cells, story, playIntro, onWarm, onEnter, onEnterAt }: Props) {
  const { w: W, h: H } = useViewport();
  const y = useScrollY();
  const s = y / H;
  const wide = W >= 900;
  const reduce = useMemo(reducedMotion, []);
  const [heroLit, setHeroLit] = useState(reduce || !playIntro);
  const [activeSource, setActiveSource] = useState(0);
  const [station, setStation] = useState<number | null>(null);
  const entered = useRef(false);
  const warmed = useRef(false);
  const tier = useQualityTier();
  const stage = useIdleStages(4);
  const cap = Math.min(window.devicePixelRatio || 1, 2);
  const q = QUALITY[tier];
  const dpr = (v: number) => Math.min(cap, v);
  const enterAtRef = useRef(onEnterAt);
  enterAtRef.current = onEnterAt;
  const openAt = useCallback((lon: number, lat: number) => enterAtRef.current(lon, lat), []);

  // ── Section layout, measured ──
  const rootRef = useRef<HTMLDivElement>(null);
  const secRefs = useRef<Partial<Record<SectionId, HTMLElement | null>>>({});
  const [lay, setLay] = useState(() => {
    const start = {} as Record<SectionId, number>; let acc = 0;
    for (const [id, len] of SECTIONS) { start[id] = acc; acc += len; }
    return { start, len: { ...DEFAULT_LEN }, max: acc - 1 };
  });
  useLayoutEffect(() => {
    const measure = () => {
      const start = {} as Record<SectionId, number>, len = {} as Record<SectionId, number>;
      for (const [id, def] of SECTIONS) {
        const el = secRefs.current[id];
        start[id] = el ? el.offsetTop / H : 0;
        len[id] = el ? el.offsetHeight / H : def;
      }
      const total = (rootRef.current?.offsetHeight ?? H) / H;
      setLay((prev) => {
        const next = { start, len, max: Math.max(1, total - 1) };
        return JSON.stringify(prev) === JSON.stringify(next) ? prev : next;
      });
    };
    measure();
    const ro = new ResizeObserver(measure);
    if (rootRef.current) ro.observe(rootRef.current);
    return () => ro.disconnect();
  }, [W, H, wide, story, meta]);
  const S = lay.start, MAX = lay.max;

  /** Opacity/offset of a pinned story panel (wide screens only; phones scroll naturally). */
  const panelStyle = (id: SectionId) => {
    if (!wide) return undefined;
    const t = (s - S[id]) / Math.max(0.1, lay.len[id] - 1);
    const o = win(t, -0.45, 0.02, 0.82, 1.12);
    return { opacity: o, transform: `translateY(${(1 - o) * (t < 0.5 ? 24 : -24)}px)`, visibility: o < 0.01 ? ("hidden" as const) : undefined };
  };


  // ── Scene values driven by scroll ──
  const minSide = Math.min(W, H);
  const heroScale = wide ? 0.86 : 0.92;
  const radarHero = 1 - ramp(s, 0.3, 0.95);
  const radarSure = win(s, S.sure - 0.55, S.sure + 0.05, S.first - 0.45, S.first + 0.05);
  const radarOpacity = Math.max(radarHero, radarSure);

  const sureX = wide ? 0.5 + 0.2 * win(s, S.sure - 0.8, S.sure - 0.4, S.first - 0.2, S.first + 0.2) : 0.5;
  const sureY = wide ? 0.5 : s > S.move + 0.5 ? 0.34 : 0.5;
  const radarScale = s < S.move ? heroScale : wide ? 0.7 : 0.78;

  // Evidence polygon: one corner per dataset; the portal opens the map through it.
  const polyIn = ramp(s, S.sources - 0.5, S.sources + 0.05);
  // 05: the decagon glides to the centre and becomes the Earth, which the scroll then spins
  // and dives into Houston, landing on the live map's own camera before handing over to it.
  const toCenter = smooth(ramp(s, S.portal - 0.9, S.portal - 0.25));
  const polyX = wide ? lerp(0.68, 0.5, toCenter) : 0.5;
  const polyY = wide ? lerp(0.52, 0.5, toCenter) : lerp(0.3, 0.5, toCenter);
  const morph = smooth(ramp(s, S.portal - 0.2, S.portal + 0.15));
  const dive = ramp(s, S.portal + 0.25, MAX - 0.22);
  const handoff = smooth(ramp(s, MAX - 0.22, MAX - 0.04));

  const galaxyOpacity = Math.max(1 - 0.7 * ramp(s, 0.4, 1.5), 0.3 + 0.7 * morph);
  const topoOpacity = win(s, 0.55, 1.35, S.sources - 0.5, S.sources) * (1 - 0.75 * radarSure);
  const showTopo = stage >= 1 || s > 0.25;
  // Only one big background animates at a time: the others hold still where they're covered.
  const topoMoving = topoOpacity > 0.02 && radarSure < 0.5;
  const galaxyStill = topoOpacity > 0.6 && morph < 0.01;
  const topoTilt = lerp(64, 34, smooth(ramp(s, S.move, S.sources - 1)));
  const topoElevation = lerp(0.6, 1.7, ramp(s, S.move, S.sure + 0.5));

  // Warm the dashboard before the portal so its map has tiles by the time it shows.
  useEffect(() => { if (!warmed.current && (stage >= 2 || s > S.sources - 0.3)) { warmed.current = true; onWarm(); } }, [s, stage, S.sources, onWarm]);
  useEffect(() => {
    if (!entered.current && meta && s >= MAX - 0.02 && MAX > 3) { entered.current = true; onEnter(); }
  }, [s, MAX, meta, onEnter]);

  // ── Data ──
  const years = meta ? `${meta.record.start.slice(0, 4)}–${meta.record.end.slice(0, 4)}` : "2016–2026";
  const blips = useMemo<Blip[]>(() => {
    if (!meta || !sites) return [];
    const where = new Map(sites.gps.map((g) => [g.id, g]));
    const k = Math.cos((HOUSTON[1] * Math.PI) / 180);
    const rows = meta.validation.points.flatMap((p) => {
      const g = where.get(p.id);
      if (!g) return [];
      return [{ id: p.id, gps: p.gps, sat: p.sat, lon: g.lon, lat: g.lat, dx: (g.lon - HOUSTON[0]) * k, dy: g.lat - HOUSTON[1], band: band(Math.abs(p.sat - p.gps)) }];
    });
    // Farthest station at 92% of the scope; true relative positions.
    const reach = Math.max(...rows.map((r) => Math.hypot(r.dx, r.dy)), 1e-6) / 0.92;
    return rows.map((r) => ({ ...r, x: r.dx / reach, y: r.dy / reach, bearing: Math.atan2(r.dx, r.dy) })).sort((a, b) => a.bearing - b.bearing);
  }, [meta, sites]);

  const sources = useMemo(() => {
    if (!meta) return [];
    const a = meta.nisarArchive;
    const pt = meta.predictionTest;
    const nisarUse = pt?.verdict === "pass"
      ? "Before its 2026 images existed, we wrote down which areas it should see moving most. Grouped into 10 km areas, it ranked them in nearly the same order."
      : "A first look: each square says how long NISAR needs to confirm its sinking.";
    return [
      { short: "NISAR", name: "NISAR, NASA and India's new radar satellite", what: `Passes over Houston every 12 days. We use all ${a.processedPairs} of its image pairs, ${monthLabel(a.first)} to ${monthLabel(a.last)}.`, use: nisarUse },
      { short: "Radar record", name: `Ten years of NASA satellite radar, ${years}`, what: `${meta.record.products} snapshots of how far the ground moved, every few months.`, use: "The long record the whole map is built from." },
      { short: "GPS", name: "HoustonNet GPS stations", what: `${meta.stations.total} stations that measure their own height to the millimeter.`, use: `The ground truth we check the satellite against. ${meta.stations.deepSeated.length} stations bolted to deep underground anchors are left out: they track deep ground, not the surface.` },
      { short: "Flood zones", name: "FEMA flood zones", what: "The official map of flood risk.", use: "Sinking inside a high-risk zone moves a square up the list. A square with no mapped zone counts as unknown, never as safe." },
      { short: "Harvey", name: "Hurricane Harvey flood maps, USGS", what: "Where Harvey's water actually reached in 2017, and how deep.", use: "A real-world check of the flood view." },
      { short: "Wells", name: "Groundwater wells, USGS", what: "Whether underground water levels have dropped.", use: "Part of every square's evidence." },
      { short: "Soil gauges", name: "Soil compaction gauges, USGS", what: "How much the clay underground has squeezed, some since 1973.", use: "Part of every square's evidence. The Addicks gauge alone recorded almost 4 feet." },
      { short: "Elevation", name: "Ground elevation, NASA", what: "How high every square sits.", use: "Finds the low ground for the flood view." },
      { short: "Surface water", name: "Surface water, NASA", what: "Where water covers the ground.", use: "Marks lakes and bays as 'no measurement' instead of guessing." },
      { short: "Construction", name: "Construction and clearing, NASA", what: "Where land was dug up or cleared.", use: "Lowers our confidence where construction could look like sinking." },
    ];
  }, [meta, years]);
  const N = Math.max(3, sources.length || 10);

  // ── Radar-synced overlays (direct DOM writes once per radar frame) ──
  const letterRefs = useRef<(HTMLSpanElement | null)[]>([]);
  const lit = useRef<boolean[]>(WORD.split("").map(() => reduce || !playIntro));
  const blipRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const cornerRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const geo = useRef({ cx: 0, cy: 0, sure: 0, heroOn: true, blips });
  geo.current = { cx: sureX * W, cy: sureY * H, sure: radarSure, heroOn: radarHero > 0.01, blips };
  const activeRef = useRef(0);
  const heldUntil = useRef(0);
  const lastPulse = useRef(0);
  const polyShown = useRef(false);

  const letterAt = useRef({ y: NaN, w: 0, bearings: [] as number[] });
  const onSweep = useCallback((sweep: number, intro: number) => {
    const g = geo.current;
    if (g.heroOn) {
      let all = true;
      const cache = letterAt.current;
      if (cache.y !== window.scrollY || cache.w !== window.innerWidth) {
        // Measure only when the page has moved, not on every radar frame.
        cache.bearings = letterRefs.current.map((el) => { if (!el) return 0; const r = el.getBoundingClientRect(); return Math.atan2(r.left + r.width / 2 - g.cx, g.cy - (r.top + r.height / 2)); });
        cache.y = window.scrollY; cache.w = window.innerWidth;
      }
      letterRefs.current.forEach((el, i) => {
        if (!el) return;
        const gap = gapBehind(sweep, cache.bearings[i]);
        if (!lit.current[i] && (i === 0 || lit.current[i - 1]) && intro > 0.55 && gap < 0.35) { lit.current[i] = true; el.classList.add("on"); }
        el.style.setProperty("--f", Math.exp(-gap * 2.4).toFixed(3));
        all &&= lit.current[i];
      });
      if (all) setHeroLit(true);
    }
    if (g.sure > 0.01) g.blips.forEach((b, i) => blipRefs.current[i]?.style.setProperty("--f", Math.exp(-gapBehind(sweep, b.bearing) * 1.3).toFixed(3)));
  }, []);

  // Sonar: every ping that reaches the rim lights all corners; each new ping moves to the next dataset.
  const polyVisible = useRef(false);
  polyVisible.current = polyIn > 0.01;
  const onPing = useCallback((pulse: number) => {
    if (!polyVisible.current) { polyShown.current = false; return; }
    if (!polyShown.current) { polyShown.current = true; activeRef.current = 0; heldUntil.current = performance.now() + 2500; setActiveSource(0); }
    const f = Math.exp(-Math.abs(pulse - 1) * 7);
    cornerRefs.current.forEach((el) => el?.style.setProperty("--f", f.toFixed(3)));
    if (pulse < lastPulse.current - 0.5 && performance.now() > heldUntil.current) {
      activeRef.current = (activeRef.current + 1) % Math.max(1, cornerRefs.current.filter(Boolean).length);
      setActiveSource(activeRef.current);
    }
    lastPulse.current = pulse;
  }, []);
  const pickSource = (i: number) => { activeRef.current = i; heldUntil.current = performance.now() + 9000; setActiveSource(i); };

  useEffect(() => { letterRefs.current.forEach((el, i) => el?.classList.toggle("on", lit.current[i])); });

  const toStory = () => window.scrollTo({ top: S.move * H, behavior: reduce ? "auto" : "smooth" });

  // Scope geometry in screen pixels.
  const sureR = (radarScale * minSide) / 2;
  const sureBox = { left: sureX * W - sureR, top: sureY * H - sureR, width: 2 * sureR, height: 2 * sureR };
  const pcx = polyX * W, pcy = polyY * H;
  const polyR = (0.56 * minSide) / 2;
  const polyScale = (2 * polyR) / minSide;
  // The Earth starts exactly the decagon's size, spins half a turn to the Gulf Coast, then dives.
  const target = dashCamera;
  const lat0 = 16;
  const diveCamera = (t: number, m = 1) => ({
    lon: lerp(target.center[0] + 180, target.center[0], smooth(ramp(t, 0, 0.75))),
    lat: lerp(lat0, target.center[1], smooth(ramp(t, 0.1, 0.85))),
    zoom: lerp(zoomForRadius(radiusForVisible(polyR * lerp(0.9, 1, m)), lat0), target.zoom, smooth(ramp(t, 0.18, 1))),
  });
  const camera = diveCamera(dive, morph);
  const pathRef = useRef(diveCamera);
  pathRef.current = diveCamera;
  const divePath = useCallback((t: number) => pathRef.current(t), []);
  const showPoly = stage >= 3 || s > S.first - 0.2;
  const showGlobe = stage >= 4 || s > S.portal - 0.8;
  const corners = Array.from({ length: N }, (_, k) => { const b = (k / N) * TAU; return { b, x: pcx + Math.sin(b) * polyR, y: pcy - Math.cos(b) * polyR }; });
  // Portal: a polygon hole in the scene shows the live map underneath.

  const st = story;
  const portalCopy = win(s, S.portal - 0.2, S.portal + 0.15, S.portal + 0.55, S.portal + 0.95);
  const chartH = Math.round(Math.max(140, Math.min(200, H * 0.2)));

  return (
    <div className="landing" ref={rootRef}>
      {/* ── Fixed scene ── */}
      <div className="scene" style={{ opacity: 1 - handoff, visibility: handoff > 0.995 ? "hidden" : undefined }}>
        <div className="layer" style={{ opacity: galaxyOpacity }} aria-hidden="true">
          <Galaxy transparent={false} backgroundColor={UI.space} starColors={[...STARS, UI.accent, UI.blue]} density={1.1} glowIntensity={0.28} twinkleIntensity={0.4} saturation={0.2} hueShift={200} rotationSpeed={0.04} starSpeed={0.3} mouseRepulsion={false} repulsionStrength={1} intro={playIntro && !reduce} disableAnimation={galaxyStill} dpr={dpr(q.galaxy)} />
        </div>
        {showTopo && (
          <div className="layer" style={{ opacity: topoOpacity, visibility: topoOpacity < 0.01 ? "hidden" : undefined }} aria-hidden="true">
            <Topography color={UI.blue} lineCount={26} lineWidth={1.1} elevation={topoElevation} tilt={topoTilt} speed={topoMoving ? 0.18 : 0} glow={0.6} fog={0.5} depthOfField={0.35} foreground={0.25} parallax={0.4} markers={topoMoving && s > S.first - 0.3 ? "plus" : "none"} hoverEffect="lift" clickEffect="pulse" dpr={dpr(q.topo)} />
          </div>
        )}
        {(
          <div className="layer" style={{ opacity: radarOpacity, visibility: radarOpacity < 0.01 ? "hidden" : undefined }} aria-hidden="true">
            <Radar sweepStart={-1.35} color={UI.accent} scale={radarScale} centerX={sureX} centerY={sureY} ringCount={wide ? 6 : 5} spokeCount={12} targets={0} clutter={0.1} trail={0.42} glow={0.9} gridOpacity={0.8} speed={0.9} grain={0.02} paused={radarOpacity < 0.01} onSweep={onSweep} dpr={dpr(q.radar)} />
          </div>
        )}
        {showPoly && (
          <div className="layer" style={{ opacity: polyIn * (1 - morph), visibility: polyIn * (1 - morph) < 0.01 ? "hidden" : undefined }} aria-hidden="true">
            <PolygonRadar sides={N} intro={false} mode="pulse" color={UI.accent} scale={polyScale} centerX={polyX} centerY={polyY} ringCount={5} spokeCount={N} ticks={false} targets={12} clutter={0.22} trail={0.5} glow={0.85} gridOpacity={0.9} speed={0.8} grain={0.02} paused={polyIn * (1 - morph) < 0.01} onSweep={onPing} dpr={dpr(q.radar)} />
          </div>
        )}

        {showGlobe && (
          <div className="layer" style={{ opacity: morph, visibility: morph < 0.001 ? "hidden" : undefined }}>
            <GlobeDive camera={camera} cells={cells} meta={meta} active={morph > 0.001} pixelRatio={dpr(q.globe)} path={divePath} />
          </div>
        )}

        {/* GPS stations on the scope (card 02): tap one to inspect it. */}
        <div className="scope" style={{ ...sureBox, opacity: radarSure, visibility: radarSure > 0.02 ? undefined : "hidden" }}>
          <BlipDots blips={blips} station={station} setStation={setStation} refs={blipRefs} />
        </div>

        {/* Dataset names on the polygon's corners (card 04). */}
        <div className="corners" style={{ opacity: polyIn * (1 - ramp(s, S.portal - 0.95, S.portal - 0.55)), visibility: polyIn > 0.02 && s < S.portal - 0.5 ? undefined : "hidden" }} role="group" aria-label="Datasets">
          {sources.map((x, i) => {
            const c = corners[i];
            if (!c) return null;
            const out = wide ? 1.1 : 1.08;
            return (
              <button key={x.short} ref={(el) => { cornerRefs.current[i] = el; }} className={i === activeSource ? "corner on" : "corner"} onClick={() => pickSource(i)} aria-pressed={i === activeSource}
                style={{ left: pcx + Math.sin(c.b) * polyR * out, top: pcy - Math.cos(c.b) * polyR * out, transform: `translate(${-50 + 50 * Math.sin(c.b)}%, ${-50 - 50 * Math.cos(c.b)}%)` }}>
                {x.short}
              </button>
            );
          })}
        </div>
      </div>


      {/* ── Top bar ── */}
      <header className="lbar" style={dive > 0.85 ? { opacity: 1 - ramp(dive, 0.85, 1), pointerEvents: dive > 0.95 ? "none" : undefined } : undefined}>
        <span className="lbar-brand"><img src="./logo.png" alt="" width={30} height={30} />TerraGauge</span>
        <button className="ghost" onClick={onEnter}>Open the map <span aria-hidden="true">→</span></button>
      </header>

      {/* ── Hero ── */}
      <section ref={(el) => { secRefs.current.hero = el; }} className={heroLit ? "hero lit" : "hero"} style={{ height: DEFAULT_LEN.hero * H }} aria-label="TerraGauge Houston">
        <div className="hero-stage" style={{ height: H, ["--R" as string]: `${(heroScale * minSide) / 2}px` }}>
          <h1 className="wordmark" aria-label="TerraGauge">
            {WORD.split("").map((ch, i) => <span key={i} ref={(el) => { letterRefs.current[i] = el; }} aria-hidden="true">{ch}</span>)}
          </h1>
          <img className="hero-logo" src="./logo.png" alt="" />
          <div className="hero-copy">
            <p className="tagline">Where did Houston's ground move, and how sure are we?</p>
            <p className="hero-sub">Ten years of NASA satellite radar and the new NISAR mission, checked against GPS on the ground, one square kilometer at a time.</p>
            <button className="cta" onClick={toStory}>Start the story</button>
          </div>
          <div className="scroll-cue" style={{ opacity: 1 - ramp(s, 0.05, 0.3) }} aria-hidden="true"><span />Scroll</div>
        </div>
      </section>

      {/* ── 01 The problem ── */}
      <section ref={(el) => { secRefs.current.move = el; }} className="beat" style={wide ? { height: DEFAULT_LEN.move * H } : undefined} aria-labelledby="b-move">
        <div className="hold" style={wide ? { height: H } : undefined}>
          <article className="glass wide-card" style={panelStyle("move")}>
            <ProblemCard story={st} chartH={chartH} />
          </article>
        </div>
      </section>

      {/* ── 02 Confidence ── */}
      <section ref={(el) => { secRefs.current.sure = el; }} className="beat right" style={wide ? { height: DEFAULT_LEN.sure * H } : undefined} aria-labelledby="b-sure">
        <div className="hold" style={wide ? { height: H } : undefined}>
          {!wide && <div className="beat-spacer" aria-hidden="true" />}
          <article className="glass side-card" style={panelStyle("sure")}>
            <ConfidenceCard meta={meta} blips={blips} station={station} setStation={setStation} openAt={openAt} />
          </article>
        </div>
      </section>

      {/* ── 03 Priority ── */}
      <section ref={(el) => { secRefs.current.first = el; }} className="beat" style={wide ? { height: DEFAULT_LEN.first * H } : undefined} aria-labelledby="b-first">
        <div className="hold" style={wide ? { height: H } : undefined}>
          <article className="glass wide-card" style={panelStyle("first")}>
            <PriorityCard meta={meta} openAt={openAt} />
          </article>
        </div>
      </section>

      {/* ── 04 Evidence ── */}
      <section ref={(el) => { secRefs.current.sources = el; }} className="beat right" style={wide ? { height: DEFAULT_LEN.sources * H } : undefined} aria-labelledby="b-sources">
        <div className="hold" style={wide ? { height: H } : undefined}>
          {!wide && <div className="beat-spacer tall" aria-hidden="true" />}
          <article className="glass side-card" style={panelStyle("sources")}>
            <EvidenceCard sources={sources} active={activeSource} />
          </article>
        </div>
      </section>

      {/* ── 05 The map ── */}
      <section ref={(el) => { secRefs.current.portal = el; }} className="beat portal" style={{ height: DEFAULT_LEN.portal * H }} aria-labelledby="b-portal">
        <div className="hold" style={{ height: H }}>
          <div className="portal-copy" style={{ opacity: portalCopy }}>
            {/* Remounts as it comes into view, so the title starts centered and then drifts. */}
            <Marquee key={portalCopy > 0.02 ? "in" : "out"} as="h2" id="b-portal" text="Every square, its evidence, and what's missing" />
            <p className="portal-hint">Keep scrolling to dive into Houston</p>
          </div>
        </div>
      </section>
    </div>
  );
}
