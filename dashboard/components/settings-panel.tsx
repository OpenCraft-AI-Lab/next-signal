"use client";

import { Settings } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { useI18n } from "@/components/i18n-provider";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Segmented, SegmentedItem } from "@/components/ui/segmented";
import { setContentLanguage } from "@/lib/actions/language";
import { LOCALES, type Locale } from "@/lib/i18n/dictionaries";

/**
 * Self-labelled and never translated, for the same reason `LanguageToggle`'s
 * are: a language choice has to be readable to someone who cannot read the
 * language the UI is currently in.
 */
const LANGUAGE_NAMES: Record<Locale, string> = { en: "English", zh: "中文" };

/**
 * Nav settings panel. Owns the *content* language — the one the pipeline's
 * `global` policy reads (`~/.next-signal/language.json`), governing radar
 * analyses and wiki frontmatter. Deliberately separate from `LanguageToggle`
 * beside it, which is UI chrome only: reading the interface in one language
 * while generating content in another is a supported state, and nothing here
 * tries to keep the two in sync.
 */
export function SettingsPanel({ contentLanguage }: { contentLanguage: Locale }) {
  const { t } = useI18n();
  const [value, setValue] = useState<Locale>(contentLanguage);

  const choose = async (next: Locale) => {
    if (next === value) return;
    const previous = value;
    setValue(next); // optimistic — the panel is the only readback the user gets
    try {
      await setContentLanguage(next);
    } catch (err) {
      console.error("failed to update content-language preference", err);
      setValue(previous);
      toast.error(t.settings.saveFailed);
    }
  };

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="icon" aria-label={t.settings.trigger} title={t.settings.trigger}>
          <Settings size={15} />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="col w-[20rem] gap-3">
        <p className="sec-title">{t.settings.heading}</p>
        <div className="col gap-2">
          <span className="text-[13px] font-medium">{t.settings.contentLanguage}</span>
          {/* self-start: `.seg` is inline-flex, but as a child of `col` it would
              stretch to the panel width and strand the two options at the left. */}
          <Segmented className="self-start">
            {LOCALES.map((l) => (
              <SegmentedItem key={l} active={value === l} onClick={() => void choose(l)}>
                {LANGUAGE_NAMES[l]}
              </SegmentedItem>
            ))}
          </Segmented>
          <p className="muted text-[12px] leading-snug">{t.settings.contentLanguageHint}</p>
        </div>
      </PopoverContent>
    </Popover>
  );
}
