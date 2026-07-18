"use client";

import { Check, ExternalLink, Plus, Sparkles, Trash2 } from "lucide-react";
import { useState } from "react";

import { Alpaca } from "@/components/brand/alpaca";
import { RadarAlpaca } from "@/components/brand/radar-alpaca";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Chip } from "@/components/ui/chip";
import { useI18n } from "@/components/i18n-provider";
import { Input, SearchWrap, Textarea } from "@/components/ui/input";
import { Segmented, SegmentedItem } from "@/components/ui/segmented";
import { scoreHue, scoreLOff } from "@/lib/score";

type Tab = "tokens" | "components" | "states" | "brand";

export default function DesignPage() {
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>("tokens");

  return (
    <div className="page page-enter">
      <div className="shell">
        <div
          className="row"
          style={{
            justifyContent: "space-between",
            alignItems: "flex-end",
            marginBottom: 18,
          }}
        >
          <div>
            <h1 className="page-title">{t.design.title}</h1>
            <p className="page-sub">
              {t.design.subtitle}
            </p>
          </div>
          <Segmented>
            {(
              [
                ["tokens", t.design.tabs.tokens],
                ["components", t.design.tabs.components],
                ["states", t.design.tabs.states],
                ["brand", t.design.tabs.brand],
              ] as [Tab, string][]
            ).map(([id, label]) => (
              <SegmentedItem key={id} active={tab === id} onClick={() => setTab(id)}>
                {label}
              </SegmentedItem>
            ))}
          </Segmented>
        </div>

        {tab === "tokens" && <Tokens />}
        {tab === "components" && <Components />}
        {tab === "states" && <States />}
        {tab === "brand" && <Brand />}
      </div>
    </div>
  );
}

/* ---------- helpers ---------- */

function Spec({ children }: { children: React.ReactNode }) {
  return (
    <span className="mono" style={{ fontSize: 10.5, color: "var(--text-4)" }}>
      {children}
    </span>
  );
}

function Swatch({ varName, label }: { varName: string; label: string }) {
  return (
    <div className="col" style={{ gap: 6 }}>
      <div
        style={{
          height: 52,
          borderRadius: 8,
          background: `var(${varName})`,
          boxShadow: "var(--ring)",
        }}
      />
      <div className="col" style={{ gap: 1 }}>
        <span style={{ fontSize: 12, fontWeight: 500 }}>{label}</span>
        <Spec>{varName}</Spec>
      </div>
    </div>
  );
}

function ScoreChip({
  value,
  size = "md",
  denom = false,
}: {
  value: number;
  size?: "sm" | "md" | "lg";
  denom?: boolean;
}) {
  const hue = scoreHue(value);
  const lOff = scoreLOff(value);
  const color = `hsl(${hue} var(--score-s) calc(var(--score-l) - ${lOff}%))`;
  const tint = `hsl(${hue} var(--score-s) calc(var(--score-l) - ${lOff}%) / var(--score-tint-a))`;
  const dim = size === "lg" ? 58 : size === "sm" ? 38 : 48;
  const fs = size === "lg" ? 26 : size === "sm" ? 16 : 22;
  return (
    <div
      className="score"
      style={{
        width: dim,
        height: dim,
        minWidth: dim,
        background: tint,
        color,
        boxShadow: `inset 0 0 0 1px color-mix(in srgb, ${color} 26%, transparent)`,
      }}
    >
      <span className="n" style={{ fontSize: fs }}>
        {Math.round(value)}
      </span>
      {denom && <span className="d">/ 100</span>}
    </div>
  );
}

/* ---------- tabs ---------- */

