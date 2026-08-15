"use client";

import {
  Check,
  ChevronDown,
  ChevronRight,
  FileText,
  Plus,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";

import { useI18n } from "@/components/i18n-provider";
import { Button } from "@/components/ui/button";
import {
  addGoal,
  deleteGoal,
  saveGoal,
  seedGoalsFromExample,
} from "@/lib/actions/goals";
import type { GoalConfig, GoalsKind } from "@/lib/goals";

type DraftGoal = {
  name: string;
  description: string;
  topics: string[];
  keywords: string[];
};

const EMPTY_DRAFT: DraftGoal = {
  name: "",
  description: "",
  topics: [],
  keywords: [],
};

function normalize(goal: DraftGoal): GoalConfig {
  return {
    name: goal.name.trim(),
    description: goal.description.trim(),
    topics: goal.topics.map((item) => item.trim()).filter(Boolean),
    keywords: goal.keywords.map((item) => item.trim()).filter(Boolean),
  };
}

function ChipList({
  items,
  onChange,
  tag,
}: {
  items: string[];
  onChange: (items: string[]) => void;
  tag?: boolean;
}) {
  const { t } = useI18n();
  const [value, setValue] = useState("");
  const add = () => {
    const next = value.trim();
    if (!next || items.includes(next)) return;
    onChange([...items, next]);
    setValue("");
  };
  return (
    <div className="row gap-6 wrap" style={{ alignItems: "center" }}>
      {items.map((item) => (
        <span key={item} className={`chip${tag ? " tag" : ""}`}>
          {item}
          <button
            type="button"
            className="chip-x"
            onClick={() =>
              onChange(items.filter((current) => current !== item))
            }
            title={t.goals.removeTitle(item)}
            style={{ background: "none", border: 0, padding: 0 }}
          >
            <X size={11} />
          </button>
        </span>
      ))}
      <input
        className="input mono"
        style={{ width: 130, height: 26, fontSize: 11 }}
        placeholder={t.goals.fields.addPlaceholder}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            add();
          }
        }}
        onBlur={add}
      />
    </div>
  );
}

function GoalForm({
  goal,
  nameReadOnly,
  disabled,
  onChange,
}: {
  goal: DraftGoal;
  nameReadOnly: boolean;
  disabled: boolean;
  onChange: (goal: DraftGoal) => void;
}) {
  const { t } = useI18n();
  const set = <K extends keyof DraftGoal>(key: K, value: DraftGoal[K]) =>
    onChange({ ...goal, [key]: value });
  return (
    <div className="formgrid">
      <label className="flabel">
        {t.goals.fields.name}{" "}
        <span className="mono muted-2">
          {nameReadOnly
            ? t.goals.fields.nameHintReadOnly
            : t.goals.fields.nameHintNew}
        </span>
      </label>
      <input
        className="input mono"
        value={goal.name}
        disabled={disabled || nameReadOnly}
        placeholder="my-goal"
        onChange={(event) => set("name", event.target.value)}
      />

      <label className="flabel">{t.goals.fields.description}</label>
      <textarea
        className="input"
        rows={2}
        value={goal.description}
        disabled={disabled}
        onChange={(event) => set("description", event.target.value)}
      />

      <label className="flabel">{t.goals.fields.topics}</label>
      <ChipList
        items={goal.topics}
        tag
        onChange={(topics) => set("topics", topics)}
      />

      <label className="flabel">{t.goals.fields.keywords}</label>
      <ChipList
        items={goal.keywords}
        onChange={(keywords) => set("keywords", keywords)}
      />
    </div>
  );
}

