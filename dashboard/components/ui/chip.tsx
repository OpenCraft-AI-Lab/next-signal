import { forwardRef, type HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

interface ChipProps extends HTMLAttributes<HTMLSpanElement> {
  /** Render the `.chip.tag` variant (prepends `#`). */
  tag?: boolean;
}

export const Chip = forwardRef<HTMLSpanElement, ChipProps>(
  ({ className, tag, ...props }, ref) => (
    <span ref={ref} className={cn("chip", tag && "tag", className)} {...props} />
  ),
);
Chip.displayName = "Chip";
