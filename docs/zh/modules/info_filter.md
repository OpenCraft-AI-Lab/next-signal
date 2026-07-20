# 模块：info_filter（信息搜集过滤）

> [English](../../modules/info_filter.md) · **中文**

## 解决什么

收集外部信息流并过滤到 signal。当前实例是 **info-radar**：周期性拉
Folo / source CLI，写 `radar_items`；随后两层本地 LLM analysis 按
`configs/info_radar/goals.yaml` 做 relevance、impact scoring 和 dedup，
写 `radar_analyses` / `radar_pushed_topics`，dashboard `/radar` 负责阅读和手动触发。

## 代码位置

`src/paca/collectors/info_radar/` —— 无 LLM collector，source CLI → `radar_items`。
`src/paca/integrations/info_radar/` —— Folo / YouTube subtitle 等 provider adapter。
`src/paca/workflows/info_radar_pull.py` —— collector 的 manual-run thin shell。
`src/paca/workflows/info_radar_analysis/` —— 两层 LLM analysis pipeline。

## Agents

| agent | 模型 profile | 用途 |
|---|---|---|
| `radar_tier1_filter` | local_structured | batched Tier-1 relevance filter，按 goals 决定 keep/drop |
| `radar_tier2_impact` | local_structured | per-item full-content impact summary / score / tags |
| `radar_dedup_judge` | local_structured | pgvector candidate 后的 LLM duplicate/novel 判定 |

## 工具

- info-radar collector：`uv run paca info-radar pull [--source NAME]`。
- info-radar analysis：`uv run paca info-radar analyze [--limit N] [--source NAME]`。
- Folo subscriptions inventory：`uv run paca info-radar subscriptions --json`。

## 接的外部

- **Folo CLI**（`paca.integrations.info_radar.folo`）—— info-radar source / full content /
  subscriptions；默认 `npx --yes folocli@0.0.5`，可用 `FOLO_CLI_ARGV` 覆盖。
  Dashboard `/radar` 的 Ingest 会先用 `folocli entry get <source_id>` 拉全文并 stage 成
  `PACA_AGENT_TMP_DIR` 下的 HTML，再交给 knowledge pipeline；非 Folo source 仍走
  `radar_items.url`。
- **YouTube native subtitles**（`paca.integrations.info_radar.youtube_subs`）—— YouTube
  item 的无音频字幕补充。

## 数据存哪

- info-radar raw items：Postgres `radar_items`
- info-radar analyses：Postgres `radar_analyses`
- info-radar dedup memory：Postgres `radar_pushed_topics`（pgvector 1024-dim）
- info-radar goals：`configs/info_radar/goals.yaml`（dashboard `/goals` 可编辑）
- info-radar sources：`configs/info_radar/sources.yaml`

## 不变量

- `radar_items.seen_at` 只由 analysis 层写；collector 只写 raw item。
- `radar_analyses.radar_item_id` 是唯一键；analysis 只处理 `seen_at IS NULL`，并且在
  analysis row commit 后才写 `seen_at`，所以任意 cadence 重跑都保持幂等。
- `configs/info_radar/goals.yaml` 缺失或非法时，analysis loud fail。
- Tier-1 batch 输出结构不匹配时回退到单 item；任一 item 失败不能阻断整批。
- Tier-1 / Tier-2 失败的 item 不写 analysis row、不写 `seen_at`——留给下一轮重试
  （`radar_analyses` 唯一键 + 无 reanalyze 命令，写空行会把瞬时失败永久冻结）。
- Tier-2 打分是"定档 base 分 + 三维度 ±3 档内调节"两步 rubric（prompt 定义）；
  `opinion` tag 的 ≤65 上限由代码层 clamp 兜底（`stages/tier2.py::_apply_ceilings`），
  goals 列名的高信号个人由 prompt 引导打 `frontier-voice` tag 豁免。
- Dedup embedding 失败时 conservatively 走 novel，不静默丢 item。
- 新闻 cache 状态只能 `pulled` → `reviewed` / `pushed`；`reviewed` 不能覆盖 `pushed`。
- 不要往 logger dump 整个 provider dict。

## 规范与状态

规范：[`openspec/specs/info-radar/`](../../../openspec/specs/info-radar/)、
[`openspec/specs/info-radar-analysis/`](../../../openspec/specs/info-radar-analysis/)、
[`openspec/specs/dashboard-radar-reader/`](../../../openspec/specs/dashboard-radar-reader/)。

当前状态：info-radar pull / analysis / dashboard reader / goals editor / Folo subscriptions
table 已就位。没有后台调度——pull 和 analysis **都靠手动触发**：`paca info-radar pull|analyze`、
`paca run-workflow <name>` 或 dashboard `/radar` 的 Pull + Analyze。

dashboard `/radar` 的 `Pull + Analyze` 现在显示**实时 analyze 进度**：action 在 pull 后把
未分析条目数（denominator）连同 `analyzeRunning` 标记写进
`~/.next-signal/radar-state.json`，并以 **tracked**（非 detached）方式 spawn
`info-radar analyze`，子进程退出时翻回 `analyzeRunning=false`。页面通过
`GET /api/radar/run`（约 1.5s 轮询，`done = radar_analyses` 自最近 analyze 起的行数）驱动一个
`done/total` 进度条，并在运行中节流刷新让 `TodayTracker` 计数实时跳动；进度条的 running 状态在
页面加载时即从 `radar-state.json` 读取，刷新页面也能续上。仅覆盖 dashboard 触发的 run
（CLI run 不显示进度条）；dashboard 重启会让 in-flight 的 `analyzeRunning` 残留到下次
run（best-effort，子进程与 DB 写入不受影响）。
