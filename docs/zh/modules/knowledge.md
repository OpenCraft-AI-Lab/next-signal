# 模块：knowledge（知识管理）

> [English](../../modules/knowledge.md) · **中文**

## 解决什么

把 URL 和文件变成持久的 markdown artifact 和可检索的长期知识。
clean markdown 进 wiki 树，raw 原件归档，GBrain 做索引和 hybrid search。

## 代码位置

`src/next_signal/tools/knowledge/` —— agent-facing knowledge tools。
`src/next_signal/integrations/knowledge/` —— OpenCLI (WeChat) / Bilibili / GitHub adapters。
`src/next_signal/workflows/knowledge_ingest.py` —— centralized workflow factory。
`src/next_signal/workflows/stages/knowledge_ingest/` —— workflow-private pipeline stages。
`src/next_signal/workflows/knowledge_review/` —— 间隔重复回顾调度器（`__init__.py` 放曲线 +
reconciliation，`store.py` 放 Postgres I/O）。

## Agents

| agent | 模型 profile | 用途 |
|---|---|---|
| `knowledge_artifact_editor` | local | ingest 的 clean 步：正文清洗 / whisper 纠错（DB-free 转换 agent） |
| `knowledge_github_cleaner` | local | github repo 专用 clean 步：只对 `## README` 段做激进精简（去 badge / 安装命令 / sponsor 等），结构化 signal section 原样保留 |
| `knowledge_frontmatter` | local | ingest 的 enrich 步：产出 summary/tags/freshness（`FrontmatterDraft` schema，DB-free） |
| `knowledge_github_summary` | local | github repo 专用 enrich 步：summary 按 does/value/maturity/ecosystem 四个角度组织，复用 `FrontmatterDraft` schema |
| `knowledge_classifier` | local | ingest 时按 taxonomy 选 wiki 分类目录（DB-free 转换 agent） |

## 工具

knowledge 领域工具：

- `knowledge_ingest_workflow` —— 单篇入库路径（fetch → clean → enrich → classify → persist）。

KB **检索**是横向基础设施（不在本模块）：`search_knowledge` 在
`next_signal/tools/knowledge/search.py`；`gbrain_search` / `gbrain_get` / `gbrain_query` /
`gbrain_ingest` 在 `next_signal/tools/gbrain.py`；GBrain bridge 在
`next_signal/integrations/gbrain.py` —— 任何模块的 agent 都能按名字引用这些工具。

## 接的外部

- **OpenCLI** —— 微信公众号图文入口。本地 `node opencli weixin download` subprocess，
  下载文章 + 图片到 raw store，按 slot 索引把 markdown 里的图片链接重写成本地相对路径。
  `OPENCLI_BIN` 必填，在 call time 读。
- **MarkItDown** —— YouTube / PDF / HTML / Office / text-like 文件转 markdown
  （横向 adapter：`next_signal/integrations/markitdown.py`）。
- **Bilibili** —— 优先公开字幕；没字幕时下临时音频、本地转写、删临时媒体。
  另导出轻量 `bilibili_fetch_captions`（只取字幕+标题+简介、不下音频）——这是给
  跨领域抽样场景用的工具函数，next-signal 当前没有消费它的调用方，留着以备未来用途，
  不是 ingest 路径。
- **GitHub** —— 收藏单个 repo 用。只接受 `github.com/owner/repo` 根 URL（subpath
  loud fail）；调 REST API 收 repo 元数据 / 顶层文件树 / 最近 3 个 release / 顶层 manifest
  / 最近 10 条 commit / contributors + 语言分布 / README，拼成结构化 markdown 包；
  专用 `knowledge_github_cleaner` 对 README 段激进精简，专用 `knowledge_github_summary`
  按 does/value/maturity/ecosystem 四角度写 summary。`GITHUB_TOKEN` 可选，缺省走匿名
  （60/h rate limit，个人偶尔收藏够用）；token 设了在 call time 读自动加 Bearer 头。
