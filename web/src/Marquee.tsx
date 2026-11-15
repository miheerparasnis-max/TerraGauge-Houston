import { useLayoutEffect, useRef, type ElementType } from "react";

/**
 * A heading whose own text drifts across its full-width band. It starts with one
 * copy exactly centered, so the title reads first and then moves. Screen readers
 * get the text once; reduced motion shows it still and centered.
 */
export function Marquee({ text, as: Tag = "h2", id, className }: { text: string; as?: ElementType; id?: string; className?: string }) {
  const box = useRef<HTMLElement>(null);
  const first = useRef<HTMLSpanElement>(null);
  useLayoutEffect(() => {
    const place = () => {
      const el = box.current, copy = first.current;
      if (!el || !copy) return;
      const step = copy.getBoundingClientRect().width; // one copy plus its separator
      const textW = copy.firstElementChild ? (copy.firstElementChild as HTMLElement).getBoundingClientRect().width : step;
      const centered = (el.clientWidth - textW) / 2;
      // Shift by whole copies so a copy also fills the left edge.
      const start = centered - Math.ceil(centered / step) * step;
      el.style.setProperty("--start", `${start.toFixed(1)}px`);
    };
    place();
    const ro = new ResizeObserver(place);
    if (box.current) ro.observe(box.current);
    return () => ro.disconnect();
  }, [text]);
  const run = (key: string, lead = false) => (
    <span className="marquee-run" key={key} aria-hidden="true">
      {Array.from({ length: 3 }, (_, i) => <span key={i} ref={lead && i === 0 ? first : undefined}><b>{text}</b><i className="marquee-sep" /></span>)}
    </span>
  );
  return (
    <Tag id={id} ref={box} className={`marquee${className ? ` ${className}` : ""}`} aria-label={text}>
      <span className="marquee-track">{run("a", true)}{run("b")}</span>
      <span className="marquee-still">{text}</span>
    </Tag>
  );
}
