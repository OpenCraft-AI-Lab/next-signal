# Codex 工作指南

This file is read by Codex on every session. Keep it short and high-signal —
it's not project documentation, it's instructions for the AI assistant working here.

> 人类文档：[`docs/`](./docs/architecture.md)（英文标准版；中文镜像在 [`docs/zh/`](./docs/zh/architecture.md)） ·
> 能力规格：[`openspec/specs/`](./openspec/specs/) · 待办变更：[`openspec/changes/`](./openspec/changes/)

**文档双语，英文是标准版本。** 英文在 `README.md` + `docs/` + `dashboard/README.md`，
中文镜像在 `README.zh-CN.md` + `docs/zh/` + `dashboard/README.zh-CN.md`（结构一一
对应，每页顶部有语言切换链接）。**所有面向人的文档都必须两版齐全**，改文档时
**两个语言在同一个 change 里一起改**——只改一边就是没改完。

有意不翻的两处：本文件（agent 指令，只中文）和 `openspec/specs/`（能力契约，只英文）。

---

## 项目本质

`next-signal`（Python 包名 `paca`）。
本地优先的 info-radar + knowledge 框架，基于 agno 2.6+ 构建。
单一 AgentOS 进程承载所有 agent / workflow，从 CLI 调用；Dashboard 是独立
Next.js 进程。agno 会话 / trace / 记忆存在本地 Postgres + pgvector；用户可手改的运行时
状态优先放 `~/.next-signal/`。本地模型优先用 OMLX (Qwen3)，云模型作为回落。

---

## 工作原则（meta，优先级最高）

四条贯穿所有任务的元规则。下面"代码组织铁律"/"不要做的事"/"错误处理风格"等节都是这些原则在
paca 项目里的具体落地——具体规则与原则冲突时，**原则赢**。

### 1. 先想再写

不假设、不藏困惑、显式列 trade-off：

- 假设说出来；不确定就问，不要默默 pick 一个解释跑下去
- 多个合理解读 → 列给用户挑，不要替用户选
- 看到更简单的路径 → 说出来；该 push back 就 push back
- 看不懂就停下、说清楚哪里看不懂、问

### 2. 最简实现

解决问题需要的**最少代码**，不写未来可能用的东西：

- 不加用户没要求的功能 / 抽象 / 可配置性
- 不为不存在的场景写错误处理（与下面"防御性代码"规则同义）
- 200 行能压成 50 行就重写
- 高级工程师会说"过度复杂"吗？会就简化

### 3. 外科手术式修改

只动该动的，只清自己留下的烂摊子：

- 改 A 时不"顺手"美化邻近的 B 的格式 / 注释 / 代码
- 别 refactor 没坏的东西
- 跟现有风格走，哪怕你觉得不好看
- 看到无关 dead code → 提一句，**不要**直接删
- 自己改动产生的孤儿 import / 变量 / 函数 → 清掉

测试：每一行 diff 都能直接对应到用户的请求。

### 4. 目标驱动闭环

把任务变成可验证目标，自己跑闭环到 verified：

- "加 validation" → "先写非法输入的 test，再让它过"
- "修这个 bug" → "先写复现 test，再让它过"
- "Refactor X" → "改前改后 test 都过"

多步任务先简单列计划，每步配 verify check。强 verify 标准 = 能独立闭环；弱标准（"能跑就行"）
= 回头反复确认。

---

## 工具链与命令

**永远用 `uv` 跑 Python**，不要直接用 `python` / `pip` / `pytest`：

```bash
uv sync                    # 同步依赖（改了 pyproject 后跑）
uv run paca <subcommand>     # 跑 CLI
uv run pytest -q           # 测试
uv run ruff check src      # lint（如配置）
uv add <pkg>               # 加依赖（自动写 pyproject + uv.lock）
uv add --dev <pkg>         # 加 dev 依赖
```

**不要**手动编辑 `uv.lock`。

### OpenSpec slash aliases

