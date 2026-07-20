# 运维与排查

## 安装

> 容器化部署（cloud-LLM，Docker Compose）见
> [`containerized-deployment.md`](./containerized-deployment.md)。以下是 host-native 安装步骤。

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

## 必需 / 可选服务

必需（最小可用）：Postgres 16+ with pgvector、OMLX OpenAI 兼容端点、
GBrain CLI（知识检索必需）。

可选：folocli 认证（info-radar collector）、GitHub token（knowledge 的 GitHub
收藏功能，缺省匿名 60 req/h）、OpenCLI（WeChat 文章入库）。

Dashboard 是单独的 Next.js 进程，不要求 `paca serve` 同时运行；它的 server action
会直接启动一次性 `paca` CLI 子进程，数据页直接读 Postgres。

## 环境变量

repo-local `.env` 关键值：

- `DATABASE_URL`
- `OMLX_BASE_URL` / `OMLX_API_KEY`
- 各云模型 / API key（按需）
- `GBRAIN_BIN`（`gbrain` 不在 `PATH` 时；dashboard 与后端同一套解析）
- `PACA_WIKI_DIR` / `PACA_WIKI_RAW_DIR`（**必填**，无代码默认；缺失时 knowledge pipeline 与 dashboard wiki 视图 fail loud）
- `PACA_STATE_DIR` / `PACA_AGENT_TMP_DIR`（可选，测试或换路径）

不要在任意模块直接读这些；走对应的 core / helper 函数。完整 key 列表见 `.env.example`。

| 集成 | Env Var |
|---|---|
| LLM: Anthropic / OpenAI / Google / DeepSeek | `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GOOGLE_API_KEY` / `DEEPSEEK_API_KEY`（+ 可选 `DEEPSEEK_BASE_URL`，默认 `https://api.deepseek.com`） |
| Folo (info-radar) | `FOLO_TOKEN`（可选；不设则用 `~/.folo/config.json`） + 可选 `FOLO_CLI_ARGV` 覆盖默认 `npx --yes folocli@<v>` |
| GBrain / OpenCLI (knowledge) | `GBRAIN_BIN`（`gbrain` 不在 PATH 时） / `OPENCLI_BIN`（WeChat 下载，main.js 路径或 wrapper） |
| GitHub (knowledge 收藏) | `GITHUB_TOKEN`（可选；缺省匿名 60 req/h） |
| OMLX embedder (info-radar analysis dedup) | `OMLX_BASE_URL` 必须可达；`configs/models.yaml::embedders.local.model_id` 默认 `Qwen3-Embedding-0.6B-8bit` (1024-dim)，需要 OMLX server 加载该模型 |

每个云集成在 call time 才检查 key，缺 key 只让对应工具失败，不阻断启动。

## State 位置

- 项目 repo：configs、prompts、代码、tests、OpenSpec specs。
- 用户 state（`~/.next-signal/`）：`knowledge_ingest_manifest.json`、`agent-tmp/`。
- 知识库：`~/Projects/digitalpaca-wiki/`（clean）、`~/Projects/digitalpaca-wiki-raw/`（raw）
  ——路径由 `PACA_WIKI_DIR` / `PACA_WIKI_RAW_DIR` 指定，不是硬编码默认值。
- agno 自管表（sessions / memory / knowledge / traces）：本地 Postgres + pgvector。
- 日志：只写 stdout（structlog，TTY 下 console 渲染，非 TTY 下 JSON）；`~/Library/Logs/next-signal/`
  目录会被创建但当前没有代码往里写文件。

## 健康检查

```bash
uv run paca doctor
```

检查：`DATABASE_URL`、`ANTHROPIC_API_KEY`、`DEEPSEEK_API_KEY`、`OMLX_BASE_URL`、Postgres 可达、
configured agents、registered tools、GBrain CLI/service（`gbrain doctor --fast`）、
folocli auth（`folocli whoami` — `FOLO_TOKEN` 或 `~/.folo/config.json` 任一可用即可）、
info-radar `configs/info_radar/goals.yaml` 存在且可解析（缺则 `paca info-radar analyze`
会 loud RuntimeError）。
代码层面不区分"必需"和"可选"检查——任一项失败（包括上面标为可选的 folocli auth）
doctor 都退出非零；上面的必需/可选划分只是"这台机器不打算用这个功能就可以忽略对应的✗"。

