"use server";

import { revalidatePath } from "next/cache";

import {
  type GoalConfig,
  type GoalsKind,
  goalsPathFor,
  readExampleGoals,
  readGoals,
  writeGoalsAtomic,
} from "@/lib/goals";
import {
  getDictionary,
  normalizeLocale,
  type Locale,
} from "@/lib/i18n/dictionaries";

type ActionResult =
  | { ok: true; message: string }
  | { ok: false; message: string };

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

async function currentGoals(_kind: GoalsKind): Promise<GoalConfig[]> {
  const result = await readGoals(goalsPathFor());
  if (!result.ok) throw new Error(result.message);
  return result.goals;
}

export async function saveGoal(
  kind: GoalsKind,
  goal: GoalConfig,
  localeValue?: Locale,
): Promise<ActionResult> {
  const t = getDictionary(normalizeLocale(localeValue));
  try {
    const goals = await currentGoals(kind);
    const index = goals.findIndex((item) => item.name === goal.name);
    if (index === -1)
      return { ok: false, message: t.goals.messages.notFound(goal.name) };
    const next = goals.map((item) => (item.name === goal.name ? goal : item));
    await writeGoalsAtomic(next, goalsPathFor());
    revalidatePath("/goals");
    return { ok: true, message: t.goals.messages.saved(goal.name) };
  } catch (error) {
    return { ok: false, message: errorMessage(error) };
  }
}

export async function addGoal(
  kind: GoalsKind,
  goal: GoalConfig,
  localeValue?: Locale,
): Promise<ActionResult> {
  const t = getDictionary(normalizeLocale(localeValue));
  try {
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(goal.name)) {
      return { ok: false, message: t.goals.messages.invalidName };
    }
    const result = await readGoals(goalsPathFor());
    const goals = result.ok ? result.goals : [];
    if (!result.ok && !result.missing) throw new Error(result.message);
    if (goals.some((item) => item.name === goal.name)) {
      return { ok: false, message: t.goals.messages.exists(goal.name) };
    }
    await writeGoalsAtomic([...goals, goal], goalsPathFor());
    revalidatePath("/goals");
    return { ok: true, message: t.goals.messages.added(goal.name) };
  } catch (error) {
    return { ok: false, message: errorMessage(error) };
  }
}

/**
 * Copy the shipped example goals into the runtime goals file.
 *
 * The only write the page performs that is not an edit to a specific goal, and
 * it is always driven by an explicit click — rendering `/goals` never writes.
 * Refuses to run when goals already exist, so it can restore a cleared list but
 * can never overwrite configured goals: merging is not offered because example
 * names can collide with the operator's and duplicates are rejected.
 */
export async function seedGoalsFromExample(
  _kind: GoalsKind,
  localeValue?: Locale,
): Promise<ActionResult> {
  const t = getDictionary(normalizeLocale(localeValue));
  try {
    const existing = await readGoals(goalsPathFor());
    if (existing.ok && existing.goals.length > 0) {
      return { ok: false, message: t.goals.messages.seedRefused };
    }
    if (!existing.ok && !existing.missing) throw new Error(existing.message);

    const example = await readExampleGoals();
    if (!example.ok) throw new Error(example.message);

    await writeGoalsAtomic(example.goals, goalsPathFor());
    revalidatePath("/goals");
    return { ok: true, message: t.goals.messages.seeded(example.goals.length) };
  } catch (error) {
    return { ok: false, message: errorMessage(error) };
  }
}

export async function deleteGoal(
  kind: GoalsKind,
  name: string,
  localeValue?: Locale,
): Promise<ActionResult> {
  const t = getDictionary(normalizeLocale(localeValue));
  try {
    const goals = await currentGoals(kind);
    const next = goals.filter((goal) => goal.name !== name);
    if (next.length === goals.length)
      return { ok: false, message: t.goals.messages.notFound(name) };
    await writeGoalsAtomic(next, goalsPathFor());
    revalidatePath("/goals");
    return { ok: true, message: t.goals.messages.deleted(name) };
  } catch (error) {
    return { ok: false, message: errorMessage(error) };
  }
}
