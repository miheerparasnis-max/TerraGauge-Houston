import type { ElementType } from "react";

/**
 * A heading whose own text scrolls across the full width of the screen.
 * Used where a container has nothing beside it, so the empty sides carry the
 * title instead. Screen readers get the text once; reduced motion shows it still.
 */
export function Marquee({ text, as: Tag = "h2", id, className }: { text: string; as?: ElementType; id?: string; className?: string }) {
  const run = (key: string) => (
    <span className="marquee-run" key={key} aria-hidden="true">
      {Array.from({ length: 3 }, (_, i) => <span key={i}>{text}<i className="marquee-sep" /></span>)}
    </span>
  );
  return (
    <Tag id={id} className={`marquee${className ? ` ${className}` : ""}`} aria-label={text}>
      <span className="marquee-track">{run("a")}{run("b")}</span>
      <span className="marquee-still">{text}</span>
    </Tag>
  );
}
