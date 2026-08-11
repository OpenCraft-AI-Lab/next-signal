"use client";

import { useState } from "react";
import { toast } from "sonner";

import { useI18n } from "@/components/i18n-provider";
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
 * The *content* language the pipeline's `global` policy reads
 * (`~/.next-signal/language.json`).
 *
 * Deliberately separate from the interface toggle in the nav, which is UI
 * chrome only: reading the interface in one language while generating content
 * in another is a supported state, and nothing here tries to keep the two in
 * sync.
 */
export function LanguageSection({ initial }: { initial: Locale }) {
  const { t } = useI18n();
  const [value, setValue] = useState<Locale>(initial);

  const choose = async (next: Locale) => {
    if (next === value) return;
    const previous = value;
    setValue(next); // optimistic — the panel is the only readback the user gets
    try {
      await setContentLanguage(next);
      toast.success(t.settings.contentLanguageSaved);
    } catch (err) {
      console.error("failed to update content-language preference", err);
      setValue(previous);
      toast.error(t.settings.saveFailed);
    }
  };

  return (
    <section className="card pad set-card" id="language">
      <div className="set-row">
        <div className="set-rowtext">
          <span className="set-label">{t.settings.contentLanguage}</span>
          <span className="set-hint">{t.settings.contentLanguageHint}</span>
        </div>
        <div className="set-rowctl">
          <Segmented>
            {LOCALES.map((l) => (
              <SegmentedItem
                key={l}
                active={value === l}
                onClick={() => void choose(l)}
              >
                {LANGUAGE_NAMES[l]}
              </SegmentedItem>
            ))}
          </Segmented>
        </div>
      </div>
    </section>
  );
}
