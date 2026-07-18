"use client";

import { type CSSProperties, type ReactNode, useEffect, useRef, useState } from "react";

const MIN = 180;
const MAX = 600;
const DEFAULT = 248;
const STORAGE_KEY = "paca:know-sidebar-w";

/**
 * Wraps the wiki sidebar with a draggable right edge so users can widen it to
 * read long doc titles. The width drives the `.knowgrid` track via the
 * `--know-sidebar-w` CSS var and persists to localStorage. Below the stacked
 * breakpoint the var is ignored (see globals.css) so the sidebar goes full-width.
 */
export function ResizableSidebar({ children }: { children: ReactNode }) {
  const [width, setWidth] = useState(DEFAULT);
  const widthRef = useRef(width);
  widthRef.current = width;

  // Read the saved width after mount to avoid an SSR/hydration mismatch.
  useEffect(() => {
    const saved = Number(localStorage.getItem(STORAGE_KEY));
    if (saved >= MIN && saved <= MAX) setWidth(saved);
  }, []);

  const startDrag = (e: React.PointerEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startW = widthRef.current;
    const onMove = (ev: PointerEvent) => {
      const next = Math.min(MAX, Math.max(MIN, startW + ev.clientX - startX));
      setWidth(next);
    };
    const onUp = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      localStorage.setItem(STORAGE_KEY, String(widthRef.current));
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  };

  return (
    <div
      className="know-side"
      style={{ "--know-sidebar-w": `${width}px` } as CSSProperties}
    >
      {children}
      <div
        className="know-resizer"
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize sidebar"
        onPointerDown={startDrag}
      />
    </div>
  );
}