`/opsx:<name> ...`（`explore` / `propose` / `apply` / `archive`）= 读
`.claude/commands/opsx/<name>.md`，严格按其 workflow 走；status / 校验用本地 `openspec` CLI。

**默认工作流**：非平凡的能力开发先 `/opsx:propose` 起一个 change（写
proposal / design / tasks），再实现；完成后 `/opsx:archive` 把 delta 合进
`openspec/specs/`。判断"非平凡"：

- 非平凡（需要 change）：加 / 删一个 agent、tool、integration、workflow；新
  CLI 子命令；改变某个已有 capability 的行为或契约（`openspec/specs/`
  里已经描述过的东西变了）
- 平凡（可直接改，不需要 change）：bug fix、行为不变的纯 refactor、typo、
  格式化、单个 prompt 文案微调、补测试

不确定属于哪类 → 按非平凡处理，先问或先 `/opsx:propose`，不要默默直接改。

CLI 子命令：
- `paca list` — 列 agents / workflows
- `paca doctor` — 自检 .env / Postgres / OMLX / 注册的 tools / GBrain health / folocli auth / info-radar goals.yaml
- `paca run-agent <name> "<prompt>"` — 一次性调某个 agent
- `paca knowledge ingest <url|file>` — 路由输入、保存 raw / clean markdown、可选导入 GBrain
  （`--category <taxonomy-path>` 指定落点跳过自动分类；`--progress` 每步输出一行 JSON 事件，dashboard 入库进度面板用）
- `paca knowledge gbrain-search|gbrain-ingest` — 通过本地 GBrain CLI 搜索 / 导入 markdown
- `paca knowledge review` — 对照 wiki 与 `knowledge_reviews`（入列新文档、移除文件已删的行）；回顾卡片直接用文档 frontmatter 的 `summary`，不调 LLM（固定艾宾浩斯曲线）
- `paca info-radar pull [--source NAME]` — 跑一次 info-radar 各 source 的 CLI，写入 `radar_items`
- `paca info-radar sweep` — 删除 30 天前的 `radar_items` 行
- `paca info-radar analyze [--limit N] [--source NAME]` — 跑 info-radar analysis 两层 pipeline，写 `radar_analyses`
- `paca info-radar recap --since D --until D [--min-score N] [--novel-only] [--regenerate]` — 把区间内 kept 信号归纳成 3-5 条带引用的主线，缓存进 `radar_recaps`（按 `(since, until, min_score, novel_only)` 幂等）
- `paca info-radar subscriptions --json` — 读取 Folo 订阅，输出 dashboard 稳定 JSON 行
- `paca run-workflow <name>` — 通过 workflow 的 `extra.run_now` 手动跑一次（dashboard re-index 走 `paca run-workflow knowledge_ingest`）
- `paca serve` — 启动 AgentOS（端口 7777）

---

## 代码组织铁律

依赖方向严格向下，不允许反向 import：

```
interfaces  →  orchestrator / workflows / teams / agents  →  tools  →  integrations  →  core
```

- `core` 不能依赖任何上层。
- `tools` 可以编排 `integrations`（向下依赖 OK）；`integrations` 不能反向 import `tools` / agents。
- workflow 可以组合 agents / tools / workflow-private stages；私有 stage 放
  `paca/workflows/stages/<workflow>/`。
- 如果发现需要 `core` import `tools`，或 integration 反向 import tool / agent，停下来重新设计。

### runnable / tools / integrations

repo = runnable orchestrator 底盘 + 按领域组织的 tools / integrations / workflows：

- **runnable**：agent / workflow / team。配置分别在 `configs/agents/`、
  `configs/workflows/`、`configs/teams/`；prompt 分别在 `prompts/agents/`、
  `prompts/workflows/`、`prompts/teams/`。当前没有 shipped team——`configs/teams/`
  为空，加新团队方向时才会用到这层。
- **workflow 实现**：集中在 `paca/workflows/`；只服务某个 workflow 的 stage 放
  `paca/workflows/stages/<workflow>/`。