`DEEPSEEK_API_KEY` 缺失算非零项 —— `local*` 的默认 fallback profile 用 DeepSeek（OMLX 不可达时回落）；
`ANTHROPIC_API_KEY` 缺失也算非零项，供 `claude_*` profile 使用。若刻意只跑本地，要明白这些云 fallback 会失败。

## 常用命令

```bash
uv run paca list                                     # 列 agents / workflows
uv run paca doctor                                   # 自检
uv run paca run-agent <name> "<prompt>"              # 一次性调某个 agent
uv run paca serve [--port 7777]                       # 启动 AgentOS
uv run paca dashboard [--port 3000]                   # 启动 Next.js dashboard
uv run paca dashboard --build                         # dashboard production build
uv run paca dashboard --start                         # 启动已 build 的 dashboard
uv run paca knowledge ingest <url|staged-file>        # ingest 到知识库
#   --category <taxonomy-path>   指定落点，跳过自动分类
#   --progress                   每步输出一行 JSON 事件（dashboard 入库进度面板用）
uv run paca knowledge gbrain-search "query"           # 搜索本地 GBrain
uv run paca knowledge gbrain-ingest <file|dir>        # 导入 markdown 到 GBrain
uv run paca info-radar pull [--source NAME]           # 跑各 source CLI，写 radar_items
uv run paca info-radar sweep                          # 删 radar_items 中超 30 天的行
uv run paca info-radar analyze [--limit N] [--source NAME]
                                                      # 跑两层 analysis pipeline，写 radar_analyses
                                                      # 手动触发（CLI / dashboard）；没有后台调度
                                                      # `seen_at` 保证任意频率重跑 idempotent
                                                      # 前置：configs/info_radar/goals.yaml 必须存在
                                                      # (cp configs/info_radar/goals.example.yaml configs/info_radar/goals.yaml 后手改)
uv run paca info-radar subscriptions --json           # 读取 Folo 订阅，输出 dashboard 稳定 JSON 行
uv run paca run-workflow knowledge_ingest             # 手动跑 wiki → GBrain re-ingest
```

Dashboard UI 默认中文，可在导航栏切英文；选择存到 `paca_locale` cookie。这里只翻译
界面文案，文章标题、分析摘要、tag、YAML 内容等数据按原样显示。

需要碰真实 GBrain 索引的全链路测试，用隔离的 PGLite brain：

```bash
uv run paca knowledge init-test-gbrain
PACA_GBRAIN_HOME=state/test-gbrain uv run paca doctor
```

`PACA_GBRAIN_HOME` 是父目录，GBrain 把配置和 `brain.pglite` 存到
`$PACA_GBRAIN_HOME/.gbrain/`。保持在 ignored 的 `state/` 下，别动生产 `~/.gbrain`。

## 故障排查

- **`DATABASE_URL not set`** → 复制 `.env.example` 到 `.env` 并填好。
- **Postgres unreachable** → 启动 Postgres.app 或 Homebrew service，重跑 `paca doctor`。
- **OMLX profile 回落到 DeepSeek** → 查 `OMLX_BASE_URL` / `OMLX_API_KEY` / 端点 `/v1/models`；
  OMLX 恢复后长驻进程要调 `paca.core.models.reset_cache()`。
- **GBrain 搜索 / re-index 失败** → 跑 `paca doctor` 和 `gbrain doctor --fast`；
  embed 失败时 ingest 应在写完 wiki artifact 后 loud fail，manifest 不前进，
  修好后重跑 `paca run-workflow knowledge_ingest`。
- **Dashboard 起不来** → 先确认 `pnpm` 在 PATH；用 `uv run paca dashboard --build`
  看 Next.js 编译错误。Dashboard 不需要 `paca serve`，但 `/radar` 需要 Postgres，
  `/knowledge` 需要 GBrain CLI，`/subscriptions` 需要 Folo auth。
- **knowledge ingest 拒绝本地文件** → 本地文件输入必须 stage 在 `PACA_AGENT_TMP_DIR` 下。
  Dashboard `/radar` 的 Folo ingest 会自动把 `folocli entry get` 的全文 stage 到
  `PACA_AGENT_TMP_DIR/radar-ingest/`；非 Folo radar item 仍要求 `radar_items.url` 是合法 URL。
- **某工具 agent 看不到** → 查工具是否注册（`_IN_TREE_TOOLS`、`tools/<domain>.register()`、
  workflow tool exposure 或集成注册）、agent YAML 是否写了准确注册名，跑 `tests/test_registry.py`。
