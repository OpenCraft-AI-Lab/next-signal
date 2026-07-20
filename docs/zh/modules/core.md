# 模块：core（框架底盘）

> [English](../../modules/core.md) · **中文**

## 解决什么

所有 runnable 共用的基础设施：模型工厂与回落、数据库连接、shared context、
per-provider 并发。改任何业务模块之前先懂这一层——两个产品模块
（[knowledge](./knowledge.md) / [info_filter](./info_filter.md)）
的 agent、表、embedding 全部跑在它上面。

## 代码位置

- `src/paca/core/models.py` —— 模型工厂（profile → agno Model）+ embedder + OMLX 端点
- `src/paca/core/config.py` —— 全部 YAML loader（strict pydantic，未知 key loud fail）
- `src/paca/core/db.py` —— `database_url()` + agno 自管表的 `get_db()` 单例
- `src/paca/core/context.py` —— shared context 拼接
- `src/paca/core/concurrency.py` —— per-provider 推理并发 semaphore
- `src/paca/core/paths.py` / `logging.py` / `fileio.py` —— 路径约定 / structlog / 原子写

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
  结果是 lru-cached 的——**OMLX 恢复后必须 `paca.core.models.reset_cache()` 才会重试本地**，
  长驻进程（`paca serve`）尤其注意。
- OMLX 端点只从 `paca.core.models.omlx_endpoint()` 读（`OMLX_BASE_URL` / `OMLX_API_KEY`），
  其他地方不要复制这段读取逻辑。
- Qwen3 细节固化在 `_build_omlx`：关 thinking、sampling 参数、结构化输出走 OpenAI 标准
  `response_format` json_schema（OMLX 侧 xgrammar 约束解码），agno 的 native structured
  outputs 保持关闭。
- DeepSeek 走 `_build_deepseek`：OpenAI 兼容（`DEEPSEEK_API_KEY` + 可选 `DEEPSEEK_BASE_URL`，
  默认 `https://api.deepseek.com`），但只支持 `response_format` json_object、不支持 json_schema，
  所以 schema 经 prompt 传递、由 `run_structured` 解析/校验/修复。
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

- **agno 自管表**（sessions / memory / knowledge / traces）→ `paca.core.db.get_db()` 单例。
  URL 走 `database_url(for_sqlalchemy=True)`，自动把 scheme 改写成
  `postgresql+psycopg://`（psycopg v3）。agno 自动建表，不要重复定义。
- **业务表**（`radar_items` / `radar_analyses` / `radar_pushed_topics`）→ 裸
  `psycopg.connect(database_url())` 的同步 short-lived 连接；DDL 集中在
  `scripts/bootstrap_db.py`，运行时读写在对应模块的 store / tool 里。

## Shared context

`prompts/_shared/*.md` 按文件名字母序拼接（两位数前缀控顺序：`00_house_rules.md`、
`10_user_profile.md`），以 markdown 横线分隔，prepend 到**每个 agent** 的 instructions 头部
（`paca.core.context.shared_context()`）。

- `_*.md` 前缀：**不加载**也不提交——纯草稿。
- `99_*.md`：**会加载**（排序在最后）但被 gitignore——本地个人层，机器有效、仓库无痕。
- import 时读一次并缓存；dashboard 热加载路径调 `reload()`。
- 单个 agent 退出继承：YAML `extra: {shared_context: false}`（纯转换 / 判定类 agent 均退出，
  另配 `extra: {db: false}` 不建会话库）。

## 不变量

- `core` 不 import 任何上层（tools / integrations / workflows / agents）。
- env 一律 call time 读，不在 import time——缺 key 不能阻断启动。
- 失败要 loud：配置缺失 / 端点配置坏 → `RuntimeError`，不静默 default。
- telemetry 全关：`AgentOS(telemetry=False)`，直接构造 `Agent` 也要 `telemetry=False`。

agent / 工具的全景清单不在文档里维护：`uv run paca list` 列 runnable，
`src/paca/registry.py` + 各 `tools/<domain>/register()` 是工具面的 source of truth。

## 规范

[`openspec/specs/core-models/`](../../../openspec/specs/core-models/)、`core-database`、
`core-agents`、`core-tools`、`core-integrations`、`core-agent-os`、`core-cli`。
state 目录与日志位置见 [运维文档](../operations.md#state-位置)。
