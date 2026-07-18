"use client";

import * as CollapsiblePrimitive from "@radix-ui/react-collapsible";
import {
  forwardRef,
  type ComponentPropsWithoutRef,
  type ElementRef,
} from "react";

import { cn } from "@/lib/utils";

/**
 * Radix-backed Collapsible that uses the design's `.collapsible / .inner`
 * grid-rows animation from globals.css. The `data-state` attribute toggles
 * the `.open` class so the height transition kicks in.
 */
export const Collapsible = CollapsiblePrimitive.Root;
export const CollapsibleTrigger = CollapsiblePrimitive.Trigger;

export const CollapsibleContent = forwardRef<
  ElementRef<typeof CollapsiblePrimitive.Content>,
  ComponentPropsWithoutRef<typeof CollapsiblePrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <CollapsiblePrimitive.Content
    ref={ref}
    forceMount
    className={cn(
      // `.collapsible` from globals.css gives the grid-row height transition;
      // toggle the `.open` class via data-state so we don't reach for Radix's
      // CSS variable height (which fights the design's grid-row strategy).
      "collapsible data-[state=open]:!grid-rows-[1fr]",
      className,
    )}
    {...props}
  >
    <div className="inner">{children}</div>
  </CollapsiblePrimitive.Content>
));
CollapsibleContent.displayName = CollapsiblePrimitive.Content.displayName;
