# 模块：knowledge（知识管理）

> [English](../../modules/knowledge.md) · **中文**

## 解决什么

把 URL 和文件变成持久的 markdown artifact 和可检索的长期知识。
clean markdown 进 wiki 树，raw 原件归档，GBrain 做索引和 hybrid search。

## 代码位置

`src/paca/tools/knowledge/` —— agent-facing knowledge tools。
`src/paca/integrations/knowledge/` —— OpenCLI (WeChat) / Bilibili / GitHub adapters。
`src/paca/workflows/knowledge_ingest.py` —— centralized workflow factory。
`src/paca/workflows/stages/knowledge_ingest/` —— workflow-private pipeline stages。
`src/paca/workflows/knowledge_review/` —— 间隔重复回顾调度器（`__init__.py` 放曲线 +
reconciliation，`store.py` 放 Postgres I/O）。

## Agents

| agent | 模型 profile | 用途 |
|---|---|---|
| `knowledge_artifact_editor` | local | ingest 的 clean 步：正文清洗 / whisper 纠错（DB-free 转换 agent） |
| `knowledge_github_cleaner` | local | github repo 专用 clean 步：只对 `## README` 段做激进精简（去 badge / 安装命令 / sponsor 等），结构化 signal section 原样保留 |
| `knowledge_frontmatter` | local | ingest 的 enrich 步：产出 title/summary/tags/freshness（`FrontmatterDraft` schema，DB-free）。locale-aware：`.zh.md` / `.en.md` 变体按 ingest locale 生成 title/summary |
| `knowledge_github_summary` | local | github repo 专用 enrich 步：summary 按 does/value/maturity/ecosystem 四个角度组织，复用 `FrontmatterDraft` schema。locale-aware（`.zh.md` / `.en.md`） |
| `knowledge_tag_translator` | local_structured | best-effort：把英文 tag key 翻成本地化显示标签（`TagLabel` schema），按 `(tag, locale)` 缓存进 `knowledge_tag_labels` |
| `knowledge_classifier` | local | ingest 时按 taxonomy 选 wiki 分类目录（DB-free 转换 agent） |

## 工具

knowledge 领域工具：

- `knowledge_ingest_workflow` —— 单篇入库路径（fetch → clean → enrich → classify → persist）。

KB **检索**是横向基础设施（不在本模块）：`search_knowledge` 在
`paca/tools/knowledge/search.py`；`gbrain_search` / `gbrain_get` / `gbrain_query` /
`gbrain_ingest` 在 `paca/tools/gbrain.py`；GBrain bridge 在
`paca/integrations/gbrain.py` —— 任何模块的 agent 都能按名字引用这些工具。

## 接的外部

- **OpenCLI** —— 微信公众号图文入口。本地 `node opencli weixin download` subprocess，
  下载文章 + 图片到 raw store，按 slot 索引把 markdown 里的图片链接重写成本地相对路径。
  `OPENCLI_BIN` 必填，在 call time 读。
- **MarkItDown** —— YouTube / PDF / HTML / Office / text-like 文件转 markdown
  （横向 adapter：`paca/integrations/markitdown.py`）。
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
  （`paca/integrations/gbrain.py`），不是本模块独占。
- **Obsidian Git plugin** —— wiki repo ↔ GitHub 同步走 vault 内的 plugin，
  不在 paca 进程里。详见下面 "Wiki ↔ GitHub 同步" 一节。

## 数据存哪

- clean wiki：`~/Projects/digitalpaca-wiki/`
- raw 归档：`~/Projects/digitalpaca-wiki-raw/`
- re-ingest manifest：`~/.next-signal/knowledge_ingest_manifest.json`
- 回顾调度：`knowledge_reviews` 表（Postgres）
- 索引：GBrain 自管本地存储

## 怎么用

