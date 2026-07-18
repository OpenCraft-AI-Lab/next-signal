import { Alpaca } from "@/components/brand/alpaca";

interface RadarAlpacaProps {
  size?: number;
}

/**
 * Production radar emblem — animated radar rings + rotating sweep + blips
 * with a centered Alpaca. Ported as-is from
 * `dashboard/design/components.jsx::RadarAlpaca`.
 *
 * The sweep / blip animations live in `app/globals.css` under
 * `.radar-sweep`, `.blip`, `@keyframes radarSpin`, `@keyframes blipPulse`.
 *
 * Variant emblems (`RadarAlpacaScope`, `RadarAlpacaArc`) intentionally NOT ported.
 */
export function RadarAlpaca({ size = 76 }: RadarAlpacaProps) {
  return (
    <div className="radar-emblem" style={{ width: size, height: size }}>
      <svg viewBox="0 0 100 100" width={size} height={size}>
        <defs>
          <linearGradient id="sweepGrad" x1="0" y1="0" x2="1" y2="0.4">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.45" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
          </linearGradient>
        </defs>
        {/* rings */}
        <circle cx="50" cy="50" r="46" fill="none" stroke="var(--border)" strokeWidth="1" />
        <circle cx="50" cy="50" r="32" fill="none" stroke="var(--border-2)" strokeWidth="1" />
        <circle cx="50" cy="50" r="18" fill="none" stroke="var(--border-2)" strokeWidth="1" />
        {/* crosshairs */}
        <line x1="50" y1="4" x2="50" y2="96" stroke="var(--border-2)" strokeWidth="1" />
        <line x1="4" y1="50" x2="96" y2="50" stroke="var(--border-2)" strokeWidth="1" />
        {/* rotating sweep */}
        <g className="radar-sweep" style={{ transformOrigin: "50px 50px" }}>
          <path d="M50 50 L50 4 A46 46 0 0 1 91 28 Z" fill="url(#sweepGrad)" />
          <line x1="50" y1="50" x2="50" y2="4" stroke="var(--accent)" strokeWidth="1.2" strokeOpacity="0.7" />
        </g>
        {/* blips */}
        <circle className="blip b1" cx="69" cy="31" r="2.6" fill="var(--accent)" />
        <circle className="blip b2" cx="33" cy="66" r="2.1" fill="var(--green)" />
        <circle className="blip b3" cx="64" cy="68" r="1.8" fill="var(--amber)" />
        {/* center alpaca */}
        <g transform="translate(36 35) scale(1.18)">
          <Alpaca size={24} color="var(--accent)" eye="var(--bg)" />
        </g>
      </svg>
    </div>
  );
}
