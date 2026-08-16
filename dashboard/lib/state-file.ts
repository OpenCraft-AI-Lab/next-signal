import { randomUUID } from "node:crypto";
import { mkdir, rename, writeFile } from "node:fs/promises";
import path from "node:path";

/**
 * Publish `payload` at `target` so a reader sees either the old file or the new
 * one, never a half-written one. Every `~/.next-signal/*.json` the settings page
 * owns is written through here — the Python side reads these files at call time,
 * so a partial read is a live pipeline reading nonsense.
 *
 * The temp name carries the pid and a uuid rather than a fixed `.tmp` suffix,
 * which matters for the second writer rather than the file. Two saves in flight
 * at once — which the settings page produces whenever one control commits while
 * another is still writing — would share one temp path, and the first rename
 * consumes it, so the second fails with ENOENT. The file left behind is intact
 * either way; what breaks is the caller, which reports a failed save and rolls
 * its control back to a value that is no longer what is on disk.
 */
export async function writeStateFile(
  target: string,
  payload: string,
  options?: {
    /**
     * POSIX file mode for the created file, e.g. `0o600` for a file holding
     * credentials. Applied at creation rather than after, so the content is
     * never briefly readable at the default `0o644`. Windows maps modes onto
     * ACLs only nominally; the guarantee is scoped to the Linux container.
     */
    mode?: number;
  },
): Promise<void> {
  await mkdir(path.dirname(target), { recursive: true });
  const tmp = `${target}.${process.pid}.${randomUUID()}.tmp`;
  await writeFile(tmp, payload, { encoding: "utf-8", mode: options?.mode });
  await rename(tmp, target);
}
