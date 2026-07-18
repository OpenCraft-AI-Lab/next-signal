"use client";

import { useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

/**
 * Empty mount point inside the nav. The `dashboard-radar` change renders its
 * `Pull + Analyze` button into this slot via `<NavTriggerPortal>` without
 * needing to import anything from radar-land into `nav.tsx`.
 */
export const NAV_TRIGGER_SLOT_ID = "nav-trigger-slot";

export function NavTriggerSlot() {
  return <span id={NAV_TRIGGER_SLOT_ID} className="row gap-8" />;
}

/** Renders its children into the nav trigger slot. */
export function NavTriggerPortal({ children }: { children: ReactNode }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return null;
  const host = document.getElementById(NAV_TRIGGER_SLOT_ID);
  return host ? createPortal(children, host) : null;
}
