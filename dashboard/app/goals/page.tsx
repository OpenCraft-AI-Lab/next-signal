import { GoalsTabs, type GoalsTabData } from "@/components/goals/goals-tabs";
import {
  goalsExampleFor,
  goalsPathFor,
  readExampleGoals,
  readGoals,
} from "@/lib/goals";
import { getDictionary } from "@/lib/i18n/dictionaries";
import { getLocale } from "@/lib/i18n/server";

export const dynamic = "force-dynamic";

/**
 * Reads only. Provisioning the runtime goals file belongs to container bootstrap
 * and to the explicit "Start from example" control — never to a page render.
 *
 * The example goals are read here so the reference disclosure can be shown in
 * every state without a round trip; a failure to read them is not fatal, since
 * they are reference material rather than the page's subject.
 */
async function readRadarGoals(): Promise<GoalsTabData> {
  const [result, example] = await Promise.all([
    readGoals(goalsPathFor()),
    readExampleGoals(),
  ]);
  const examplePath = goalsExampleFor();
  const exampleGoals = example.ok ? example.goals : [];
  if (result.ok) {
    return {
      ok: true,
      missing: false,
      message: "",
      goals: result.goals,
      examplePath,
      exampleGoals,
    };
  }
  return {
    ok: false,
    missing: result.missing,
    message: result.message,
    goals: [],
    examplePath,
    exampleGoals,
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