- **领域工具**：agent-facing 业务动作放 `paca/tools/<domain>/`，由该 package 的
  `register()` 暴露给 registry；横向工具直接放 `paca/tools/`。
- **领域集成**：provider adapter 放 `paca/integrations/<domain>/`；横向 adapter 直接放
  `paca/integrations/`。
- **collectors**：周期性 CLI 数据搬运（无 LLM、无 agent caller、写业务表）。放
  `paca/collectors/<name>/`。判断规则 = 同时满足"没有 LLM step"+"没有 agent 直接调用"
  +"周期性"+"写一张业务表"。手动 run 按 workflow 名分发，所以每个 collector 配一个
  `paca/workflows/<name>.py` 薄壳（`expose.agent_os: false`，`extra.run_now` 指向 collector
  入口，由 `paca run-workflow <name>` 调用）。当前实例：`paca/collectors/info_radar/`。

### tools vs integrations vs core

按职责分，不按"谁调用谁方便"分：

- `integrations/`：外部系统的低层 adapter / client。负责 API auth、HTTP / CLI 调用、分页、
  provider response → 稳定 dict。一般不直接给 agent 看。
- `tools/`：agent 能直接看到、能直接调用的业务动作。编排一个或多个 integration、写本地文件、
  做领域 helper。
- `core/`：整个系统通用的基础设施（配置、路径、模型、DB、logging、concurrency）。某个领域
  内部的 helper（比如 knowledge markdown normalization）不进 core。

归属按职责，不按调用方便：

- agent 可直接调用的动作必须在 `tools/` 暴露稳定名字。
- 外部系统细节必须在 `integrations/`，不要在 tool 里直接写 provider HTTP，除非只是非常薄的临时迁移。
- workflow 是组合层，不放在 `tools/<domain>/` 或 `integrations/<domain>/`。
- 可被多个 workflow 或领域复用的 stage/action，提升到 `tools/` 或 `integrations/`。

---

## 配置 vs 代码

**所有 agent / workflow / team 的可调参数走 YAML**：模型 profile、instructions、tools 列表、温度等。
Python 代码只定义"形状"——通用的 loader/builder。

加一个新 agent 的标准流程：
1. 写 `configs/agents/<name>.yaml`，**file stem 与 yaml `name:` 字段必须相同**（snake_case）
2. 如有自定义指令：`prompts/agents/<name>.md`
3. 如有新工具：横向工具实现在 `paca/tools/` 并在 `paca/registry.py::_IN_TREE_TOOLS` 加一行；
   领域工具实现在 `paca/tools/<domain>/` 并在该 package `register()` 里注册。
   工具函数名用完整 `<integration>_<verb>` 前缀（`gbrain_search`）避免 LLM 路由混淆
4. 如有新云 API 集成：见下面 `外部集成模式` 一节
5. 重启 `paca serve` —— 自动加载

**不要**：在 Python 里 hardcode model ID、instructions、tool 列表。

Production agent 也必须走这套流程。不要在 tool / workflow 函数里临时 `Agent(...)` 然后把
instructions、model profile 写死。需要一个 LLM 子任务（例如 frontmatter enrichment）时：

- 新增正式 `configs/agents/<name>.yaml`
- 新增正式 `prompts/agents/<name>.md`
- 通过 `paca.agents.loader.build_from_name("<name>")` 调用
- 如果这个 agent 是纯转换 / verifier，不需要会话库，YAML 写 `extra: {db: false}`
- 如果不应继承 shared context，YAML 写 `extra: {shared_context: false}`

### Shared context（系统级规则）

`prompts/_shared/*.md` 里的 .md 文件会被 `paca.core.context.shared_context()` 自动拼起来，
prepend 到**每个 agent** 的 instructions 头部。house rules / 用户 profile / 默认行为放这。

- 文件名按字母序拼接，前缀两位数（`00_house_rules.md`、`10_user_profile.md`）控顺序
- `_*.md` 前缀和 `99_*.md` 是 git-ignored 的草稿位
- 单个 agent 想退出 shared context，YAML 里加 `extra: {shared_context: false}`

