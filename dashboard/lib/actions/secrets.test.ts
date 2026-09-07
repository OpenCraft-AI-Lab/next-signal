import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, stat, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

/**
 * The store's write path, which `lib/secrets.test.ts` does not reach: that file
 * covers the pure parse/serialize helpers, while everything here touches disk.
 *
 * Each test points `NEXT_SIGNAL_STATE_DIR` at a fresh temp dir before importing
 * the actions, so nothing can read or overwrite a real `~/.next-signal`.
 */
async function withStore<T>(
  body: (
    actions: typeof import("./secrets"),
    storePath: string,
  ) => Promise<T>,
): Promise<T> {
  const dir = await mkdtemp(path.join(os.tmpdir(), "ns-secrets-"));
  const previous = process.env.NEXT_SIGNAL_STATE_DIR;
  process.env.NEXT_SIGNAL_STATE_DIR = dir;
  try {
    // Fresh module each time: `secretsStateFile()` reads the env at call time,
    // but importing once and mutating the env between tests would still share
    // one module instance across them.
    const actions = (await import(
      `./secrets.ts?case=${Math.random()}`
    )) as typeof import("./secrets");
    return await body(actions, path.join(dir, "secrets.json"));
  } finally {
    if (previous === undefined) delete process.env.NEXT_SIGNAL_STATE_DIR;
    else process.env.NEXT_SIGNAL_STATE_DIR = previous;
  }
}

test("an absent store reports every credential as unset", async () => {
  await withStore(async ({ getCredentialPresence }) => {
    const presence = await getCredentialPresence();
    assert.equal(presence.OPENAI_API_KEY, false);
    assert.equal(presence.FOLO_TOKEN, false);
  });
});

test("a saved credential is written to disk and reported present", async () => {
  await withStore(async (actions, storePath) => {
    await actions.saveCredential("OPENAI_API_KEY", "sk-example");

    assert.deepEqual(JSON.parse(await readFile(storePath, "utf-8")), {
      OPENAI_API_KEY: "sk-example",
    });
    assert.equal(
      (await actions.getCredentialPresence()).OPENAI_API_KEY,
      true,
    );
  });
});

test("presence never returns the value it reports on", async () => {
  await withStore(async (actions) => {
    await actions.saveCredential("OPENAI_API_KEY", "sk-example");

    const presence = await actions.getCredentialPresence();
    assert.ok(!JSON.stringify(presence).includes("sk-example"));
  });
});

test("saving one credential leaves the others intact", async () => {
  await withStore(async (actions, storePath) => {
    await actions.saveCredential("OPENAI_API_KEY", "sk-one");
    await actions.saveCredential("FOLO_TOKEN", "folo-token");
    await actions.saveCredential("OPENAI_API_KEY", "sk-two");

    assert.deepEqual(JSON.parse(await readFile(storePath, "utf-8")), {
      FOLO_TOKEN: "folo-token",
      OPENAI_API_KEY: "sk-two",
    });
  });
});

test("clearing removes one credential and is idempotent", async () => {
  await withStore(async (actions, storePath) => {
    await actions.saveCredential("OPENAI_API_KEY", "sk-example");
    await actions.saveCredential("FOLO_TOKEN", "folo-token");

    await actions.deleteCredential("OPENAI_API_KEY");
    await actions.deleteCredential("OPENAI_API_KEY");

    assert.deepEqual(JSON.parse(await readFile(storePath, "utf-8")), {
      FOLO_TOKEN: "folo-token",
    });
  });
});

test("an empty value is refused rather than stored", async () => {
  await withStore(async (actions) => {
    await assert.rejects(
      () => actions.saveCredential("OPENAI_API_KEY", "   "),
      /empty value/,
    );
  });
});

test("a malformed name is refused", async () => {
  await withStore(async (actions) => {
    await assert.rejects(
      () => actions.saveCredential("lowercase", "value"),
      /credential name/,
    );
  });
});

test("a damaged store is reported rather than read as empty", async () => {
  await withStore(async (actions, storePath) => {
    const { writeFile } = await import("node:fs/promises");
    await writeFile(storePath, "{ not json", "utf-8");

    await assert.rejects(
      () => actions.getCredentialPresence(),
      /invalid credential store/,
    );
  });
});

