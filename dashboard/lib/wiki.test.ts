import assert from "node:assert/strict";
import { mkdir, mkdtemp, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";

import { listWikiTree, type WikiNode } from "./wiki";

async function buildWiki(): Promise<string> {
  const root = await mkdtemp(path.join(os.tmpdir(), "paca-wiki-"));
  // loose .md in a nested folder
  await mkdir(path.join(root, "investing", "quant"), { recursive: true });
  await writeFile(path.join(root, "investing", "quant", "note.md"), "# note\n");
  // empty folder (must still show)
  await mkdir(path.join(root, "empty-folder"), { recursive: true });
  // per-article folder: <slug>/<slug>.md + images/ → collapses to one doc
  await mkdir(path.join(root, "articles", "my-article", "images"), {
    recursive: true,
  });
  await writeFile(
    path.join(root, "articles", "my-article", "my-article.md"),
    "# article\n",
  );
  process.env.PACA_WIKI_DIR = root;
  return root;
}

function folder(nodes: WikiNode[], name: string) {
  const n = nodes.find((x) => x.kind === "folder" && x.name === name);
  assert.ok(n && n.kind === "folder", `expected folder ${name}`);
  return n;
}

test("listWikiTree nests folders, keeps empties, folds per-article dirs", async () => {
  await buildWiki();
  const tree = await listWikiTree();

  // folders sorted by path, before docs
  assert.deepEqual(
    tree.filter((n) => n.kind === "folder").map((n) => (n as { name: string }).name),
    ["articles", "empty-folder", "investing"],
  );

  // empty folder is present with zero docs
  assert.equal(folder(tree, "empty-folder").docCount, 0);
  assert.equal(folder(tree, "empty-folder").children.length, 0);

  // per-article folder collapses to a single doc leaf (not a folder)
  const articles = folder(tree, "articles");
  assert.equal(articles.docCount, 1);
  assert.equal(articles.children.length, 1);
  const leaf = articles.children[0];
  assert.equal(leaf.kind, "doc");
  if (leaf.kind === "doc") {
    assert.equal(leaf.doc.id, path.join("articles", "my-article", "my-article.md"));
  }

  // nested folder carries its doc + subtree count
  const investing = folder(tree, "investing");
  assert.equal(investing.docCount, 1);
  const quant = folder(investing.children, "quant");
  assert.equal(quant.children[0].kind, "doc");
});
