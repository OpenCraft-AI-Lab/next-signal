import { GoalsTabs, type GoalsTabData } from "@/components/goals/goals-tabs";
import { goalsExampleFor, goalsPathFor, readGoals } from "@/lib/goals";
import { getDictionary } from "@/lib/i18n/dictionaries";
import { getLocale } from "@/lib/i18n/server";

export const dynamic = "force-dynamic";

async function readRadarGoals(): Promise<GoalsTabData> {
  const result = await readGoals(goalsPathFor());
  const examplePath = goalsExampleFor();
  if (result.ok) {
    return { ok: true, missing: false, message: "", goals: result.goals, examplePath };
  }
  return {
    ok: false,
    missing: result.missing,
    message: result.message,
    goals: [],
    examplePath,
  };
}

export default async function GoalsPage() {
  const locale = await getLocale();
  const t = getDictionary(locale);
  const radar = await readRadarGoals();

  return (
    <div className="page page-enter">
      <div className="shell" style={{ maxWidth: 980 }}>
        <h1 className="page-title" style={{ marginBottom: 14 }}>
          {t.goals.title}
        </h1>
        <GoalsTabs radar={radar} />
      </div>
    </div>
  );
}
