# 模块：core（框架底盘）

> [English](../../modules/core.md) · **中文**

## 解决什么

所有 runnable 共用的基础设施：模型工厂与回落、数据库连接、shared context、
per-provider 并发。改任何业务模块之前先懂这一层——两个产品模块
（[knowledge](./knowledge.md) / [info_filter](./info_filter.md)）
的 agent、表、embedding 全部跑在它上面。

## 代码位置

- `src/next_signal/core/models.py` —— 模型工厂（profile → agno Model）+ embedder + OMLX 端点
- `src/next_signal/core/config.py` —— 全部 YAML loader（strict pydantic，未知 key loud fail）
- `src/next_signal/core/db.py` —— `database_url()` + agno 自管表的 `get_db()` 单例
- `src/next_signal/core/context.py` —— shared context 拼接
- `src/next_signal/core/concurrency.py` —— per-provider 推理并发 semaphore
- `src/next_signal/core/paths.py` / `logging.py` / `fileio.py` —— 路径约定 / structlog / 原子写

## 模型体系

`configs/models.yaml` 是唯一事实源。agent YAML 用 profile 名引用模型；Python 里绝不直接
`Claude(...)` / `OpenAILike(...)`。

| profile | provider / model | 用途 |
|---|---|---|
| `local` | OMLX Qwen3.5-122B（max_tokens 32768） | 默认：对话、成文、研究 |
| `local_structured` | 同一模型，**max_tokens 4096** | 结构化输出（`output_schema`）agent 专用 |
| `deepseek_smart` | deepseek-v4-flash | `local` 的回落目标（OMLX 不可达时） |
| `deepseek_structured` | deepseek-v4-flash（max_tokens 4096） | `local_structured` 的回落目标 |
| `claude_smart` | claude-sonnet | 备用云 profile |
| `claude_fast` | claude-haiku | 轻量云任务 |

- **`local_structured` 的紧 cap 不要放宽**：xgrammar 约束解码偶尔病态循环到 cap 才停，
  4096 把 10 分钟挂死变成 ~100s 的干净失败，交给各 pipeline 的 per-item 错误隔离。
  放宽实验做过、无效，结论固化在 `configs/models.yaml` 注释里。
- **回落链**：构建 provider 时抛 `RuntimeError`（典型：OMLX 端点不可达）→ 自动改建
  `fallback_profile`；`KeyError` / `ValueError`（程序员错误）不回落、直接抛。
  结果是 lru-cached 的——**OMLX 恢复后必须 `next_signal.core.models.reset_cache()` 才会重试本地**，
  长驻进程（`next-signal serve`）尤其注意。
- OMLX 端点只从 `next_signal.core.models.omlx_endpoint()` 读（`OMLX_BASE_URL` / `OMLX_API_KEY`），
  其他地方不要复制这段读取逻辑。
- Qwen3 细节固化在 `_build_omlx`：关 thinking、sampling 参数、结构化输出走 OpenAI 标准
  `response_format` json_schema（OMLX 侧 xgrammar 约束解码），agno 的 native structured
  outputs 保持关闭。
- DeepSeek 走 `_build_deepseek`：OpenAI 兼容（`DEEPSEEK_API_KEY` + 可选 `DEEPSEEK_BASE_URL`，
  默认 `https://api.deepseek.com`），但只支持 `response_format` json_object、不支持 json_schema，
  所以 schema 经 prompt 传递、由 `run_structured` 解析/校验/修复。
- **DeepSeek thinking mode 默认开启（effort "high"）**——deepseek-v4-flash/-pro 的 API 行为，
  reasoning token 按普通 output token 计费，不设置就默默变慢变贵。按 profile 用
  `extra.reasoning_effort`（`"low"`/`"high"`/`"max"`，原样传进请求体）调，或用
  `extra.extra_body.thinking.type: disabled` 整个关掉。`deepseek_smart` 设了
  `reasoning_effort: low`；`deepseek_structured` 直接关掉 thinking——它的 4096
  max_tokens cap 下，默认 high-effort 推理可能在真正吐 JSON 答案之前就把预算耗尽。
- **embedder**（`models.yaml::embedders.local`）：Qwen3-Embedding-0.6B-8bit，**1024 维**，
  与 `radar_pushed_topics.embedding` 的 `vector(1024)` 列对齐；
  换不同维度的模型需要列迁移。

