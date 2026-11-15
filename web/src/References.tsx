import { REFS, sortRefs, type Ref, type RefKey } from "./sources";

/** One APA 7 reference entry, with its DOI or URL as a link. */
function Entry({ r }: { r: Ref }) {
  const title = r.italicTitle ? <i>{r.title}</i> : r.title;
  const periodical = r.periodical && (
    <>
      {" "}<i>{r.periodical}</i>
      {r.volume && <>, <i>{r.volume}</i></>}
      {r.issue && `(${r.issue})`}
      {r.pages && `, ${r.pages}`}.
    </>
  );
  return (
    <li>
      {r.author.endsWith(".") ? r.author : `${r.author}.`} ({r.date}). {title}{r.after ?? ""}.{periodical}
      {r.publisher && ` ${r.publisher}.`}
      {r.retrieved && ` ${r.retrieved}`}{" "}
      <a href={r.url} target="_blank" rel="noreferrer">{r.url}</a>
    </li>
  );
}

/** A references list in APA order (by author, then date). */
export function References({ keys, title = "Sources" }: { keys: RefKey[]; title?: string }) {
  return (
    <footer className="sources">
      <h2>{title}</h2>
      <ol className="refs">{sortRefs(keys).map((k) => <Entry key={k} r={REFS[k]} />)}</ol>
    </footer>
  );
}

/** In-text citation, e.g. "(Stork & Sneed, 2002)", linked to the source. */
export function Cite({ refs }: { refs: RefKey[] }) {
  return (
    <cite>
      ({refs.map((k, i) => (
        <span key={k}>{i > 0 && "; "}<a href={REFS[k].url} target="_blank" rel="noreferrer">{REFS[k].cite}</a></span>
      ))})
    </cite>
  );
}
