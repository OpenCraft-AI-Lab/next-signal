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
`src/paca/workflows/info_radar_recap/` —— 区间 recap 归纳。

## Agents

| agent | 模型 profile | 用途 |
|---|---|---|
| `radar_tier1_filter` | local_structured | batched Tier-1 relevance filter，按 goals 决定 keep/drop |
| `radar_tier2_impact` | local_structured | per-item full-content impact summary / score / tags |
| `radar_dedup_judge` | local_structured | pgvector candidate 后的 LLM duplicate/novel 判定 |
| `radar_recap` | local_structured | 把一个日期区间的 kept item 聚成 3-5 条带引用的主线叙述 |

## 工具

- info-radar collector：`uv run paca info-radar pull [--source NAME]`。
- info-radar analysis：`uv run paca info-radar analyze [--limit N] [--source NAME]`。
- info-radar recap：`uv run paca info-radar recap --since D --until D [--min-score N] [--novel-only] [--regenerate]`。
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
- info-radar recaps：Postgres `radar_recaps`，一行对应一个
  `(since, until, min_score, novel_only)`
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
- recap 的身份是 `(since, until, min_score, novel_only)`。重复请求走缓存；
  regenerate 是原地 upsert，不追加新行。
- recap 区间按 radar 时区的 `analyzed_at` 取，两端闭区间——和 day group 同一套
  约定，所以 7 天 recap 覆盖的正好是下方那七行 day row。绝不用 `published_at`
  （可为 NULL，且会和页面上其他所有日期对不上）。
- recap agent 只拿 `summary`，绝不拿 `impact_md`：recap 做的是跨 item 归纳，
  per-item 深挖会让 prompt 体积翻三倍去塞主线本该抽象掉的内容。
- 选取上限为 score 最高的 60 条。`item_count` 和 `considered_count` 都会持久化，
  让读者知道这次 recap 只覆盖了子集——上限不会静默生效。
- recap 引用到未知 id 会被丢弃；引用全失效的主线整条丢弃；若无任何主线存活，
  本次算失败，不写 `done`。regenerate 失败时上一版 recap 仍可读。
- `radar_recaps` **没有**指向 `radar_items` 的外键——引用 id 存在 `themes` JSONB
  里，好让 recap 活过 30 天 sweep。来源已消失的引用渲染成纯文本。
- recap 过期（区间内又有新分析落库）只**标注**，绝不自动重算：一进页面就重算会把
  每次访问活跃区间变成一分钟本地推理。
- 不要往 logger dump 整个 provider dict。
- analysis 的**输出语言由请求 locale 决定**（`run(locale=)` / `analyze --locale`），
  不再由 goals 语言决定。locale ∈ {`zh`, `en`}，默认 `en`；goals / 文章正文可以是任意
  语言（只作输入），locale 只固定输出语言。每个 stage 有 `zh` / `en` 两份纯语言 prompt，
  两种语言都带显式后缀（`prompts/agents/radar_*.zh.md` 和 `radar_*.en.md`；这些多语言
  agent 没有无后缀 base，loader 按 `<stem>.<locale>.md` 解析）；tier-1 的 drop 类别 cue
  词表在两份里都保持中英双语（同义惯用，不直译），因为任一 locale 都可能分析另一语言的
  文章。tier-2 的两步打分 rubric 现在存在两份文件里——改 rubric 必须同步改
  `radar_tier2_impact.zh.md` 和 `radar_tier2_impact.en.md`。
- `radar_analyses.locale` 记录每行的生成语言；不做事后翻译，语料库按 locale 混合是预期
  行为。dedup 候选检索**不按 locale 过滤**（跨语言去重是有意为之，embedding 多语言）。
- 面向读者的**条目标题随 locale**：tier-2 产出 `display_title`（属于 `Tier2Analysis`，
  按运行 locale 生成，两份 `radar_tier2_impact.{zh,en}.md` 要同步），keep 行持久化到
  `radar_analyses.display_title`（可空；用 `ADD COLUMN IF NOT EXISTS` 加列，不回填）。
  `/radar` 阅读页渲染 `display_title ?? radar_items.title`，详情页把原始 feed 标题作为
  次级"原标题"行保留——`radar_items.title` 永不被覆盖。

## 规范与状态

规范：[`openspec/specs/info-radar/`](../../../openspec/specs/info-radar/)、
[`openspec/specs/info-radar-analysis/`](../../../openspec/specs/info-radar-analysis/)、
[`openspec/specs/info-radar-recap/`](../../../openspec/specs/info-radar-recap/)、
[`openspec/specs/dashboard-radar-reader/`](../../../openspec/specs/dashboard-radar-reader/)。

当前状态：info-radar pull / analysis / recap / dashboard reader / goals editor / Folo
subscriptions table 已就位。没有后台调度——pull 和 analysis **都靠手动触发**：`paca info-radar pull|analyze`、
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

`/radar` 的 **Recap** 面板选一个区间（最近 7 天 / 最近 30 天 / 自定义 from–to，预设在
radar 时区解析），并继承 filter bar 当前的 score 阈值和 novel-only 作为质量门槛，所以
recap 和下方条目列表描述的是同一批内容——换个门槛就是另一条缓存记录。生成走
detached spawn `paca info-radar recap`，再轮询 `GET /api/radar/recap` 拿行的 `status`；
`running` → `done` 时客户端调 `router.refresh()`，由服务端渲染的面板接手结果。失败会
展示存下来的错误，而不是一直轮询。`?export=1` 下整个面板不渲染。
