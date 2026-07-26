import type { CSSProperties } from "react";

import type { MarkVariant } from "@/components/brand/signal-mark";

interface KnowledgeMarkProps {
  size?: number;
  /** Detail tier. Never inferred from `size` — see design D3. */
  variant?: MarkVariant;
  color?: string;
  /** The one secondary colour this mark spends: the index hub. */
  spark?: string;
  className?: string;
  style?: CSSProperties;
}

/**
 * knowledge-base mark — concepts linked into a structure resting on a base,
 * routing through a single index hub.
 *
 * The nav tier carries the *larger* authored stroke (2.5 vs 2.4): a 24-unit
 * viewBox drawn into 16px scales by 0.667, so nav lands at 1.67 device px
 * against icon's 2.4.
 */
export function KnowledgeMark({
  size = 24,
  variant = "icon",
  color = "currentColor",
  spark = "var(--brand-spark-kb)",
  className,
  style,
}: KnowledgeMarkProps) {
  const nav = variant === "nav";
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      className={className}
      style={style}
      aria-hidden="true"
    >
      <g
        fill="none"
        stroke={color}
        strokeWidth={nav ? 2.5 : 2.4}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <line x1="12" y1="5.2" x2="12" y2="12" />
        <line x1="12" y1="12" x2="5.6" y2="18.4" />
        <line x1="12" y1="12" x2="18.4" y2="18.4" />
        <line x1="5.6" y1="18.4" x2="18.4" y2="18.4" />
      </g>
      <g fill={color}>
        <circle cx="12" cy="5.2" r={nav ? 2.6 : 2.4} />
        <circle cx="5.6" cy="18.4" r={nav ? 2.6 : 2.4} />
        <circle cx="18.4" cy="18.4" r={nav ? 2.6 : 2.4} />
      </g>
      <circle cx="12" cy="12" r={nav ? 3.2 : 3} fill={spark} />
    </svg>
  );
}

/** Satellite concepts feeding the three core nodes. */
const SATELLITES = [
  { cx: 32, cy: 8, parent: [50, 20] },
  { cx: 68, cy: 8, parent: [50, 20] },
  { cx: 8, cy: 58, parent: [22, 74] },
  { cx: 14, cy: 92, parent: [22, 74] },
  { cx: 92, cy: 58, parent: [78, 74] },
  { cx: 86, cy: 92, parent: [78, 74] },
] as const;

/** Each core node's signal, translated onto the hub at (50,52). */
const FLOWS = [
  { cx: 50, cy: 20, dx: 0, dy: 32 },
  { cx: 22, cy: 74, dx: 28, dy: -22 },
  { cx: 78, cy: 74, dx: -28, dy: -22 },
] as const;

/**
 * knowledge-base emblem — the network field. Concepts feed inward along the
 * spokes and land in the index.
 *
 * Transparent, token-coloured, no `"use client"`: motion comes from the
 * `.brand-flow` / `.brand-sat` / `.brand-ping` hooks in `globals.css`.
 */
export function KnowledgeEmblem({
  size = 96,
  className,
}: {
  size?: number;
  className?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      className={className}
      aria-hidden="true"
    >
      {/* the wider topology the three core concepts sit inside */}
      <g
        fill="none"
        stroke="var(--border)"
        strokeWidth="1.2"
        strokeDasharray="3 4"
        strokeLinecap="round"
      >
        <line x1="50" y1="20" x2="22" y2="74" />
        <line x1="50" y1="20" x2="78" y2="74" />
      </g>

      <g fill="none" stroke="var(--border)" strokeWidth="1.6" strokeLinecap="round">
        {SATELLITES.map((s) => (
          <line key={`${s.cx}-${s.cy}`} x1={s.cx} y1={s.cy} x2={s.parent[0]} y2={s.parent[1]} />
        ))}
      </g>

      <g
        fill="none"
        stroke="var(--accent)"
        strokeWidth="3.4"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.85"
      >
        <line x1="50" y1="20" x2="50" y2="52" />
        <line x1="50" y1="52" x2="22" y2="74" />
        <line x1="50" y1="52" x2="78" y2="74" />
        <line x1="22" y1="74" x2="78" y2="74" />
      </g>

      <g fill="var(--accent)">
        {SATELLITES.map((s, i) => (
          <circle
            key={`${s.cx}-${s.cy}`}
            className={`brand-sat s${i + 1}`}
            cx={s.cx}
            cy={s.cy}
            r="3"
          />
        ))}
      </g>

      {FLOWS.map((f, i) => (
        <circle
          key={`${f.cx}-${f.cy}`}
          className={`brand-flow f${i + 1}`}
          cx={f.cx}
          cy={f.cy}
          r="2.8"
          fill="var(--brand-spark-kb)"
          style={{ "--dx": `${f.dx}px`, "--dy": `${f.dy}px` } as CSSProperties}
        />
      ))}

      <g fill="var(--accent)">
        <circle cx="50" cy="20" r="5" />
        <circle cx="22" cy="74" r="5" />
        <circle cx="78" cy="74" r="5" />
      </g>

      <circle
        className="brand-ping"
        cx="50"
        cy="52"
        r="10"
        fill="none"
        stroke="var(--brand-spark-kb)"
        strokeWidth="1.8"
      />
      <circle cx="50" cy="52" r="7" fill="var(--brand-spark-kb)" />
    </svg>
  );
}
