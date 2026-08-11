export const CODEX_REASONING_EFFORTS = [
  "minimal",
  "low",
  "medium",
  "high",
  "xhigh",
] as const;
export const CODEX_SERVICE_TIERS = ["default", "fast"] as const;
export const CLAUDE_EFFORTS = [
  "low",
  "medium",
  "high",
  "xhigh",
  "max",
] as const;

export type CodexReasoningEffort = (typeof CODEX_REASONING_EFFORTS)[number];
export type CodexServiceTier = (typeof CODEX_SERVICE_TIERS)[number];
export type ClaudeEffort = (typeof CLAUDE_EFFORTS)[number];

export interface CodexSettings {
  model: string;
  modelReasoningEffort: CodexReasoningEffort | "";
  serviceTier: CodexServiceTier | "";
}

export interface ClaudeSettings {
  model: string;
  effort: ClaudeEffort | "";
}

export interface CodingAgentSettings {
  codex: CodexSettings;
  claude: ClaudeSettings;
}

export const UNSET_CODEX_SETTINGS: CodexSettings = {
  model: "",
  modelReasoningEffort: "",
  serviceTier: "",
};

export const UNSET_CLAUDE_SETTINGS: ClaudeSettings = {
  model: "",
  effort: "",
};

export const UNSET_CODING_AGENT_SETTINGS: CodingAgentSettings = {
  codex: UNSET_CODEX_SETTINGS,
  claude: UNSET_CLAUDE_SETTINGS,
};

const CODEX_MODEL_ID = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/;
const CLAUDE_MODEL_ID = /^[A-Za-z0-9][A-Za-z0-9._:/[\]-]{0,511}$/;
const TOP_LEVEL_KEYS = new Set([
  "codex",
  "claude",
  "updated_at",
  "updated_by",
]);
const CODEX_KEYS = new Set(["model", "model_reasoning_effort", "service_tier"]);
const CLAUDE_KEYS = new Set(["model", "effort"]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function rejectUnknownKeys(
  value: Record<string, unknown>,
  allowed: Set<string>,
): void {
  const unknown = Object.keys(value).find((key) => !allowed.has(key));
  if (unknown) throw new Error(`unknown coding-agent preference: ${unknown}`);
}

function optionalString(
  value: Record<string, unknown>,
  key: string,
  scope: string,
): string {
  const selected = value[key];
  if (selected === undefined) return "";
  if (typeof selected !== "string") {
    throw new Error(`${scope}.${key} must be a string`);
  }
  return selected;
}

export function validateCodexSettings(value: CodexSettings): CodexSettings {
  const model = value.model.trim();
  if (!CODEX_MODEL_ID.test(model)) {
    throw new Error("invalid Codex model identifier");
  }
  if (
    !value.modelReasoningEffort ||
    !CODEX_REASONING_EFFORTS.includes(value.modelReasoningEffort)
  ) {
    throw new Error(
      `invalid Codex reasoning effort: ${value.modelReasoningEffort}`,
    );
  }
  if (!value.serviceTier || !CODEX_SERVICE_TIERS.includes(value.serviceTier)) {
    throw new Error(`invalid Codex service tier: ${value.serviceTier}`);
  }
  return { ...value, model };
}

export function validateClaudeSettings(value: ClaudeSettings): ClaudeSettings {
  const model = value.model.trim();
  if (!CLAUDE_MODEL_ID.test(model)) {
    throw new Error("invalid Claude model identifier");
  }
  if (!value.effort || !CLAUDE_EFFORTS.includes(value.effort)) {
    throw new Error(`invalid Claude effort: ${value.effort}`);
  }
  return { ...value, model };
}

export function parseCodingAgentSettings(raw: string): CodingAgentSettings {
  const data: unknown = JSON.parse(raw);
  if (!isRecord(data)) {
    throw new Error("coding-agent preferences must be an object");
  }
  rejectUnknownKeys(data, TOP_LEVEL_KEYS);
  for (const key of ["updated_at", "updated_by"]) {
    if (data[key] !== undefined && typeof data[key] !== "string") {
      throw new Error(`${key} must be a string`);
    }
  }

  let codexSettings = { ...UNSET_CODEX_SETTINGS };
  const codex = data.codex;
  if (codex !== undefined) {
    if (!isRecord(codex)) {
      throw new Error("codex preferences must be an object");
    }
    rejectUnknownKeys(codex, CODEX_KEYS);
    // Older next-signal versions wrote `{ codex: {} }` for inherited values.
    // Treat that exact legacy shape as unconfigured, but reject partial fields.
    if (Object.keys(codex).length > 0) {
      codexSettings = validateCodexSettings({
        model: optionalString(codex, "model", "codex"),
        modelReasoningEffort: optionalString(
          codex,
          "model_reasoning_effort",
          "codex",
        ) as CodexReasoningEffort | "",
        serviceTier: optionalString(codex, "service_tier", "codex") as
          | CodexServiceTier
          | "",
      });
    }
  }
  let claudeSettings = { ...UNSET_CLAUDE_SETTINGS };
  const claude = data.claude;
  if (claude !== undefined) {
    if (!isRecord(claude)) {
      throw new Error("claude preferences must be an object");
    }
    rejectUnknownKeys(claude, CLAUDE_KEYS);
    if (Object.keys(claude).length > 0) {
      claudeSettings = validateClaudeSettings({
        model: optionalString(claude, "model", "claude"),
        effort: optionalString(claude, "effort", "claude") as
          | ClaudeEffort
          | "",
      });
    }
  }

  return {
    codex: codexSettings,
    claude: claudeSettings,
  };
}

export function serializeCodingAgentSettings(
  value: CodingAgentSettings,
): string {
  const hasCodexSelection = Boolean(
    value.codex.model ||
    value.codex.modelReasoningEffort ||
    value.codex.serviceTier,
  );
  const codex = hasCodexSelection
    ? validateCodexSettings(value.codex)
    : undefined;
  const hasClaudeSelection = Boolean(value.claude.model || value.claude.effort);
  const claude = hasClaudeSelection
    ? validateClaudeSettings(value.claude)
    : undefined;
  return JSON.stringify({
    ...(codex
      ? {
          codex: {
            model: codex.model,
            model_reasoning_effort: codex.modelReasoningEffort,
            service_tier: codex.serviceTier,
          },
        }
      : {}),
    ...(claude ? { claude } : {}),
    updated_at: new Date().toISOString(),
    updated_by: "dashboard",
  });
}
