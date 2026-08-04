"use client";

import { Palette, Rss, Target } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ComponentType } from "react";

import { KnowledgeMark } from "@/components/brand/knowledge-mark";
import { RadarMark } from "@/components/brand/radar-mark";
import { SignalMark } from "@/components/brand/signal-mark";
import { useI18n } from "@/components/i18n-provider";
import { LanguageToggle } from "@/components/language-toggle";
import { NavTriggerSlot } from "@/components/nav-trigger-slot";
import { SettingsPanel } from "@/components/settings-panel";
import { ThemeToggle } from "@/components/theme-toggle";
import type { Locale } from "@/lib/i18n/dictionaries";
import { cn } from "@/lib/utils";

type NavItem = {
  href: string;
  icon: ComponentType<{ size?: number }>;
};

// Radar and Knowledge are the two products with their own brand mark, so their
// nav entries use it; the rest stay on lucide. A brand glyph in the nav means
// something, and would stop meaning anything if every row had one.
// Both pass spark=currentColor so they sit at lucide's weight — the module
// spark belongs to the icon/emblem tiers, not a 15px nav row. Radar's nav tier
// has no blip today, but stating it keeps the two symmetric and stops a future
// blip from silently appearing in cyan here.
const RadarNavIcon = (props: { size?: number }) => (
  <RadarMark {...props} variant="nav" spark="currentColor" />
);
const KnowledgeNavIcon = (props: { size?: number }) => (
  <KnowledgeMark {...props} variant="nav" spark="currentColor" />
);

// `/design` is an internal design-system reference, not a product surface —
// it stays out of the nav outside dev builds. The route itself still resolves.
const IS_DEV = process.env.NODE_ENV === "development";

const NAV_ITEMS: NavItem[] = [
  { href: "/radar", icon: RadarNavIcon },
  { href: "/knowledge", icon: KnowledgeNavIcon },
  { href: "/goals", icon: Target },
  { href: "/subscriptions", icon: Rss },
  ...(IS_DEV ? [{ href: "/design", icon: Palette }] : []),
];

/** `contentLanguage` is resolved server-side in the root layout so the
 * settings panel renders its current value without a fetch on open. */
export function Nav({ contentLanguage }: { contentLanguage: Locale }) {
  const pathname = usePathname();
  const { t } = useI18n();
  const [host, setHost] = useState<string | null>(null);

  useEffect(() => {
    setHost(window.location.host);
  }, []);

  return (
    <nav className="nav">
      <div className="nav-inner">
        <div className="brand">
          <span className="mark">
            <SignalMark size={17} />
          </span>
          <span>next-signal</span>
          {host && <span className="env">{host}</span>}
        </div>
        <div className="nav-links">
          {NAV_ITEMS.map((item) => {
            const active =
              pathname === item.href || pathname.startsWith(`${item.href}/`);
            const Icon = item.icon;
            const label =
              item.href === "/radar"
                ? t.nav.radar
                : item.href === "/knowledge"
                  ? t.nav.knowledge
                  : item.href === "/goals"
                    ? t.nav.goals
                    : item.href === "/subscriptions"
                      ? t.nav.subscriptions
                      : t.nav.design;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn("nav-link", active && "active")}
              >
                <Icon size={15} />
                {label}
              </Link>
            );
          })}
        </div>
        <div className="nav-spacer" />
        <div className="nav-tools">
          <NavTriggerSlot />
          <LanguageToggle />
          <SettingsPanel contentLanguage={contentLanguage} />
          <ThemeToggle />
        </div>
      </div>
    </nav>
  );
}
