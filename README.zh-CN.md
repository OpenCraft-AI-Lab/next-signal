# next-signal

> [English](./README.md) · **简体中文**

本地优先的 info-radar + knowledge 框架，基于 [agno](https://github.com/agno-agi/agno) 构建。
Python 包名 `paca`。

一个 runnable orchestrator 底盘 + 按领域组织的 tools / integrations / workflows。
一个 AgentOS 进程承载所有 agent / workflow；CLI 通过 runnable loader 调同一组
能力，Dashboard 是独立 Next.js 进程（读 Postgres / 起一次性 `paca` CLI）。状态存本地
Postgres + pgvector，本地模型走 OMLX (Qwen3) 优先，云模型作为回落。

## 快速开始（Docker Compose）

**容器是 next-signal 的推荐运行方式。** 整个栈——Postgres + pgvector、schema
bootstrap、dashboard——一条命令起来；镜像里已经打好了 peer CLI（`gbrain`、
`opencli`、`folocli`），不用另外装。

```bash
git clone https://github.com/OpenCraft-AI-Lab/next-signal.git
cd next-signal
cp .env.example .env && $EDITOR .env   # 见下面「最小 .env」
docker compose up --build              # postgres + bootstrap + dashboard
```

然后打开 <http://localhost:3000>。

**最小 `.env`** —— 缺了这些会直接失败：

| Key | 为什么 |
|---|---|
| 任一云模型 key：`DEEPSEEK_API_KEY`（主）、或 `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | 容器碰不到 Apple Metal，所以云路径是默认 |
| `PACA_WIKI_DIR` | clean wiki repo 的宿主机路径——读写 bind-mount |
| `PACA_WIKI_RAW_DIR` | raw 归档 repo 的宿主机路径——读写 bind-mount |

`DATABASE_URL` 和容器内的 wiki / state 路径由 `docker-compose.yml` 设定，
不要在 `.env` 里覆盖。

日常容器命令：

```bash
docker compose up -d                          # 后台起栈
docker compose exec dashboard paca doctor     # 在容器里自检
docker compose exec dashboard paca list       # 列 agents / workflows
docker compose run --rm dashboard paca info-radar pull
docker compose logs -f dashboard              # 跟 dashboard 日志
docker compose down                           # 停栈，保留 pgdata/pstate 卷
```

> 任何端到端验证都走容器，不在宿主机裸跑——让验证环境和真正 ship 的环境一致。
> 完整设计与卷 / 环境变量映射见
> [docs/containerized-deployment.md](./docs/containerized-deployment.md)。

**可选 —— 本地模型。** OMLX/MLX 需要 Metal GPU，**无法容器化**。云回落覆盖了对话，
但 *embedder* 只走 OMLX，所以 `paca info-radar analyze` 的 dedup 需要它。
在宿主机跑 OMLX server，然后让容器指过去：

```bash
OMLX_BASE_URL=http://host.docker.internal:<port>/v1   # 写进 .env
```

**Host-native 安装**（不用 Docker；想让本地模型跑在同一进程里就得走这条）是备选路径，
见 [docs/zh/operations.md](./docs/zh/operations.md#安装)。

## 常用命令

在容器里去掉 `uv run` 前缀（`paca` 已经在 `PATH` 上）。

```bash
uv run paca list                                     # 列 agents / workflows
uv run paca doctor                                   # 自检 env / Postgres / OMLX / tools / GBrain
uv run paca run-agent <name> "<prompt>"              # 一次性调某个 agent
uv run paca serve [--port 7777]                       # 启动 AgentOS
uv run paca dashboard [--port 3000]                   # 启动 dashboard
uv run paca knowledge ingest <url|staged-file>        # ingest 到知识库
uv run paca info-radar pull [--source NAME]           # 拉取信息源到 radar_items
uv run paca info-radar analyze [--limit N]            # 两层分析 pipeline
uv run paca run-workflow knowledge_ingest             # 手动跑 wiki → GBrain re-ingest
uv run pytest -q                                      # 测试
```

## 文档地图

| 你想… | 看 |
|---|---|
| 理解系统怎么搭、为什么这么搭 | [docs/zh/architecture.md](./docs/zh/architecture.md) |
| 加 agent / 工具 / 集成 / 模型 / 新领域 | [docs/zh/development.md](./docs/zh/development.md) |
| 安装、env 配置、`paca doctor`、故障排查 | [docs/zh/operations.md](./docs/zh/operations.md) |
| 容器化部署（Docker Compose，cloud-LLM） | [docs/zh/containerized-deployment.md](./docs/zh/containerized-deployment.md) |
| 深入某个方向 | [docs/zh/modules/](./docs/zh/modules/)：[core](./docs/zh/modules/core.md) · [knowledge](./docs/zh/modules/knowledge.md) · [info_filter](./docs/zh/modules/info_filter.md) · [dashboard](./docs/zh/modules/dashboard.md) |
| 能力的规范契约 / 待办变更 | [openspec/specs/](./openspec/specs/) · [openspec/changes/](./openspec/changes/) |

当前主要领域：`knowledge`（知识管理）、`info_filter`（info-radar）。
领域能力放在 `src/paca/tools/<domain>/` 和 `src/paca/integrations/<domain>/`，
workflow 集中放 `src/paca/workflows/`。

### 文档是双语的

英文是标准版本，放在 `README.md` 和 `docs/` 下；中文镜像在
[`docs/zh/`](./docs/zh/)、本文件、以及
[`dashboard/README.zh-CN.md`](./dashboard/README.zh-CN.md)，每页顶部都有语言切换
链接。**所有面向人的文档都有中英两版**，且两边在同一个 commit 里一起改。

有意不翻的两处：`CLAUDE.md`（给 agent 的指令，只有中文）和 `openspec/specs/`
（能力契约，只有英文）。这两层都随代码高频变动，多一份拷贝只会漂移。

## 相关项目

- [`garrytan/gbrain`](https://github.com/garrytan/gbrain) —— 长期知识库 peer service：markdown-first + pgvector hybrid search + 自动 typed-link 图谱 + MCP server
