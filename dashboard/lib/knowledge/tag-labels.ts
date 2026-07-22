import { query } from "@/lib/db";

/**
 * Localized display labels for tag keys, read from `knowledge_tag_labels`.
 *
 * Tag KEYS stay canonical English (stable GBrain join keys); this returns a
 * `key -> label` map for the given locale so the reader can show tags in the
 * item's own language. `en` is the identity (label === key) so it returns an
 * empty map and callers fall back to the key. Best-effort: a DB failure yields
 * an empty map (render falls back to keys), never throwing.
 */
export async function getTagLabels(
  tags: string[],
  locale: string,
): Promise<Map<string, string>> {
  const labels = new Map<string, string>();
  if (tags.length === 0 || locale === "en") return labels;
  try {
    const rows = await query<{ tag: string; label: string }>(
      "SELECT tag, label FROM knowledge_tag_labels WHERE locale = $1 AND tag = ANY($2)",
      [locale, tags],
    );
    for (const row of rows) labels.set(row.tag, row.label);
  } catch {
    // Display chrome only — degrade to the English keys.
  }
  return labels;
}
