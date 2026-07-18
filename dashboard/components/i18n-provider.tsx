"use client";

import { createContext, useContext, useMemo, type ReactNode } from "react";

import {
  DEFAULT_LOCALE,
  getDictionary,
  type Dictionary,
  type Locale,
} from "@/lib/i18n/dictionaries";

type I18nContextValue = {
  locale: Locale;
  t: Dictionary;
};

const I18nContext = createContext<I18nContextValue>({
  locale: DEFAULT_LOCALE,
  t: getDictionary(DEFAULT_LOCALE),
});

export function I18nProvider({
  locale,
  children,
}: {
  locale: Locale;
  children: ReactNode;
}) {
  const value = useMemo(() => ({ locale, t: getDictionary(locale) }), [locale]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  return useContext(I18nContext);
}
