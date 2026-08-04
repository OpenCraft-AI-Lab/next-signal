"use client";

import * as Select from "@radix-ui/react-select";
import { Check, ChevronDown, Languages } from "lucide-react";
import { useRouter } from "next/navigation";

import { useI18n } from "@/components/i18n-provider";
import { LOCALE_COOKIE, type Locale } from "@/lib/i18n/dictionaries";

/**
 * Language names are always self-labelled and never translated — a language
 * menu has to be readable to someone who cannot read the language the UI is
 * currently in.
 */
const LOCALES: { value: Locale; name: string; short: string }[] = [
  { value: "en", name: "English", short: "EN" },
  { value: "zh", name: "中文", short: "中文" },
];

/**
 * UI-chrome locale picker. Built on Radix Select rather than a menu primitive
 * because this picks a value rather than firing a command — which also makes
 * the trigger announce the current language instead of an ambiguous target.
 *
 * Governs interface text only. Generated content (radar analyses, wiki
 * frontmatter) follows the separate content-language setting in
 * `SettingsPanel`.
 */
export function LanguageToggle() {
  const router = useRouter();
  const { locale, t } = useI18n();
  const current = LOCALES.find((l) => l.value === locale) ?? LOCALES[0];

  return (
    <Select.Root
      value={locale}
      onValueChange={(next) => {
        if (next === locale) return;
        // UI chrome only. The pipeline's content language is a separate
        // setting, owned by the nav settings panel — the two are independent
        // and may hold different values on purpose.
        document.cookie = `${LOCALE_COOKIE}=${next}; path=/; max-age=31536000; samesite=lax`;
        router.refresh();
      }}
    >
      <Select.Trigger
        className="btn ghost sm lang-toggle"
        aria-label={t.language.label}
      >
        <Languages size={14} />
        <span>{current.short}</span>
        <Select.Icon asChild>
          <ChevronDown size={12} style={{ color: "var(--text-3)" }} />
        </Select.Icon>
      </Select.Trigger>

      <Select.Portal>
        <Select.Content
          position="popper"
          side="bottom"
          align="end"
          sideOffset={6}
          className="z-50 min-w-[8.5rem] overflow-hidden rounded-lg bg-elevated p-1 shadow-menu data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95"
        >
          <Select.Viewport>
            {LOCALES.map((l) => (
              <Select.Item
                key={l.value}
                value={l.value}
                className="flex cursor-pointer select-none items-center justify-between gap-4 rounded-md px-2.5 py-1.5 text-[13.5px] text-text outline-none data-[highlighted]:bg-hover"
              >
                <Select.ItemText>{l.name}</Select.ItemText>
                <Select.ItemIndicator>
                  <Check size={13} className="text-accent" />
                </Select.ItemIndicator>
              </Select.Item>
            ))}
          </Select.Viewport>
        </Select.Content>
      </Select.Portal>
    </Select.Root>
  );
}
