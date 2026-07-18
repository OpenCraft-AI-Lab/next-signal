# next-signal

本地优先的 info-radar + knowledge 框架，基于 [agno](https://github.com/agno-agi/agno) 构建。
Python 包名 `paca`。

一个 runnable orchestrator 底盘 + 按领域组织的 tools / integrations / workflows。
一个 AgentOS 进程承载所有 agent / workflow；CLI / launchd 通过 runnable loader 调同一组
能力，Dashboard 是独立 Next.js 进程（读 Postgres / 起一次性 `paca` CLI）。状态存本地
Postgres + pgvector，本地模型走 OMLX (Qwen3) 优先，云模型作为回落。

## Quick start

```bash
brew install uv
brew install --cask postgres-app          # 或 brew install postgresql@16
uv sync
cp .env.example .env && $EDITOR .env       # 至少 DATABASE_URL + 一个 LLM key
createdb next_signal
uv run python scripts/bootstrap_db.py
uv run paca doctor
uv run paca serve                          # → http://localhost:7777
uv run paca dashboard                      # → http://localhost:3000
```

## 常用命令

```bash
uv run paca list                                     # 列 agents / workflows
uv run paca doctor                                   # 自检 env / Postgres / OMLX / tools / GBrain
uv run paca run-agent <name> "<prompt>"              # 一次性调某个 agent
uv run paca serve [--port 7777]                       # 启动 AgentOS
uv run paca dashboard [--port 3000]                   # 启动 dashboard
uv run paca knowledge ingest <url|staged-file>        # ingest 到知识库
uv run paca info-radar pull [--source NAME]           # 拉取信息源到 radar_items
uv run paca info-radar analyze [--limit N] [--source NAME]  # 两层分析 pipeline
uv run paca schedule run-now weekly_knowledge_sync  # 手动跑 wiki → GBrain re-ingest
uv run pytest -q                                      # 测试
```

## 文档地图

| 你想… | 看 |
|---|---|
| 理解系统怎么搭、为什么这么搭 | [docs/architecture.md](./docs/architecture.md) |
| 加 agent / 工具 / 集成 / 模型 / 新领域 | [docs/development.md](./docs/development.md) |
| 安装、env 配置、`paca doctor`、故障排查 | [docs/operations.md](./docs/operations.md) |
| 容器化部署（Docker Compose，cloud-LLM） | [docs/containerized-deployment.md](./docs/containerized-deployment.md) |
| 深入某个方向（底盘 / 知识 / 信息流 / 操作台） | [docs/modules/](./docs/modules/)：[core](./docs/modules/core.md) · [knowledge](./docs/modules/knowledge.md) · [info_filter](./docs/modules/info_filter.md) · [dashboard](./docs/modules/dashboard.md) |
| 能力的规范契约 / 待办变更 | [openspec/specs/](./openspec/specs/) · [openspec/changes/](./openspec/changes/) |

当前主要领域：`knowledge`（知识管理）、`info_filter`（info-radar）。
领域能力放在 `src/paca/tools/<domain>/` 和 `src/paca/integrations/<domain>/`，
workflow 集中放 `src/paca/workflows/`。

## 相关项目

- [`garrytan/gbrain`](https://github.com/garrytan/gbrain) —— 长期知识库 peer service：markdown-first + pgvector hybrid search + 自动 typed-link 图谱 + MCP server

## 来源

这是从 `intelligent-digitalpaca` 拆出的 info-radar + knowledge 子集，作为独立项目的起始代码。
其余领域（smart-money、financial-news/portfolio、content-studio、Discord 个人助手）
不在这个 repo 的范围内。
