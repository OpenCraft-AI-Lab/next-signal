# 开发指南

> [English](../development.md) · **中文**

## 默认工作流

非平凡的能力开发走 OpenSpec：

1. 在 `openspec/changes/` 新建或选一个 change。
2. 写 / 改 `proposal.md`、delta specs、`tasks.md`。
3. `openspec validate --all` 校验。
4. 按 task 实现，验证一个勾一个。
5. 实现完 `openspec archive <name>`，delta 合并进 `openspec/specs/`。

Slash 别名（`.claude/commands/opsx/`）：`/opsx:explore`、`/opsx:propose`、
`/opsx:apply`、`/opsx:archive`。

## 工具链

永远用 `uv`，不要直接 `python` / `pip` / `pytest`：

```bash
uv sync                 # 同步依赖（改了 pyproject 后）
uv run paca <cmd>        # 跑 CLI
uv run pytest -q         # 测试
uv run ruff check src    # lint
uv add <pkg>             # 加依赖（自动写 pyproject + uv.lock）
```

不要手改 `uv.lock`。

## 加一个 agent

1. 写 `configs/agents/<name>.yaml`，file stem 必须等于 yaml `name:` 字段（snake_case）。
2. 指令文本放 `prompts/agents/<name>.md`（除非极短）。
3. 模型按 profile 名引用（`configs/models.yaml`）；工具按注册名引用。
4. 重启 `paca serve`，或 `paca run-agent <name> "..."` 烟测。

```yaml
name: knowledge_frontmatter
model_profile: local_structured
tools: []
instructions_file: agents/knowledge_frontmatter.md
markdown: false
add_history_to_context: false
extra: { db: false, shared_context: false }
```

production agent 不要在 Python 里硬编码 model / instructions。纯转换 / verifier
agent 可在 yaml 写 `extra: {db: false}`（不要会话库）、`extra: {shared_context: false}`
（不继承 shared context）。

## runnable 配置

agent / workflow / team 都是 runnable，配置是 repo-local source of truth：

```text
configs/agents/<name>.yaml
configs/workflows/<name>.yaml
configs/teams/<name>.yaml
```

共同规则：

- `name:` 必须等于文件名 stem。
- `kind:` 写 `agent` / `workflow` / `team`。
- `enabled: false` 表示保留配置但不进运行时。
- YAML 只用 JSON-compatible subset，便于后续前端用 JSON object 编辑、后端写回 YAML。
- prompt 只存路径，不把长 prompt 塞进 YAML。

Python code 只定义 loader / factory / schema。新增普通 agent 不写 Python；workflow / 复杂 team
才写 factory。

## 加一个工具

工具 = agent 能直接调用的业务动作。

- **横向工具**（跨领域通用，如 GBrain 检索）→ `src/paca/tools/`，
  在 `paca/registry.py::_IN_TREE_TOOLS` 加一行。
- **领域工具** → `src/paca/tools/<domain>/`，在该 package 的 `register()` 里
  `registry.register(...)`。

命名用 `<integration>_<verb>` / `<domain>_<verb>` 前缀（`gbrain_search`），
避免 `search` / `fetch` 这种泛名让 LLM 路由混淆。docstring 一行。

## 加一个集成

集成 = 外部 provider 的低层 API / CLI adapter。

- **通用 provider**（任何领域都可能用）→ `src/paca/integrations/`，
  在 `integrations/__init__.py` 的 `_MODULES` 加一行。
- **领域 provider** → `src/paca/integrations/<domain>/`，由对应领域工具或 workflow stage 调用。

```python
from agno.tools import tool
from paca.integrations._helpers import env, http_client, to_jsonable

@tool(show_result=False)
def provider_action(query: str) -> dict:
    """One-line LLM-visible docstring."""
    with http_client(headers={"Authorization": f"Bearer {env('PROVIDER_API_KEY')}"}) as c:
        r = c.get("https://api.example.com/search", params={"q": query})
        r.raise_for_status()
    return to_jsonable(r.json())

def register(registry) -> None:
    registry.register("provider_action", provider_action)
```

只有 integration 本身就是 agent-facing capability 时才实现 `register()` 并进
`paca/integrations/__init__.py` 的 `_MODULES`；普通领域 adapter 不直接注册给 agent，
由 tool 或 workflow stage 调用。

铁律：API key 在 call time 用 `env()` 读（不在 import time）；HTTP 走 `http_client()`；
返回值过 `to_jsonable()`；长文本过 `truncate()`；module top-level 不做副作用。

## 加一个 workflow

