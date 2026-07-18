"use client";

import { Target } from "lucide-react";

import { GoalsEditor } from "@/components/goals/goals-editor";
import { useI18n } from "@/components/i18n-provider";
import type { GoalConfig } from "@/lib/goals";

export type GoalsTabData = {
  ok: boolean;
  missing: boolean;
  message: string;
  goals: GoalConfig[];
  examplePath: string;
};

export function GoalsTabs({ radar }: { radar: GoalsTabData }) {
  const { t } = useI18n();

  return (
    <>
      <p className="page-sub" style={{ marginBottom: 18 }}>
        {t.goals.subtitle(radar.goals.length)}
      </p>

      {!radar.ok && (
        <div
          className="filter-empty"
          style={{ marginBottom: 14, textAlign: "left" }}
        >
          <div
            className="row gap-8"
            style={{ alignItems: "center", marginBottom: 8 }}
          >
            <Target size={16} className="muted-2" />
            <strong style={{ color: "var(--text)" }}>
              {radar.missing ? t.goals.missing : t.goals.attention}
            </strong>
          </div>
          <p style={{ margin: 0, lineHeight: 1.6 }}>
            {t.goals.help(radar.message, radar.examplePath)}
          </p>
        </div>
      )}

      <GoalsEditor kind="radar" initialGoals={radar.goals} />
    </>
  );
}
