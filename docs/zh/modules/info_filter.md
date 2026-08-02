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
  subscriptions / unread counts；默认 `npx --yes folocli@0.0.5`，可用 `FOLO_CLI_ARGV` 覆盖。
  subscriptions 盘点合并两个命令：`subscription list` 不带 unread 字段，每个 feed 的未读数
  由 `unread list` 提供，按 `feedId` join。
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
- Tier-2 的 `score` 衡量的是**后果**——这件事该多大程度改变读者的判断或行动——
  明确不是证据质量。方法论严谨度（消融、对抗测试、顶会接收）写进 `impact` 作为
  多信它数字的理由，本身绝不加分。rubric 是：先做一个机械问句"外部现在立刻能
  拿到什么"给非论文条目定底分，再对锚点表（带具体分数的参照点）微调，并有一条
  硬次序约束——旗舰发布高于单实验室窄任务论文，与谁更严谨无关。`opinion` tag 的
  ≤65 上限由代码层 clamp 兜底（`stages/tier2.py::_apply_ceilings`），goals 列名的
  高信号个人由 prompt 引导打 `frontier-voice` tag 豁免。
- 不设比采样波动更细的档内数值调节。此前的"三维度 ±3"机制已删除：它最多能挪
  ±9 分，而这正好是 `local_structured` 温度下同条重跑的波动幅度；且 36% 的实测
  分数落在它的算术算不出来的值上——模型压根没在执行它。
- Tier-2 prompt 明确告诉 agent：feed 里的条目比它的训练数据新，且都是真实发生的。
  没有这句时，没听说过的模型名和看起来在未来的日期会被判成造假——有一次前沿模型
  发布被打上 `misinformation`，三遍分别给了 0 / 15 / 15 分。
- `content_status` 反映的是"有没有拿到真正的正文"，不是"响应是否非空"。正文在
  做任何长度判断和截断之前先摊平成纯文本（某个源实测 91% 是标签，导致 16k 上限
  只送进约 1,400 字真文），摊平后不足 200 字符的一律报 `fallback`——付费墙媒体的
  导语不是文章。tier-2 prompt 有配套的一句：正文薄时缺的是篇幅不是证据；没有这句
  时如实标注实测掉 5.3 分，因为按证据分档的 rubric 会把"没有细节"读成"没有证据"。
  **两者必须一起上。**
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

## 输出语言

