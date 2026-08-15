# 运维与排查

> [English](../operations.md) · **中文**

## 安装

> **容器是推荐路径** —— 见
> [`containerized-deployment.md`](./containerized-deployment.md)，或
> [README 快速开始](../../README.zh-CN.md#快速开始)。
> 以下是 host-native 备选路径；需要本地 OMLX 模型跑在同一进程里时走这条。

```bash
brew install uv
brew install --cask postgres-app          # 或 brew install postgresql@16
uv sync
cp .env.example .env && $EDITOR .env       # 至少 DATABASE_URL + 一个 LLM key
createdb next_signal
uv run python scripts/bootstrap_db.py
uv run next-signal doctor
uv run next-signal serve                          # → http://localhost:7777
uv run next-signal dashboard                      # → http://localhost:3000
```

## 必需 / 可选服务

必需（最小可用）：Postgres 16+ with pgvector、OMLX OpenAI 兼容端点、
GBrain CLI（知识检索必需）。

可选：folocli 认证（info-radar collector）、GitHub token（knowledge 的 GitHub
收藏功能，缺省匿名 60 req/h）、OpenCLI（WeChat 文章入库），以及本机安装的 Codex /
Claude Code CLI（显式委托仓库任务）。

Dashboard 是单独的 Next.js 进程，不要求 `next-signal serve` 同时运行；它的 server action
会直接启动一次性 `next-signal` CLI 子进程，数据页直接读 Postgres。

## 环境变量

repo-local `.env` 关键值：

- `DATABASE_URL`
- `OMLX_BASE_URL` / `OMLX_API_KEY`
- 各云模型 / API key（按需）
- `GBRAIN_BIN`（`gbrain` 不在 `PATH` 时；dashboard 与后端同一套解析）
- `WIKI_DIR` / `WIKI_RAW_DIR`（**代码层面必填**，无默认；缺失时 knowledge pipeline 与
  dashboard wiki 视图 fail loud。跑 Docker Compose 时可以留空：Compose 会挂载
  `./state/wiki` 和 `./state/wiki-raw` 并自己设定容器内的值，所以代码读到的地方永远有值）
- `NEXT_SIGNAL_STATE_DIR` / `NEXT_SIGNAL_AGENT_TMP_DIR`（可选，测试或换路径）

内容语言——radar 分析和 wiki frontmatter 用什么语言写——**不是** env var，而是 `global`
语言 policy 的实时偏好文件 `~/.next-signal/language.json`（`content_language: zh | en`），
由 dashboard 的**设置页**（`/settings`，从 nav 上的齿轮进入）写入，文件缺失时回落到硬编码默认值。旁边
nav 上的语言选择器是另一个独立设置，只改 dashboard 自己的界面文案；两者互不影响，可以不
一致。见 [modules/core.md](./modules/core.md#输出语言)。

不要在任意模块直接读这些；走对应的 core / helper 函数。完整 key 列表见 `.env.example`。

| 集成 | Env Var |
|---|---|
| LLM: Anthropic / OpenAI / Google / DeepSeek | `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GOOGLE_API_KEY` / `DEEPSEEK_API_KEY`（+ 可选 `DEEPSEEK_BASE_URL`，默认 `https://api.deepseek.com`） |
| Folo (info-radar) | `FOLO_TOKEN`（可选；不设则用 `~/.folo/config.json`） + 可选 `FOLO_CLI_ARGV` 覆盖默认 `npx --yes folocli@<v>` |
| GBrain / OpenCLI (knowledge) | `GBRAIN_BIN`（`gbrain` 不在 PATH 时） / `OPENCLI_BIN`（WeChat 下载，main.js 路径或 wrapper） |
| Coding agents | `CODEX_BIN` / `CLAUDE_BIN`（可选的可执行文件覆盖；已保存的 CLI 登录仍由 provider 管理） |
| GitHub (knowledge 收藏) | `GITHUB_TOKEN`（可选；缺省匿名 60 req/h） |
| Embedder (info-radar analysis dedup) | 取决于**设置 → 向量嵌入**里选的 provider，见下 |

每个云集成在 call time 才检查 key，缺 key 只让对应工具失败，不阻断启动。

### 选择 embedder

dedup gate 的 embedder 与 LLM 引擎分开选，在 `/settings` 上，存进
`~/.next-signal/embedding.json`。三个 provider：

| Provider | 配置 | 说明 |
|---|---|---|
| `omlx`（默认） | `OMLX_BASE_URL` 可达；`configs/models.yaml::embedders.local.model_id` 默认 `Qwen3-Embedding-0.6B-8bit`，需要 OMLX server 加载该模型 | `OMLX_API_KEY` 仍是可选的。数据不出本机 |
| `openai` | `OPENAI_API_KEY`；模型取自 `embedders.openai`（默认 `text-embedding-3-small`） | 按条目计费；摘要会离开本机 |
| `openai_compatible` | 一个 API **根地址**（例如 `https://host.example/v1`——`/embeddings` 由程序拼），一个模型，存放密钥的环境变量**名字**，以及一个向量空间 id | 没有出厂默认值；四项都保存后才能选中 |

换之前有三条值得先想清楚：

- **每个 embedder 都必须返回正好 1024 个有限数值。** 云端路径会带 `dimensions: 1024`；
  其他情况在调用时直接抛，不会被塑形。所以 `text-embedding-ada-002` 之类做不到 1024
  的定宽模型无法使用。
- **状态文件从不存密钥。** `openai_compatible` 存的是 `api_key_env`——变量的*名字*——
  取值时从流水线进程的环境读。URL 里带凭据（userinfo、query、fragment）会被直接拒绝。
- **改 `.env` 不会热加载。** 改状态文件下一个 item 就生效、不用重启；但凭据只存在于
  设置之后才启动的进程里：重启宿主进程，或
  `docker compose up -d --force-recreate dashboard scheduler`。

`space_id` 是你自己给通用端点产出的向量起的标签。权重、分词器、pooling、量化或维度行为
变了就换一个；同一个服务换个 URL **不需要**换。它和模型名分开，是因为两个端点可以打着
同一个模型名产出互不可比的向量，而误判成重复会把真正的新条目吞掉。

### 换 embedder，以及 `legacy:unknown` 那些行

每条存下来的向量都在 `radar_pushed_topics.embedder` 里记着产生它的身份
（`omlx:<model>`、`openai:<model>` 或 `openai_compatible:<space_id>`），dedup 检索永远只在
同一个身份内比较。所以换 provider 是把上一个身份的记忆**搁置**，而不是翻译过去：在新身份
下重新积累之前，见过的主题会被报成 novel。切回去那些行原样恢复、不需要重新嵌入——全程
不删任何数据。

这个列出现之前写下的行标记为 `legacy:unknown` 并永久搁置。bootstrap 不猜它们的来源：
`embedders.local.model_id` 一直是可改的，按出厂默认值去认会给改过配置的安装打错标签，
正好制造出这个身份要防的跨空间比较。

如果你自己确知它们出自哪个模型——比如你从没改过 `embedders.local.model_id`——可以自己重新
打标。这一步刻意保持手动、没有 UI，靠猜执行是不安全的：

```sql
-- 只有在你确定迁移前的每一行都出自这个模型时才执行。
UPDATE radar_pushed_topics
   SET embedder = 'omlx:Qwen3-Embedding-0.6B-8bit'
 WHERE embedder = 'legacy:unknown';
```

先看清楚你要改的是哪些：

```sql
SELECT embedder, count(*), min(first_seen_at), max(last_seen_at)
  FROM radar_pushed_topics GROUP BY embedder ORDER BY 2 DESC;
```

### 从 `paca` 旧名字迁移

`next-signal` 改名之前的版本用 `PACA_` 前缀、`paca` CLI、以及 `paca` 这个
Postgres role。有三件事仓库里没有任何脚本能替你做：

1. **改 `.env` 里的 key** —— 它是 git-ignored 的，改名没碰它：

   | 旧 | 新 |
   |---|---|
   | `PACA_WIKI_DIR` / `PACA_WIKI_RAW_DIR` | `WIKI_DIR` / `WIKI_RAW_DIR` |
   | `PACA_GBRAIN_HOME` / `PACA_GBRAIN_DATABASE_URL` | `GBRAIN_HOME` / `GBRAIN_DATABASE_URL` |
   | `PACA_WHISPER_MODEL` / `PACA_YOUTUBE_TRANSCRIPT_LANGS` | `WHISPER_MODEL` / `YOUTUBE_TRANSCRIPT_LANGS` |
   | `PACA_STATE_DIR` / `PACA_AGENT_TMP_DIR` | `NEXT_SIGNAL_STATE_DIR` / `NEXT_SIGNAL_AGENT_TMP_DIR` |
   | `PACA_LOG_LEVEL` / `PACA_DATABASE_URL` | `NEXT_SIGNAL_LOG_LEVEL` / `NEXT_SIGNAL_DATABASE_URL` |

   `WIKI_DIR` 不设会 loud 失败（`RuntimeError`）而不是走默认值 —— 这是设计如此，
   不是 regression。

2. **改 Postgres role**（复用已有 `pgdata` volume 时）。`POSTGRES_USER` 只在
   `initdb`（空数据目录）时生效，所以光改 compose 默认值不会迁移一个已经存在的
   volume —— 见 [containerized-deployment.md](./containerized-deployment.md)。

3. **Dashboard 界面会重置一次。** locale 和 recap 面板的 cookie 改名了
   （`paca_locale` → `ns_locale`，`paca_recap_collapsed` → `ns_recap_collapsed`），
   旧的不再被读取：界面回到默认语言，recap 面板展开。两个都是点一下就恢复。

## State 位置

- 项目 repo：configs、prompts、代码、tests、OpenSpec specs。
- 用户 state（`~/.next-signal/`）：`knowledge_ingest_manifest.json`、`language.json`
  （内容语言偏好）、`engine.json`（production LLM 选择）、`embedding.json`
  （dedup embedder 选择）、`coding-agents.json`（显式 Codex / Claude CLI 设置）、
  `goals.yaml`（info-radar 目标描述）、`agent-tmp/`。

  `goals.yaml` 放这里而不是 `configs/` 下，是因为 dashboard 写它、scheduler 读它：
  `configs/` 烤进镜像，写在那里只会落到某一个容器的可写层，另一个容器看不见，下次
  rebuild 还会丢。容器 bootstrap 在全新安装时把它填好——有旧的
  `configs/info_radar/goals.yaml` 就迁移过来，否则复制
  `configs/info_radar/goals.example.yaml`。文件已存在就是 no-op，**包括**里面是
  故意清空的 `goals:` 列表，所以清空目标这件事能扛过重启。
- 知识库：`~/Projects/digitalpaca-wiki/`（clean）、`~/Projects/digitalpaca-wiki-raw/`（raw）
  ——路径由 `WIKI_DIR` / `WIKI_RAW_DIR` 指定，不是硬编码默认值。
- agno 自管表（sessions / memory / knowledge / traces）：本地 Postgres + pgvector。
- 日志：只写 stdout（structlog，TTY 下 console 渲染，非 TTY 下 JSON）；`~/Library/Logs/next-signal/`
  目录会被创建但当前没有代码往里写文件。

跑 Docker Compose 时这些改为映射到 `pstate` 卷和 wiki bind mount，见
[`containerized-deployment.md`](./containerized-deployment.md)。

## 健康检查

```bash
uv run next-signal doctor                            # host-native
docker compose exec dashboard next-signal doctor     # 容器里
```

检查：`DATABASE_URL`、`ANTHROPIC_API_KEY`、`DEEPSEEK_API_KEY`、`OMLX_BASE_URL`、
解析后的内容语言（报出 `global` policy 的值、来自偏好文件还是硬编码默认值，偏好文件
损坏或值不认识则标红）、解析后的 embedder（打印当前向量空间身份，以及它需要的配置在不在
——全程不发嵌入请求，`embedding.json` 不可用时报成失败项而不是把 doctor 弄挂）、
Postgres 可达、
configured agents、registered tools、GBrain CLI/service（`gbrain doctor --fast`）、
folocli auth（`folocli whoami` — `FOLO_TOKEN` 或 `~/.folo/config.json` 任一可用即可）、
info-radar 运行时 goals 文件存在、可解析、且至少有一个目标。goals 这一项把三种失败
分开报——完全没有文件、`goals:` 配成空列表、解析出错——因为处理方式不同；三种情况下
`next-signal info-radar analyze` 都会 loud RuntimeError。
代码层面不区分"必需"和"可选"检查——任一项失败（包括上面标为可选的 folocli auth）
doctor 都退出非零；上面的必需/可选划分只是"这台机器不打算用这个功能就可以忽略对应的✗"。

`DEEPSEEK_API_KEY` 缺失算非零项 —— `local*` 的默认 fallback profile 用 DeepSeek（OMLX 不可达时回落）；
`ANTHROPIC_API_KEY` 缺失也算非零项，供 `claude_*` profile 使用。若刻意只跑本地，要明白这些云 fallback 会失败。

纯云容器里 OMLX（以及没配的 Anthropic）显示 ✗ 是预期的——确认 Postgres / agents / tools
是 ✔ 即可，其余当参考信息。

## 可选 coding-agent CLI

`next-signal coding-agent` 调用本机安装的命令行程序；它不控制 Codex 或 Claude 桌面版，
也不会把这两个 worker 注册成 agno model 或 agent tool。先按 provider 的正常方式安装并
登录 CLI，再单独检查这些可选前置条件：

```bash
uv run next-signal coding-agent doctor
```

`doctor` 从 `PATH`（或 `CODEX_BIN` / `CLAUDE_BIN`）解析 `codex` / `claude`，只运行
`--version`，不会发起模型请求。执行任务时必须显式指定工作目录：

```bash
uv run next-signal coding-agent run codex "检查这个仓库" --cwd .
uv run next-signal coding-agent run claude "修复失败的测试" --cwd . --profile edit
uv run next-signal coding-agent run codex "总结这次修改" --cwd . --progress
```

默认使用 `review` profile：Codex 运行在只读 sandbox，Claude 使用 `dontAsk` 且只有
只读工具。需要编辑时必须显式选择 `edit`：Codex 使用 `workspace-write`，Claude 只能使用
`configs/coding_agents.yaml` 里列出的文件工具和命令模式。仓库自带配置无法选择 Codex
`danger-full-access` 或 Claude `bypassPermissions`。

同一份 YAML 会把解析后的工作目录限制在本项目内，设置超时和输出上限，并列出 provider
子进程可以额外继承的环境变量“名字”。runner 总会传递 CLI 和已保存登录所需的少量 OS
基础变量，但不会把 next-signal 的其余环境整体复制过去。只有子进程确实需要某个 API key
时才把对应变量名加入列表；同时要记住，agent 执行的仓库代码可能读取这个值。

Dashboard 设置页可以覆盖后续 next-signal Codex 调用的模型、推理强度和标准/快速速度，
也可以覆盖 Claude 调用的模型和思考强度。它写入 `~/.next-signal/coding-agents.json`；缺失
两个 CLI 都不会继承或使用硬编码默认值：二者必须显式保存模型和强度，Codex 还必须保存
速度，调用才能启动。runner 每次调用 provider 时都会读取并校验；缺少必需状态或文件损坏
时会在启动 provider 前失败。Claude 模型和强度分别
使用单次会话的 `--model`、`--effort`，强度可选 `low`、`medium`、`high`、`xhigh`、`max`，
实际可用值取决于所选模型。Codex 快速模式只在当前模型和账号支持时可用，而且会更快消耗
额度。next-signal 不会修改 `~/.codex/config.toml` 或 `~/.claude/settings.json`。

同一个设置页把 production 引擎选择写入 `~/.next-signal/engine.json`。info-radar
分析/回顾和 knowledge ingest 的 LLM stage 在每个顶层 job 开始时读取一次，整单固定使用
同一个引擎。只有主引擎在首次成功响应之前失败时才允许使用配置的回落；schema 错误在同一
引擎修复，后续 provider 故障也不会在一单中混用引擎。OMLX constrained decoding、
DeepSeek JSON object、Claude `--json-schema` 和 Codex prompt 内 schema 最终都走同一套
本地 Pydantic/JSON5 校验和一次修复。抓取、embedding、ANN、持久化和 GBrain 不会改道。

production CLI stage 使用专用 no-tools `stage` profile，不使用直接仓库任务的 `review`
profile。每次调用只允许访问一个全新的空目录。Codex 忽略用户/仓库指令并关闭工具特性；
Claude 使用 safe mode、关闭 slash command、得到空 built-in tool set。因此新闻/文章 prompt
无权读取源码仓库、`.env`、hooks、plugins、MCP server，也不能运行命令。

Codex 和 Claude 使用各自已有的 CLI 登录；next-signal 不把 `~/.codex`、`~/.claude`
或钥匙串凭据复制到自己的 state。宿主机安装仍由用户自行安装并登录 CLI；官方 Docker
镜像则内置两个固定版本的 CLI，Dashboard 的引擎面板可以启动其固定登录流程。登录信息
分别留在挂到 `/root/.codex` 和 `/root/.claude` 的 provider-owned Docker volume 中。
浏览器不能指定命令、argv、可执行文件路径、工作目录或环境变量。

operator 直接执行 `coding-agent run` 时，Claude 默认继承本机 hooks、plugins、MCP servers、
auto memory 和 `CLAUDE.md`。只有受控的 API-key 自动化才应设置 `providers.claude.bare: true`：bare
模式会跳过这些本机上下文，也不会使用 Claude 订阅 OAuth。UI 登录、terminal 回落、
版本升级和认证卷生命周期见[容器化部署](./containerized-deployment.md#coding-agent-cli-登录)。

`--progress` 会把 stdout 改成 JSONL：先输出 provider event envelope，最后只输出一个
terminal result envelope。这个直接仓库任务命令是一次性且不持久化的；它没有隐式
resume、provider fallback、Dashboard 执行面或后台任务。production workflow 的回落由
上面的 stage adapter 管理，不属于这个直接命令。

## 常用命令

```bash
uv run next-signal list                                     # 列 agents / workflows
uv run next-signal doctor                                   # 自检
uv run next-signal run-agent <name> "<prompt>"              # 一次性调某个 agent
uv run next-signal coding-agent doctor                       # 检查可选 coding-agent CLI
uv run next-signal coding-agent run codex "检查这个仓库" --cwd . [--profile edit] [--progress]
uv run next-signal serve [--port 7777]                       # 启动 AgentOS
uv run next-signal schedule                                  # 跑墙钟调度器（前台）
                                                      # 每 30s 重读 ~/.next-signal/schedule.json；
                                                      # 在 dashboard 设置页里配置
uv run next-signal dashboard [--port 3000]                   # 启动 Next.js dashboard
uv run next-signal dashboard --build                         # dashboard production build
uv run next-signal dashboard --start                         # 启动已 build 的 dashboard
uv run next-signal knowledge ingest <url|staged-file>        # ingest 到知识库
#   --category <taxonomy-path>   指定落点，跳过自动分类
#   --progress                   每步输出一行 JSON 事件（dashboard 入库进度面板用）
uv run next-signal knowledge gbrain-search "query"           # 搜索本地 GBrain
uv run next-signal knowledge gbrain-ingest <file|dir>        # 导入 markdown 到 GBrain
uv run next-signal knowledge review                          # 对照 wiki 与 knowledge_reviews
                                                      # （入列新文档、移除已删的；固定艾宾浩斯曲线）
uv run next-signal info-radar pull [--source NAME]           # 跑各 source CLI，写 radar_items
uv run next-signal info-radar sweep                          # 删 radar_items 中超 30 天的行
uv run next-signal info-radar analyze [--limit N] [--source NAME]
                                                      # 跑两层 analysis pipeline，写 radar_analyses
                                                      # 由 CLI、dashboard 或调度器触发
                                                      # `seen_at` 保证任意频率重跑 idempotent
                                                      # 前置：运行时 goals 文件至少要有 1 个目标
                                                      # (~/.next-signal/goals.yaml，bootstrap 填好；在 /goals 页面编辑)
uv run next-signal info-radar subscriptions --json           # 读取 Folo 订阅，输出 dashboard 稳定 JSON 行
                                                      # 合并 `unread list` 拿每个 feed 的未读数
uv run next-signal info-radar recap --since D --until D [--min-score N] [--novel-only] [--regenerate]
                                                      # 把一个日期区间的 kept 信号归纳成主线叙述
                                                      # （按区间 + 门槛缓存）
uv run next-signal run-workflow knowledge_ingest             # 手动跑 wiki → GBrain re-ingest
```

Dashboard UI 默认英文，可在导航栏切中文；选择存到 `ns_locale` cookie。这里只翻译
界面文案，文章标题、分析摘要、tag、YAML 内容等数据按原样显示。

需要碰真实 GBrain 索引的全链路测试，用隔离的 PGLite brain：

```bash
uv run next-signal knowledge init-test-gbrain
GBRAIN_HOME=state/test-gbrain uv run next-signal doctor
```

`GBRAIN_HOME` 是父目录，GBrain 把配置和 `brain.pglite` 存到
`$GBRAIN_HOME/.gbrain/`。保持在 ignored 的 `state/` 下，别动生产 `~/.gbrain`。

## 无人值守运行

雷达链路——先 `info-radar pull` 再 `info-radar analyze`——可以按墙钟自动跑，不必手动触发。
`docker-compose.yml` 里的 `scheduler` 服务跑 `next-signal schedule`：一个轮询循环，在每个配置
的本地时间点触发这条链。在 **dashboard 设置页**（nav 上的齿轮）里配置：开关、时间、
以及错过时怎么办。

计划存在 `~/.next-signal/schedule.json`，每次轮询都重读，所以在 dashboard 改完 30 秒内生效，
不需要重启。手改也可以：

```json
{ "enabled": true, "at": ["08:00", "13:00", "20:00"], "catch_up": false }
```

`at` 是一组 `INFO_RADAR_TIMEZONE` 下的 24 小时制本地时间——和 dashboard 划分雷达"当天"用的是
同一个时区。**列出的每个时间点每天都会触发**，所以上面这个例子每天跑三次。写入时会去重并排序；
也仍然接受裸字符串并读作单个时间——多时间点出现之前这个字段就是这么存的。文件不存在表示从没
配置过，读作关闭；正因如此，这个服务在没人配置过的栈上常驻也是安全的。

`enabled` 和 `catch_up` 必须是**真正的 JSON 布尔值**。带引号的 `"enabled": "false"` 会被
拒绝并报出字段名，而不是被读成 `true`——后者正是朴素的字符串转布尔会干的事，且与写下它的人
想表达的意思完全相反。这两个字段缺失是可以的，读作 false。文件损坏会让调度器 loud 报错退出、
重启后再撞上同一个错误，这是刻意的：dashboard 全程不受影响，所以修这个文件的面板始终可达。

**`catch_up` 只覆盖一种情况：时间点到来时没人在看。** 关着（默认）就跳过；开着就
补跑**一次**——无论错过了多少个时间点都只跑一次，配了多个每日时间点时也是一次而不是每个错过
的时间点各一次。它不会因为你改了计划、加了时间点或刚打开开关而触发；今天已经过去的时间点永远
不会触发运行。

"没人在看"由时钟判定，跟调度器为什么不在场无关：容器停了、宿主机睡过了那个点（进程从头到尾
没重启过）、上一趟运行超时压过了下一个时间点——这是同一种情况，得到同一个答案。最后那条正是
为什么关着 catch-up 时，一趟长跑不会在自己尾巴上再叠一趟。

宿主机没在跑 Docker 时什么都不会触发。容器里的东西没法启动 Docker，所以合着盖子过了一夜就是
错过这个窗口——`catch_up` 是缓解手段，不是修复。

设置页会显示上次运行处在什么状态——尚未运行、正在运行（连同已经跑了多久）、成功、失败。被杀掉
的容器留下的中断运行，在调度器再次启动后读作失败，而不是仍在飞行中。一趟完整的雷达运行可能要
几十分钟，所以"正在运行"这一行的意义就是把"还在干活"和"什么都没干"区分开。调度器每次运行也会
写容器日志：

```bash
docker compose logs -f scheduler
```

## 故障排查

- **`DATABASE_URL not set`** → 复制 `.env.example` 到 `.env` 并填好。
- **Postgres unreachable** → 启动 Postgres.app 或 Homebrew service，重跑 `next-signal doctor`。
- **OMLX profile 回落到 DeepSeek** → 查 `OMLX_BASE_URL` / `OMLX_API_KEY` / 端点 `/v1/models`；
  OMLX 恢复后长驻进程要调 `next_signal.core.models.reset_cache()`。
- **GBrain 搜索 / re-index 失败** → 跑 `next-signal doctor` 和 `gbrain doctor --fast`；
  embed 失败时 ingest 应在写完 wiki artifact 后 loud fail，manifest 不前进，
  修好后重跑 `next-signal run-workflow knowledge_ingest`。
- **Dashboard 起不来** → 先确认 `pnpm` 在 PATH；用 `uv run next-signal dashboard --build`
  看 Next.js 编译错误。Dashboard 不需要 `next-signal serve`，但 `/radar` 需要 Postgres，
  `/knowledge` 需要 GBrain CLI，`/subscriptions` 需要 Folo auth。
- **knowledge ingest 拒绝本地文件** → 本地文件输入必须 stage 在 `NEXT_SIGNAL_AGENT_TMP_DIR` 下。
  Dashboard `/radar` 的 Folo ingest 会自动把 `folocli entry get` 的全文 stage 到
  `NEXT_SIGNAL_AGENT_TMP_DIR/radar-ingest/`；非 Folo radar item 仍要求 `radar_items.url` 是合法 URL。
- **某工具 agent 看不到** → 查工具是否注册（`_IN_TREE_TOOLS`、`tools/<domain>.register()`、
  workflow tool exposure 或集成注册）、agent YAML 是否写了准确注册名，跑 `tests/test_registry.py`。
- **容器相关问题**（build 失败、卷映射、纯云环境下的 embedder 缺口）→ 见
  [`containerized-deployment.md`](./containerized-deployment.md) §7–§8。