## 并发

`models.yaml::concurrency` 给每个 provider 一个并发上限（`omlx: 2` —— 本地单 GPU；
云端 64/32 只防 runaway loop）。模型工厂产出的每个 model 的
`response` / `aresponse` / 两个 stream 入口都裹了对应 provider 的 semaphore；
embedder 调用也占同一配额（本地 LLM 和 embedding 共抢一块 GPU）。
所有经由工厂的 agent / workflow / tool 自动继承，不需要各处自管。

## 数据库双路径

按用途选，不混用：

- **agno 自管表**（sessions / memory / knowledge / traces）→ `next_signal.core.db.get_db()` 单例。
  URL 走 `database_url(for_sqlalchemy=True)`，自动把 scheme 改写成
  `postgresql+psycopg://`（psycopg v3）。agno 自动建表，不要重复定义。
- **业务表**（`radar_items` / `radar_analyses` / `radar_pushed_topics` / `radar_recaps` /
  `knowledge_reviews`）→ 裸
  `psycopg.connect(database_url())` 的同步 short-lived 连接；DDL 集中在
  `scripts/bootstrap_db.py`，运行时读写在对应模块的 store / tool 里。

## Shared context

`prompts/_shared/*.md` 按文件名字母序拼接（两位数前缀控顺序：`00_house_rules.md`、
`10_user_profile.md`），以 markdown 横线分隔，**append** 到每个 agent 的 instructions 末尾
（`next_signal.core.context.shared_context()`）。

- `_*.md` 前缀：**不加载**也不提交——纯草稿。
- `99_*.md`：**会加载**（排序在最后）但被 gitignore——本地个人层，机器有效、仓库无痕。
- import 时读一次并缓存；dashboard 热加载路径调 `reload()`。
- 单个 agent 退出继承：YAML `extra: {shared_context: false}`（纯转换 / 判定类 agent 均退出，
  另配 `extra: {db: false}` 不建会话库）。

agent 自己的 instructions 在最前，shared 块作为限定条件跟在后面，这样它不会盖过 agent 被
检验的字段契约。注意语言规则该待的位置和这里相反——见下一节。

## 输出语言

每个要为读者写**散文字段**的 agent 都在自己的 YAML 里声明一个语言 policy
（`extra.output_language`），由 `next_signal.core.language` 解析：