`SIGNAL_OUTPUT_LANG`（`zh` | `en`）决定读者看到的所有散文字段用什么语言——tier-2 的
`summary` / `impact`、tier-1 的 `reason`、recap 的 headline 与 narrative——与文章语言、
与 `goals.yaml` 语言都无关。不设则各 prompt 自己的默认生效。机制见
[core.md](./core.md#输出语言)。

**实测**（13 条 × 5 次重复，真实 stage，记录 prompt digest）：旧的条件句规则下，中文 goals +
英文文章时 tier-2 `summary` 命中 0/64；改成无条件后 63/63。`impact` 和 tier-1 `reason` 在
**同一批响应**里本来就 100% 正确——出问题的恰好是字段说明里没有语言锚点的那个。英文目标在
中文 goals **且**中文文章下守住 65/65，零错误。

修后在 55 条 holdout 上、带同一晚的 baseline 对照：英文文章 + 中文目标下，英文 summary 从
**12/12 降到 0/12**，而 `impact` 长度、verdict flips、均分全都落在 baseline 自身的轮间波动范围内。
`scripts/lang_probe.py` 测 tier-2 的 `summary` / `impact` 与 tier-1 的 `reason`：**两个方向都是
0/30，无翻转**。`radar_recap` 在一个含 22 条英文 + 153 条中文 summary 的区间上跑出中文。

**未实测**：tier-2 截断有没有变多。baseline 两轮都是 2/165，本改动两轮是 8/165 和 4/165——
同一配置两轮差一倍，这个样本量下判不出来。它们是 xgrammar 的 premature-EOS，两边都落在同样
约 6 条脆弱条目上，代价是重试而不是丢数据（tier-2 失败的条目不标记 seen）。`radar_dedup_judge` 刻意豁免——它的 `reason` 既不入库也不渲染。

不要改回条件句写法，也不要加字段级语言条款：单独点名 `summary` 的变体语言命中率一样，但输出
长了 35%，截断失败从 1/65 升到 6/65（撞 4096 `max_tokens` 上限）。

### dedup 与混合语言的嵌入空间

dedup gate 嵌入的就是 tier-2 的 `summary`,所以被嵌入的文本现在也跟着
`SIGNAL_OUTPUT_LANG` 走。`radar_pushed_topics` 从不被清理——没有任何地方 DELETE 它——
所以它会永久保留 32 条输出语言改动之前冻结的英文 topic,和 210 条中文 topic 混在一起。
于是英文文章的中文 summary,要去和同一件事的英文向量做 ANN 比对。

拿 5 对这样的组合实测(存量英文 topic vs 同一条目现在产出的中文 summary):余弦距离
0.11–0.26,均值 0.195,阈值 0.40。全部通过且有余量,跨语言重复仍然抓得住。

两点推论:余量真实但有限——谁要把 `DEFAULT_THRESHOLD` 收到 ~0.30 以下,得知道空间里有
落在 0.26 的跨语言对。以及 `radar_dedup_judge` 现在会看到中文 `new_summary` 配可能是英文的
候选;它豁免语言规则(`reason` 既不入库也不渲染),而且只处理已经过了 ANN 闸门的候选。

## 调优与评测

打分行为靠测量,不靠手感。`scripts/radar_eval.py` 拿 `radar_items` 的人工标注子集
回放真实的 tier-1 / tier-2 流程,写入 `radar_eval_cases` / `radar_eval_runs` /
`radar_eval_results`。这三张表由脚本自己的 `init` 子命令创建,**刻意不由**
`scripts/bootstrap_db.py` 建——它们不承载任何运行时行为。dedup gate 被跳过,因为
它写的是共享的生产状态,且不影响 verdict 与 score。

正文在 `load` 时快照冻结并在每次 run 中重放,所以变体之间的差异可归因于提示词,
而不是 folocli 当天答不答得上来。每次 run 记录 `prompt_digest`——两个提示词加
`goals.yaml` 的哈希——任何一组数字都能追溯到产生它的那份文本。

`scripts/lang_probe.py` 是它的姊妹台,测的是输出**语言**而不是分数。它回放同样的 stage
外加 `knowledge_frontmatter`,只往 `PACA_AGENT_TMP_DIR/lang-probe/` 写 JSON,报告有多少次
生成落在了错误的语言上。那里重复次数是必须的:frontmatter 的缺陷是**不确定性**的——同一篇
文章在不同次运行之间会换语言——跑一遍很可能正好没撞上。

有两道保险,因为这两种失败都真实发生过:探针会断言构建出来的 agent 的 composed instructions
里确实点名了目标语言(曾有一次 bind mount 静默没生效,让修复看起来像没效果),并且会在某个
agent 的 instructions 跑到一半发生变化时拒绝写结果(`prompts/` 是 live bind mount,跑的过程中
改 prompt 会把两个版本混进同一批结果)。`radar_eval.py` 没有这道保险——它跑的时候不要改 prompt。

`configs/info_radar/` 下有三个标注集:

| 集合 | 条数 | 用途 |
| --- | --- | --- |
| `eval_cases.yaml` | 60 | 对抗性,堆满已知失败案例 |
| `eval_cases_focus.yaml` | 36 | 只在决策边界上 |
| `eval_cases_holdout.yaml` | 55 | 独立标注——**绝不用它调优** |

holdout 集由三个 agent 标注,它们只读 `goals.yaml`,被明确禁止读 `prompts/` 和任何
已有标注集,且只保留三人一致的条目。这是唯一有理由称得上无偏的一个集合。有一次
调优只在自己调过的集子上验证,四轮从 26/54 涨到 38/60,而 holdout 上只有 40%,
生产环境是 75%。

流程铁律以及每条背后的实测数字,在 `.claude/skills/radar-prompt-tuning/SKILL.md`。
改任何 radar 提示词之前先读它。

**已测量并否决,不看记录不要重试**:把 tier-1 的 drop 类别从"按标题措辞"改成
"按事件类型"。它在对抗集上看着是明确的胜利、护栏桶全程没退步,但在 holdout 上
误留从 4 条涨到 16 条、通过率从 75% 掉到 40%。**护栏本身是失败的原因**:那 17 条
是金价、美联储评论、名人离婚和 Java 更新,从来没失败过,所以什么都没测出来。
真实的 drop 分布是"看起来像发布的厂商通稿"和"看起来像突破的机制论文"。

另外一条:主指标的选择比它看起来更重要。分桶通过率被当主指标用了七轮,而它和
读者的实际体验并不对齐。真正对齐的是扫描 dashboard 阈值、在每个切点上数可见
信号与漏出噪音——一条拿 35 分的误留,根本到不了读者眼前。

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