多步骤 / 可调度 / 需要可观测可恢复的工作放 workflow。workflow 集中在
`src/paca/workflows/`，并由 `configs/workflows/<name>.yaml` 声明。

```yaml
name: knowledge_ingest
kind: workflow
enabled: true
factory: paca.workflows.knowledge_ingest:build
expose:
  agent_os: true
  tool:
    enabled: true
    name: knowledge_ingest_workflow
extra:
  run_now: paca.workflows.knowledge_ingest:run
```

**尚未实现**：纯 agent 串联、没有自定义 artifact / retry / 文件写入语义的简单线性
workflow，未来计划支持直接用 YAML `steps:` 声明。当前 `WorkflowConfig` 是 strict
schema（`extra="forbid"`），没有 `steps` 字段——直接写 `steps:` 的 YAML 会校验失败。
要做这类 workflow，先扩展 centralized loader 和 `WorkflowConfig` 支持 `steps:` builder。

只有 workflow 私有的 helper / stage 放 `src/paca/workflows/stages/<workflow>/`；可被多个
workflow 或 agent 复用的动作提升到 `tools/` 或 `integrations/`。

同一个 workflow 只有一个本体，是否暴露给 AgentOS 或 agent tool 由 `expose` 决定：

- `expose.agent_os: true` → `paca.os_app` 通过 centralized loader 注册到 AgentOS。
- `expose.tool.enabled: true` → `paca.orchestrator.workflow_tools` 注册一个 `WorkflowTools`
  toolkit，agent YAML 用这个 tool 名。
- `extra.run_now` → `paca run-workflow <name>` 手动触发时调用的 function。不是每个 workflow 都必须支持。

不要为同一个 workflow 再写一份 `tools/<domain>/workflow_tools.py` wrapper。

## 加一个 team

team 也走 runnable 配置。简单 team 只写 `configs/teams/<name>.yaml`；复杂 routing 才加
`src/paca/teams/<name>.py` factory。当前仓库没有 shipped team——`configs/teams/`
为空，`list_teams()` 正常返回空列表；新加一个团队方向时才需要这层。

```yaml
name: <team_name>
kind: team
enabled: true
mode: route
members:
  - <agent_a>
  - <agent_b>
instructions_file: teams/<team_name>.md
factory: paca.teams.<team_name>:build
```

新增一个产品方向时，优先新增领域目录而不是 `modules/`：
`src/paca/tools/<domain>/`、`src/paca/integrations/<domain>/`、必要时
`src/paca/workflows/<name>.py` 和 `configs/{agents,workflows,teams}/`。

## 配置约定

- 所有可调参数走 `configs/` 下的 YAML，Python 只定义 schema 和 loader。
- Pydantic strict model 拒绝未知 key（typo 要 loud fail）。
- YAML `name:` 与 file stem 对齐。
- 不在 YAML 放 secret；不在多个模块重复解析 `.env`。

## 测试

```bash
uv run pytest -q
```

- 不写 mock-heavy 单测；优先 `tmp_path` + `monkeypatch` + 真函数调用。
- 单测不碰生产本地服务 / DB / 外部 API / 真实浏览器登录态。
- 需要 OMLX / 外部 API 的集成测试：`@pytest.mark.integration` + 默认跳过。
- 新增工具 / 集成至少配一个 smoke test。
- 改注册表跑 `tests/test_registry.py`；改 `tools/_json_extract.py` 跑
  `tests/test_json_extract.py`。

任何**运行时 / 端到端**验证（跑 CLI、dashboard、完整流程、连 Postgres / gbrain /
folocli）都走 Docker，不在宿主机裸跑，让验证环境和真正 ship 的一致：

```bash
docker compose build
docker compose up
docker compose exec dashboard paca doctor
docker compose run --rm dashboard paca run-workflow knowledge_ingest
```

完整设计与卷 / 环境变量映射见
[containerized-deployment.md](../containerized-deployment.md)。

## 文档

文档双语，**英文是标准版本**。英文页在 `README.md` 和 `docs/`；中文镜像在
`README.zh-CN.md` 和 `docs/zh/`。每页开头都有指向对应语言的切换链接。

改文档时**两个语言在同一个 change 里一起改**。新写的中文内容，在这个 change 完成前
必须补上英文版。（反过来不强制：`containerized-deployment.md` 只有英文。）

## 提交

- 用户主动让 commit 才 commit。
- message 引用所属 OpenSpec change 的 task 或 spec capability 名。
- 不 amend；不 `--no-verify`。
- 不提交 `.env` / `state/` / 生成的 cache / secret。
