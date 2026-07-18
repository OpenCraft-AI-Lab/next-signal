import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  parseGoalsYaml,
  readGoals,
  renderGoalsYaml,
  validateGoals,
  writeGoalsAtomic,
} from "./goals";

const VALID = `
goals:
  - name: ai-infra
    description: Serving systems
    topics: [inference]
    keywords: [vLLM]
`;

test("parseGoalsYaml accepts valid goals", () => {
  const goals = parseGoalsYaml(VALID, "test.yaml");
  assert.equal(goals.length, 1);
  assert.equal(goals[0].name, "ai-infra");
});

test("readGoals reports missing file without throwing", async () => {
  const dir = await mkdtemp(path.join(os.tmpdir(), "paca-goals-"));
  const result = await readGoals(path.join(dir, "missing.yaml"));
  assert.equal(result.ok, false);
  if (!result.ok) assert.equal(result.missing, true);
});

test("parseGoalsYaml rejects duplicate names", () => {
  assert.throws(
    () =>
      parseGoalsYaml(`
goals:
  - name: g
    description: one
  - name: g
    description: two
`),
    /duplicate goal name/,
  );
});

test("parseGoalsYaml rejects unknown top-level keys", () => {
  assert.throws(() => parseGoalsYaml(`${VALID}\nextra: true\n`), /unknown top-level keys/);
});

test("parseGoalsYaml rejects unknown entry keys", () => {
  assert.throws(
    () =>
      parseGoalsYaml(`
goals:
  - name: g
    description: d
    unexpected: true
`),
    /unknown keys/,
  );
});

test("validateGoals rejects empty list", () => {
  assert.throws(() => validateGoals([]), /non-empty list/);
});

test("validateGoals rejects non-string topics", () => {
  assert.throws(
    () => validateGoals([{ name: "g", description: "d", topics: [1], keywords: [] }]),
    /topics: must be a list of strings/,
  );
});

test("writeGoalsAtomic writes canonical yaml", async () => {
  const dir = await mkdtemp(path.join(os.tmpdir(), "paca-goals-"));
  const file = path.join(dir, "goals.yaml");
  await writeGoalsAtomic([{ name: "g", description: "d", topics: ["t"], keywords: [] }], file);
  const raw = await readFile(file, "utf8");
  assert.deepEqual(parseGoalsYaml(raw).map((goal) => goal.name), ["g"]);
  assert.match(raw, /goals:/);
});

test("renderGoalsYaml rejects invalid data before writing", async () => {
  assert.throws(() => renderGoalsYaml([{ name: "g", description: "" }]), /description/);
  const dir = await mkdtemp(path.join(os.tmpdir(), "paca-goals-"));
  const file = path.join(dir, "goals.yaml");
  await writeFile(file, VALID, "utf8");
  await assert.rejects(() => writeGoalsAtomic([], file), /non-empty list/);
  assert.match(await readFile(file, "utf8"), /ai-infra/);
});
