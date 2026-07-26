import type { CSSProperties } from "react";

export type MarkVariant = "icon" | "nav";

interface SignalMarkProps {
  size?: number;
  /** Detail tier. Never inferred from `size` — see design D3. */
  variant?: MarkVariant;
  color?: string;
  className?: string;
  style?: CSSProperties;
}

/**
 * next-signal parent mark — the Vanguard: a node leaving the origin and
 * accelerating up-and-right through two chevrons.
 *
 * The `nav` variant re-spaces both chevrons rather than scaling the icon
 * geometry, so the pair keeps ~2 device px of clearance at 16px. It never
 * drops to a single chevron — that costs the mark its signature.
 */
export function SignalMark({
  size = 24,
  variant = "icon",
  color = "currentColor",
  className,
  style,
}: SignalMarkProps) {
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
        strokeWidth={nav ? 2.8 : 3}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path
          d={nav ? "M7 11 L14 11 L14 18" : "M6.5 10.5 L14.5 10.5 L14.5 18.5"}
          opacity={nav ? 0.45 : 0.42}
        />
        <path d={nav ? "M12 4.8 L20 4.8 L20 12.8" : "M11 5 L20 5 L20 14"} />
      </g>
      <circle
        cx={nav ? 5.6 : 6.5}
        cy={nav ? 18.6 : 18.5}
        r={nav ? 2.7 : 2.8}
        fill={color}
      />
    </svg>
  );
}

/**
 * next-signal emblem — the linear field. A launch wave fires outward through
 * the gates along the trajectory axis.
 *
 * Transparent, token-coloured, no `"use client"`: motion comes from the
 * `.brand-chev` hooks in `globals.css`.
 */
export function SignalEmblem({
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
      {/* the diagonal puts its mass low-left of the frame; nudge to optical centre */}
      <g transform="translate(-2 2)">
        <line
          x1="26"
          y1="74"
          x2="78.3"
          y2="21.7"
          stroke="var(--border)"
          strokeWidth="1.2"
          strokeLinecap="round"
        />
        <g
          fill="none"
          stroke="var(--accent)"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path
            className="brand-chev c1"
            d="M36.6 51.4 L48.6 51.4 L48.6 63.4"
            strokeWidth="3.5"
          />
          <path
            className="brand-chev c2"
            d="M43.5 41.5 L58.5 41.5 L58.5 56.5"
            strokeWidth="4.5"
          />
          <path
            className="brand-chev c3"
            d="M51.8 30.2 L69.8 30.2 L69.8 48.2"
            strokeWidth="5.5"
          />
        </g>
        <circle cx="33" cy="67" r="5.5" fill="var(--accent)" />
      </g>
    </svg>
  );
}