设计 doc：[`docs/architecture.md`](./docs/architecture.md)

---

## 模型与 OMLX

- 模型从 `configs/models.yaml` 的 profile 引用，绝不在 agent 代码里 `Codex(...)`
- OMLX 端点读自 `.env` 的 `OMLX_BASE_URL` + `OMLX_API_KEY`，**只通过**
  `paca.core.models.omlx_endpoint()` 读，不要在别处复制读取逻辑
- OMLX 不可达时 `paca.core.models.get_model` 自动捕获 `RuntimeError` 并切到 `fallback_profile`
  （YAML 里配）；恢复后需要 `reset_cache()` 才会重试 OMLX
- Qwen3 sampling（temp 0.4 / top_p 0.85 / min_p 0.05 / 关 thinking）与 agno `OpenAILike`
  的结构化输出开关（`supports_json_schema_outputs=True` + `supports_native_structured_outputs=False`，
  走 OMLX 标准 `response_format` json_schema / xgrammar 约束解码）都固化在
  `paca.core.models._build_omlx`，**不要轻易改**

---

## 数据库

两条平行连接路径，按用途选——不要混用：

- **agno 自管的表**（sessions / memory / knowledge / traces）→ `paca.core.db.get_db()` 单例，
  绝不要自己 `PostgresDb(...)`。URL 走 `database_url(for_sqlalchemy=True)`，自动改 scheme 到 psycopg v3。
  agno 会自动 provision 这些表，**不要**重复定义
- **我们自己的业务表**（`radar_items` / `radar_analyses` / `radar_pushed_topics` /
  `radar_recaps` / `knowledge_reviews`）→ 裸
  `psycopg.connect(database_url())`（同步 short-lived 连接）；
  DDL 在 `scripts/bootstrap_db.py`，运行时读写在对应 collector / workflow 模块里

---

## info-radar（当前默认）

> agent / 工具 / 数据落点完整清单见 [`docs/modules/info_filter.md`](./docs/modules/info_filter.md)。

在这条链路上工作时只须守住：

- collector (`paca/collectors/info_radar/`) 只写 `radar_items`；analysis 层
  (`paca/workflows/info_radar_analysis/`) 是**唯一**写 `radar_items.seen_at` 的代码路径，
  `seen_at` 让任意 cadence 重跑都幂等（`radar_analyses` 也 `UNIQUE(radar_item_id)`）
- `configs/info_radar/goals.yaml` 必填，缺失 / 非法 → loud `RuntimeError`
- 三个 analysis agent 走 `local_structured` profile（`extra: {db: false, shared_context: false}`，
  `max_tokens: 4096`）——**不要放宽 max_tokens**：xgrammar 约束解码偶尔生成到 cap 才停，
  宽 cap 会把单次失败拖成 10+ 分钟挂死
- 每个 item 独立 try/except，一个 LLM 爆炸不阻断整批；tier1 batch 结构不符回退单 item；
  dedup embed 失败 conservatively 走 novel，都不静默丢 item
- 手动 run 走 thin shell `configs/workflows/info_radar_analysis.yaml`
  (`expose.agent_os: false` + `extra.run_now`，由 `paca info-radar analyze` / `paca run-workflow` 调)；cadence 不是 contract

---

## Knowledge（知识管理）

> agent（artifact_editor / frontmatter / classifier / github_*）、集成（opencli / bilibili /
> github / markitdown）、不变量（artifact 不随 GBrain 失败丢失、manifest 前进规则、slug 防撞、
> Related marker 块）完整清单见 [`docs/modules/knowledge.md`](./docs/modules/knowledge.md)。

在这里工作时的放置 / 铁律：

- 入库 workflow 在 `paca/workflows/knowledge_ingest.py`（由 `configs/workflows/knowledge_ingest.yaml`
  声明）；新增 stage 逻辑放 `paca/workflows/stages/knowledge_ingest/<stage>.py`，不要外溢
