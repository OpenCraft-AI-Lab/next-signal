import assert from "node:assert/strict";
import { mkdtemp, readdir, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";

import { writeStateFile } from "./state-file";

test("writeStateFile publishes the payload and leaves no temp file behind", async () => {
  const dir = await mkdtemp(path.join(tmpdir(), "ns-state-"));
  const target = path.join(dir, "nested", "state.json");

  await writeStateFile(target, '{"a":1}');

  assert.equal(await readFile(target, "utf-8"), '{"a":1}');
  assert.deepEqual(await readdir(path.dirname(target)), ["state.json"]);
});

// POSIX-only. `rename(2)` over an existing path is atomic and always succeeds,
// so a losing writer still reports success. On Windows the equivalent can fail
// with EPERM while another handle holds the target, which makes this assertion
// unreachable there. The dashboard ships in a Linux container, so the guarantee
// under test is the one that actually runs.
test("concurrent saves both succeed and one of them is what lands", {
  skip: process.platform === "win32" ? "POSIX-only: rename-over-existing is not atomic on Windows" : false,
}, async () => {
  // Both writers previously shared one `${target}.tmp`, so the first rename
  // consumed it and the second always failed with ENOENT — surfacing in the
  // settings page as a spurious "save failed" plus a control rolled back to a
  // value that is no longer on disk. The file itself was never the casualty.
  const dir = await mkdtemp(path.join(tmpdir(), "ns-state-"));
  const target = path.join(dir, "state.json");
  const a = JSON.stringify({ who: "a" });
  const b = JSON.stringify({ who: "b" });

  for (let i = 0; i < 20; i++) {
    const results = await Promise.allSettled([
      writeStateFile(target, a),
      writeStateFile(target, b),
    ]);
    assert.deepEqual(
      results.map((r) => r.status),
      ["fulfilled", "fulfilled"],
      "neither save may report a failure it did not have",
    );
    const landed = await readFile(target, "utf-8");
    assert.ok(landed === a || landed === b, "one payload in full, not a blend");
  }
});
