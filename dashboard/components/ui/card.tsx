import { forwardRef, type HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** Apply the `.card.pad` 14×16 padding variant. */
  pad?: boolean;
  /** Apply the `.card.hoverable` lift-on-hover variant. */
  hoverable?: boolean;
}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ className, pad, hoverable, ...props }, ref) => (
    <div
      ref={ref}
      className={cn("card", pad && "pad", hoverable && "hoverable", className)}
      {...props}
    />
  ),
);
Card.displayName = "Card";