- agent-facing 边界工具在 `paca/tools/knowledge/`。**GBrain 访问是横向基础设施，不属 knowledge
  私有**：bridge `paca/integrations/gbrain.py`（`GBRAIN_BIN` call time 读、wiki-relative path
  生成稳定 GBrain-safe slug）+ 工具 `paca/tools/gbrain.py` + `search_knowledge`
- ingest 的 LLM 步都走正式 `configs/agents/knowledge_*.yaml` + `prompts/`；不要在
  `artifact_editor.py` 里临时 `Agent(...)` 或写 deterministic fallback
- re-ingest 走 `PACA_WIKI_DIR` + `knowledge_ingest_manifest.json`，embed 失败必须 loud、
  manifest 不前进（否则 KB search stale）；dashboard re-index 走 `paca run-workflow knowledge_ingest`
- `dashboard/app/knowledge/page.tsx`：re-index 用 POST，不要 GET query

---

## 测试

- pytest 在 `tests/` 下，`asyncio_mode = "auto"`
- 不要写 mock-heavy 单测；优先 fixture + 真函数调用
- 集成测试如需要 OMLX 或外部 API：`@pytest.mark.integration` + 默认跳过
- 改了 `paca/tools/_json_extract.py` 必须跑 `tests/test_json_extract.py`（从生产 case 反推的）
- 测试默认全绿（含若干 `@pytest.mark.integration` / 外部环境 smoke 的 skip）；新增工具/集成至少配一个对应的 smoke test

### 验证走 Docker（不在宿主机裸跑）

单元测试 `uv run pytest` 本地跑即可；但任何**运行时 / 端到端验证**（跑 CLI、dashboard、
完整流程、连 Postgres / gbrain / folocli）必须通过 docker build + 容器执行，让验证环境和
真正 ship 的 Linux 容器一致——不在宿主机裸起 `paca serve` / `paca dashboard` 去验证：

- 构建：`docker compose build`；起栈：`docker compose up`（postgres + bootstrap + dashboard，见
  `docker-compose.yml`）
- 进容器验证：`docker compose exec dashboard <cmd>`，或一次性 `docker compose run --rm dashboard <cmd>`
  （app 镜像已把 `paca` / `uv` 放进 PATH，例如 `paca doctor`、`paca run-workflow knowledge_ingest`、
  `paca info-radar pull`）
- 完整设计与卷 / 环境变量映射见 [`docs/containerized-deployment.md`](./docs/containerized-deployment.md)

---

## 不要做的事

- ❌ `dashboard/` 是自有的 `paca-dashboard` Next.js scaffold；新功能放新页 / 新组件，复用现有 design-system primitives 与 tokens，不要为单个页面硬改 app shell。design system 活文档在 `/design`（`dashboard/app/design/page.tsx`）——nav 入口只在 `NODE_ENV === "development"` 渲染，路由本身没拦（任何 build 下直接访问都能开）；新增 token / UI primitive 时同一个 change 里补进这页
- ❌ dashboard UI 默认语言是**英文**（`dashboard/lib/i18n/dictionaries.ts::DEFAULT_LOCALE`），中文靠 nav 的语言按钮切、存 `paca_locale` cookie；i18n 只覆盖界面文案，文章标题 / 分析摘要 / tag / YAML 值按原样渲染
- ❌ 不要在 `dashboard/` 里起第二个 `next dev`——它和用户已在跑的 dev server 共用同一个 `.next`，两个进程互写缓存会把 build manifest 搞坏（典型报错 `Cannot read properties of undefined (reading 'call')`）。验证完的 dev server 一定要停掉；一个大改动收尾后 `rm -rf dashboard/.next` 清掉膨胀的增量缓存（dev 缓存大头是 `.next/cache/webpack/`，会随 HMR 一直涨）
- ❌ 不要在 `os_app.py` 里硬编码 agent / team / workflow——一切从 configs 装
- ❌ 不要把 `.env` / `state/` 提交到 git
- ❌ 不要在 logger 里 dump 整个 dict（容易泄 token）
- ❌ 不要为不存在的场景写"防御性"代码——失败要 loud（`RuntimeError`），不要静默 default
- ❌ docstring 不写多段散文——默认一行，逻辑复杂时可多写几行说明即可；长篇设计写进 design.md
- ❌ 不要在 import 时读 env / 调网络——会让 startup 不稳