- **GBrain** —— 长期知识库 peer service。入库走横向 GBrain bridge
  （`next_signal/integrations/gbrain.py`），不是本模块独占。
- **Obsidian Git plugin** —— wiki repo ↔ GitHub 同步走 vault 内的 plugin，
  不在 next-signal 进程里。详见下面 "Wiki ↔ GitHub 同步" 一节。

## 数据存哪

- clean wiki：`~/Projects/digitalpaca-wiki/`
- raw 归档：`~/Projects/digitalpaca-wiki-raw/`
- re-ingest manifest：`~/.next-signal/knowledge_ingest_manifest.json`
- 回顾调度：`knowledge_reviews` 表（Postgres）
- 索引：GBrain 自管本地存储

## 怎么用

```bash
uv run next-signal knowledge ingest <url|staged-file>
uv run next-signal knowledge ingest <url> --category knowledge/ai-ml   # 指定落点文件夹（跳过自动分类）
uv run next-signal knowledge ingest <url> --progress                   # 每个 pipeline step 一行 JSON 事件 + 末行结果 JSON
uv run next-signal knowledge gbrain-search "query"
uv run next-signal run-workflow knowledge_ingest            # re-ingest 变更文件 + 刷新所有 Related 区块
uv run next-signal knowledge review                         # 对照 wiki 与 knowledge_reviews（入列新的 / 移除已删的）
```

`--category` 必须是 `configs/knowledge_taxonomy.yaml` 里的某个 path，非法值在 fetch 之前
loud fail。`--progress` 给 dashboard 的入库进度面板用（见下）。
本地文件输入只接受 `NEXT_SIGNAL_AGENT_TMP_DIR` 下的 staged file；`/radar` 的 Folo ingest 也遵守
这个边界，先把 full-text HTML 写到该目录，再把文件路径交给通用 knowledge pipeline。

## 知识回顾（间隔重复）

ingest 是写入侧，回顾是读取侧。每篇 wiki 文档在 `knowledge_reviews` 里有一行，
沿固定艾宾浩斯曲线重新推到读者眼前，让收录的内容在遗忘之前被刷新。

- **曲线** —— 阶段在文档 `captured_at` 之后 **1、3、7、15、30、60、120 天**；
  `next_due_at = captured_at + STAGES[stage]`，永远锚在收录日期，绝不锚在读者点击的时间。
  没有回忆评分、没有 ease factor —— "已回顾" 就是一次确认。
- **快进** —— 给已有语料 seed 时，每篇锚在真实 `captured_at`，跳到第一个尚未到期的阶段：
  100 天前收录的文档落在 120 天阶段，而不是甩出六条过期回顾。advance 时同样按
  `max(stage + 1, 第一个未到期阶段)`，所以迟到的回顾也不会立刻产出一张已过期的卡。
- **退休** —— advance 越过最后一个阶段就把 `next_due_at` 置 `NULL`，文档不再出现。
  因此以 120 天以上老内容为主的语料会冒一次头就安静下来；让退休文档重新入列是另一个
  常青轮换功能，而不是把阶段列表加长。
- **卡片内容** —— 卡片直接复用文档自己的 frontmatter `summary`，所以回顾层**不调 LLM**、
  行里也不存生成文本。手写、没有 `summary` 的文档回退到正文首段。
- **对账（reconciliation）** —— `next-signal knowledge review` 遍历 wiki，把未知文档入列
  （按曲线 seed），把文件已删的行移除。wiki 根缺失或空时直接拒绝，而不是把 "没有文件" 读成
  "全部删了"。`captured_at` 从 frontmatter 解析，优先级 `captured_at` → `updated_at` →
  `created_at` → mtime，与 dashboard wiki 视图一致。

投放形态是 `/knowledge` 顶部（入库表单之上）的一个区块，最多五张卡、最久过期在前，
并标出剩余数量。点击卡片会在页面的预览面板里打开该文档全文并滚动过去（`#doc-preview`），所以回顾是重读原文而非仅仅提醒——打开不推进阶段。"已回顾" 是 POST server action，在请求内推进阶段（GET 会让 prefetch
推进曲线）；刷新控件把 `--sync` 任务 detached 起，因为对账加要点生成是 LLM 活。

