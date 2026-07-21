"use client";

import { ChevronDown } from "lucide-react";
import { type CSSProperties, type ReactNode, useState } from "react";

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { RECAP_COLLAPSED_COOKIE } from "@/lib/radar/recap-ui";

const triggerStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 6,
  background: "none",
  border: "none",
  padding: 0,
  margin: 0,
  cursor: "pointer",
  color: "inherit",
  font: "inherit",
};

/**
 * Collapsible shell for the Smart Recap section. Controlled so the collapsed
 * state both animates instantly (client) and survives navigation (cookie).
 *
 * `initialOpen` is resolved server-side: the stored preference, but forced open
 * when the URL targets a specific recap (a saved-recap click), so reopening one
 * never lands the reader on a collapsed, empty-looking header.
 */
export function SmartRecapSection({
  initialOpen,
  title,
  subtitle,
  children,
}: {
  initialOpen: boolean;
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(initialOpen);

  return (
    <section id="recap">
      <Collapsible
        open={open}
        onOpenChange={(next) => {
          setOpen(next);
          document.cookie = `${RECAP_COLLAPSED_COOKIE}=${next ? "0" : "1"}; path=/; max-age=31536000; samesite=lax`;
        }}
      >
        <div className="sec-head">
          <CollapsibleTrigger asChild>
            <button type="button" style={triggerStyle} aria-expanded={open}>
              <ChevronDown
                size={15}
                style={{
                  color: "var(--text-4)",
                  transition: "transform 0.2s ease",
                  transform: open ? "none" : "rotate(-90deg)",
                }}
              />
              <h2 className="sec-title">{title}</h2>
            </button>
          </CollapsibleTrigger>
          <span className="sec-sub">{subtitle}</span>
        </div>
        <CollapsibleContent>{children}</CollapsibleContent>
      </Collapsible>
    </section>
  );
}