```bash
uv run paca knowledge ingest <url|staged-file>
uv run paca knowledge ingest <url> --category knowledge/ai-ml   # 指定落点文件夹（跳过自动分类）
uv run paca knowledge ingest <url> --progress                   # 每个 pipeline step 一行 JSON 事件 + 末行结果 JSON
uv run paca knowledge gbrain-search "query"
uv run paca run-workflow knowledge_ingest            # re-ingest 变更文件 + 刷新所有 Related 区块
uv run paca knowledge review                         # 对照 wiki 与 knowledge_reviews（入列新的 / 移除已删的）
```

`--category` 必须是 `configs/knowledge_taxonomy.yaml` 里的某个 path，非法值在 fetch 之前
loud fail。`--progress` 给 dashboard 的入库进度面板用（见下）。
本地文件输入只接受 `PACA_AGENT_TMP_DIR` 下的 staged file；`/radar` 的 Folo ingest 也遵守
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
- **卡片内容** —— 卡片直接复用文档自己的 frontmatter `summary`（入库时写进 frontmatter 和
  canonical `## Summary` 那段的收尾摘要、渲染时本地化），所以回顾层**不调 LLM**、行里也不存生成文本。手写、没有 `summary`
  的文档回退到正文首段。
- **对账（reconciliation）** —— `paca knowledge review` 遍历 wiki，把未知文档入列
  （按曲线 seed），把文件已删的行移除。wiki 根缺失或空时直接拒绝，而不是把 "没有文件" 读成
  "全部删了"。`captured_at` 从 frontmatter 解析，优先级 `captured_at` → `updated_at` →
  `created_at` → mtime，与 dashboard wiki 视图一致。

投放形态是 `/knowledge` 顶部（入库表单之上）的一个区块，最多五张卡、最久过期在前，
并标出剩余数量。点击卡片会在页面的预览面板里打开该文档全文并滚动过去（`#doc-preview`），所以回顾是重读原文而非仅仅提醒——打开不推进阶段。"已回顾" 是 POST server action，在请求内推进阶段（GET 会让 prefetch
推进曲线）；刷新控件把 `--sync` 任务 detached 起，因为对账加要点生成是 LLM 活。

## 不变量

- 回顾状态完全存在 `knowledge_reviews`；回顾层从不写任何 wiki markdown 文件（含
  frontmatter）。`doc_path`（wiki 相对路径）是身份，靠对账而非外键与文件系统保持一致。
- GBrain ingest 失败不能丢 artifact：clean wiki / raw 文件保留在磁盘，workflow loud fail。
  不把这次运行标成成功；修好 GBrain 后靠 direct ingest / weekly sync 补索引。
- re-ingest manifest 只在成功索引后才前进，否则后续不重试、KB search 会 stale。
- 直接 ingest 和 re-ingest 必须从 wiki-relative path 推出同一个 GBrain-safe slug；
  非 ASCII 路径要补稳定 hash 后缀避免 GBrain page 撞车。
- wiki 文件名由**来源标题**（`source_title`，LLM 之前的原标题）派生，**不是**本地化后的
  `title`——这样同一来源在不同 locale 下保持同一个稳定 slug 和 GBrain 标识。frontmatter 记
  `digest`（来源 hash）作为同源标识：同源 re-ingest 原地覆盖（幂等更新）；同名标题但不同来源
  时新文件追加 `-<digest[:8]>` 后缀，绝不静默覆盖别人的文章（两种目录布局间的撞车也算）。
