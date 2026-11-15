import type { Hazard, Meta, Mode } from "./types";
import { num } from "./labels";

export interface TourStep { title: string; body: string; mode: Mode; hazard?: Hazard; cell?: string | null; history?: boolean }

/** Five stops that tell the whole story, for judges and first-time visitors. */
export function tourSteps(meta: Meta, stats: { fast: number; measured: number }, picks: { fastest?: string; harvey?: string }): TourStep[] {
  const fc = meta.forecast, h = meta.hazards?.harvey;
  const last = fc ? fc.years[fc.years.length - 1] : 2031;
  const err = fc?.benchmark.table.find((t) => t.method === fc.method)?.by_horizon_cm[String(Math.round(fc.tested_horizon_years))];
  return [
    { title: "Houston is sinking", mode: "movement", history: true, cell: null,
      body: `NASA radar satellites measured every square kilometer from 2016 to 2026${meta.predictionTest?.verdict === "pass" ? ", and NISAR, NASA and India's newest radar satellite, sees the same pattern in 2026" : ""}. Watch the ground drop: ${stats.fast.toLocaleString()} of ${stats.measured.toLocaleString()} squares sank 1 cm a year or more, mostly in the northwest and east, where groundwater pumping squeezes the clay.` },
    { title: "How sure are we?", mode: "confidence", cell: null,
      body: `We checked the satellite against ${meta.validation.stations} GPS stations it never saw: they agree within about ${num(meta.validation.typical_diff_mm_year)} mm a year. Every square gets its own confidence level, and shaky readings are blended with their neighbors instead of shown as-is.` },
    { title: `How much more by ${last}?`, mode: "future", cell: picks.fastest ?? null,
      body: `We tested ${fc?.benchmark.table.length ?? 9} ways to forecast on past years, including machine learning, and use the one tied for most accurate. Five years ahead it was typically off by ${num(err ?? null)} cm. This square is one of the fastest-sinking in a flood zone.` },
    { title: "What would a flood do?", mode: "hazards", hazard: "flood", cell: picks.harvey ?? null,
      body: h && h.by_class["1pct"] && h.by_class.minimal ? `Sinking land floods deeper. We checked our flood map against Hurricane Harvey's real flood maps: high-risk squares had ${num(h.by_class["1pct"].mean_flooded_share_pct, 0)}% of their area flooded, low-risk squares ${num(h.by_class.minimal.mean_flooded_share_pct, 0)}%. Drought and ground-bending views are here too.` : "Sinking land floods deeper. The flood, drought and ground-bending views show what the moving ground does in a disaster." },
    { title: "Where to put sensors", mode: "priority", cell: null,
      body: `Satellites find the sinking; ground sensors confirm it. We suggest ${meta.sensors.length} permanent GPS stations (numbered), ${meta.nodes.length} low-cost sensors (orange diamonds), and ${meta.gaps.length} sensors for land nothing measures yet (white diamonds).` },
  ];
}

export function Tour({ steps, index, onGo, onClose }: { steps: TourStep[]; index: number; onGo: (i: number) => void; onClose: () => void }) {
  const s = steps[index];
  return (
    <div className="tour" role="dialog" aria-label="Guided tour">
      <div className="tour-top"><span>{index + 1} of {steps.length}</span><button onClick={onClose} aria-label="Close tour">×</button></div>
      <h3>{s.title}</h3>
      <p>{s.body}</p>
      <div className="tour-nav">
        <button onClick={() => onGo(index - 1)} disabled={index === 0}>Back</button>
        <span className="dots">{steps.map((_, i) => <i key={i} className={i === index ? "on" : ""} />)}</span>
        {index < steps.length - 1 ? <button className="primary" onClick={() => onGo(index + 1)}>Next</button> : <button className="primary" onClick={onClose}>Explore</button>}
      </div>
    </div>
  );
}
