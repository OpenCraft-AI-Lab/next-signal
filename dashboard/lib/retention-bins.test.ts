import assert from "node:assert/strict";
import { test } from "node:test";

import { REVIEW_STAGES, toBins } from "./knowledge/review";

// `toBins` is the only part of the distribution that is not SQL, so this covers
// the shaping: fixed length, stage -> bin mapping, and the two ways a row can
// fail to land on a stage (retired, or a stage outside the schedule).

const row = (over: Partial<Parameters<typeof toBins>[0][number]> = {}) => ({
  retired: false,
  stage: 0,
  total: 1,
  due: 0,
  ...over,
});

test("always returns one bin per stage plus the terminal bin", () => {
  const bins = toBins([]);
  assert.equal(bins.length, REVIEW_STAGES.length + 1);
  assert.deepEqual(
    bins.map((b) => b.days),
    [...REVIEW_STAGES, null],
  );
  assert.ok(bins.every((b) => b.total === 0 && b.due === 0));
});

test("sparse rows land on their stage and leave the rest at zero", () => {
  const bins = toBins([
    row({ stage: 0, total: 6, due: 3 }),
    row({ stage: 3, total: 11, due: 3 }),
  ]);
  assert.deepEqual(bins[0], { days: 1, total: 6, due: 3 });
  assert.deepEqual(bins[3], { days: 15, total: 11, due: 3 });
  assert.deepEqual(bins[1], { days: 3, total: 0, due: 0 });
  assert.deepEqual(bins[6], { days: 120, total: 0, due: 0 });
});

test("retired rows land in the terminal bin whatever their stage says", () => {
  const bins = toBins([
    row({ retired: true, stage: 7, total: 3 }),
    row({ retired: true, stage: 2, total: 1 }),
  ]);
  assert.deepEqual(bins[bins.length - 1], { days: null, total: 4, due: 0 });
  assert.equal(bins[2].total, 0);
});

test("an out-of-range stage is clamped, not dropped", () => {
  const bins = toBins([
    row({ stage: 99, total: 2, due: 1 }),
    row({ stage: -4, total: 5 }),
  ]);
  assert.deepEqual(bins[REVIEW_STAGES.length - 1], { days: 120, total: 2, due: 1 });
  assert.equal(bins[0].total, 5);
  const enrolled = bins.reduce((sum, b) => sum + b.total, 0);
  assert.equal(enrolled, 7);
});

test("counts arriving as strings are coerced", () => {
  const bins = toBins([
    { retired: false, stage: 1, total: "4", due: "2" } as unknown as ReturnType<typeof row>,
  ]);
  assert.deepEqual(bins[1], { days: 3, total: 4, due: 2 });
});
