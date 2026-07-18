"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { useI18n } from "@/components/i18n-provider";
import { Button } from "@/components/ui/button";

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const { t } = useI18n();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  // Avoid the icon flicker between SSR (no theme) and client hydration.
  if (!mounted) {
    return <Button variant="icon" aria-label={t.theme.toggle} />;
  }
  const isDark = resolvedTheme === "dark";
  return (
    <Button
      variant="icon"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      aria-label={t.theme.toggle}
      title={t.theme.toggle}
    >
      {isDark ? <Sun size={15} /> : <Moon size={15} />}
    </Button>
  );
}