function GoalCard({
  kind,
  goal,
  onSaved,
}: {
  kind: GoalsKind;
  goal: GoalConfig;
  onSaved: (next?: GoalConfig, deletedName?: string) => void;
}) {
  const { locale, t } = useI18n();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<DraftGoal>(goal);
  const [pending, startTransition] = useTransition();

  const reset = () => {
    setDraft(goal);
    setOpen(false);
  };

  const save = () => {
    const next = normalize(draft);
    startTransition(async () => {
      const result = await saveGoal(kind, next, locale);
      if (result.ok) {
        toast.success(result.message);
        onSaved(next);
        setOpen(false);
        router.refresh();
      } else {
        toast.error(result.message);
      }
    });
  };

  const remove = () => {
    if (!window.confirm(t.goals.deleteConfirm(goal.name))) return;
    startTransition(async () => {
      const result = await deleteGoal(kind, goal.name, locale);
      if (result.ok) {
        toast.success(result.message);
        onSaved(undefined, goal.name);
        router.refresh();
      } else {
        toast.error(result.message);
      }
    });
  };

  return (
    <div className="card" style={{ overflow: "hidden" }}>
      <div className="goalhead">
        <button
          className="goalexp"
          type="button"
          onClick={() => setOpen(!open)}
        >
          {open ? (
            <ChevronDown size={14} className="muted-2" />
          ) : (
            <ChevronRight size={14} className="muted-2" />
          )}
          <span className="goalname mono">{goal.name}</span>
        </button>
        <span className="elip muted" style={{ flex: 1, fontSize: 13 }}>
          {goal.description}
        </span>
        <span className="badge" style={{ marginLeft: 2 }}>
          {t.goals.topicKeywordCount(goal.topics.length, goal.keywords.length)}
        </span>
        <div className="row gap-4" style={{ marginLeft: 6 }}>
          <Button
            variant="icon"
            size="sm"
            className="ghost"
            type="button"
            onClick={() => setOpen(!open)}
            title={t.goals.edit}
          >
            <ChevronRight size={13} />
          </Button>
          <Button
            variant="icon"
            size="sm"
            className="danger"
            type="button"
            onClick={remove}
            disabled={pending}
            title={t.goals.delete}
          >
            <Trash2 size={13} />
          </Button>
        </div>
      </div>
      <div className={`collapsible ${open ? "open" : ""}`}>
        <div className="inner">
          <div className="goalbody">
            <GoalForm
              goal={draft}
              nameReadOnly
              disabled={pending}
              onChange={setDraft}
            />
            <div
              className="row gap-8"
              style={{ marginTop: 16, justifyContent: "flex-end" }}
            >
              <Button
                variant="ghost"
                type="button"
                onClick={reset}
                disabled={pending}
              >
                {t.goals.cancel}
              </Button>
              <Button
                variant="primary"
                type="button"
                onClick={save}
                disabled={pending}
              >
                <Check size={14} /> {t.goals.saveChanges}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * The shipped example goals, read-only.
 *
 * Available in every state, not just when the list is empty: wanting to consult
 * the examples while your own goals are configured should not require deleting
 * them first. Merging them in is deliberately not offered — example names can
 * collide with configured names, and duplicates are rejected.
 */
function ExampleGoals({
  goals,
  path,
}: {
  goals: GoalConfig[];
  path: string;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  if (goals.length === 0) return null;

  return (
    <div className="card" style={{ overflow: "hidden", marginTop: 4 }}>
      <div className="goalhead">
        <button
          className="goalexp"
          type="button"
          onClick={() => setOpen(!open)}
        >
          {open ? (
            <ChevronDown size={14} className="muted-2" />
          ) : (
            <ChevronRight size={14} className="muted-2" />
          )}
          <span className="row gap-6" style={{ alignItems: "center" }}>
            <FileText size={13} className="muted-2" />
            {t.goals.viewExamples}
          </span>
        </button>
        <span className="elip muted" style={{ flex: 1, fontSize: 13 }}>
          {t.goals.viewExamplesHint}
        </span>
        <span className="badge mono" style={{ marginLeft: 2 }}>
          {path}
        </span>
      </div>
      <div className={`collapsible ${open ? "open" : ""}`}>
        <div className="inner">
          <div className="goalbody col gap-8">
            {goals.map((goal) => (
              <div key={goal.name}>
                <div className="row gap-8" style={{ alignItems: "center" }}>
                  <span className="goalname mono">{goal.name}</span>
                  <span className="badge">
                    {t.goals.topicKeywordCount(
                      goal.topics.length,
                      goal.keywords.length,
                    )}
                  </span>
                </div>
                <p className="muted" style={{ margin: "4px 0 6px" }}>
                  {goal.description}
                </p>
                <div className="row gap-6 wrap">
                  {goal.topics.map((item) => (
                    <span key={item} className="chip tag">
                      {item}
                    </span>
                  ))}
                  {goal.keywords.map((item) => (
                    <span key={item} className="chip">
                      {item}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export function GoalsEditor({
  kind,
  initialGoals,
  exampleGoals,
  examplePath,
}: {
  kind: GoalsKind;
  initialGoals: GoalConfig[];
  exampleGoals: GoalConfig[];
  examplePath: string;
}) {
  const { locale, t } = useI18n();
  const router = useRouter();
  const [goals, setGoals] = useState(initialGoals);
  const [draft, setDraft] = useState<DraftGoal>(EMPTY_DRAFT);
  // Starts closed even with no goals: an empty list is now a real, savable
  // state, so the page explains it and offers a choice rather than assuming the
  // operator wants to type a goal right now.
  const [adding, setAdding] = useState(false);
  const [pending, startTransition] = useTransition();

  const seed = () => {
    startTransition(async () => {
      const result = await seedGoalsFromExample(kind, locale);
      if (result.ok) {
        toast.success(result.message);
        setGoals(exampleGoals);
        router.refresh();
      } else {
        toast.error(result.message);
      }
    });
  };

  const onSaved = (next?: GoalConfig, deletedName?: string) => {
    if (deletedName) {
      setGoals((current) =>
        current.filter((goal) => goal.name !== deletedName),
      );
    } else if (next) {
      setGoals((current) =>
        current.map((goal) => (goal.name === next.name ? next : goal)),
      );
    }
  };

  const add = () => {
    const next = normalize(draft);
    startTransition(async () => {
      const result = await addGoal(kind, next, locale);
      if (result.ok) {
        toast.success(result.message);
        setGoals((current) => [...current, next]);
        setDraft(EMPTY_DRAFT);
        setAdding(false);
        router.refresh();
      } else {
        toast.error(result.message);
      }
    });
  };

  return (
    <div className="col gap-8">
      {adding && (
        <div className="card" style={{ overflow: "hidden" }}>
          <div className="goalbody" style={{ borderTop: 0 }}>
            <GoalForm
              goal={draft}
              nameReadOnly={false}
              disabled={pending}
              onChange={setDraft}
            />
            <div
              className="row gap-8"
              style={{ marginTop: 16, justifyContent: "flex-end" }}
            >
              <Button
                variant="ghost"
                type="button"
                onClick={() => {
                  setDraft(EMPTY_DRAFT);
                  setAdding(false);
                }}
                disabled={pending}
              >
                {t.goals.cancel}
              </Button>
              <Button
                variant="primary"
                type="button"
                onClick={add}
                disabled={pending}
              >
                <Check size={14} /> {t.goals.saveGoal}
              </Button>
            </div>
          </div>
        </div>
      )}
      {!adding && goals.length === 0 && (
        <div className="filter-empty" style={{ textAlign: "left" }}>
          <strong style={{ color: "var(--text)" }}>{t.goals.emptyTitle}</strong>
          <p style={{ margin: "6px 0 12px", lineHeight: 1.6 }}>
            {t.goals.emptyBody}
          </p>
          <div className="row gap-8 wrap">
            <Button
              variant="primary"
              type="button"
              onClick={() => setAdding(true)}
              disabled={pending}
            >
              <Plus size={14} /> {t.goals.addGoal}
            </Button>
            {exampleGoals.length > 0 && (
              <Button
                variant="ghost"
                type="button"
                onClick={seed}
                disabled={pending}
              >
                <Sparkles size={14} /> {t.goals.startFromExample}
              </Button>
            )}
          </div>
        </div>
      )}
      {!adding && goals.length > 0 && (
        <Button
          variant="primary"
          type="button"
          onClick={() => setAdding(true)}
          style={{ alignSelf: "flex-start", marginBottom: 4 }}
        >
          <Plus size={14} /> {t.goals.addGoal}
        </Button>
      )}
      {goals.map((goal) => (
        <GoalCard key={goal.name} kind={kind} goal={goal} onSaved={onSaved} />
      ))}
      <ExampleGoals goals={exampleGoals} path={examplePath} />
    </div>
  );
}
