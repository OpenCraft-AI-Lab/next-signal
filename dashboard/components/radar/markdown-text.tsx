import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";

/**
 * Shared markdown renderer for radar `impact_md` / `summary` text. Same
 * plugin stack as the detail page, used by `<SignalCard>` so the card
 * preview and the full detail render identically (no `**bold**` literals
 * leaking through one path while the other resolves them).
 *
 * Wraps the result in `.markdown-body` so paragraph spacing / list / link
 * styles from globals.css apply.
 */
// Canonical auto-generated headings are stored in English; the knowledge
// preview swaps them to the item's own locale at render (chrome the frontend
// owns, per the localize-knowledge-ingest model). Radar callers omit
// `headingLocale`, leaving the text untouched.
const HEADING_SWAP: Record<string, { summary: string; related: string }> = {
  zh: { summary: "总结", related: "相关" },
};

function swapHeadings(md: string, labels: { summary: string; related: string }): string {
  return md
    .replace(/^(##[ \t]+)Summary[ \t]*$/m, `$1${labels.summary}`)
    .replace(/^(##[ \t]+)Related[ \t]*$/m, `$1${labels.related}`);
}

export function MarkdownText({
  children,
  className,
  headingLocale,
}: {
  children: string;
  className?: string;
  headingLocale?: string;
}) {
  const labels = headingLocale ? HEADING_SWAP[headingLocale] : undefined;
  const text = labels ? swapHeadings(children, labels) : children;
  return (
    <div className={`markdown-body${className ? ` ${className}` : ""}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw, rehypeSanitize]}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