卡片旁边是一条与 info-radar tracker 同构的 strip：左侧是汇总数字（已入列 / 待回顾 / 排期中 / 完成，
外加中位阶段——全部从同一批 bins 推出，不额外查一次库），右端是一张**留存柱状图**，标题直接写"艾宾浩斯
曲线"。每个阶段一根柱（`1d` … `120d`），外加一根走完全部阶段的终点柱，
每根再拆成"已到期"（实心）和"排期中"（半透明）两段，并配一行图例——这个区分只靠透明度，
不像 info-radar 的分数柱状图那样可以不标。它回答的是"内容目前落在曲线的哪个阶段"，这是待回顾数本身给不出的：
全部停在 `1d` 的库和大多数已经走到 `120d` 的库，都只显示 "3 篇待回顾"。分桶取自 `stage` 列和
`next_due_at IS NULL`，绝不从 `captured_at` 加今天重算——阶段推进已经在 SQL 里做了 fast-forward，
在这里再算一遍等于把同一条规则放两个地方。它的位置与 info-radar tracker 摆放分数柱状图的方式一致
（header 下方那条 strip 的右端，同样的 232px 槽位与柱体几何）。它的框架——标题、完整坐标轴、图例
——在任何状态下都渲染，包括"暂无待回顾"和一篇都没入列时；这与 info-radar 一致：没有条目的那天，
tracker 依然显示"分数分布 · 0-100"和完整坐标轴。折叠态砍掉的是卡片和卡片外框，不是图表的标注。
配色走自己的留存色阶（`--kb-*`），绝不复用分数色阶：那条是 info-radar 的判定色，借过来会把
120 天的文档读成"分数高"。

## 输出语言

