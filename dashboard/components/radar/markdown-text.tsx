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
export function MarkdownText({
  children,
  className,
}: {
  children: string;
  className?: string;
}) {
  return (
    <div className={`markdown-body${className ? ` ${className}` : ""}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw, rehypeSanitize]}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