- **本地化按条目走，存储保持 canonical。** 存下来的 `.md` 与 locale 无关：frontmatter 的
  KEY 是英文、枚举 token 是英文（`status: clean`、`freshness`、`source_type`、`converter`）、
  tag KEY 是英文、`## Summary` / `## Related` 标题也是 canonical 英文。随 locale 变的 LLM 文本
  ——`title` 和 `summary`——按 ingest 的 `--locale` 生成，并记进 `locale` frontmatter 字段；
  LLM 之前的原标题保留为 `source_title`。来源信息（`source_url` / `published` / `author`）以
  结构化 frontmatter 存储，radar 入库时从暂存的 `<stem>.meta.json` sidecar 读取（不再把英文
  标签块烤进正文）。dashboard 按条目自己的 `locale` 本地化每一个标签——frontmatter 的
  key/value 标签、两个标题、以及 tag 显示别名（来自 `knowledge_tag_labels`，由
  `knowledge_tag_translator` 按 `(tag, locale)` 生成一次、best-effort）——所以每个条目都整体
  以它自己的语言渲染，与 UI cookie 无关。切换 UI 语言不会重译已有条目；换个 locale 重新入库
  才会重生成文本。两份 `knowledge_frontmatter.{zh,en}.md`（和
  `knowledge_github_summary.{zh,en}.md`）prompt 变体要结构同步。
- `knowledge_artifact_editor` 失败不能产出 deterministic fallback 内容。
- WeChat artifact 走 per-article 目录布局（`<category>/<slug>/<slug>.md` + 同目录 `images/`）；
  `gbrain_slug_for_path` 折叠这层重复目录，保证 GBrain slug 跟平铺布局产出相同。
- 每篇 wiki 文章末尾的 `<!-- gbrain:related ... -->` marker 块是 GBrain-driven 的派生数据，
  ingest 时按 title+summary 跑一次 hybrid query 写入，weekly sync 全量刷新；marker 块内
  内容**不要手编辑**，正文其他位置随便改。Related 列表是 `[[wiki/path/Note]]` 显式
  wikilink，Obsidian 自动渲染 + Backlinks 面板联动，GBrain `extract` 反向同步成 typed edge。

## Wiki ↔ GitHub 同步

`digitalpaca-wiki/` 到 GitHub 的同步**不在 paca 进程里**，由 vault 内的
[Obsidian Git plugin](https://github.com/Vinzent03/obsidian-git) 负责，跟 paca 完全解耦。
paca 这边只保证 wiki 落盘那一刻跟 GBrain 同步成功；剩下定时推到 GitHub 是 plugin 的事。

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
paca knowledge ingest
  → fetch + clean + classify + persist
  → 写 wiki/<category>/<slug>/<slug>.md + images/
  → gbrain put + embed   ← 失败这里 loud fail，但 artifact 留在磁盘
  → 成功 → paca 收工，wiki 文件留下
       ↓ (paca 不再参与)
Obsidian Git plugin（每 30 min）
  → git add -A && git commit && git push
```

## 规范与状态

规范：[`openspec/specs/knowledge-pipeline/`](../../../openspec/specs/knowledge-pipeline/)、
`knowledge-search-tool`、`knowledge-reindex`、`knowledge-review`、
`dashboard-knowledge-ingest`、`dashboard-knowledge-review`。

当前状态：artifact pipeline、GBrain ingest/search、weekly re-ingest workflow baseline、
`paca doctor` GBrain health check、间隔重复回顾层（`knowledge_reviews` 表、固定艾宾浩斯
曲线、`paca knowledge review`、`/knowledge` 回顾区块）、dashboard `/knowledge` redesigned
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
spawn `paca knowledge ingest … --progress`），面板通过 SSE（`/api/knowledge/ingest/stream`）
订阅，按 source 标签实时显示 fetch/clean/enrich/classify/persist 五步进度。

`/radar` 入口会先把 radar row 解析成普通 ingest 输入：Folo source 用 `source_id` 调
`folocli entry get` 拉全文，stage 为 `PACA_AGENT_TMP_DIR/radar-ingest/*.html` 后 ingest；
非 Folo source 校验 `radar_items.url` 后直接 ingest URL。knowledge pipeline 本身不认识
`radar://` 这类内部引用，只处理 URL 或 staged file。registry 是单进程内存态：dashboard
重启会丢掉进行中 job 的进度视图（子进程和 artifact 写入不受影响）。runner 防御性跳过
非事件 JSON 行（structlog 默认写 stdout）。
