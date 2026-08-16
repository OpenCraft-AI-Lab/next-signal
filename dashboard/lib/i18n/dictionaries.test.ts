import assert from "node:assert/strict";
import test from "node:test";

import { LOCALES, dictionaries } from "./dictionaries";

/**
 * `getDictionary` casts (`dictionaries[locale] as Dictionary`), so TypeScript
 * never checks the non-English locales against the English shape: a key missing
 * from `zh` compiles and renders `undefined` in the UI. The project rule is that
 * both languages ship together, so hold it here instead.
 */
function leafKeys(value: unknown, prefix = ""): string[] {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return [prefix];
  }
  return Object.entries(value as Record<string, unknown>).flatMap(([k, v]) =>
    leafKeys(v, prefix ? `${prefix}.${k}` : k),
  );
}

const english = new Set(leafKeys(dictionaries.en));

for (const locale of LOCALES.filter((l) => l !== "en")) {
  test(`${locale} defines every key English does`, () => {
    const theirs = new Set(leafKeys(dictionaries[locale]));

    assert.deepEqual(
      [...english].filter((k) => !theirs.has(k)),
      [],
      `missing from ${locale}`,
    );
  });

  test(`${locale} defines no key English lacks`, () => {
    const theirs = leafKeys(dictionaries[locale]);

    assert.deepEqual(
      theirs.filter((k) => !english.has(k)),
      [],
      `absent from en`,
    );
  });

  test(`${locale} has no empty strings`, () => {
    const empties = Object.entries(dictionaries[locale]).flatMap(([section, v]) =>
      leafKeys(v, section).filter((path) => {
        const value = path
          .split(".")
          .reduce<unknown>(
            (acc, k) => (acc as Record<string, unknown>)?.[k],
            dictionaries[locale],
          );
        return typeof value === "string" && value.trim() === "";
      }),
    );

    assert.deepEqual(empties, []);
  });
}
