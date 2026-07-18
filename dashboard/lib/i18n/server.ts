import { cookies } from "next/headers";

import {
  DEFAULT_LOCALE,
  LOCALE_COOKIE,
  getDictionary,
  normalizeLocale,
  type Locale,
} from "@/lib/i18n/dictionaries";

export async function getLocale(): Promise<Locale> {
  const store = await cookies();
  return normalizeLocale(store.get(LOCALE_COOKIE)?.value ?? DEFAULT_LOCALE);
}

export async function getServerDictionary() {
  return getDictionary(await getLocale());
}
