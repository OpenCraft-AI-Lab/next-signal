import type { CSSProperties } from "react";

import type { MarkVariant } from "@/components/brand/signal-mark";

interface RadarMarkProps {
  size?: number;
  /** Detail tier. Never inferred from `size` — see design D3. */
  variant?: MarkVariant;
  color?: string;
  /** The one secondary colour this mark spends: the caught blip. */
  spark?: string;
  className?: string;
  style?: CSSProperties;
}

/**
 * info-radar mark — a scope, not a reticle.
 *
 * Tier contract: `icon` keeps two rings, crosshairs, the wedge and one blip;
 * `nav` keeps one ring, the wedge and the core. The sweep wedge survives every
 * tier — it is the single element separating a radar from a target.
 */
export function RadarMark({
  size = 24,
  variant = "icon",
  color = "currentColor",
  spark = "var(--brand-spark-radar)",
  className,
  style,
}: RadarMarkProps) {
  const nav = variant === "nav";

  if (nav) {
    return (
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        className={className}
        style={style}
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="8.8" fill="none" stroke={color} strokeWidth="2.4" />
        <path d="M12 12 L12 3.2 A8.8 8.8 0 0 1 18.22 5.78 Z" fill={color} opacity="0.28" />
        <line
          x1="12"
          y1="12"
          x2="18.22"
          y2="5.78"
          stroke={color}
          strokeWidth="2.4"
          strokeLinecap="round"
        />
        <circle cx="12" cy="12" r="2.4" fill={color} />
      </svg>
    );
  }

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      className={className}
      style={style}
      aria-hidden="true"
    >
      <g fill="none" stroke={color} strokeLinecap="round">
        <circle cx="12" cy="12" r="9.2" strokeWidth="2" />
        <circle cx="12" cy="12" r="4.9" strokeWidth="1.3" opacity="0.5" />
        <line x1="12" y1="2.8" x2="12" y2="21.2" strokeWidth="0.9" opacity="0.35" />
        <line x1="2.8" y1="12" x2="21.2" y2="12" strokeWidth="0.9" opacity="0.35" />
      </g>
      <path d="M12 12 L12 2.8 A9.2 9.2 0 0 1 18.5 5.5 Z" fill={color} opacity="0.22" />
      <line
        x1="12"
        y1="12"
        x2="18.5"
        y2="5.5"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
      />
      <circle cx="12" cy="12" r="2.3" fill={color} />
      {/* sits in the clear annulus between the rings (r 5.55..8.20), off the wedge */}
      <circle cx="8" cy="17.6" r="1.3" fill={spark} />
    </svg>
  );
}

const TICK_BEARINGS = [15, 45, 75, 105, 135, 165, 195, 225, 255, 285, 315, 345];

/**
 * info-radar emblem — the polar field. A beam sweeps the bearings and each
 * blip lights as it passes.
 *
 * Transparent, token-coloured, no `"use client"`: motion comes from the
 * `.brand-sweep` / `.brand-blip` hooks in `globals.css`, where each blip's
 * delay is derived from its bearing rather than hand-tuned.
 *
 * `gradientId` must be unique per instance when more than one emblem renders in
 * the same document — `/design` shows two. `useId()` would need a client
 * component, so the id is a prop instead.
 */
export function RadarEmblem({
  size = 96,
  className,
  gradientId = "brandRadarSweep",
}: {
  size?: number;
  className?: string;
  gradientId?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      className={className}
      aria-hidden="true"
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="1" x2="0.75" y2="0">
          <stop offset="0%" stopColor="var(--accent)" stopOpacity="0" />
          <stop offset="100%" stopColor="var(--accent)" stopOpacity="0.44" />
        </linearGradient>
      </defs>

      <circle cx="50" cy="50" r="46" fill="none" stroke="var(--border-strong)" strokeWidth="1.1" />
      <g fill="none" stroke="var(--border)" strokeWidth="1">
        <circle cx="50" cy="50" r="33" />
        <circle cx="50" cy="50" r="20" />
        <line x1="50" y1="4" x2="50" y2="96" />
        <line x1="4" y1="50" x2="96" y2="50" />
      </g>

      <g stroke="var(--border-strong)" strokeWidth="1.4" strokeLinecap="round">
        {TICK_BEARINGS.map((deg) => (
          <line
            key={deg}
            x1="50"
            y1="4"
            x2="50"
            y2="9.5"
            transform={`rotate(${deg} 50 50)`}
          />
        ))}
      </g>

      <g className="brand-sweep">
        <path d="M50 50 L50 4 A46 46 0 0 1 82.5 17.5 Z" fill={`url(#${gradientId})`} />
        <line
          x1="50"
          y1="50"
          x2="82.5"
          y2="17.5"
          stroke="var(--accent)"
          strokeWidth="1.6"
          strokeLinecap="round"
        />
      </g>

      {/* bearings 45 / 200 / 300 -> delays 0 / 1.72 / 2.83s in globals.css */}
      <circle className="brand-blip b1" cx="69.8" cy="30.2" r="3" fill="var(--brand-spark-radar)" />
      <circle className="brand-blip b2" cx="37" cy="85.7" r="2.4" fill="var(--accent)" />
      <circle className="brand-blip b3" cx="32.7" cy="40" r="2" fill="var(--brand-spark-radar)" />

      <circle cx="50" cy="50" r="4.6" fill="var(--accent)" />
    </svg>
  );
}
