import { Fragment } from "react";

interface HighlightedSnippetProps {
  /**
   * Raw snippet from gbrain. May contain `<em>...</em>` highlight pairs and
   * arbitrary HTML lifted from the underlying wiki markdown (which is NOT
   * a trusted source — wiki docs are markdown that may embed raw HTML).
   */
  html: string;
  className?: string;
}

/**
 * Renders a gbrain snippet as plain text plus `<em>` highlights, without
 * trusting the input. gbrain is NOT an HTML sanitizer — it just emits
 * `<em>` markers around query matches. The actual sink (this component)
 * has to be the sanitization boundary.
 *
 * Algorithm: split on `<em>...</em>` pairs; everything between pairs is
 * rendered as raw text (React auto-escapes); the inner content of each
 * pair is also rendered as text, wrapped in a real `<em>` element. Any
 * other tags in the input are inert text, never DOM nodes.
 */
export function HighlightedSnippet({ html, className }: HighlightedSnippetProps) {
  // /s = dotAll so newlines inside the highlight count; ?+ keeps it lazy.
  const re = /<em>([\s\S]*?)<\/em>/g;
  const parts: React.ReactNode[] = [];
  let cursor = 0;
  let i = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(html)) !== null) {
    if (m.index > cursor) {
      parts.push(<Fragment key={`t${i}`}>{html.slice(cursor, m.index)}</Fragment>);
    }
    parts.push(<em key={`e${i}`}>{m[1]}</em>);
    cursor = m.index + m[0].length;
    i += 1;
  }
  if (cursor < html.length) {
    parts.push(<Fragment key={`t${i}`}>{html.slice(cursor)}</Fragment>);
  }
  return <p className={className}>{parts}</p>;
}
