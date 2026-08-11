# 容器化部署（Cloud-LLM）

> [English](../containerized-deployment.md) · **中文**

如何用 **Docker Compose** + **云端 LLM 后端**（不跑本地 MLX 模型），把整个
`next-signal` 栈跑在一个与宿主机操作系统隔离的环境里。本文是设计层面的：它解释
*什么*跑在*哪里*、*为什么*。它**不能**替代
[operations.md](./operations.md)（host-native 安装）—— 它是容器化的另一条路径。

> 范围：单用户、单主机、本地优先。不是多租户，不是高可用。
> [architecture.md](./architecture.md) 里的非目标同样适用于这里。

---

## 1. 为什么是 Docker Compose（而不是虚拟机）

决定性的约束是**本地模型**。OMLX / Qwen3 通过 `mlx-lm` 跑在 Apple 的 **Metal GPU**
上。而 Docker 和 Apple Silicon 上的 Linux 虚拟机**都访问不到 Metal** —— MLX 只在
裸机 macOS 上能用。所以本地模型**根本无法容器化**。

一旦你决定走**云 LLM 路线**，这个阻塞就消失了：剩下的每个组件（next-signal、Next.js
dashboard、Postgres、以及那些 Node CLI）都能在 Linux 容器里正常跑，通过 HTTPS 访问
云端模型。

- **Docker Compose** —— 可复现（`docker compose up`）、声明式、与宿主机的
  Python/Node/Postgres 天然隔离、挂卷简单。这是推荐方案。
- **虚拟机（UTM/Lima/Multipass）** —— 隔离更强但很重；在 macOS 上你的容器本来就跑在
  一个轻量 Linux 虚拟机里，再手工管一个 VM 只增加成本、收益不大。
- **宿主机上裸 `uv venv`** —— 隔离最弱（共享宿主机的 Postgres/Node/PATH）；容器化
  正是要*离开*这种状态。

**云 LLM + Docker 是天然搭配；本地 LLM + Docker 不是。**

---

## 2. 运行时拓扑

下图把**父操作系统边界**画清楚。双线框内的一切都跑在你的 Mac 上 —— 既包括 Docker
容器，*也*包括那个无法容器化的宿主机进程（本地 LLM server）。只有第三类连接会离开
这台机器。

```mermaid
flowchart TB
    user(["你 —— 浏览器"])

    subgraph host["父操作系统 —— macOS 宿主机（Apple Silicon）"]
        direction TB
        subgraph compose["docker compose"]
            direction TB
            subgraph appc["app（同一个镜像）"]
                next-signal["next-signal<br/>CLI（由 dashboard spawn）"]
                dash["dashboard<br/>Next.js :3000"]
                tools["gbrain · opencli · folocli"]
            end
            pg[("Postgres 16 + pgvector<br/>next-signal 主库")]
            gstore[("gbrain 存储<br/>Postgres 上的 gbrain 库")]
        end
        omlx["(A) OMLX / MLX server<br/>Metal GPU 上的 Qwen3<br/>本地 LLM —— embedding"]
    end

    subgraph remote["远端 / 互联网"]
        cloud["(B) 云 LLM API —— DeepSeek / Anthropic / OpenAI<br/>Folo 后端 · GitHub API · 公开网页（微信 HTML）"]
    end

    user -->|"localhost :3000"| dash
    next-signal -->|":5432 内部"| pg
    tools --> gstore
    appc -->|"(A) host.docker.internal:OMLX_PORT —— 留在宿主机"| omlx
    appc ==>|"(B) 出站 HTTPS/WSS —— 离开这台机器"| cloud

    classDef container fill:#e6f0ff,stroke:#3b6fb0,color:#0b2545;
    classDef local fill:#e8f5e9,stroke:#3a9d4a,color:#12401b;
    classDef ext fill:#fdeaea,stroke:#c0392b,color:#5a1a13;
    class next-signal,dash,tools,pg,gstore container;
    class omlx local;
    class cloud ext;
    linkStyle 3 stroke:#3a9d4a,stroke-width:2px;
    linkStyle 4 stroke:#c0392b,stroke-width:2px,stroke-dasharray:5 5;
```

