import assert from "node:assert/strict";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";

import { addCategory, listCategories, removeCategoriesUnder } from "./taxonomy";

// Includes hand-aligned inline comments: a YAML-AST round-trip would collapse
// the spacing before `#`, so tests assert these survive byte-for-byte.
const TAXONOMY = `# important comment that must survive edits
freshness:
  default: stable
  tiers:
    permanent:
      review_after_months: null   # never expires
    stable:
      review_after_months: 24     # yearly
categories:
  - path: investing/quant
    scope: quant stuff
    default_freshness: evolving
  - path: life
    scope: life stuff
`;

async function tmpTaxonomy(): Promise<string> {
  const dir = await mkdtemp(path.join(os.tmpdir(), "paca-taxonomy-"));
  const file = path.join(dir, "knowledge_taxonomy.yaml");
  await writeFile(file, TAXONOMY, "utf8");
  return file;
}

test("addCategory appends and leaves untouched lines byte-identical", async () => {
  const file = await tmpTaxonomy();
  await addCategory("knowledge/ai-ml", "ml theory", "stable", file);
  const raw = await readFile(file, "utf8");
  // aligned inline comments and the header survive verbatim
  assert.match(raw, /# important comment that must survive edits/);
  assert.match(raw, /review_after_months: null {3}# never expires/);
  assert.match(raw, /review_after_months: 24 {5}# yearly/);
  const cats = await listCategories(file);
  assert.deepEqual(
    cats.map((c) => c.path),
    ["investing/quant", "life", "knowledge/ai-ml"],
  );
  assert.equal(cats.find((c) => c.path === "knowledge/ai-ml")?.scope, "ml theory");
});

test("add then remove restores the file byte-for-byte", async () => {
  const file = await tmpTaxonomy();
  const before = await readFile(file, "utf8");
  await addCategory("knowledge/ai-ml", "ml theory", "stable", file);
  await removeCategoriesUnder("knowledge/ai-ml", file);
  assert.equal(await readFile(file, "utf8"), before);
});

test("addCategory quotes scopes that would break YAML", async () => {
  const file = await tmpTaxonomy();
  await addCategory("x/y", "has: a colon # and hash", undefined, file);
  const cats = await listCategories(file);
  assert.equal(cats.find((c) => c.path === "x/y")?.scope, "has: a colon # and hash");
});

test("addCategory rejects duplicates", async () => {
  const file = await tmpTaxonomy();
  await assert.rejects(() => addCategory("life", "", undefined, file), /already exists/);
});

test("removeCategoriesUnder prunes path + descendants, keeps comments", async () => {
  const file = await tmpTaxonomy();
  const removed = await removeCategoriesUnder("investing", file);
  assert.equal(removed, 1);
  const raw = await readFile(file, "utf8");
  assert.match(raw, /# important comment that must survive edits/);
  const cats = await listCategories(file);
  assert.deepEqual(
    cats.map((c) => c.path),
    ["life"],
  );
});

test("removeCategoriesUnder returns 0 for non-taxonomy dir", async () => {
  const file = await tmpTaxonomy();
  const removed = await removeCategoriesUnder("tools", file);
  assert.equal(removed, 0);
});
