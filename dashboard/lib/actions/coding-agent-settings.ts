"use server";

import { readFile } from "node:fs/promises";

import {
  UNSET_CODING_AGENT_SETTINGS,
  parseCodingAgentSettings,
  serializeCodingAgentSettings,
  type ClaudeSettings,
  type CodexSettings,
  type CodingAgentSettings,
} from "@/lib/coding-agent-preferences";
import { codingAgentPreferencesFile } from "@/lib/paths";
import { writeStateFile } from "@/lib/state-file";

function unsetSettings(): CodingAgentSettings {
  return {
    codex: { ...UNSET_CODING_AGENT_SETTINGS.codex },
    claude: { ...UNSET_CODING_AGENT_SETTINGS.claude },
  };
}

/** Read live provider defaults without making a damaged file hide the panel. */
export async function getCodingAgentSettings(): Promise<CodingAgentSettings> {
  let raw: string;
  try {
    raw = await readFile(codingAgentPreferencesFile(), "utf-8");
  } catch {
    return unsetSettings();
  }
  try {
    return parseCodingAgentSettings(raw);
  } catch (err) {
    console.error(
      `${codingAgentPreferencesFile()} is unusable, using unconfigured values`,
      err,
    );
    return unsetSettings();
  }
}

async function writeSettings(next: CodingAgentSettings): Promise<void> {
  await writeStateFile(
    codingAgentPreferencesFile(),
    serializeCodingAgentSettings(next),
  );
}

/** Save Codex defaults while preserving the latest Claude section. */
export async function setCodexSettings(next: CodexSettings): Promise<void> {
  const current = await getCodingAgentSettings();
  await writeSettings({ ...current, codex: next });
}

/** Save Claude defaults while preserving the latest Codex section. */
export async function setClaudeSettings(next: ClaudeSettings): Promise<void> {
  const current = await getCodingAgentSettings();
  await writeSettings({ ...current, claude: next });
}