**两类连接** —— 这正是边界的意义所在：

- **(A) 本地 LLM —— 留在宿主机。** 云端跑的是*对话*模型 (B)；embedder 可选，默认走
  OMLX（info-radar `analyze` 的 dedup 需要它）。`app` 容器通过
  `host.docker.internal:<port>` 访问宿主机的 MLX server；这部分流量从不离开你的 Mac。
  不配它，就要么选一个云端 embedder，要么接受 dedup gate 降级（见 §7）。
- **(B) 远端 —— 唯一离开机器的东西。** 云 LLM API、Folo 后端、GitHub REST API
  （knowledge 的 repo 查询）、以及公开网页抓取 —— 都是 `app` 容器的出站 HTTPS/WSS。

除 Postgres 外一个镜像就够了：单个 `app` 镜像打包所有可运行部分。dashboard 和
`next-signal` **必须共用一个镜像**，因为 dashboard 的 server action 会 spawn `next-signal` CLI
子进程（并 shell out 到 `gbrain` / `folocli`）—— 见
`dashboard/lib/actions/spawn-cli.ts`。

这个镜像撑起两个常驻服务，外加一次性的 `bootstrap`：`dashboard`（:3000）和 `scheduler`。
**scheduler** 跑 `next-signal schedule`——一个在配置的墙钟时间触发雷达链路的轮询循环，见
[运维](./operations.md#无人值守运行)。把它放进容器正是定时能跨平台的原因：宿主机方案意味着
要分别维护 cron、launchd 和 Windows Task Scheduler，而容器在三个平台上看到的是同一个 Linux。

它**刻意不放在 Compose profile 后面**。`~/.next-signal/schedule.json` 不存在就读作关闭，所以
没配置过计划的栈拿到的是一个闲置容器，而不是崩溃重启循环。

对应的限制：**宿主机没在跑 Docker 时什么都不会触发。** 没有容器能启动 Docker，所以睡眠或关机
的机器就是错过那个窗口；计划里的 `catch_up` 选项可以在调度器重新看得见时补跑一次来缓解，仅此而已。

---

## 3. 精确的放置图

三个桶 —— 诚实的划分不只是「容器 vs 宿主机」，还有「外部云」（两者都不是）。

### 3.1 容器内

| 组件 | 容器 | 说明 |
|---|---|---|
| Postgres 16 + pgvector | `postgres` | next-signal 主库：agno sessions/memory/traces + 业务表 |
| next-signal（Python 3.11 + uv） | `app` | CLI 入口，由 dashboard spawn |
| Next.js dashboard | `app` | 用 pnpm 构建，服务 `:3000`；会 spawn `next-signal` CLI 子进程，所以共用镜像 |
| gbrain 二进制 | `app` | 构建时从钉住的上游 clone 用 Bun 编译（Bun 只存在于 builder 阶段） |
| opencli（Node） | `app` | `weixin download` 走纯 HTTP；不打包也不需要浏览器 |
| folocli | `app` | 运行时经 `npx --yes` 拉取；与云端 Folo 后端通信 |
| Codex CLI + Claude Code CLI | `app` | 构建镜像时安装精确 npm 版本；直接仓库任务和选中的 production LLM stage 都通过 next-signal 的受限 bridge 执行 |
| gbrain 存储 | `postgres` | 同一个 Postgres 服务器上的独立 `gbrain` 库（`GBRAIN_DATABASE_URL`）。bun 编译出的二进制跑不了 PGLite（扩展 bundle 没有内嵌），而 pgvector 已经带了 `vector` + `pg_trgm` —— 所以 gbrain 用它的 Postgres 引擎 |

production CLI stage 比直接仓库任务更严格：provider 工具/自定义项全部关闭，只能看到一个
全新的空临时目录，看不到源码仓库或只读挂载的 `.env`。

### 3.2 父操作系统（宿主机）上

| 组件 | 为什么留在宿主机 |
|---|---|
| Docker Desktop / colima | 容器运行时本身 |
| `.env` | 只读挂载进 `app`；不放进镜像因为里面是真实密钥 |
| `digitalpaca-wiki/` + `digitalpaca-wiki-raw/` | 知识内容；bind-mount 让宿主机和容器保持一致。路径必须和容器*内部*的 `WIKI_DIR` / `WIKI_RAW_DIR` 对应 |
| `~/.next-signal/` state | knowledge_ingest_manifest.json、agent-tmp/，以及 dashboard 写的那几个设置——`language.json`、`engine.json`、`coding-agents.json`、`schedule.json`、`embedding.json`。用具名卷（或 bind mount）以便重建镜像后仍然保留。这五个文件正是 state root 不能烤进镜像的原因：dashboard 在运行时写它们，所有读者都在 call time 读、不用重启就生效，面板不可达时还能手改 |
| 发布的端口 | `localhost:3000` 是你访问容器的方式 |
| **OMLX / MLX 模型服务**（可选） | **无法容器化**（需要 Metal GPU）。除非在设置页选了云端 embedder，否则 info-radar `analyze` 的 **embedding** 需要它。云端对话模型不需要。用的话，容器通过 `host.docker.internal:<port>` 访问 |

### 3.3 外部 / 互联网（既不在容器也不在宿主机）

`app` 容器只通过出站 HTTPS/WSS 访问 —— 无需安装任何东西：

- **云 LLM：** DeepSeek（主），Anthropic/OpenAI 作为可配置的回落。
- **Folo 后端**（folocli 的服务器）、**GitHub REST API**（knowledge 的 repo 查询）、
  以及**公开网页**（opencli 抓取的微信文章 HTML）。

### 3.4 边界穿越

- **容器 → 宿主机：** 发布的端口（3000）；bind mount（`.env`、wiki 目录）；可选的
  `host.docker.internal` 调用到宿主机 OMLX server。
- **容器 → 外部：** 所有 LLM + Folo + GitHub + 网页流量，只出不进。
- **持久化状态：** `pgdata` 和 gbrain 存储用具名卷；用户 state 在 `pstate`；provider
  认证分别放在 `codex_auth` 和 `claude_auth` 具名卷中。

---

## 4. gbrain 和 opencli 从哪来

假设新用户**只**clone `next-signal` 这一个仓库，所以 `Dockerfile` /
`docker-compose.yml` 放在它里面，构建时必须从网络拉取这两个 peer 工具
（**钉住版本的 clone**，不是 vendor 进来）。

| | OpenCLI | gbrain |
|---|---|---|
| 上游 | `github.com/jackwener/OpenCLI` | `github.com/garrytan/gbrain` |
| 钉住的版本（已验证可用） | tag `v1.8.1` | `master` 上的 commit `a25209b`（该仓库没有 release tag） |
| 工具链 | Node + npm | **Bun** |
| 构建 | `npm install`（它的 `prepare` hook 会构建 `dist/src/main.js`） | `bun build --compile` → 自包含的 `bin/gbrain` |

规则：

- **钉住 ref**（tag 或 SHA），通过构建参数（`GBRAIN_REF`、`OPENCLI_REF`）传入。
  绝不 clone 裸 `main` —— 那会重新引入漂移并破坏缓存。
- 两个仓库都是公开的，不需要认证。但构建过程需要网络。
- **绝不拷贝宿主机的构建产物。** 本地的 `dist/`、`bin/` 或 `node_modules/` 都是为
  macOS/arm64 构建的，在 Linux 容器里跑不起来。镜像会重新构建它们。
- **多阶段构建：** 在 builder 阶段（带 Bun + Node）构建 gbrain + opencli，只把产物
  （`gbrain` 二进制；opencli 的 `dist/` + 运行时 `node_modules`）拷进运行时阶段。
- **在镜像内接好 env：** 把 `gbrain` 放上 `PATH`（或设 `GBRAIN_BIN`），并把
  `OPENCLI_BIN` 设成容器内 `dist/src/main.js` 的路径 —— 覆盖 `.env` 里的宿主机路径。

---

## 5. OpenCLI 需要浏览器吗

**不需要 —— 至少 next-signal 用的那条命令不需要。** OpenCLI 有「Browser Bridge」（一个
微守护进程 + Chrome 扩展）和 CDP 模式，两者都需要挂到*你*提供的、已登录的真实
Chrome 上。但 next-signal 只调用 `opencli weixin download`
（`src/next_signal/integrations/knowledge/opencli.py`），它的实现
（`OpenCLI/src/download/article-download.ts`）走**纯 HTTP** 抓取并把 HTML 转成
markdown。公开的微信公众号文章是服务端渲染的、不需要登录，所以 `app` 镜像保持
无浏览器 —— 不装 Chrome，也不需要 Xvfb。

### 5.1 固定版本的 coding-agent CLI

镜像在独立 Node stage 中安装精确的 `CODEX_CLI_VERSION` 和 `CLAUDE_CODE_VERSION`
构建参数（当前为 `0.145.0` 和 `2.1.220`）。构建时会运行两个版本命令，只把 launcher
和 package 目录复制到 runtime stage，并设置 `DISABLE_AUTOUPDATER=1`。升级属于镜像变更，
不是运行中容器里的自更新：

```bash
CODEX_CLI_VERSION=0.145.0 CLAUDE_CODE_VERSION=2.1.220 docker compose build dashboard scheduler
docker compose up -d --force-recreate dashboard scheduler
```

部署自动化不要使用 `latest`。重建镜像或重建服务不会移除登录，因为认证在具名卷里，
不在镜像里。

---

## 6. 构建 → 运行的生命周期

### 构建（镜像）

1. Linux/arm64 基础镜像 + Python 3.11；安装 `uv`、Node 22 + `pnpm`，以及（builder
   阶段）Bun。
2. 先拷依赖清单（`pyproject.toml`、`uv.lock`、dashboard 的 `package.json` + lockfile），
   在拷源码*之前*执行 `uv sync` 和 `pnpm install` —— 为了层缓存。
3. 在 builder 阶段做钉住版本的 clone 并构建 gbrain（Bun）和 opencli（npm），同时安装
   精确版本的 Codex CLI 和 Claude Code CLI。
4. 拷应用源码（next-signal 的 `src/`、`configs/`、`prompts/`、`scripts/`、dashboard 应用），
   然后 `pnpm build` 构建 dashboard。
5. 运行时阶段只拷产物。**绝不烘焙** `.env`、密钥、`state/`、`.venv`、宿主机的
   `node_modules` 或 wiki 内容。用 `.dockerignore`。

### 启动（compose）

6. 先起 `postgres`；挂上 `pgdata` 卷。
7. 让 `app` 依赖 Postgres 的**健康状态**（`depends_on: condition: service_healthy`），
   而不只是「已启动」。
8. 注入配置：`.env` 经 `env_file`（只读）、`DATABASE_URL` 指向 `postgres` 服务名、
   `OMLX_BASE_URL` 留空（→ 云回落）、wiki bind mount、state 卷。

### 入口脚本（每次启动，幂等）

9. 跑 `scripts/container_bootstrap.sh` —— next-signal 主库 schema（pgvector 扩展 + 业务表，
   经 `bootstrap_db.py`），然后创建 `gbrain` 数据库并跑 `gbrain init`（Postgres
   引擎）。全部幂等。
10. 可选地把 `next-signal doctor` 作为非致命日志跑一次（纯云环境下 OMLX / Anthropic 会显示
    ✗ —— 这是预期的；确认 Postgres / agents / tools 是 ✔ 即可）。
11. 启动长驻进程：`next-signal dashboard --start`（:3000）。
12. 把端口 3000 发布到宿主机；设 `restart: unless-stopped`。

一句话概括顺序：**构建镜像 → 起 Postgres → 等健康 → 挂 env+wiki+state → bootstrap
数据库（幂等）→ 启动 dashboard → 发布端口 → 自动重启，数据存在卷里。**

---

## 7. 用 Docker 跑起来

仓库根目录已经带了 `Dockerfile`、`docker-compose.yml` 和 `.dockerignore`。
前置条件：Docker Engine + Compose v2，以及一个 `.env`（从 `.env.example` 拷），
里面至少要有一个云 LLM key，以及指向你 wiki 仓库宿主机路径的 `WIKI_DIR` /
`WIKI_RAW_DIR`。

> **把栈跑起来 vs. 拿它验证一个改动。** 本节讲前者。如果你要验证一个改动是否生效
> ——改了什么该跑哪个 loop、容器里跑的到底是不是你的代码、哪些命令不烧 token、
> 什么才算证据——见
> [`.claude/skills/docker-verify/SKILL.md`](../../.claude/skills/docker-verify/SKILL.md)。
> 它要防的那个坑：`/app` 是烤进镜像的，所以改完 `src/` 直接 `docker compose exec`
> 验的是**改之前**的代码。

> **与宿主机相关。** 下面的 shell 片段默认 POSIX shell（macOS 上是 zsh，自 Catalina
> 起的默认）。Windows 上跑在 PowerShell 里，引号处理和 exit code 的语义都不同，
> 而且是静默出错——跨平台对照表在上面那个 skill 里。

### 快速开始

1. 安装并启动 Docker Engine + Compose v2（Docker Desktop 或 colima）。
2. `cp .env.example .env`，然后编辑：至少设一个云 LLM key
   （DeepSeek/Anthropic/OpenAI），以及把 `WIKI_DIR` / `WIKI_RAW_DIR`
   设成你 wiki 仓库的宿主机路径。
3. 构建并启动整个栈：
   ```bash
   docker compose up --build
   ```
4. 等 `bootstrap` 跑完（一次性任务，依赖 Postgres 健康）—— `dashboard` 会自动等它。
5. 打开 <http://localhost:3000> 访问 dashboard。
6. 对要使用的 provider，各执行一次 **设置 → Codex CLI / Claude Code CLI → 连接**；
   在官方页面完成登录，Claude 要求时把授权码粘贴回 Dashboard。显式保存该 CLI 的模型和
   强度（Codex 还要保存速度），再选择 production 引擎。
7. `docker compose down` 停止（保留所有具名卷）；只有明确要清空数据库、应用 state
   和两个 CLI 登录时才加 `-v`。

- **服务：** `postgres`（pgvector）、`bootstrap`（一次性 schema）、`dashboard`
  （`next-signal dashboard --start`）和 `scheduler`（`next-signal schedule`）。
- **配置：** `.env` 经 `env_file` 注入（绝不烘焙进镜像）；`DATABASE_URL` 和容器内的
  wiki/state 路径在 compose 的 `environment:` 块里覆盖。peer 工具的 ref 和 coding-agent
  版本都是构建参数（`GBRAIN_REF`、`OPENCLI_REF`、`CODEX_CLI_VERSION`、
  `CLAUDE_CODE_VERSION`）。
- **持久化：** 具名卷 `pgdata`（Postgres —— 包括 `gbrain` 数据库）、`pstate`
  （`~/.next-signal` state + gbrain 的 `config.json`）、`codex_auth`（`/root/.codex`）
  和 `claude_auth`（`/root/.claude`）。`docker compose down` 会保留它们；`down -v`
  会把四个都清空。

### coding-agent CLI 登录

Dashboard 登录端点刻意不是 shell。浏览器只能选择 `codex` 或 `claude`；服务端映射成
`codex login --device-auth` 或 `claude auth login --claudeai`，在有边界的 PTY 中运行，
最多接收一行授权码，并且只允许跳转到 provider 域名白名单内的 HTTPS URL。短期 transcript
只存在进程内存中，不写入 `/state` 或应用日志。

Compose 默认把端口绑在 `127.0.0.1`，因为登录和退出会改变凭据状态。确实要远程访问时，
先放到带认证的 HTTPS 反向代理后面，再显式设置 `DASHBOARD_BIND_ADDRESS`；不要直接把端口
无认证地暴露出去。

UI 无法完成流程时，可以在 Dashboard 容器 terminal 中使用同一认证卷：

```bash
docker compose exec dashboard codex login --device-auth
docker compose exec dashboard claude auth login --claudeai
docker compose exec dashboard next-signal coding-agent auth-status codex
docker compose exec dashboard next-signal coding-agent auth-status claude
```

重建镜像和 `docker compose down` 都保留登录。移除单个登录时优先在设置中点**断开连接**，
也可以执行 provider 的 logout 命令。即使 CLI 损坏也要删除凭据文件时，先停止服务，再只删
对应的具名卷；除非数据库和 next-signal state 也准备丢掉，否则不要用
`docker compose down -v`。

**本地 LLM（可选）。** 纯云部署应在设置中选择 DeepSeek 或已登录的 CLI（也可以把它设为
首次响应前的回落）。要启用 OMLX 引擎和 embedder——info-radar `analyze` 的语义去重需要
后者——在**宿主机**上跑一个 OMLX server，然后
在 `.env` 里加：`OMLX_BASE_URL=http://host.docker.internal:<port>/v1`。
`host.docker.internal` 已经通过 `extra_hosts: host-gateway` 为 Linux 接好。

**首次构建注意。** `openai-whisper` 会带进 **torch**；`pyproject.toml` 把 Linux 上的
安装钉到 PyTorch 的纯 CPU wheel 源（`tool.uv.sources` / `tool.uv.index`，见 §8），
这样构建不会把 CUDA 工具链拖进来。如果 `pnpm build` 因为某个 dashboard 页面在预渲染
时访问 Postgres/wiki 而失败，把 `dashboard` 的 command 换成 dev 模式：
`["next-signal", "dashboard", "--port", "3000"]`。

---

## 8. 纯云容器特有的注意事项

1. **embedder 可选，但它自己永远不回落。** 默认走 OMLX，所以在纯容器环境里
   info-radar `analyze` 的 dedup 在你动手之前会**失败**——那时每个条目都会被当成新的。
   对话、agent 和 dashboard 页面都正常。两条出路：

   - 通过 `OMLX_BASE_URL=http://host.docker.internal:<port>/v1` 暴露一个宿主机/远程
     OMLX 端点；或者
   - 打开 **设置 → 向量嵌入**，选 OpenAI（需要 `OPENAI_API_KEY`）或者你自己的
     OpenAI 兼容端点。

   选云端 embedder 有两个后果，值得刻意决定一下。每条留下来的条目，它的分析摘要都会
   **发给那个服务商**——而 OMLX 同时承担两半时这些文本根本不出本机——并且每个条目都
   **可能计费**，包括没人盯着的无人值守定时运行。embedder 之间刻意**没有**自动回落：
   悄悄换一个就等于换了向量空间，会把当前 provider 的 dedup 记忆搁置掉，所以失败保持
   loud，条目按 novel 处理。

   凭据来自进程环境，不在状态文件里。改 `.env` **不会**影响已经在跑的容器：先重建服务
   （`docker compose up -d --force-recreate dashboard scheduler`）再指望新值存在。
   `docker compose exec dashboard next-signal doctor` 会报告解析出来的 embedder 身份以及
   它的变量在不在，全程不发模型请求。
2. **`next-signal doctor` 只要有任何一项失败就退出非零** —— 纯云环境下把 OMLX / Anthropic
   的 ✗ 当作预期，别让它阻断启动。
3. **密钥不进镜像。** `.env` 目前存的是真实 key；运行时挂载，绝不 `COPY` 进某一层，
   也绝不推送出去。
4. **各页面的依赖不同：** `/goals` 和 `/design` 只需要 Postgres/文件系统；`/radar`
   需要 `info-radar pull` 填充过的 Postgres；`/knowledge` 需要 gbrain CLI；
   `/subscriptions` 需要 Folo 认证。
5. **`openai-whisper` → torch 仍然是最大的单个依赖。** whisper 只被 Bilibili ingest
   集成使用，而且只作为无字幕视频的音频转写回落
   （`src/next_signal/integrations/knowledge/bilibili.py`）。`pyproject.toml` 把 Linux 的
   `torch` 安装路由到 PyTorch 的纯 CPU 源（`tool.uv.sources` / `[[tool.uv.index]]`
   指向 `download.pytorch.org/whl/cpu`），这样 CUDA 工具链 + nvidia-*/triton 那一堆
   不会被拉进来 —— 光这一项就是好几个 GB。如果你从不入库无字幕视频，把
   `openai-whisper`/`torch` 在 `pyproject.toml` 里改成可选依赖能进一步缩小镜像
   （那条回落路径届时会在被触发时 loud fail）。
6. **已有的 `pgdata` volume 里还是旧的 `paca` role。** compose 里 `POSTGRES_USER`
   的默认值现在是 `next_signal`，但 `POSTGRES_USER` 只在 `initdb`（数据目录为*空*）
   时生效 —— `next-signal` 改名之前创建的 volume 里只有 `paca` 这个 role，所以
   所有连接都会以 `role "next_signal" does not exist` 失败。先改一次名，再让新
   默认值生效。

   Postgres 不允许改自己当前连接用的那个 role（`ERROR: session user cannot be
   renamed`），而这个镜像里没有第二个超级用户 —— 所以要临时建一个：

   ```bash
   docker compose exec -T postgres psql -U paca -d next_signal -c "CREATE ROLE tmp_rename SUPERUSER LOGIN;"
   docker compose exec -T postgres psql -U tmp_rename -d next_signal -c "ALTER ROLE paca RENAME TO next_signal;" -c "ALTER ROLE next_signal WITH PASSWORD 'next_signal';"
   docker compose exec -T postgres psql -U next_signal -d next_signal -c "DROP ROLE tmp_rename;"
   ```

   第二条不是可选的：`ALTER ROLE ... RENAME` 会清掉已存的密码。整个过程不碰任何
   表数据 —— 改的是 role，不是 schema。想完全跳过迁移，就在 `.env` 里钉住
   `POSTGRES_USER=paca`。回滚是同样三步、名字对调。从空 volume 起步则完全不需要。

   role 改名会留下一个尾巴：gbrain 把自己的 `database_url` 缓存在
   `$GBRAIN_HOME/.gbrain/config.json` 里，而 bootstrap 脚本在这个文件已存在时走
   `gbrain init --migrate-only`（见 `scripts/container_bootstrap.sh`），所以那个
   缓存里的 URL 会一直是旧 role。在 compose 下无害 —— compose 总会注入
   `GBRAIN_DATABASE_URL`，优先级更高。但任何**不带**这个变量的 gbrain 调用都会用
   一个已经不存在的 role 去认证。要么保证这个变量始终注入，要么删掉那个
   `config.json` 再跑一次 `bootstrap` 服务，把缓存刷新一次。

---

## 9. 一句话总结

两个容器：`postgres`（`pgvector/pgvector:pg16`）+ 一个 `app` 镜像，打包了
Python(uv)+next-signal、Node(pnpm)+dashboard，外加 gbrain（Bun 构建）和 opencli（纯 HTTP），
两者都在构建时从上游做钉住版本的 clone。宿主机只保留 Docker 运行时、挂载的文件
（`.env`、wiki、state），以及 —— *仅当你想用本地 embedding 而不是云端的时候* —— 一个
宿主机 OMLX server。其余一切要么在容器里，要么作为外部云 API 被访问。
