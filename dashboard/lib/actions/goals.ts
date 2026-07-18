"use server";

import { revalidatePath } from "next/cache";

import {
  type GoalConfig,
  type GoalsKind,
  goalsPathFor,
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

async function currentGoals(kind: GoalsKind): Promise<GoalConfig[]> {
  const result = await readGoals(goalsPathFor(kind));
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
    await writeGoalsAtomic(next, goalsPathFor(kind));
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
    const result = await readGoals(goalsPathFor(kind));
    const goals = result.ok ? result.goals : [];
    if (!result.ok && !result.missing) throw new Error(result.message);
    if (goals.some((item) => item.name === goal.name)) {
      return { ok: false, message: t.goals.messages.exists(goal.name) };
    }
    await writeGoalsAtomic([...goals, goal], goalsPathFor(kind));
    revalidatePath("/goals");
    return { ok: true, message: t.goals.messages.added(goal.name) };
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
    await writeGoalsAtomic(next, goalsPathFor(kind));
    revalidatePath("/goals");
    return { ok: true, message: t.goals.messages.deleted(name) };
  } catch (error) {
    return { ok: false, message: errorMessage(error) };
  }
}