一次入库会**同时**用到两条语言 policy（机制见 [core.md](./core.md#输出语言)），因为它产出
的是两种不同性质的文本：

| 步骤 | Agent | 产出 | Policy | 语言 |
|---|---|---|---|---|
| 清洗正文 | `knowledge_artifact_editor` / `knowledge_github_cleaner` | 文章正文 | `same_as_source` | 文章自己的语言（探测得到） |
| 写 frontmatter | `knowledge_frontmatter` / `knowledge_github_summary` | `title` / `summary` | `global` | 内容语言设置 |

正文就是归档本身——wiki 里存着那段源文本的唯一副本，翻译掉就等于毁掉它。而
`title` 和 `summary` 是条目的索引项，是知识列表和回顾卡片上显示的文字，所以跟着读者在
dashboard 设置面板里选的内容语言走。

因此一个 wiki 文件是允许双语的：英文的 `title`/`summary` 配中文正文（如果设置是那样）。
这是有意的，也和 radar 阅读器一致——那边早就是翻译过的标题配源语言文章。

- **探测**出的语言在 `fetch()` 里每条算一次（确定性算法，不走 LLM，见
  `next_signal.core.language_detect`），挂在 `KnowledgeArtifact.detected_language` 上，只作为
  `language=` 传给正文清洗 agent。frontmatter 那步不传 override，自己解析设置。
- `tags` **豁免**，任何语言下都保持小写英文——走的是针对该字段的专门 prompt 指令，不是
  语言 policy 机制（同一次调用里某个字段需要跟别的字段不一样，就留在 prompt 层单独处理，
  见 core.md）。`_normalize_tags` 会静默丢弃含 CJK 的 tag，所以把 tag 推成中文不会得到
  中文 tag，只会得到没有 tag 的文档。

**实测**，就是在当前这套配置下测的——frontmatter 的目标是操作者设定的语言，而非文章自己的
语言。

修前，完全没有语言规则时：英文文章下 17.9% 的 title、7.7% 的 summary 是纯英文，而且
**同一篇文章**在不同次运行之间来回翻——手动测一次很可能正好抽到对的。

修后，在 frontmatter 改回 `global` 之后重测（每个方向 10 条真实 `radar_items` × 3 次重复，
走 `scripts/lang_probe.py`，本地 `Qwen3.5-122B`）：

| 步骤 | 语料 / 设置 | 字段 | 缺陷 | 翻转 |
|---|---|---|---|---|
| frontmatter（`global`） | 英文源，设置 `zh` | title / summary | 0/30 · 0/30 | 无 |
| frontmatter（`global`） | 中文源，设置 `en` | title / summary | 0/30 · 0/30 | 无 |
| 正文清洗（`same_as_source`） | 中文源，设置 `en` | body | 0/30 | 无 |
| 正文清洗（`same_as_source`） | 英文源，设置 `zh` | body | 0/30 | 无 |

清洗那两行是更狠的测法：设置被**刻意指向相反的语言**，所以正文只要往操作者偏好方向漂
——正是 `same_as_source` 要防的那种失败——就会暴露出来。中文正文回来时 CJK 比例均值
0.909，英文正文 0.000；而且 `--agent cleaner` 每一次重复都会逐条断言组合出的规则指向的是
探测出的语言、而不是那个设置。

判定标准是「整段都是错的语言」，所以要连着 CJK 比例一起看，而不是只看缺陷数：中文目标下，
一个保留了英文模型名的标题是**正确**输出。十条英文样本里有四条是 `Last Week in AI` 播客，
标题几乎全是专有名词，所以它们正确的中文译法比例也低到 0.156
（`LWiAI #247：Opus 4.8、微软 MAI 与 Anthropic 上市`——`微软`、`上市` 都翻了，模型名保留）。
更早一次在不同语料、不同模型 pin 下跑的中文→英文方向测出过 2/30（6.7%）且有翻转；这套配置
没有复现，但样本只有 10 篇，不构成保证。

**跟语言无关、但同一次跑出来的现象**：语料里唯一那篇长文（41k 字符，第二长的才 13k），
`knowledge_artifact_editor` 三次重复都把正文压到 0.32 的保留率——用的是生产自己的
`_content_length`，所以和 `_MIN_LONG_TEXT_RETENTION`（0.6）直接可比。
`_check_summarized` 会用一个 loud 的 `RuntimeError` 直接拒掉这次入库，而不是把一份被
摘要过的正文写进 wiki。守卫本身是好的；
它说明的是**超长文章目前可能过不了清洗这一关**。其余每条都 ≥0.88。这是清洗质量问题，
不是语言问题——那份被过度压缩的输出语言仍然是正确的英文。

**`knowledge_classifier`，以及"`off` 是白省的"这个错觉。** 分类器只输出一条从输入里逐字
复制的 taxonomy 路径，所以把它设成 `off` 看着像 no-op。实测不是：30 条真实条目（5 篇 wiki
文档 + 25 条已分析的 radar 条目）× 3 次重复，`off` 与"把规则块加回去"的同一个 agent 相比，
**7/30 不一致**——而把同一份配置跑两遍得到的 A/A 噪声底线是 **1/30**（Fisher 精确检验双侧
p ≈ 0.05）。机制就写在规则自己的豁免句里，它点名的正是这个 agent 的输出类型：
"Identifier-like fields — tags, slugs, **category paths** — stay lowercase English."

方向上是支持 `off` 的。七条里有五条是分类器在 `knowledge/ai-engineering` 与 `radar/tech`
之间自我翻转（同一个变体内部就不一致），没有信号。两条干净的（两边各自一致且不同）里，有
一条能用 taxonomy 判对错：`radar/tech` 的 scope 写的是「科技领域的阶段性综述(digest，不是
单条新闻)」，而对一条**单条新闻**（台积电芯片涨价），`off` 3/3 答 `temp-inbox`——正是
prompt 设计的「没有明确归属就交给人归档」的出口——带规则的那版 3/3 答 `radar/tech`，违反了
该 scope。注意：n=30、p 卡在阈值上，且这对边界本来就是分类器最不稳的地方。

**风险，以及它为什么不会触发**：wiki 文件名由 `title` 推导
（`persist.py::_artifact_slug`），所以任何批量重写标题的动作都会让全项目文件改名，且没有
自动迁移。把 frontmatter 挪回操作者的设置，看上去正好会把这个风险带回来——切一下设置、
re-index 一遍、所有文件改名。

实际不会，因为 re-index 根本不重写 frontmatter。`next-signal run-workflow knowledge_ingest` 跑的是
`reindex_wiki`：它对每个 wiki markdown 文件算摘要，把变了的重新 embed 进 GBrain，frontmatter
agent 不在这条路径上。唯一会写 `title` 的是一次全新的 `next-signal knowledge ingest <source>`，
一次一篇、且是刻意触发的。所以改设置只影响之后的入库，已有文档的文件名和 frontmatter 语言
会一直保持不变——包括在这次拆分之前入库的整个知识库，会一直停在各自的源语言，直到某个来源
被重新入库为止。

## 不变量

- 回顾状态完全存在 `knowledge_reviews`；回顾层从不写任何 wiki markdown 文件（含
  frontmatter）。`doc_path`（wiki 相对路径）是身份，靠对账而非外键与文件系统保持一致。
- GBrain ingest 失败不能丢 artifact：clean wiki / raw 文件保留在磁盘，workflow loud fail。
  不把这次运行标成成功；修好 GBrain 后靠 direct ingest / weekly sync 补索引。
- re-ingest manifest 只在成功索引后才前进，否则后续不重试、KB search 会 stale。
- 直接 ingest 和 re-ingest 必须从 wiki-relative path 推出同一个 GBrain-safe slug；
  非 ASCII 路径要补稳定 hash 后缀避免 GBrain page 撞车。
- wiki 文件名由标题派生，frontmatter 记 `digest`（来源 hash）作为同源标识：同源 re-ingest
  原地覆盖（幂等更新）；同名标题但不同来源时新文件追加 `-<digest[:8]>` 后缀，绝不静默
  覆盖别人的文章（两种目录布局间的撞车也算）。
- `knowledge_artifact_editor` 失败不能产出 deterministic fallback 内容。
- WeChat artifact 走 per-article 目录布局（`<category>/<slug>/<slug>.md` + 同目录 `images/`）；
  `gbrain_slug_for_path` 折叠这层重复目录，保证 GBrain slug 跟平铺布局产出相同。
- 每篇 wiki 文章末尾的 `<!-- gbrain:related ... -->` marker 块是 GBrain-driven 的派生数据，
  ingest 时按 title+summary 跑一次 hybrid query 写入，weekly sync 全量刷新；marker 块内
  内容**不要手编辑**，正文其他位置随便改。Related 列表是 `[[wiki/path/Note]]` 显式
  wikilink，Obsidian 自动渲染 + Backlinks 面板联动，GBrain `extract` 反向同步成 typed edge。

## Wiki ↔ GitHub 同步

`digitalpaca-wiki/` 到 GitHub 的同步**不在 next-signal 进程里**，由 vault 内的
[Obsidian Git plugin](https://github.com/Vinzent03/obsidian-git) 负责，跟 next-signal 完全解耦。
next-signal 这边只保证 wiki 落盘那一刻跟 GBrain 同步成功；剩下定时推到 GitHub 是 plugin 的事。

### 凭据

macOS 桌面端 Obsidian Git 直接 shell-out 调系统 `git`，继承全局 git config。一次性配置：

```bash
gh auth setup-git   # 让 git HTTPS ops 通过 gh CLI 已登录的 PAT 走 keychain
```

不需要在 plugin UI 里贴 token。如果 plugin 找不到 helper 路径，在 plugin 设置里把
"Custom git binary path" 改成 `which git` 的输出（一般是 `/opt/homebrew/bin/git`）。

手机端 Obsidian 是另一套链路（isomorphic-git），需要在 plugin 设置里直接贴 PAT；本地
桌面单点用不到。

### 推荐 plugin 配置

| 设置项 | 值 | 作用 |
|---|---|---|
| Vault backup interval (minutes) | `30` | 自动 commit + push 间隔 |
| Auto pull interval (minutes) | `10` | 自动 pull，避免冲突堆积 |
| Pull updates on startup | ✓ | 开 Obsidian 时立即 sync |
| Pull before push | ✓ | 推前先拉，减少 reject |
| Commit message | `vault: {{date}} ({{numFiles}} files)` | 模板 |
| Date placeholder format | `YYYY-MM-DD HH:mm` | 给 `{{date}}` 用 |

### 链路全景

```
next-signal knowledge ingest
  → fetch + clean + classify + persist
  → 写 wiki/<category>/<slug>/<slug>.md + images/
  → gbrain put + embed   ← 失败这里 loud fail，但 artifact 留在磁盘
  → 成功 → next-signal 收工，wiki 文件留下
       ↓ (next-signal 不再参与)
Obsidian Git plugin（每 30 min）
  → git add -A && git commit && git push
```

## 规范与状态

规范：[`openspec/specs/knowledge-pipeline/`](../../../openspec/specs/knowledge-pipeline/)、
`knowledge-search-tool`、`knowledge-reindex`、`knowledge-review`、
`dashboard-knowledge-ingest`、`dashboard-knowledge-review`。

当前状态：artifact pipeline、GBrain ingest/search、weekly re-ingest workflow baseline、
`next-signal doctor` GBrain health check、间隔重复回顾层（`knowledge_reviews` 表、固定艾宾浩斯
曲线、`next-signal knowledge review`、`/knowledge` 回顾区块）、dashboard `/knowledge` redesigned
页面均已就位。
Dashboard 端提供 wiki tree、ANN search、preview pane 和 `Re-index` 触发；界面文案走
dashboard i18n（默认英文，可切中文），wiki 文档内容本身不翻译。

`/knowledge` 的 wiki tree 支持文件管理（纯 dashboard，server action）：嵌套展示真实目录
（含空目录；per-article `<slug>/<slug>.md` 折叠成单文档），行内 hover 出删除按钮 + 确认弹窗。
**新建文件夹** = 建目录 + 把 path 追加进 `configs/knowledge_taxonomy.yaml`（文本行 splice，
保留注释与对齐，不整篇 reserialize）；**删除文件夹/文件** 只删 wiki 文件（删文件夹再 prune 对应
taxonomy 条目），**不碰 GBrain 索引和 raw 归档**——索引一致性靠 `Re-index`。tree/taxonomy 改写
逻辑在 `dashboard/lib/wiki.ts` + `dashboard/lib/taxonomy.ts`，action 在
`dashboard/lib/actions/knowledge.ts`（路径穿越校验 + `revalidatePath`）。

`/knowledge` 还有一个入库表单（URL 输入 + 可选 folder `<select>`，按 taxonomy namespace
分组、option `title` 显示 scope）和「进行中的入库」面板。两个入库入口（knowledge 表单 +
`/radar` 的 Ingest to wiki）都走 dashboard 的共享内存 job registry（`lib/ingest/jobs.ts`，
spawn `next-signal knowledge ingest … --progress`），面板通过 SSE（`/api/knowledge/ingest/stream`）
订阅，按 source 标签实时显示 fetch/clean/enrich/classify/persist 五步进度。

`/radar` 入口会先把 radar row 解析成普通 ingest 输入：Folo source 用 `source_id` 调
`folocli entry get` 拉全文，stage 为 `NEXT_SIGNAL_AGENT_TMP_DIR/radar-ingest/*.html` 后 ingest；
非 Folo source 校验 `radar_items.url` 后直接 ingest URL。knowledge pipeline 本身不认识
`radar://` 这类内部引用，只处理 URL 或 staged file。registry 是单进程内存态：dashboard
重启会丢掉进行中 job 的进度视图（子进程和 artifact 写入不受影响）。runner 防御性跳过
非事件 JSON 行（structlog 默认写 stdout）。
