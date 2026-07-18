// One-off smoke test for lib/score.ts. Run via:
//   pnpm exec tsx lib/score.test.mjs
// or migrate to Vitest if/when test infra lands.

import { scoreHue, scoreLOff } from "./score.ts";

const tests = [
  { name: "scoreHue(0) ≈ 28", actual: scoreHue(0), expect: 28, tol: 0.01 },
  { name: "scoreHue(50) ≈ 55", actual: scoreHue(50), expect: 55, tol: 0.01 },
  { name: "scoreHue(100) ≈ 143", actual: scoreHue(100), expect: 143, tol: 0.01 },
  { name: "scoreLOff(40) === 0", actual: scoreLOff(40), expect: 0, tol: 0 },
  { name: "scoreLOff(60) > 0", actual: scoreLOff(60), expect: 1, tol: 14 },
];

let failed = 0;
for (const t of tests) {
  const diff = Math.abs(t.actual - t.expect);
  const pass = diff <= t.tol;
  if (!pass) {
    failed++;
    console.error(`FAIL: ${t.name} → got ${t.actual}, expected within ${t.tol} of ${t.expect}`);
  } else {
    console.log(`ok: ${t.name} (${t.actual})`);
  }
}

if (failed > 0) process.exit(1);