- `off`——完全不加语言规则（裸 `false` 出于向后兼容也等价于这个）。用于不产出散文的
  agent：输出会被丢弃的（`radar_dedup_judge`），或输出是标识符而非散文的
  （`knowledge_classifier`，它唯一的输出是从输入里逐字复制的一条 taxonomy 路径）。
  这**不是**白省 prompt——把规则从 `knowledge_classifier` 拿掉实测会改变边界情况的归档
  结果（见 [knowledge.md](./knowledge.md#输出语言)），所以 `off` 是一个行为选择，不只是
  省开销。
- `global`——从实时偏好文件（`~/.next-signal/language.json` 的 `content_language`）解析；
  该文件不存在时回落到硬编码的 `"en"`。**不**读 `.env`——已退役的 `SIGNAL_OUTPUT_LANG`
  机制。写这个文件的是 dashboard 的**设置面板**（nav 上的语言按钮不写——那个只管界面
  文案）；容器启动时的一个钩子在文件缺失时播种它。所有**写给读者看的**输出都用这条
  policy：info-radar 里三个输出会被展示的 agent（`radar_tier1_filter`、
  `radar_tier2_impact`、`radar_recap`——`radar_dedup_judge` 是 `off`），加上两个
  frontmatter agent——它们的 `title`/`summary` 是条目的索引项。
- `same_as_source`——从调用方传入的 `language=` override 解析，不读任何全局设置；调用方
  （某个 workflow stage）必须传入，否则 build agent 时 `RuntimeError`。只有两个 agent 用
  它，即知识库的两个正文清洗 agent：目标是**文章自己的**语言，由
  `next_signal.core.language_detect.detect_language()` 对每个条目探测一次——一个确定性、非 LLM 的
  Unicode 文字比例启发式，绝不用 LLM 调用（让 LLM 自己判断该用什么语言,会重新引入这套
  机制本要消除的那种采样方差问题）。
- `fixed:<lang>`——一个字面量、无条件的目标，忽略偏好文件和任何 override。

以下机制从原来的单一 env var 版本原样继承：

- call time 解析（从不缓存），偏好文件一改，下次 build agent 就生效，不需要 `reload()`。
- 两种投递方式。prompt 里写了 `{{OUTPUT_LANGUAGE}}` 的，由 `language_name()` 就地替换成语言
  名，规则留在作者放的位置，prompt 自己的收尾句（`Return JSON`、`Do NOT pad`）仍然在最后；
  没写 token 的，才把 `language_rule()` 的块 append 在 shared context 之后。
- append 到 prompt 收尾句**之后**这个做法实测被否：在 55 条 holdout 上让 `impact` 输出长了
  约 31%，截断从 2/165 涨到 7/165（撞 `max_tokens` 上限）。新 prompt 优先用 token。
- prompt 写了 token 但 YAML 又设了 `output_language: off` → `RuntimeError`，
  否则字面量 token 会直接送到模型面前。
- 与 `shared_context` **相互独立**地控制。所有生产 agent 都关掉了 shared context 但仍然
  需要语言规则；把两者绑一起等于强行给结构化输出 agent 灌 house rules。
- 标识符字段豁免：`tags` 在任何语言下都保持小写英文——不是走这套机制,而是两个 frontmatter
  agent 各自 prompt 里针对该字段的专门指令,因为 `_normalize_tags` 会静默丢弃含 CJK 的
  tag。曾经试过在注入的规则里加一条针对具体字段的分句,实测更差（输出长 35%,截断从
  1/65 涨到 6/65），所以这套机制刻意每次调用只表达一个目标语言——某个字段需要不一样,
  就留在 prompt 层面单独处理,不做成 policy 开关。
- 两条 policy 的分界线是**输出物是什么**，不是它属于哪个模块。
  `knowledge_artifact_editor` / `knowledge_github_cleaner` 输出的是文章正文本身——wiki 里
  源文本的唯一副本——所以用 `same_as_source`，永不翻译，但目标语言仍是显式给定的，不依赖
  模型的默认倾向。**同一条目**的 frontmatter agent 则用 `global`，因为 `title`/`summary`
  是读者浏览的生成散文，不是存档文本。因此一个 wiki 文件可以是双语的：英文索引项配中文
  正文。这是有意的，也和 radar 阅读器一致——那边早就是翻译过的标题配源语言文章。
  `radar_dedup_judge` 仍是 `off`：它的 `reason` 既不入库也不渲染。
- 规则刻意写成无条件句——条件句形式（"如果 goals 是中文…"）在中文 goals + 英文文章下实测
  tier-2 summary 命中 0/64，改成无条件后 63/63。
- 两个读者，两种失败模式，这是有意的：`next_signal.core.language` 在偏好文件损坏或值不认识时
  抛错，因为 pipeline 不能用一个没人选过的语言生成内容。dashboard 自己的读取器
  （`lib/actions/language.ts::getContentLanguage`）则改成 log + 回落到默认值——nav 在每个
  页面都渲染，在那里抛错会让整个 dashboard 挂掉，包括用来修这个值的那块设置面板。
  `next-signal doctor` 仍然是唯一那个 loud 的检查。

## 不变量

- `core` 不 import 任何上层（tools / integrations / workflows / agents）。
- env 一律 call time 读，不在 import time——缺 key 不能阻断启动。
- 失败要 loud：配置缺失 / 端点配置坏 → `RuntimeError`，不静默 default。
- telemetry 全关：`AgentOS(telemetry=False)`，直接构造 `Agent` 也要 `telemetry=False`。

agent / 工具的全景清单不在文档里维护：`uv run next-signal list` 列 runnable，
`src/next_signal/registry.py` + 各 `tools/<domain>/register()` 是工具面的 source of truth。

## 规范

[`openspec/specs/core-models/`](../../../openspec/specs/core-models/)、`core-database`、
`core-agents`、`core-tools`、`core-integrations`、`core-agent-os`、`core-cli`。
state 目录与日志位置见 [运维文档](../operations.md#state-位置)。
