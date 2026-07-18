import type { CSSProperties } from "react";

interface AlpacaProps {
  size?: number;
  color?: string;
  /** Color for the eye dots / interior negative space. */
  eye?: string;
  className?: string;
  style?: CSSProperties;
}

/**
 * Production alpaca mark — filled geometric SVG.
 * Ported as-is from `dashboard/design/components.jsx::Alpaca`.
 *
 * Exploratory variants (`AlpacaOutline`, `AlpacaFace`, `AlpacaBadge`) are
 * intentionally NOT ported. We ship this one mark.
 */
export function Alpaca({
  size = 24,
  color = "currentColor",
  eye = "var(--bg)",
  className,
  style,
}: AlpacaProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={color}
      className={className}
      style={style}
      aria-hidden="true"
    >
      {/* ears */}
      <rect x="6.4" y="1.4" width="2.5" height="5.2" rx="1.25" transform="rotate(-13 7.65 4)" />
      <rect x="15.1" y="1.4" width="2.5" height="5.2" rx="1.25" transform="rotate(13 16.35 4)" />
      {/* forelock fluff */}
      <rect x="9.4" y="2.6" width="5.2" height="3.4" rx="1.7" />
      {/* head */}
      <rect x="6.6" y="4.4" width="10.8" height="9.2" rx="4.3" />
      {/* body */}
      <rect x="4.4" y="10.3" width="15.2" height="11.4" rx="5.4" />
      {/* leg gap */}
      <rect x="10.6" y="18.6" width="2.8" height="3.6" rx="1.3" fill={eye} />
      {/* eyes */}
      <circle cx="9.6" cy="8.3" r="1.05" fill={eye} />
      <circle cx="14.4" cy="8.3" r="1.05" fill={eye} />
      {/* snout shading */}
      <ellipse cx="12" cy="11.7" rx="2.5" ry="1.7" fill={eye} opacity="0.18" />
    </svg>
  );
}
