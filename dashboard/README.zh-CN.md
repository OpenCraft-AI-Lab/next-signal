# paca dashboard

> [English](./README.md) · **简体中文**

本地 Next.js 15 应用 —— 操作者查看 `radar`、`knowledge`、goals 和 Folo 订阅的界面。
单用户、仅桌面端 —— 无认证、无移动端适配。跨模块约定见
[docs/zh/modules/dashboard.md](../docs/zh/modules/dashboard.md)。

## 前置依赖

- Node 20+
- pnpm（没有的话 `npm install -g pnpm`；推荐 pnpm 11+）
- `uv` 在 `PATH` 上（server action 调 `paca ...` 用）
- `gbrain` 在 `PATH` 上（knowledge 搜索的 server action 用）
- `npx` / Folo 认证供 `/subscriptions` 用（`FOLO_TOKEN` 或 `~/.folo/config.json`）

## 运行

推荐入口走 `paca` CLI，这样两个后端共用一个二进制：

```bash
uv run paca dashboard             # http://localhost:3000，带 HMR
uv run paca dashboard --port 3001 # 自定义端口
uv run paca dashboard --build     # `pnpm build`
uv run paca dashboard --start     # `pnpm start`（需要先 --build）
```

它是 `pnpm` 的薄封装：`os.execvp` 会替换掉 python 进程，所以 Ctrl-C / SIGTERM
直接打到 Next 上，中间没有转发层。原生 pnpm 命令照样能用：

```bash
cd dashboard
pnpm install
pnpm dev          # http://localhost:3000，带 HMR
pnpm build
pnpm test         # dashboard 聚焦 helper 测试
pnpm typecheck
```

## dashboard **不**依赖 `paca serve`

`paca serve`（AgentOS 在 `:7777`）和 `paca dashboard`（Next 在 `:3000`）是
**完全解耦的两个进程**。dashboard 现有的每个功能，要么直接读 Postgres，要么
spawn 一次性 `paca` CLI 子进程 —— 没有任何一个走 AgentOS 的 HTTP 调用。

| 做这件事 | 需要 `paca serve` 吗？ |
| --- | --- |
| 浏览 `/radar`，点 Ingest / Pull+Analyze | ❌ 不需要 |
| 搜索 `/knowledge`，点 Re-index | ❌ 不需要 |
| 手动跑 workflow（`paca info-radar pull/analyze`、`paca run-workflow knowledge_ingest`） | ❌ 不需要（CLI 子进程，直接写 Postgres） |
| 调试新的 agent / workflow | ✅ 需要（或者用 `paca run-agent`） |

`NEXT_PUBLIC_AGENT_OS_URL` 已经预接好（默认 `http://localhost:7777`），留给将来
真的有页面需要调 AgentOS HTTP 端点的那天 —— 目前没有。

## 环境变量

| 名称 | 默认值 | 谁在用 |
| --- | --- | --- |
| `PACA_WIKI_DIR` | （无 —— 必填） | `/knowledge`（树 + re-index） |
| `NEXT_PUBLIC_AGENT_OS_URL` | `http://localhost:7777` | 浏览器端调 AgentOS（目前没有） |
| `DATABASE_URL` | （Postgres URL） | `dashboard-radar`（直接读 DB） |
| `PACA_DATABASE_URL` | `DATABASE_URL` | 可选的 dashboard 专用 Postgres URL |
| `PACA_RADAR_TIMEZONE` | `America/Los_Angeles` | `/radar` 按日历天分组 |
| `FOLO_TOKEN` | （Folo CLI session 文件） | `/subscriptions`，经 `paca info-radar subscriptions --json` |
| `FOLO_CLI_ARGV` | `npx --yes folocli@0.0.5` | 可选，覆盖 Folo CLI 启动方式 |

## 视觉设计系统

design system 的事实源是应用内的 [`/design`](./app/design) 展示路由 —— token、
组件、状态、brand mark，全部由真实 primitive 渲染。token 在
[`app/globals.css`](./app/globals.css)，组件在
[`components/ui/`](./components/ui/)。

**`/design` 的 nav 入口只在 `NODE_ENV === "development"` 时渲染**（见
[`components/nav.tsx`](./components/nav.tsx)），所以部署出去的 dashboard 上看不到。
路由本身没有拦截 —— 任何 build 下直接访问 `/design` 都能打开，这是检查生产构建时
的逃生口。

### 怎么消化一份 design mock

新页面通常从一份 Claude Design mock（HTML/JSX 原型）开始。把 mock 当作**临时的、
外部的脚手架** —— 它们留在 Claude Design 工作区，**不提交进本仓库**。实现步骤：

1. 在 `app/` 和 `components/` 下搭页面，复用已有 token（`app/globals.css`）和
   `components/ui/` primitive —— 不要自创颜色、间距或一次性样式。
2. 如果 mock 确实需要一个还不存在的 token 或 primitive，把它加进
   `app/globals.css` / `components/ui/`，并在 `/design` 里露出来，保证展示页完整。
