# 架构

> [English](../architecture.md) · **中文**

next-signal（Python 包名 `next_signal`）是一个本地优先的 info-radar + knowledge 框架，
基于 [agno](https://github.com/agno-agi/agno) 2.6+ 构建。

## 心智模型：runnable 底盘 + 能力积木

这个 repo 不是"一个 bot"，而是**一个 orchestrator 底盘 + 若干可运行单元**：

- **runnable** —— agent / workflow / team，统一由 `configs/{agents,workflows,teams}/`
  声明和加载。
- **tools** —— agent-facing 业务动作，按领域放在 `src/next_signal/tools/<domain>/`，横向通用工具
  直接放 `src/next_signal/tools/`。
- **integrations** —— provider / CLI / HTTP adapter，按领域放在
  `src/next_signal/integrations/<domain>/`，横向通用 adapter 直接放 `src/next_signal/integrations/`。
- **workflows** —— 集中编排 agent / tool / stage，放在 `src/next_signal/workflows/`。

一个 AgentOS 进程承载所有 runnable 和工具能力（`next-signal serve`，:7777，目前没有内建的
聊天入口挂在它上面）。CLI 通过 centralized runnable loader 调同一组
workflow / agent；Dashboard 是独立 Next.js 进程，目前读 Postgres 或启动一次性
`next-signal` CLI 子进程，不依赖 `next-signal serve` 在线。

## 运行时拓扑

```text
next-signal AgentOS FastAPI (:7777)
  - specialist agents / workflows
  - tool registry

CLI -------------------------> runnable loader / workflow run_now
Dashboard (:3000 Next.js) ---> Postgres reads + one-shot `next-signal` CLI children
Scheduler（不开端口）--------> 轮询墙钟，到点跑 radar 链

shared lower layers:
  production stage adapter -> selected OMLX / DeepSeek / Codex CLI / Claude CLI
  静态 AgentOS 模型工厂（YAML profiles）
  tools -> integrations -> 外部 API / CLI / 本地 state
```

三个常驻进程，只有第三个会自己动手。调度器每次轮询都重读
`~/.next-signal/schedule.json` 和 `schedule_state` 表，到点跑
`info_radar_pull` → `info_radar_analysis`。**这是唯一一条没人敲命令也会烧
token 的路径**——所以它的状态是持久化的，配置也是现读而不是启动时抓一份。

## 代码分层

```
src/next_signal/
  core/              config / db / models / engine preferences / OMLX resolver / paths
                     clock.py     全系统共用的一条本地日界线
                     schedule.py  读调度状态文件；文件坏了要 loud
  agents/loader.py   通用 interactive-agent 装配（YAML → agno.Agent）
  agents/stage.py    production LLM routing + whole-job engine affinity/fallback
  orchestrator/      runnable loader / workflow tools / runtime 装配
                     schedule.py  墙钟轮询循环及其持久状态
                     run_now.py   按名字解析某个 workflow 的手动入口
  workflows/         集中 workflow factory；私有 stage 放 workflows/stages/<name>/
  teams/             team factory（复杂 team 才需要 Python；当前无 shipped team）
  interfaces/        cli 入口
  api/               自定义 FastAPI 路由（规划中，当前为空包）
  os_app.py          AgentOS 运行时装配入口
  registry.py        工具面装配器（注册并解析所有工具）
  tools/             agent-facing tools，按领域分组：knowledge/
  integrations/      provider adapters，按领域分组：knowledge/ info_radar/
                     coding_agents/（可选 Codex / Claude Code CLI 的受限子进程管理与认证）
  collectors/        周期性 CLI 数据搬运（无 LLM、无 agent caller、写业务表）
                     例：info_radar/ 写 radar_items；其上的 analysis layer 在
                     workflows/info_radar_analysis/ 消费这张表并写 radar_analyses
                     + radar_pushed_topics
```

**归属按职责，不按调用方便。** `tools/` 是 agent 能看到的业务动作；`integrations/`
是低层外部系统 adapter；`workflows/` 是集中编排层。领域能力可以按子目录组织，但 workflow
不放进领域 tool 目录，避免编排逻辑散落。

## 运行时状态文件

行为定义在 `configs/*.yaml`，随镜像一起烤进去。**运行期间**操作者会改的东西放
`~/.next-signal/`——一个 Docker 卷，可以手改，而且写它的进程本来就写不了镜像：

| 文件 | 谁写 | 谁读 |
|---|---|---|
| `language.json` | 设置页 | output-language policy 为 `global` 的 agent |
| `engine.json` | 设置页 | 每个 production LLM stage，在 job 开始时 |
| `coding-agents.json` | 设置页 | CLI stage 与 `coding-agent run`，在 job 开始时 |
| `schedule.json` | 设置页 | 调度器，每 30s 轮询一次 |
| `embedding.json` | 设置页 | dedup gate，每个 item 一次 |

三条性质对所有文件都成立，每条都承重：

- **call time 读，绝不 import time 读。** dashboard 改完不用重启就生效，文件缺失
  也不会把 startup 搞挂。
- **pipeline 侧 loud，dashboard 侧宽容。** Python reader 遇到坏文件直接抛；
  dashboard 的 reader 回落并记日志，因为它要渲染出操作者用来修这个文件的那个面板。
  布尔值是**校验**而不是强转——`bool("false")` 是 `True`，而这些文件是给人手改的。
- **按 job 冻结，不是按 stage。** 一个 job 只读一次 `engine.json` 和
  `coding-agents.json` 然后一直用。radar job 会跑几十分钟，一批 item 的分数是互相
  比较的，中途重读会让同一批的前后两半用不同模型打分。

`embedding.json` 是最后这条性质的例外，而且理由同源。向量不是一个可以事后修正的判断
——它会被存下来，而且只能跟同一个 embedder 产出的向量比较——所以换 provider 必须尽快
生效，而不是等到下一个 job 边界。于是 gate **按 item** 解析出一个不可变快照：provider、
模型、端点、凭据，以及一个稳定的向量空间身份，在请求发出之前一起冻住。这个身份就是
`radar_pushed_topics.embedder` 存的值，也是检索过滤用的值——所以即使设置在"嵌入响应
回来"和"那一行写入"之间被改掉，也不可能把一条向量标成它并非来自的那个空间。新选择从
下一个 item 开始生效。身份字符串归 `core-embedding` 所有，别的层不再自行推导一个。

唯一**刻意不放**在这里的设置是时区。`INFO_RADAR_TIMEZONE` 是环境变量，因为同一个值
同时决定调度、radar 按天分组和 review 到期日；一个自带时区的 schedule 会出现"按某个
时区的 08:00 触发、结果却归进另一个时区画出的那一天"。

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
  `src/next_signal/workflows/stages/<workflow>/`。
- `registry.py` / `os_app.py` 是装配模块，位于整个 stack 之上。
- 如果发现需要 `core` import `tools`，或 integration 反向 import tool / agent，停下来重新设计。

production LLM stage 是 interactive AgentOS agent 旁边的一条明确路径：workflow 调
`run_stage`，直接 interactive agent 仍走 `build_from_name`。AgentOS 暴露的 knowledge
workflow 会把 sync、async、streaming 全部包在一个 stage-job context 里。CLI stage 是一次性
model worker，不是 agno model：每次在空临时目录中用 no-tools provider profile 接收 composed
prompt，因此不可信文章内容不能变成仓库检查或命令执行。

## 关键设计决策

| 决策 | 原因 |
|---|---|
| **agno 框架** | AgentOS 自带 FastAPI / tracing / sessions / memory，不自造框架 |
| **单一 AgentOS 进程** | CLI / Dashboard（间接）共用同一组件定义；trace / sessions 单一存储模型 |
| **Postgres + pgvector** | agno 原生支持；pgvector 省掉第二个向量库；单一备份策略 |
| **YAML 定义行为** | Dashboard 可编辑 + 热加载；diff 可读；Python 只定义"形状" |
| **本地模型优先** | 隐私 + 成本；云模型作为显式 fallback，不是默认 |
| **每个 production job 一个引擎** | Dashboard state 为所有 LLM stage 选同一 provider；只有首次成功响应前允许 fallback，模型配置在 job 开始时冻结 |
| **运行时状态放 `~/.next-signal/`，行为放 `configs/`** | 容器里的 repo 树是烤进镜像的；dashboard 写的东西必须落在卷上，且 call time 读，改完不用重启 |
| **一个墙钟调度器，状态存 Postgres** | 笔记本会睡、Docker 会被退出，所以循环每次轮询都从时钟和持久 slot 重新推导欠什么，而不是握着一个定时器 |
| **显式工具注册表** | LLM 可见的工具面 grep 得到；不做动态扫描（隐式暴露是安全风险） |
| **GBrain 外挂做长期知识库** | markdown-first + hybrid search + 自动图谱；不自建 |
| **框架 telemetry 关闭** | AgentOS/agno 使用 telemetry 关闭；选择 cloud/API/CLI 引擎时 stage prompt 仍会发给对应 provider |

## 非目标

刻意不做：多用户授权 / 云 SaaS、高可用 / 集群、宿主机层面的调度（cron / launchd /
任务计划程序——调度器就是一个容器，所以根本不用面对这个平台分裂）、cron 表达式与
按星期过滤、重造 agno 的 AgentOS / tracing / memory、把 GBrain 当 agent 操作系统。

## 新能力怎么插进底盘

1. 新 agent：`configs/agents/<name>.yaml` + `prompts/agents/<name>.md`。
2. 新 tool：放 `src/next_signal/tools/<domain>/`，在该 package 的 `register()` 暴露稳定名字。
3. 新 integration：放 `src/next_signal/integrations/<domain>/` 或横向 `src/next_signal/integrations/`。
4. 新 workflow：`configs/workflows/<name>.yaml` 声明，复杂的在 `src/next_signal/workflows/<name>.py` 实现 factory。
5. 新 team：`configs/teams/<name>.yaml` 声明；复杂 routing 才加 `src/next_signal/teams/<name>.py`。
6. 新 collector（周期性 CLI 数据搬运，无 LLM）：实现在 `src/next_signal/collectors/<name>/`，
   手动 run 接入靠 `src/next_signal/workflows/<name>.py` 薄壳（YAML 设 `expose.agent_os: false`，
   `extra.run_now` 指向 collector 入口，由 `next-signal run-workflow <name>` 调用）。
7. collector 之上的 analysis workflow（LLM-driven 消费 collector 的业务表）：
   `src/next_signal/workflows/<name>_analysis/` 作为 package 实现，stages 拆到
   `stages/`；agent + prompt 用标准 YAML/markdown 路径；手动 run 接入同样靠
   thin shell `extra.run_now`；`seen_at` 列归 analysis 写，collector 不碰。
   currently shipped: `info_radar_analysis`。

完整步骤见 [开发指南](./development.md)。能力的规范契约在
[`openspec/specs/`](../../openspec/specs/)。各方向的深入文档（底盘 / 知识 / 信息流 /
操作台）在 [`docs/modules/`](./modules/core.md)；agent / 工具的全景清单不在
文档维护——`uv run next-signal list` 与 `src/next_signal/registry.py` 是 source of truth。
