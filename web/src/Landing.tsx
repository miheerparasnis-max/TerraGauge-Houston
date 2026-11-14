import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Galaxy from "./reactbits/Galaxy";
import Topography from "./reactbits/Topography";
import Radar from "./reactbits/Radar";
import { Intro, HOUSTON } from "./Intro";
import type { Meta, Sites } from "./types";
import { CONFIDENCE, num } from "./labels";

const TAU = Math.PI * 2;
const CYAN = "#19E6D9";
const BLUE = "#2F7DFF";

const clamp01 = (v: number) => Math.max(0, Math.min(1, v));
const ramp = (s: number, a: number, b: number) => clamp01((s - a) / (b - a));
/** 0 before a, up to 1 at b, 1 until c, down to 0 at d. */
const win = (s: number, a: number, b: number, c: number, d: number) => Math.min(ramp(s, a, b), 1 - ramp(s, c, d));
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const smooth = (t: number) => t * t * (3 - 2 * t);
const gapBehind = (sweep: number, bearing: number) => (((sweep - bearing) % TAU) + TAU) % TAU;

// Scroll story: section lengths in screen heights. Pinned sections hold their panel for (len - 1) screens.
const SECTIONS = [
  ["hero", 1.15],
  ["move", 2.1],
  ["sure", 2.3],
  ["first", 2.1],
  ["sources", 2.7],
  ["portal", 2.3],
] as const;
type SectionId = (typeof SECTIONS)[number][0];
const START = {} as Record<SectionId, number>;
let acc = 0;
for (const [id, len] of SECTIONS) { START[id] = acc; acc += len; }
const TOTAL = acc;
const MAX = TOTAL - 1; // furthest scroll, in screens
const LEN = Object.fromEntries(SECTIONS) as Record<SectionId, number>;

const WORD = "TERRAGAUGE";
const AGREE_MM = 2;

export interface Stats { measured: number; fast: number }

