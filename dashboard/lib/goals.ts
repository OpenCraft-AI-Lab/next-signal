import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import path from "node:path";
import YAML from "yaml";

import { REPO_ROOT } from "@/lib/paths";

export const GOALS_PATH = path.join(REPO_ROOT, "configs", "info_radar", "goals.yaml");
export const GOALS_EXAMPLE_PATH = path.join(
  REPO_ROOT,
  "configs",
  "info_radar",
  "goals.example.yaml",
);

/** Which goals file a view/action targets. Only info-radar filtering exists here. */
export type GoalsKind = "radar";

export function goalsPathFor(_kind: GoalsKind): string {
  return GOALS_PATH;
}

export function goalsExampleFor(_kind: GoalsKind): string {
  return GOALS_EXAMPLE_PATH;
}

export type GoalConfig = {
  name: string;
  description: string;
  topics: string[];
  keywords: string[];
};

export type GoalsReadResult =
  | { ok: true; path: string; goals: GoalConfig[] }
  | { ok: false; path: string; missing: boolean; message: string };

const ALLOWED_TOP_KEYS = new Set(["goals"]);
const ALLOWED_GOAL_KEYS = new Set(["name", "description", "topics", "keywords"]);

function asObject(value: unknown, label: string): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${label}: must be a mapping`);
  }
  return value as Record<string, unknown>;
}

function validateStringList(value: unknown, label: string): string[] {
  if (!Array.isArray(value) || !value.every((item) => typeof item === "string")) {
    throw new Error(`${label}: must be a list of strings`);
  }
  return [...value];
}

export function validateGoals(value: unknown, source = "goals"): GoalConfig[] {
  if (!Array.isArray(value) || value.length === 0) {
    throw new Error(`${source}: \`goals:\` must be a non-empty list`);
  }

  const seen = new Set<string>();
  return value.map((entry, index) => {
    const raw = asObject(entry, `${source}[${index}]`);
    const extra = Object.keys(raw).filter((key) => !ALLOWED_GOAL_KEYS.has(key));
    if (extra.length > 0) {
      throw new Error(`${source}[${index}]: unknown keys ${extra.sort().join(", ")}`);
    }

    const name = raw.name;
    if (typeof name !== "string" || name.length === 0) {
      throw new Error(`${source}[${index}]: \`name\` is required`);
    }
    if (seen.has(name)) {
      throw new Error(`${source}: duplicate goal name ${name}`);
    }
    seen.add(name);

    const description = raw.description;
    if (typeof description !== "string" || description.length === 0) {
      throw new Error(`${source}[${name}]: \`description\` is required`);
    }

    const topics = validateStringList(raw.topics ?? [], `${source}[${name}].topics`);
    const keywords = validateStringList(raw.keywords ?? [], `${source}[${name}].keywords`);

    return { name, description, topics, keywords };
  });
}

export function parseGoalsYaml(raw: string, source = "goals.yaml"): GoalConfig[] {
  const parsed = (YAML.parse(raw) ?? {}) as unknown;
  const top = asObject(parsed, source);
  const extra = Object.keys(top).filter((key) => !ALLOWED_TOP_KEYS.has(key));
  if (extra.length > 0) {
    throw new Error(`${source}: unknown top-level keys ${extra.sort().join(", ")}`);
  }
  return validateGoals(top.goals, source);
}

export async function readGoals(goalsPath = GOALS_PATH): Promise<GoalsReadResult> {
  try {
    const raw = await readFile(goalsPath, "utf8");
    return { ok: true, path: goalsPath, goals: parseGoalsYaml(raw, goalsPath) };
  } catch (error) {
    if (error && typeof error === "object" && "code" in error && error.code === "ENOENT") {
      return {
        ok: false,
        path: goalsPath,
        missing: true,
        message: `goals.yaml missing at ${goalsPath}; copy goals.example.yaml to goals.yaml`,
      };
    }
    return {
      ok: false,
      path: goalsPath,
      missing: false,
      message: error instanceof Error ? error.message : String(error),
    };
  }
}

export function renderGoalsYaml(goals: unknown): string {
  const validGoals = validateGoals(goals);
  return YAML.stringify({ goals: validGoals }, { lineWidth: 100 });
}

export async function writeGoalsAtomic(
  goals: unknown,
  goalsPath = GOALS_PATH,
): Promise<GoalConfig[]> {
  const validGoals = validateGoals(goals);
  const tmp = `${goalsPath}.${process.pid}.${Date.now()}.tmp`;
  await mkdir(path.dirname(goalsPath), { recursive: true });
  await writeFile(tmp, renderGoalsYaml(validGoals), "utf8");
  await rename(tmp, goalsPath);
  return validGoals;
}
