"use client";

import {
  Book,
  Palette,
  Radar as RadarIcon,
  Rss,
  Target,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ComponentType } from "react";

import { Alpaca } from "@/components/brand/alpaca";
import { useI18n } from "@/components/i18n-provider";
import { LanguageToggle } from "@/components/language-toggle";
import { NavTriggerSlot } from "@/components/nav-trigger-slot";
import { ThemeToggle } from "@/components/theme-toggle";
import { cn } from "@/lib/utils";

type NavItem = {
  href: string;
  icon: ComponentType<{ size?: number }>;
};

// `/design` is an internal design-system reference, not a product surface —
// it stays out of the nav outside dev builds. The route itself still resolves.
const IS_DEV = process.env.NODE_ENV === "development";

const NAV_ITEMS: NavItem[] = [
  { href: "/radar", icon: RadarIcon },
  { href: "/knowledge", icon: Book },
  { href: "/goals", icon: Target },
  { href: "/subscriptions", icon: Rss },
  ...(IS_DEV ? [{ href: "/design", icon: Palette }] : []),
];

export function Nav() {
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
            <Alpaca size={20} color="var(--accent-fg)" eye="var(--accent)" />
          </span>
          <span>paca</span>
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
          <ThemeToggle />
        </div>
      </div>
    </nav>
  );
}