interface Props {
  meta: Meta | null;
  sites: Sites | null;
  stats: Stats | null;
  playIntro: boolean;
  /** Mount the dashboard underneath so the portal can reveal it. */
  onWarm: () => void;
  onEnter: () => void;
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

function useScrollScreens(h: number) {
  const [s, setS] = useState(() => window.scrollY / h);
  useEffect(() => {
    let raf = 0;
    const on = () => { if (!raf) raf = requestAnimationFrame(() => { raf = 0; setS(window.scrollY / h); }); };
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => { window.removeEventListener("scroll", on); cancelAnimationFrame(raf); };
  }, [h]);
  return s;
}

const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Opacity/offset of a pinned story panel in section `id` at scroll `s`. */
function panelStyle(s: number, id: SectionId) {
  const t = (s - START[id]) / (LEN[id] - 1);
  const o = win(t, -0.45, 0.02, 0.82, 1.12);
  return { opacity: o, transform: `translateY(${(1 - o) * (t < 0.5 ? 24 : -24)}px)`, visibility: o < 0.01 ? "hidden" as const : undefined };
}

export function Landing({ meta, sites, stats, playIntro, onWarm, onEnter }: Props) {
  const { w: W, h: H } = useViewport();
  const s = useScrollScreens(H);
  const wide = W >= 900;
  const reduce = useMemo(reducedMotion, []);
  const [phase, setPhase] = useState<"intro" | "fading" | "ready">(playIntro && !reduce ? "intro" : "ready");
  const [skip, setSkip] = useState(false);
  const [heroLit, setHeroLit] = useState(reduce || !playIntro);
  const [activeSource, setActiveSource] = useState(0);
  const entered = useRef(false);
  const warmed = useRef(false);

  // ── Intro: lock scrolling; any scroll, swipe or key skips it. ──
  useEffect(() => {
    if (phase !== "intro") return;
    const root = document.documentElement;
    root.style.overflow = "hidden";
    window.scrollTo(0, 0);
    const skipNow = () => setSkip(true);
    const onKey = (e: KeyboardEvent) => { if (["ArrowDown", "PageDown", " ", "Enter", "Escape"].includes(e.key)) skipNow(); };
    window.addEventListener("wheel", skipNow, { passive: true });
    window.addEventListener("touchmove", skipNow, { passive: true });
    window.addEventListener("keydown", onKey);
    return () => {
      root.style.overflow = "";
      window.removeEventListener("wheel", skipNow);
      window.removeEventListener("touchmove", skipNow);
      window.removeEventListener("keydown", onKey);
    };
  }, [phase]);
  const introDone = useCallback(() => setPhase((p) => (p === "intro" ? "fading" : p)), []);
  useEffect(() => {
    if (phase !== "fading") return;
    const t = window.setTimeout(() => setPhase("ready"), 1100);
    return () => clearTimeout(t);
  }, [phase]);

  // ── Scroll-driven scene values ──
  const minSide = Math.min(W, H);
  const heroScale = wide ? 0.86 : 0.92;
  const radarHero = 1 - ramp(s, 0.3, 0.95);
  const radarSure = win(s, START.sure - 0.55, START.sure + 0.05, START.first - 0.4, START.first + 0.05);
  const radarSources = ramp(s, START.sources - 0.5, START.sources + 0.05);
  const radarOpacity = phase === "intro" ? 0 : Math.max(radarHero, radarSure, radarSources);
  // Portal: copy shows over the scope, fades; the live map appears inside the scope; then the scope grows to fill the screen.
  const portalT = smooth(ramp(s, START.portal + 0.45, MAX - 0.03));
  const holeIn = ramp(s, START.portal + 0.05, START.portal + 0.4);
  const sureShift = wide ? 0.18 * win(s, START.sure - 0.8, START.sure - 0.4, START.first - 0.2, START.first + 0.2) : 0;
  const centerX = 0.5 + sureShift;
  // On phones the scope sits low beside the GPS story, and high in the sources beat so the readout fits below it.
  const centerY = wide ? 0.5 : radarSure > 0.5 ? 0.6 : s > START.sources - 0.6 ? 0.4 : 0.5;
  const baseScale = s < START.move ? heroScale : radarSure > 0 && s < START.first ? (wide ? 0.74 : 0.8) : wide ? 0.72 : 0.84;
  const r0 = (baseScale * minSide) / 2;
  const cx0 = () => centerX * W;
  const rPortal = lerp(r0, Math.hypot(Math.max(cx0(), W - cx0()), Math.max(centerY * H, H - centerY * H)) + 40, portalT);
  const radarScale = s >= START.portal ? (2 * rPortal) / minSide : baseScale;
  const R = (radarScale * minSide) / 2;
  const cx = centerX * W, cy = centerY * H;

  const galaxyOpacity = 1 - 0.7 * ramp(s, 0.4, 1.5);
  const topoOpacity = phase === "intro" ? 0 : win(s, 0.55, 1.35, START.sources - 0.5, START.sources) * (1 - 0.6 * radarSure);
  const showTopo = phase !== "intro" && s > 0.25 && s < START.sources + 0.3;
  const topoTilt = lerp(64, 34, smooth(ramp(s, START.move, START.sources - 1)));
  const topoElevation = lerp(0.6, 1.7, ramp(s, START.move, START.sure + 0.5));

  // Warm the dashboard before the portal so its map has tiles by the time it shows.
  useEffect(() => { if (!warmed.current && s > START.sources - 0.3) { warmed.current = true; onWarm(); } }, [s, onWarm]);
  // Arriving at the bottom of the portal opens the app.
  useEffect(() => {
    if (!entered.current && meta && s >= MAX - 0.02) { entered.current = true; onEnter(); }
  }, [s, meta, onEnter]);

  // ── Data for the story ──
  const years = meta ? `${meta.record.start.slice(0, 4)}–${meta.record.end.slice(0, 4)}` : "";
  const blips = useMemo(() => {
    if (!meta || !sites) return [];
    const where = new Map(sites.gps.map((g) => [g.id, g]));
    const k = Math.cos((HOUSTON[1] * Math.PI) / 180);
    const rows = meta.validation.points.flatMap((p) => {
      const g = where.get(p.id);
      if (!g) return [];
      return [{ id: p.id, gps: p.gps, sat: p.sat, dx: (g.lon - HOUSTON[0]) * k, dy: g.lat - HOUSTON[1], agree: Math.abs(p.sat - p.gps) <= AGREE_MM }];
    });
    // Fit the farthest station at 92% of the scope; keep true relative positions.
    const reach = Math.max(...rows.map((r) => Math.hypot(r.dx, r.dy)), 1e-6) / 0.92;
    return rows.map((r) => ({ ...r, x: r.dx / reach, y: r.dy / reach, bearing: Math.atan2(r.dx, r.dy) }));
  }, [meta, sites]);
  const agree = blips.filter((b) => b.agree).length;

  const sources = useMemo(() => {
    if (!meta) return [];
    const a = meta.nisarArchive;
    return [
      { short: "OPERA", name: "NASA JPL OPERA · Sentinel-1 radar", what: `How much each 1 km square moved, every few months, ${years}.`, use: "The main movement measurement." },
      { short: "GPS", name: "HoustonNet GPS", what: `${meta.stations.total} stations that measure movement very precisely at single points.`, use: `Checks the satellite. The ${meta.stations.deepSeated.length} antennas on deep extensometer anchors are left out: they track the anchor, not the land surface.` },
      { short: "NISAR", name: "NASA/ISRO NISAR", what: `The newest radar satellite, ${a.first.slice(0, 7)} to ${a.last.slice(0, 7)}.`, use: `A quality check so far: ${a.processedPairs} of ${a.pairs} pairs processed. Its 12-day pairs are still mostly noise, so they don't color the map.` },
      { short: "Wells", name: "USGS groundwater wells", what: "Whether water levels have dropped.", use: "Context in each square's evidence." },
      { short: "Extensometers", name: "USGS extensometers", what: "How much soil has squeezed underground.", use: "Context in each square's evidence." },
      { short: "FEMA", name: "FEMA flood zones", what: "Official high-risk flood areas.", use: "Raise priority for squares that moved down. A square with no matching zone is unknown, not safe." },
    ].map((src, i, all) => ({ ...src, bearing: (i / all.length) * TAU + TAU / (all.length * 2) }));
  }, [meta, years]);

  // ── Radar-synced overlays (direct DOM writes, once per radar frame) ──
  const letterRefs = useRef<(HTMLSpanElement | null)[]>([]);
  const lit = useRef<boolean[]>(WORD.split("").map(() => reduce || !playIntro));
  const blipRefs = useRef<(HTMLSpanElement | null)[]>([]);
  const srcRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const geo = useRef({ cx, cy, radarSure, radarSources, heroOn: radarHero > 0.01, blips, sources });
  geo.current = { cx, cy, radarSure, radarSources, heroOn: radarHero > 0.01, blips, sources };
  const activeRef = useRef(0);
  const heldUntil = useRef(0); // a clicked source label holds the readout for a few seconds
  const pickSource = (i: number) => { activeRef.current = i; heldUntil.current = performance.now() + 9000; setActiveSource(i); };

  const onSweep = useCallback((sweep: number, intro: number) => {
    const g = geo.current;
    if (g.heroOn) {
      let all = true;
      letterRefs.current.forEach((el, i) => {
        if (!el) return;
        const r = el.getBoundingClientRect();
        const bearing = Math.atan2(r.left + r.width / 2 - g.cx, g.cy - (r.top + r.height / 2));
        const gap = gapBehind(sweep, bearing);
        // Letters light in reading order as the sweep crosses them.
        if (!lit.current[i] && (i === 0 || lit.current[i - 1]) && intro > 0.55 && gap < 0.35) { lit.current[i] = true; el.classList.add("on"); }
        el.style.setProperty("--f", Math.exp(-gap * 2.4).toFixed(3));
        all &&= lit.current[i];
      });
      if (all) setHeroLit(true);
    }
    if (g.radarSure > 0.01) {
      g.blips.forEach((b, i) => {
        const el = blipRefs.current[i];
        if (el) el.style.setProperty("--f", Math.exp(-gapBehind(sweep, b.bearing) * 1.3).toFixed(3));
      });
    }
    if (g.radarSources > 0.01 && g.sources.length) {
      let best = 0, bestGap = TAU;
      g.sources.forEach((src, i) => {
        const gap = gapBehind(sweep, src.bearing);
        if (gap < bestGap) { bestGap = gap; best = i; }
        srcRefs.current[i]?.style.setProperty("--f", Math.exp(-gap * 1.1).toFixed(3));
      });
      if (best !== activeRef.current && performance.now() > heldUntil.current) { activeRef.current = best; setActiveSource(best); }
    }
  }, []);

  // Keep lit letters lit across re-renders.
  useEffect(() => { letterRefs.current.forEach((el, i) => el?.classList.toggle("on", lit.current[i])); });

  const toPortalEnd = () => window.scrollTo({ top: MAX * H + 2, behavior: reduce ? "auto" : "smooth" });
  const toStory = () => window.scrollTo({ top: START.move * H, behavior: reduce ? "auto" : "smooth" });

  const maskR = rPortal * 0.965;
  const mask = holeIn > 0
    ? `radial-gradient(circle at ${cx}px ${cy}px, rgba(0,0,0,${(1 - 0.92 * holeIn).toFixed(3)}) ${maskR}px, #000 ${maskR + 1.5}px)`
    : undefined;
  const scopeBox = { left: cx - R, top: cy - R, width: 2 * R, height: 2 * R };
  const src = sources[activeSource];
  const draft = meta && meta.status !== "reviewed";

  return (
    <div className="landing" style={{ height: TOTAL * H }}>
      {/* ── Fixed scene ── */}
      <div className="scene" style={{ WebkitMaskImage: mask, maskImage: mask }}>
        <div className="layer" style={{ opacity: galaxyOpacity }} aria-hidden="true">
          <Galaxy transparent={false} backgroundColor="#030817" starColors={["#FFFFFF", "#BFE6FF", CYAN, BLUE]} density={1.15} glowIntensity={0.32} twinkleIntensity={0.45} saturation={0.3} hueShift={200} rotationSpeed={0.04} starSpeed={0.3} mouseRepulsion={false} repulsionStrength={1} intro={playIntro && !reduce} dpr={1.5} />
        </div>
        {showTopo && (
          <div className="layer" style={{ opacity: topoOpacity }} aria-hidden="true">
            <Topography color={BLUE} lineCount={26} lineWidth={1.1} elevation={topoElevation} tilt={topoTilt} speed={0.18} glow={0.75} fog={0.5} depthOfField={0.35} foreground={0.25} parallax={0.4} markers={s > START.first - 0.3 ? "plus" : "none"} hoverEffect="lift" clickEffect="pulse" dpr={1.5} />
          </div>
        )}
        {phase !== "intro" && (
          <div className="layer" style={{ opacity: radarOpacity }} aria-hidden="true">
            <Radar sweepStart={-1.35} color={CYAN} scale={radarScale} centerX={centerX} centerY={centerY} ringCount={wide ? 6 : 5} spokeCount={12} targets={0} clutter={0.12} trail={0.42} glow={1.1} gridOpacity={0.85} speed={0.9} grain={0.025} paused={radarOpacity < 0.01} onSweep={onSweep} dpr={1.5} />
          </div>
        )}

        {/* GPS stations as scope blips (beat 2) */}
        <div className="scope" style={{ ...scopeBox, opacity: radarSure }} aria-hidden="true">
          {blips.map((b, i) => (
            <span key={b.id} ref={(el) => { blipRefs.current[i] = el; }} className={b.agree ? "blip" : "blip off"} style={{ left: `${50 + b.x * 50}%`, top: `${50 - b.y * 50}%` }} title={`${b.id}: GPS ${num(b.gps)}, satellite ${num(b.sat)} mm a year`} />
          ))}
        </div>

        {/* Data sources around the scope (beat 4) */}
        <div className="scope" style={{ ...scopeBox, opacity: radarSources * (1 - ramp(s, START.portal - 0.4, START.portal + 0.1)), visibility: radarSources > 0.01 ? undefined : "hidden" }} role="group" aria-label="Data sources">
          {sources.map((x, i) => (
            <button key={x.short} ref={(el) => { srcRefs.current[i] = el; }} className={i === activeSource ? "src on" : "src"} onClick={() => pickSource(i)} aria-pressed={i === activeSource} tabIndex={radarSources > 0.5 ? 0 : -1} style={{ left: `${50 + Math.sin(x.bearing) * 50 * (wide ? 1.13 : 1.02)}%`, top: `${50 - Math.cos(x.bearing) * 50 * (wide ? 1.13 : 1.1)}%`, transform: wide ? undefined : `translate(${-50 - 50 * Math.sin(x.bearing)}%, -50%)` }}>
              <i />{x.short}
            </button>
          ))}
        </div>
      </div>

      {phase !== "ready" && (
        <div className={phase === "fading" ? "intro fade" : "intro"}>
          <Intro skip={skip} onDone={introDone} />
          {phase === "intro" && <button className="skip" onClick={() => setSkip(true)}>Skip intro</button>}
        </div>
      )}

      {/* ── Top bar ── */}
      <header className={phase === "intro" ? "lbar hidden" : "lbar"} style={portalT > 0 ? { opacity: 1 - portalT * 2, pointerEvents: portalT > 0.3 ? "none" : undefined } : undefined}>
        <span className="lbar-brand"><img src="./logo.png" alt="" width={30} height={30} />TerraGauge <em>Houston</em></span>
        <span className="lbar-right">
          {draft && <span className="draft" title="Provisional: the reference region has not been team-reviewed yet. Describes past records only.">Draft</span>}
          <button className="ghost" onClick={onEnter}>Open the map <span aria-hidden="true">→</span></button>
        </span>
      </header>

      {/* ── Scrolling content ── */}
      <section className={heroLit ? "hero lit" : "hero"} style={{ height: LEN.hero * H }} aria-label="TerraGauge Houston">
        <div className={phase === "intro" ? "hero-stage pre" : "hero-stage"} style={{ height: H, ["--R" as string]: `${(heroScale * minSide) / 2}px` }}>
          <h1 className="wordmark" aria-label="TerraGauge">
            {WORD.split("").map((ch, i) => <span key={i} ref={(el) => { letterRefs.current[i] = el; }} aria-hidden="true">{ch}</span>)}
          </h1>
          <img className="hero-logo" src="./logo.png" alt="" />
          <div className="hero-copy">
            <p className="tagline">Where did Houston's ground move, and how sure are we?</p>
            <p className="hero-sub">Past ground motion from NASA satellite radar, checked against GPS, wells and flood zones, one 1 km square at a time.</p>
            <div className="hero-cta">
              <button className="cta" onClick={toStory}>Start the story</button>
              <button className="ghost" onClick={onEnter}>Skip to the map</button>
            </div>
          </div>
          <div className="scroll-cue" style={{ opacity: 1 - ramp(s, 0.05, 0.3) }} aria-hidden="true"><span />Scroll</div>
        </div>
      </section>

      <section className="beat" style={{ height: LEN.move * H }} aria-labelledby="b-move">
        <div className="hold" style={{ height: H }}>
          <article className="glass" style={panelStyle(s, "move")}>
            <p className="kicker">01 · Movement</p>
            <h2 id="b-move">Where did the ground move?</h2>
            <p className="big"><strong>{stats ? stats.fast.toLocaleString() : "—"}</strong><span>of {stats ? stats.measured.toLocaleString() : "—"} measured 1 km squares moved down 1 cm a year or more in the {years} satellite record.</span></p>
            <p>Each square is measured relative to a reference region, from {meta?.record.products ?? "—"} NASA OPERA radar snapshots, {years}. Where trees, fields or water hide the ground, the square says so instead of guessing from its neighbors.</p>
          </article>
        </div>
      </section>

      <section className="beat right" style={{ height: LEN.sure * H }} aria-labelledby="b-sure">
        <div className="hold" style={{ height: H }}>
          <article className="glass" style={panelStyle(s, "sure")}>
            <p className="kicker">02 · Confidence</p>
            <h2 id="b-sure">How sure are we?</h2>
            <p>We checked the satellite against {meta?.validation.stations ?? "—"} GPS stations it was never calibrated on. Each blip on the scope is one of them, drawn where it sits around Houston.</p>
            <div className="duo">
              <p className="big"><strong>{meta ? meta.validation.r.toFixed(2) : "—"}</strong><span>correlation with GPS</span></p>
              <p className="big"><strong>{meta ? num(meta.validation.typical_diff_mm_year) : "—"}</strong><span>mm a year typical (median) difference</span></p>
            </div>
            <ul className="keyline">
              <li><i className="k-agree" />{agree} stations agree within {AGREE_MM} mm a year</li>
              <li><i className="k-differ" />{blips.length - agree} differ by more</li>
            </ul>
            <p className="fine">Every square gets its own confidence level: {CONFIDENCE.high.name.toLowerCase()} where a nearby GPS station confirms it.</p>
          </article>
        </div>
      </section>

      <section className="beat" style={{ height: LEN.first * H }} aria-labelledby="b-first">
        <div className="hold" style={{ height: H }}>
          <article className="glass" style={panelStyle(s, "first")}>
            <p className="kicker">03 · Priority</p>
            <h2 id="b-first">Where should we look first?</h2>
            <p className="big"><strong>{meta ? (meta.counts.priority.urgent ?? 0).toLocaleString() : "—"}</strong><span>urgent squares: moved down at least 1 cm a year, or 5 mm a year inside a FEMA high-risk flood zone, clearly above noise.</span></p>
            {meta && (
              <ol className="mini-sites">
                {meta.sensors.slice(0, 3).map((x) => (
                  <li key={x.id}><span className="rank">{x.rank}</span><span><b>Area moved down about {num(Math.abs(x.areaRate / 10))} cm a year</b><small>{num(x.gpsKm)} km from the nearest GPS{x.sfha ? ", high-risk flood zone" : ""}</small></span></li>
                ))}
              </ol>
            )}
            <p className="fine">The top {meta?.sensors.length ?? "—"} places where a new GPS sensor would add the most evidence.</p>
          </article>
        </div>
      </section>

      <section className="beat center" style={{ height: LEN.sources * H }} aria-labelledby="b-sources">
        <div className="hold" style={{ height: H }}>
          <header className="sources-head" style={panelStyle(s, "sources")}>
            <p className="kicker">04 · Evidence</p>
            <h2 id="b-sources">One map, every dataset</h2>
          </header>
          {src && (
            <div className="readout" style={{ ...panelStyle(s, "sources"), ["--R" as string]: `${R}px` }} aria-live="off">
              <p className="kicker">{src.short}</p>
              <h3>{src.name}</h3>
              <p>{src.what}</p>
              <p className="use">{src.use}</p>
            </div>
          )}
        </div>
      </section>

      <section className="beat center" style={{ height: LEN.portal * H }} aria-labelledby="b-portal">
        <div className="hold" style={{ height: H }}>
          <div className="portal-copy" style={{ opacity: win(s, START.portal - 0.6, START.portal - 0.1, START.portal + 0.05, START.portal + 0.3) }}>
            <p className="kicker">05 · The map</p>
            <h2 id="b-portal">Every square, its evidence, and what's missing</h2>
            <button className="cta" onClick={toPortalEnd}>Open the map</button>
          </div>
        </div>
      </section>
    </div>
  );
}
