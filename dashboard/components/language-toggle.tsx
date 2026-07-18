"use client";

import { Languages } from "lucide-react";
import { useRouter } from "next/navigation";

import { useI18n } from "@/components/i18n-provider";
import { Button } from "@/components/ui/button";
import { LOCALE_COOKIE, type Locale } from "@/lib/i18n/dictionaries";

function nextLocale(locale: Locale): Locale {
  return locale === "zh" ? "en" : "zh";
}

export function LanguageToggle() {
  const router = useRouter();
  const { locale, t } = useI18n();

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => {
        const next = nextLocale(locale);
        document.cookie = `${LOCALE_COOKIE}=${next}; path=/; max-age=31536000; samesite=lax`;
        router.refresh();
      }}
      aria-label={t.language.label}
      title={t.language.title}
      className="lang-toggle"
    >
      <Languages size={14} />
      {t.language.next}
    </Button>
  );
}