---

## 错误处理风格

- 配置缺失 / OMLX 端点配置坏 → `RuntimeError`
- 单个 agent 加载失败 → log error 但继续装其他（一个坏 YAML 不应该让整个系统挂）
- 单个 integration 模块挂 → `register_all` 已经 try/except 隔离
- 外部 API 调用失败 → 让 agno 的 retry / tracing 处理，不要自己包

---

## 提交

- 用户主动让我 commit 才 commit
- 非平凡改动提交前：`openspec status --json` 确认有没有匹配的 change；对照
  `.claude/skills/code-review/SKILL.md` 的 doc-sync map，确认没有该同步的
  文档 / spec 漏掉
- commit message 引用所属 change 的 task（例如 "info-radar: task 1.1"），或对应 spec capability 名（例如 "info-radar: goals.yaml validation"）
- 不要 amend；不要 `--no-verify`

---

## 外部集成模式

通用 provider（任何领域都可能用）放共享 `paca/integrations/`；领域 provider 放
`paca/integrations/<domain>/`，由对应工具或 workflow stage 包一层 agent-facing tool。模板：

```python
# paca/integrations/<name>.py
from agno.tools import tool
from paca.integrations._helpers import env, http_client, to_jsonable, truncate

_BASE = "https://api.example.com/v1"

@tool(show_result=False)
def example_action(arg: str) -> dict:
    """One-line docstring; agno turns this into the LLM-visible description."""
    with http_client(headers={"Authorization": f"Bearer {env('EXAMPLE_API_KEY')}"}) as c:
        r = c.get(f"{_BASE}/something", params={"q": arg})
        r.raise_for_status()
    return to_jsonable(r.json())

def register(registry) -> None:
    registry.register("example_action", example_action)
```

共享 provider 要在 `paca/integrations/__init__.py` 的 `_MODULES` 加 `"example"`
（当前该列表为空——没有横向 cloud-API provider 在用）。
领域 adapter（例如 `paca/integrations/knowledge/opencli.py`）不直接给 agent 调；
由 `tools/` 或 workflow stage 调用并暴露稳定 tool。

铁律：
- API key 用 `env(NAME)` 在 **call time** 读，不在 import time——缺 key 不能阻断 startup
- HTTP 一律走 `http_client()`（自带 30s timeout），不要直接 `requests` 或裸 `httpx`
- 返回值过 `to_jsonable()` 确保 JSON-safe
- 长文本（文章、文件内容）过 `truncate()` 防爆 context
- 一个集成挂掉不能影响其他——`register_all` 已经 try/except 了，但你写代码时也要避免在 module top-level 做副作用

### CLI-based 集成（folocli 等）

不是所有 provider 都是 HTTP API。CLI 类（如 `folocli`、`opencli`）走 subprocess，
模板在 `paca/integrations/info_radar/folo.py`：

- argv 默认走 `npx --yes folocli@<pinned-version>`（不要 `npx folocli` — 无 `--yes` 解析
  到旧 cache 会返回 stale 错误；不要 `folocli@latest` — 漂移）；version 走 `${TOOL}_CLI_ARGV`
  env var 让 operator 覆盖
- 认证优先级：`<TOOL>_TOKEN` env var > CLI 自己的 session 文件（folocli 是 `~/.folo/config.json`）
  → 无人值守场景优先用 token env var
- 给 agent / CLI 看的入口在 `paca/collectors/` 或 `paca/tools/` 而不是 integration 本身

---

## 当前状态

待办看 [`openspec/changes/`](./openspec/changes/)；各模块"已就位 / 下一步"看
[`docs/modules/*.md`](./docs/modules/) 的「规范与状态」节，已归档的 change 在
`openspec/changes/archive/`。

每完成一项 task 在对应 change 的 `tasks.md` 勾上 + 在 commit 引用。
