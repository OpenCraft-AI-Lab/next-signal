"use client";

import { ChevronDown, ChevronRight } from "lucide-react";
import type { ReactNode } from "react";

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

/**
 * The collapsible shell every functional settings section renders through.
 *
 * Collapsed, a section shows only its label and a one-line summary of what is
 * selected (or that nothing is). Changing anything requires expanding it
 * first — selecting an option is never itself a commit, and this shell is
 * what makes "expand to act" the same gesture everywhere instead of five
 * sections improvising their own affordance for it.
 *
 * Starts collapsed: a fresh install has nothing configured anywhere, and a
 * section with something to decide is one the operator opens on purpose
 * rather than one that greets them already sprawled open.
 */
export function SettingsSectionShell({
  id,
  label,
  hint,
  summary,
  children,
}: {
  id: string;
  label: string;
  hint: string;
  /** One-line description of the current state, shown whether open or closed. */
  summary: ReactNode;
  children: ReactNode;
}) {
  return (
    <Collapsible className="card pad set-card group" id={id}>
      <CollapsibleTrigger className="set-sectiontrigger" style={{ width: "100%" }}>
        <span className="set-sectionchevrons">
          <ChevronRight size={14} className="muted-2 group-data-[state=open]:hidden" />
          <ChevronDown size={14} className="muted-2 hidden group-data-[state=open]:block" />
        </span>
        <div className="set-rowtext">
          <span className="set-label">{label}</span>
          <span className="set-hint">{hint}</span>
        </div>
        <div className="set-rowctl">{summary}</div>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="set-sectionbody">{children}</div>
      </CollapsibleContent>
    </Collapsible>
  );
}
