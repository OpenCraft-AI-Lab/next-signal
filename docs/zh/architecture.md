# 架构

> [English](../architecture.md) · **中文**

next-signal（Python 包名 `paca`）是一个本地优先的 info-radar + knowledge 框架，
基于 [agno](https://github.com/agno-agi/agno) 2.6+ 构建。

## 心智模型：runnable 底盘 + 能力积木

这个 repo 不是"一个 bot"，而是**一个 orchestrator 底盘 + 若干可运行单元**：

- **runnable** —— agent / workflow / team，统一由 `configs/{agents,workflows,teams}/`
  声明和加载。
- **tools** —— agent-facing 业务动作，按领域放在 `src/paca/tools/<domain>/`，横向通用工具
  直接放 `src/paca/tools/`。
- **integrations** —— provider / CLI / HTTP adapter，按领域放在
  `src/paca/integrations/<domain>/`，横向通用 adapter 直接放 `src/paca/integrations/`。
- **workflows** —— 集中编排 agent / tool / stage，放在 `src/paca/workflows/`。

一个 AgentOS 进程承载所有 runnable 和工具能力（`paca serve`，:7777，目前没有内建的
聊天入口挂在它上面）。CLI 通过 centralized runnable loader 调同一组
workflow / agent；Dashboard 是独立 Next.js 进程，目前读 Postgres 或启动一次性
`paca` CLI 子进程，不依赖 `paca serve` 在线。

## 运行时拓扑

```text
paca AgentOS FastAPI (:7777)
  - specialist agents / workflows
  - tool registry

CLI -------------------------> runnable loader / workflow run_now
Dashboard (:3000 Next.js) ---> Postgres reads + one-shot `paca` CLI children

shared lower layers:
  模型工厂（OMLX 优先，云回落）
  tools -> integrations -> 外部 API / CLI / 本地 state
```

## 代码分层

```
src/paca/
  core/              共享基础设施：config / db / models / paths / logging / context
  agents/loader.py   通用 agent 装配（YAML → agno.Agent）
  orchestrator/      runnable loader / workflow tools / runtime 装配
  workflows/         集中 workflow factory；私有 stage 放 workflows/stages/<name>/
  teams/             team factory（复杂 team 才需要 Python；当前无 shipped team）
  interfaces/        cli 入口
  api/               自定义 FastAPI 路由（规划中，当前为空包）
  os_app.py          AgentOS 运行时装配入口
  registry.py        工具面装配器（注册并解析所有工具）
  tools/             agent-facing tools，按领域分组：knowledge/
  integrations/      provider adapters，按领域分组：knowledge/ info_radar/
  collectors/        周期性 CLI 数据搬运（无 LLM、无 agent caller、写业务表）
                     例：info_radar/ 写 radar_items；其上的 analysis layer 在
                     workflows/info_radar_analysis/ 消费这张表并写 radar_analyses
                     + radar_pushed_topics
```

**归属按职责，不按调用方便。** `tools/` 是 agent 能看到的业务动作；`integrations/`
是低层外部系统 adapter；`workflows/` 是集中编排层。领域能力可以按子目录组织，但 workflow
不放进领域 tool 目录，避免编排逻辑散落。

## 依赖方向

依赖严格向下，不允许反向 import：

```text
interfaces / api
  -> orchestrator
  -> workflows / teams / agents
  -> tools
  -> integrations
  -> core
```

铁律：

- `core` 不 import 任何上层。
- `tools` 可以编排 `integrations`（向下依赖 OK）；`integrations` 不反向 import `tools` / agents。
- workflow 可以组合 agents / tools / private stages；workflow-private helper 放
  `src/paca/workflows/stages/<workflow>/`。
- `registry.py` / `os_app.py` 是装配模块，位于整个 stack 之上。
- 如果发现需要 `core` import `tools`，或 integration 反向 import tool / agent，停下来重新设计。

## 关键设计决策

| 决策 | 原因 |
|---|---|
| **agno 框架** | AgentOS 自带 FastAPI / tracing / sessions / memory，不自造框架 |
| **单一 AgentOS 进程** | CLI / Dashboard（间接）共用同一组件定义；trace / sessions 单一存储模型 |
| **Postgres + pgvector** | agno 原生支持；pgvector 省掉第二个向量库；单一备份策略 |
| **YAML 定义行为** | Dashboard 可编辑 + 热加载；diff 可读；Python 只定义"形状" |
| **本地模型优先** | 隐私 + 成本；云模型作为显式 fallback，不是默认 |
| **显式工具注册表** | LLM 可见的工具面 grep 得到；不做动态扫描（隐式暴露是安全风险） |
| **GBrain 外挂做长期知识库** | markdown-first + hybrid search + 自动图谱；不自建 |
| **telemetry 关闭** | 本地优先，不发数据出门（`AgentOS` 和直接构造 `Agent` 都要关） |

## 非目标

刻意不做：多用户授权 / 云 SaaS、高可用 / 集群、近期的 Linux/Windows 调度、
重造 agno 的 AgentOS / tracing / memory、把 GBrain 当 agent 操作系统。

## 新能力怎么插进底盘

1. 新 agent：`configs/agents/<name>.yaml` + `prompts/agents/<name>.md`。
2. 新 tool：放 `src/paca/tools/<domain>/`，在该 package 的 `register()` 暴露稳定名字。
3. 新 integration：放 `src/paca/integrations/<domain>/` 或横向 `src/paca/integrations/`。
4. 新 workflow：`configs/workflows/<name>.yaml` 声明，复杂的在 `src/paca/workflows/<name>.py` 实现 factory。
5. 新 team：`configs/teams/<name>.yaml` 声明；复杂 routing 才加 `src/paca/teams/<name>.py`。
6. 新 collector（周期性 CLI 数据搬运，无 LLM）：实现在 `src/paca/collectors/<name>/`，
   手动 run 接入靠 `src/paca/workflows/<name>.py` 薄壳（YAML 设 `expose.agent_os: false`，
   `extra.run_now` 指向 collector 入口，由 `paca run-workflow <name>` 调用）。
7. collector 之上的 analysis workflow（LLM-driven 消费 collector 的业务表）：
   `src/paca/workflows/<name>_analysis/` 作为 package 实现，stages 拆到
   `stages/`；agent + prompt 用标准 YAML/markdown 路径；手动 run 接入同样靠
   thin shell `extra.run_now`；`seen_at` 列归 analysis 写，collector 不碰。
   currently shipped: `info_radar_analysis`。

完整步骤见 [开发指南](./development.md)。能力的规范契约在
[`openspec/specs/`](../../openspec/specs/)。各方向的深入文档（底盘 / 知识 / 信息流 /
操作台）在 [`docs/modules/`](./modules/core.md)；agent / 工具的全景清单不在
文档维护——`uv run paca list` 与 `src/paca/registry.py` 是 source of truth。
