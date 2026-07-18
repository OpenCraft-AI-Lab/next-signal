import { forwardRef, type HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export type BadgeKind = "default" | "green" | "amber" | "red" | "purple" | "accent";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  kind?: BadgeKind;
  /** Render the leading colored dot. */
  dot?: boolean;
}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, kind = "default", dot, children, ...props }, ref) => (
    <span
      ref={ref}
      className={cn("badge", kind !== "default" && kind, className)}
      {...props}
    >
      {dot && <span className="dot" />}
      {children}
    </span>
  ),
);
Badge.displayName = "Badge";