test("the operator-defined embedding credential is reported when named", async () => {
  await withStore(async (actions) => {
    await actions.saveCredential("MY_EMBED_KEY", "sk-custom");

    const presence = await actions.getCredentialPresence(["MY_EMBED_KEY"]);
    assert.equal(presence.MY_EMBED_KEY, true);
  });
});

test("the store is written owner-only", { skip: process.platform === "win32" }, async () => {
  await withStore(async (actions, storePath) => {
    await actions.saveCredential("OPENAI_API_KEY", "sk-example");

    assert.equal((await stat(storePath)).mode & 0o777, 0o600);
  });
});

test("a Radar Embedding credential is writable before any provider is selected", async () => {
  await withStore(async (actions) => {
    await actions.saveCredential("RADAR_EMBEDDING_OPENAI_API_KEY", "sk-example");
    assert.equal(
      (await actions.getCredentialPresence()).RADAR_EMBEDDING_OPENAI_API_KEY,
      true,
    );
  });
});

test("a locked Radar Embedding section rejects a credential save and delete", async () => {
  await withStore(async (actions, storePath) => {
    await actions.saveCredential("RADAR_EMBEDDING_OPENAI_API_KEY", "sk-example");

    const embeddingPath = path.join(path.dirname(storePath), "embedding.json");
    await writeFile(
      embeddingPath,
      JSON.stringify({ provider: "openai", openai: { model: "text-embedding-3-small" } }),
      "utf-8",
    );

    await assert.rejects(
      () => actions.saveCredential("RADAR_EMBEDDING_OPENAI_API_KEY", "sk-replacement"),
      /locked/,
    );
    await assert.rejects(
      () => actions.deleteCredential("RADAR_EMBEDDING_OPENAI_API_KEY"),
      /locked/,
    );
    assert.deepEqual(JSON.parse(await readFile(storePath, "utf-8")), {
      RADAR_EMBEDDING_OPENAI_API_KEY: "sk-example",
    });
  });
});

test("a locked Knowledge Embedding section rejects a credential save and delete", async () => {
  await withStore(async (actions, storePath) => {
    await actions.saveCredential("VOYAGE_API_KEY", "voyage-example");

    const gbrainHome = await mkdtemp(path.join(os.tmpdir(), "ns-gbrain-"));
    const previousGbrainHome = process.env.GBRAIN_HOME;
    process.env.GBRAIN_HOME = gbrainHome;
    try {
      await mkdir(path.join(gbrainHome, ".gbrain"), { recursive: true });
      await writeFile(
        path.join(gbrainHome, ".gbrain", "config.json"),
        JSON.stringify({ embedding_model: "voyage:voyage-3-large" }),
        "utf-8",
      );

      await assert.rejects(
        () => actions.saveCredential("VOYAGE_API_KEY", "voyage-replacement"),
        /locked/,
      );
      await assert.rejects(
        () => actions.deleteCredential("VOYAGE_API_KEY"),
        /locked/,
      );
      assert.deepEqual(JSON.parse(await readFile(storePath, "utf-8")), {
        VOYAGE_API_KEY: "voyage-example",
      });
    } finally {
      if (previousGbrainHome === undefined) delete process.env.GBRAIN_HOME;
      else process.env.GBRAIN_HOME = previousGbrainHome;
    }
  });
});

test("the serialized form is what the Python loader expects", async () => {
  await withStore(async (actions, storePath) => {
    await actions.saveCredential("B_TOKEN", "2");
    await actions.saveCredential("A_TOKEN", "1");

    // Sorted keys, two-space indent, trailing newline — byte-identical to
    // `json.dumps(..., indent=2, sort_keys=True) + "\n"` in core/secrets.py,
    // so a file written on either side reads cleanly on the other.
    assert.equal(
      await readFile(storePath, "utf-8"),
      '{\n  "A_TOKEN": "1",\n  "B_TOKEN": "2"\n}\n',
    );
  });
});