function Tokens() {
  return (
    <div className="col gap-16">
      <Card pad>
        <div className="sec-head">
          <h2 className="sec-title">Surfaces &amp; text</h2>
          <span className="sec-sub">achromatic canvas · micro-warm</span>
        </div>
        <div className="dsgrid">
          <Swatch varName="--bg" label="bg" />
          <Swatch varName="--bg-subtle" label="bg-subtle" />
          <Swatch varName="--bg-inset" label="bg-inset" />
          <Swatch varName="--elevated" label="elevated" />
          <Swatch varName="--text" label="text" />
          <Swatch varName="--text-2" label="text-2" />
          <Swatch varName="--text-3" label="text-3" />
          <Swatch varName="--text-4" label="text-4" />
        </div>
      </Card>

      <div className="row gap-16" style={{ alignItems: "stretch" }}>
        <Card pad style={{ flex: 1 }}>
          <div className="sec-head">
            <h2 className="sec-title">Accent</h2>
            <span className="sec-sub">functional only</span>
          </div>
          <div className="dsgrid">
            <Swatch varName="--accent" label="accent" />
            <Swatch varName="--accent-hover" label="hover" />
            <Swatch varName="--accent-tint" label="tint" />
            <Swatch varName="--accent-text" label="text" />
          </div>
        </Card>
        <Card pad style={{ flex: 1.6 }}>
          <div className="sec-head">
            <h2 className="sec-title">Semantic</h2>
            <span className="sec-sub">verdict / status</span>
          </div>
          <div className="dsgrid">
            <Swatch varName="--green" label="keep · novel" />
            <Swatch varName="--red" label="drop" />
            <Swatch varName="--amber" label="fallback" />
            <Swatch varName="--purple" label="duplicate" />
          </div>
        </Card>
      </div>

      <Card pad>
        <div className="sec-head">
          <h2 className="sec-title">Score ramp</h2>
          <span className="sec-sub">0–100 · continuous gradient</span>
        </div>
        <div className="col" style={{ gap: 7, marginBottom: 14 }}>
          <div
            style={{
              height: 14,
              borderRadius: 3,
              background: `linear-gradient(90deg, ${[0, 20, 40, 60, 80, 100]
                .map(
                  (s) =>
                    `hsl(${scoreHue(s)} var(--score-s) calc(var(--score-l) - ${scoreLOff(
                      s,
                    )}%)) ${s}%`,
                )
                .join(", ")})`,
            }}
          />
          <div className="row" style={{ justifyContent: "space-between" }}>
            {[
              { v: 10, label: "low" },
              { v: 50, label: "medium" },
              { v: 90, label: "high" },
            ].map((m) => (
              <span
                key={m.label}
                className="mono"
                style={{
                  fontSize: 11,
                  color: `hsl(${scoreHue(m.v)} var(--score-s) calc(var(--score-l) - ${scoreLOff(
                    m.v,
                  )}%))`,
                  fontWeight: 500,
                }}
              >
                {m.label}
              </span>
            ))}
          </div>
        </div>
        <hr className="hr" style={{ margin: "4px 0 14px" }} />
        <div className="row gap-12 wrap">
          {[18, 42, 55, 63, 71, 78, 84, 91, 96, 100].map((s) => (
            <ScoreChip key={s} value={s} size="sm" />
          ))}
        </div>
      </Card>

      <Card pad>
        <div className="sec-head">
          <h2 className="sec-title">Typography</h2>
          <span className="sec-sub">Geist Sans · Geist Mono</span>
        </div>
        <div className="col gap-12">
          <div
            className="row"
            style={{
              justifyContent: "space-between",
              alignItems: "baseline",
              borderBottom: "1px solid var(--line)",
              paddingBottom: 10,
            }}
          >
            <span style={{ fontSize: 26, fontWeight: 600, letterSpacing: "-0.045em" }}>
              Page title
            </span>
            <Spec>26 / 600 / -0.045em sans</Spec>
          </div>
          <div
            className="row"
            style={{
              justifyContent: "space-between",
              alignItems: "baseline",
              borderBottom: "1px solid var(--line)",
              paddingBottom: 10,
            }}
          >
            <span style={{ fontSize: 15, fontWeight: 600, letterSpacing: "-0.02em" }}>
              Section title
            </span>
            <Spec>15 / 600 / -0.02em sans</Spec>
          </div>
          <div
            className="row"
            style={{
              justifyContent: "space-between",
              alignItems: "baseline",
              borderBottom: "1px solid var(--line)",
              paddingBottom: 10,
            }}
          >
            <span style={{ fontSize: 14 }}>Body — standard reading text for impact notes</span>
            <Spec>14 / 400 sans</Spec>
          </div>
          <div
            className="row"
            style={{
              justifyContent: "space-between",
              alignItems: "baseline",
              borderBottom: "1px solid var(--line)",
              paddingBottom: 10,
            }}
          >
            <span className="mono" style={{ fontSize: 12 }}>
              rad_8f21 · score 92 · #agents
            </span>
            <Spec>12 / 500 mono · ids/scores/tags</Spec>
          </div>
          <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline" }}>
            <span className="eyebrow">EYEBROW LABEL</span>
            <Spec>11 / 500 mono uppercase</Spec>
          </div>
        </div>
      </Card>

      <div className="row gap-16" style={{ alignItems: "stretch" }}>
        <Card pad style={{ flex: 1 }}>
          <div className="sec-head">
            <h2 className="sec-title">Radius</h2>
          </div>
          <div className="row gap-12 wrap" style={{ alignItems: "flex-end" }}>
            {[["2", "r-1"], ["4", "r-2"], ["6", "r-3"], ["8", "r-4"], ["12", "r-5"]].map(
              ([px, t]) => (
                <div key={t} className="col" style={{ alignItems: "center", gap: 6 }}>
                  <div
                    style={{
                      width: 48,
                      height: 40,
                      background: "var(--accent-tint)",
                      borderRadius: `${px}px ${px}px 0 0`,
                      boxShadow: "var(--ring)",
                    }}
                  />
                  <Spec>{px}px</Spec>
                </div>
              ),
            )}
            <div className="col" style={{ alignItems: "center", gap: 6 }}>
              <div
                style={{
                  width: 48,
                  height: 40,
                  background: "var(--accent-tint)",
                  borderRadius: 9999,
                  boxShadow: "var(--ring)",
                }}
              />
              <Spec>pill</Spec>
            </div>
          </div>
        </Card>
        <Card pad style={{ flex: 1.2 }}>
          <div className="sec-head">
            <h2 className="sec-title">Spacing</h2>
            <span className="sec-sub">8px base · 16→32 jump</span>
          </div>
          <div className="row gap-12 wrap" style={{ alignItems: "flex-end" }}>
            {[4, 6, 8, 12, 16, 32].map((s) => (
              <div key={s} className="col" style={{ alignItems: "center", gap: 6 }}>
                <div
                  style={{
                    width: s,
                    height: 28,
                    background: "var(--accent)",
                    borderRadius: 2,
                  }}
                />
                <Spec>{s}</Spec>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card pad>
        <div className="sec-head">
          <h2 className="sec-title">Elevation</h2>
          <span className="sec-sub">shadow-as-border philosophy</span>
        </div>
        <div className="row gap-16 wrap">
          {[
            ["--ring", "ring (border)"],
            ["--shadow-card", "card"],
            ["--shadow-pop", "pop / hover"],
            ["--shadow-menu", "menu / toast"],
          ].map(([v, l]) => (
            <div key={v} className="col" style={{ alignItems: "center", gap: 8 }}>
              <div
                style={{
                  width: 120,
                  height: 56,
                  background: "var(--card)",
                  borderRadius: 8,
                  boxShadow: `var(${v})`,
                }}
              />
              <Spec>{l}</Spec>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function Components() {
  return (
    <div className="col gap-16">
      <Card pad>
        <div className="sec-head">
          <h2 className="sec-title">Buttons</h2>
        </div>
        <div className="row gap-8 wrap">
          <Button variant="primary">
            <Sparkles size={14} /> Primary
          </Button>
          <Button variant="solid">Solid</Button>
          <Button>Default</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="danger">
            <Trash2 size={14} /> Danger
          </Button>
          <Button disabled>Disabled</Button>
          <Button variant="icon">
            <Plus size={14} />
          </Button>
          <Button size="sm">Small</Button>
        </div>
      </Card>

      <Card pad>
        <div className="sec-head">
          <h2 className="sec-title">Badges &amp; chips</h2>
        </div>
        <div className="row gap-8 wrap" style={{ marginBottom: 12 }}>
          <Badge kind="green" dot>
            keep
          </Badge>
          <Badge kind="green" dot>
            novel
          </Badge>
          <Badge kind="purple" dot>
            duplicate
          </Badge>
          <Badge kind="red" dot>
            drop
          </Badge>
          <Badge kind="amber" dot>
            fallback
          </Badge>
          <Badge kind="accent">8 unread</Badge>
          <Badge>full</Badge>
        </div>
        <div className="row gap-6 wrap">
          {["inference", "agents", "mcp", "security"].map((t) => (
            <Chip key={t} tag>
              {t}
            </Chip>
          ))}
          <Chip>Newsletters</Chip>
        </div>
      </Card>

      <div className="row gap-16" style={{ alignItems: "stretch" }}>
        <Card pad style={{ flex: 1 }}>
          <div className="sec-head">
            <h2 className="sec-title">Inputs</h2>
          </div>
          <div className="col gap-12">
            <Input placeholder="Text input" />
            <SearchWrap>
              <Input placeholder="Search…" />
            </SearchWrap>
            <Textarea rows={2} placeholder="Multiline textarea" />
            <Segmented>
              <SegmentedItem active>Bars</SegmentedItem>
              <SegmentedItem>Line</SegmentedItem>
            </Segmented>
          </div>
        </Card>
        <Card pad style={{ flex: 1 }}>
          <div className="sec-head">
            <h2 className="sec-title">Score &amp; meta</h2>
          </div>
          <div className="row gap-12" style={{ alignItems: "center" }}>
            <ScoreChip value={92} size="lg" denom />
            <ScoreChip value={76} />
            <ScoreChip value={54} size="sm" />
            <ScoreChip value={31} size="sm" />
          </div>
        </Card>
      </div>
    </div>
  );
}

function StateRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div
      className="row"
      style={{
        gap: 16,
        alignItems: "center",
        padding: "12px 0",
        borderBottom: "1px solid var(--border-2)",
      }}
    >
      <span
        className="mono"
        style={{ width: 90, fontSize: 11, color: "var(--text-4)" }}
      >
        {label}
      </span>
      <div className="row gap-12 wrap" style={{ alignItems: "center" }}>
        {children}
      </div>
    </div>
  );
}

function States() {
  return (
    <div className="col gap-16">
      <Card pad>
        <div className="sec-head">
          <h2 className="sec-title">Interactive states</h2>
          <span className="sec-sub">hover &amp; focus are live — try it</span>
        </div>
        <StateRow label="default">
          <Button>Button</Button>
          <Input style={{ width: 160 }} placeholder="input" />
        </StateRow>
        <StateRow label="hover">
          <Button style={{ background: "var(--hover)" }}>Button</Button>
          <span className="muted" style={{ fontSize: 12 }}>
            ← simulated · real buttons lighten on hover
          </span>
        </StateRow>
        <StateRow label="active">
          <Button style={{ background: "var(--active-bg)", transform: "translateY(0.5px)" }}>
            Button
          </Button>
        </StateRow>
        <StateRow label="focus">
          <Button style={{ boxShadow: "var(--ring-light), var(--focus-ring)" }}>
            Button
          </Button>
          <Input
            style={{ width: 160, boxShadow: "var(--ring), var(--focus-ring)" }}
            placeholder="focused"
          />
        </StateRow>
        <StateRow label="disabled">
          <Button disabled>Button</Button>
        </StateRow>
        <StateRow label="primary">
          <Button variant="primary">Default</Button>
          <Button variant="primary" style={{ background: "var(--accent-hover)" }}>
            Hover
          </Button>
          <Button variant="primary" style={{ boxShadow: "var(--focus-ring)" }}>
            Focus
          </Button>
        </StateRow>
      </Card>

      <Card pad>
        <div className="sec-head">
          <h2 className="sec-title">Card states</h2>
        </div>
        <div className="row gap-16 wrap">
          <Card pad style={{ width: 220 }}>
            <span style={{ fontWeight: 600 }}>Rest</span>
            <p className="muted" style={{ fontSize: 12, margin: "4px 0 0" }}>
              shadow-card
            </p>
          </Card>
          <Card pad style={{ width: 220, boxShadow: "var(--shadow-pop)" }}>
            <span style={{ fontWeight: 600 }}>Hover</span>
            <p className="muted" style={{ fontSize: 12, margin: "4px 0 0" }}>
              shadow-pop · lifted
            </p>
          </Card>
          <Card
            pad
            style={{
              width: 220,
              boxShadow: "var(--shadow-card), 0 0 0 1.5px var(--accent)",
            }}
          >
            <span style={{ fontWeight: 600 }}>Selected</span>
            <p className="muted" style={{ fontSize: 12, margin: "4px 0 0" }}>
              accent ring
            </p>
          </Card>
        </div>
      </Card>
    </div>
  );
}

function MarkCell({
  label,
  sub,
  children,
}: {
  label: string;
  sub: string;
  children: React.ReactNode;
}) {
  return (
    <div className="markcell">
      <div className="markstage">{children}</div>
      <div className="col" style={{ gap: 1 }}>
        <span style={{ fontSize: 12, fontWeight: 600 }}>{label}</span>
        <Spec>{sub}</Spec>
      </div>
    </div>
  );
}

function Brand() {
  // Per D8: ship only the production marks. No multi-variant grid here.
  return (
    <div className="col gap-16">
      <Card pad>
        <div className="sec-head">
          <h2 className="sec-title">Alpaca glyph</h2>
          <span className="sec-sub">production mark · inherits accent</span>
        </div>
        <div className="markgrid">
          <MarkCell label="A · Geometric" sub="current · filled">
            <Alpaca size={50} color="var(--accent)" eye="var(--bg-inset)" />
          </MarkCell>
        </div>
        <hr className="hr" style={{ margin: "18px 0 14px" }} />
        <div
          className="row"
          style={{
            justifyContent: "space-between",
            alignItems: "flex-end",
            flexWrap: "wrap",
            gap: 16,
          }}
        >
          <div className="row gap-16" style={{ alignItems: "flex-end" }}>
            {[16, 20, 24, 32, 44].map((s) => (
              <div key={s} className="col" style={{ alignItems: "center", gap: 7 }}>
                <Alpaca size={s} color="var(--text)" eye="var(--bg)" />
                <Spec>{s}px</Spec>
              </div>
            ))}
          </div>
          <span className="mono" style={{ fontSize: 11, color: "var(--text-4)" }}>
            geometric glyph · size ramp
          </span>
        </div>
      </Card>

      <Card pad>
        <div className="sec-head">
          <h2 className="sec-title">Radar emblem</h2>
          <span className="sec-sub">production mark · animated sweep</span>
        </div>
        <div className="markgrid">
          <MarkCell label="Sweep" sub="animated radar + centered alpaca">
            <RadarAlpaca size={88} />
          </MarkCell>
        </div>
      </Card>

      <Card pad>
        <div className="sec-head">
          <h2 className="sec-title">In context</h2>
          <span className="sec-sub">how the marks live with surrounding UI</span>
        </div>
        <div className="row gap-16 wrap" style={{ alignItems: "center" }}>
          <Button variant="primary">
            <Check size={14} /> Confirm
          </Button>
          <Button>
            <ExternalLink size={14} /> Open
          </Button>
          <RadarAlpaca size={56} />
          <Badge kind="accent">paca</Badge>
        </div>
      </Card>
    </div>
  );
}