3. 在浅色和深色两种主题下对着 `/design` 验证。

页面上线后，mock 的使命就完成了，可以丢弃。从那一刻起，**上线的页面加上 `/design`
才是长期参考** —— spec 和文档指向它们，绝不指向某个 mock 文件。

## 界面语言

dashboard 的界面文案**默认英文**，可以通过 nav 上的语言按钮切换到中文。选择存在
`paca_locale` cookie 里（`en` / `zh`），`app/layout.tsx` 会设置对应的文档 `lang`。

翻译文本在 [`lib/i18n/dictionaries.ts`](./lib/i18n/dictionaries.ts)。**只有界面文案
被本地化**：标签、按钮、空状态、toast、相对时间和日期显示。用户/数据内容 —— 文章
标题、分析摘要、tag、YAML 值、wiki 文档正文、feed / 分类名 —— 一律按存储原样渲染。

## 依赖策略：先镜像 `agent-ui`，再叠加

`package.json` 的依赖集合是
[`agno-agi/agent-ui`](https://github.com/agno-agi/agent-ui) 的严格**超集**。他们
`dependencies` / `devDependencies` 里的每个包，在这里都以相同或更宽的范围钉住。
这样将来 `agent-ui` 里有组件好用（比如聊天界面），把单个源文件拷进 `components/`
应该是 `pnpm install` 层面的 no-op。

在镜像之上额外加的包（以及原因）：

- `geist` —— Vercel 官方字体包；设计用的是 Geist Sans + Mono。
- `gray-matter` —— 给 knowledge 侧边栏树解析 frontmatter。
- `pg` / `@types/pg` —— radar 阅读器在 server component 里直连 Postgres，超出
  `agent-ui` 镜像范围。
- `yaml` —— 给 `/goals` 解析和渲染 `configs/info_radar/goals.yaml`。
- `tsx` —— 聚焦的 TypeScript helper 测试。

## Radar

`/radar` 是 `info-radar` 输出的本地阅读器。它在 server component 里直接从 Postgres
读 `radar_items`、`radar_analyses` 和 `radar_pushed_topics`，把 kept 的分析按本地
日历天分组，并在阅读列表上方显示当天的 tracker。

tracker 是实时算出来的：`radar_items.fetched_at` 给出各 source 的拉取量，
`radar_analyses.verdict` 给出 tier-1 的 kept/dropped，`content_status` 给出 tier-2
的 ok/fallback/error，`dedup_status` 给出 novel/duplicate，分数则被分桶成 11 根
`0..100` 的直方图柱子。它**有意**不显示运行时长和结束时间，因为没有 run 级别的写入方。

过滤状态由 `nuqs` 挂在 URL 上：`sort=score-desc|score-asc|newest`、
`novelOnly=0|1`、`minScore=0..100`（步长 5）、`day=YYYY-MM-DD`、`lastFeedOnly=0|1`。
详情页链接会保留这些参数，所以上一条/下一条始终停留在同一个过滤后的、按天限定的列表里。

`Pull + Analyze` 先 await `uv run paca info-radar pull`，然后以 detached 方式启动
`uv run paca info-radar analyze`。pull 失败会在 toast 里显示；analyze 失败进入
dashboard 的 action log，事实源是刷新后的 Postgres 状态。dashboard 还会写
`~/.next-signal/radar-state.json`，这样零结果的点击和 `Last feed` 视图反映的是
操作者最近一次点击，而不是数据库里陈旧的聚簇。单条的 `Ingest` 会按 id 重新读取该
item 后创建一个受跟踪的 knowledge ingest job；Folo 行会先 stage 成全文 HTML，
非 Folo 行则使用校验过的 `radar_items.url`。

## Goals

`/goals` 通过 server action 直接编辑 `configs/info_radar/goals.yaml`。dashboard
镜像了 Python loader 的契约：顶层 `goals` 非空、goal 名唯一且只读、description
必填、topics/keywords 为字符串列表、weight 为数字、不允许未知字段。非法的保存在
写入前就被拒绝；合法的保存走原子 temp-file rename。

已有的 goal 名是只读的。重命名被**有意**建模成「删除 + 新增」，这样下游的分析历史
永远不会被静默地重新指向别的目标。

## Subscriptions

`/subscriptions` 是只读的。它调用
`uv run paca info-radar subscriptions --json`，把 Folo CLI 的信封结构归一化成
dashboard 行，然后在客户端做搜索/分类过滤。这个页面**从不**新增、编辑、删除或以
任何方式修改 Folo 订阅。

## 构建脚本授权

pnpm 11 要求对运行安装脚本的包显式授权。`esbuild`、`sharp`（Next.js 图片优化）和
`unrs-resolver`（Next.js 内部依赖）已在
[`pnpm-workspace.yaml`](./pnpm-workspace.yaml) 里加入白名单。
