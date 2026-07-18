"use client";

import {
  type ButtonHTMLAttributes,
  type HTMLAttributes,
  forwardRef,
} from "react";

import { cn } from "@/lib/utils";

/**
 * Segmented control matching the design's `.seg` pattern (used for sort
 * toggles, DS-page tabs, anywhere a small set of mutually-exclusive options
 * needs a chip-bar UI). Stateless — the parent decides which option is `on`.
 */
export const Segmented = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} role="tablist" className={cn("seg", className)} {...props} />
  ),
);
Segmented.displayName = "Segmented";

interface SegmentedItemProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean;
}

export const SegmentedItem = forwardRef<HTMLButtonElement, SegmentedItemProps>(
  ({ className, active, type = "button", ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      role="tab"
      aria-selected={active}
      className={cn(active && "on", className)}
      {...props}
    />
  ),
);
SegmentedItem.displayName = "SegmentedItem";
