# next-signal dashboard

> [English](./README.md) · **简体中文**

本地 Next.js 15 应用 —— 操作者查看 `radar`、`knowledge`、goals 和 Folo 订阅的界面。
单用户、仅桌面端 —— 无认证、无移动端适配。跨模块约定见
[docs/zh/modules/dashboard.md](../docs/zh/modules/dashboard.md)。

## 前置依赖

- Node 20+
- pnpm（没有的话 `npm install -g pnpm`；推荐 pnpm 11+）
- `uv` 在 `PATH` 上（server action 调 `next-signal ...` 用）
- `gbrain` 在 `PATH` 上（knowledge 搜索的 server action 用）
- `npx` 和一个 Folo token 供 `/subscriptions` 用（设置 → 凭据）

## 运行

推荐入口走 `next-signal` CLI，这样两个后端共用一个二进制：

```bash
uv run next-signal dashboard             # http://localhost:3000，带 HMR
uv run next-signal dashboard --port 3001 # 自定义端口
uv run next-signal dashboard --build     # `pnpm build`
uv run next-signal dashboard --start     # `pnpm start`（需要先 --build）
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

## dashboard **不**依赖 `next-signal serve`

`next-signal serve`（AgentOS 在 `:7777`）和 `next-signal dashboard`（Next 在 `:3000`）是
**完全解耦的两个进程**。dashboard 现有的每个功能，要么直接读 Postgres，要么
spawn 一次性 `next-signal` CLI 子进程 —— 没有任何一个走 AgentOS 的 HTTP 调用。

| 做这件事                                                                                              | 需要 `next-signal serve` 吗？             |
| ----------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| 浏览 `/radar`，点 Ingest / Pull+Analyze                                                               | ❌ 不需要                                 |
| 搜索 `/knowledge`，点 Re-index                                                                        | ❌ 不需要                                 |
| 手动跑 workflow（`next-signal info-radar pull/analyze`、`next-signal run-workflow knowledge_ingest`） | ❌ 不需要（CLI 子进程，直接写 Postgres）  |
| 调试新的 agent / workflow                                                                             | ✅ 需要（或者用 `next-signal run-agent`） |

`NEXT_PUBLIC_AGENT_OS_URL` 已经预接好（默认 `http://localhost:7777`），留给将来
真的有页面需要调 AgentOS HTTP 端点的那天 —— 目前没有。

## 环境变量

| 名称                       | 默认值                    | 谁在用                                                             |
| -------------------------- | ------------------------- | ------------------------------------------------------------------ |
| `WIKI_DIR`                 | （代码无默认；Compose 默认 `./state/wiki`） | `/knowledge`（树 + re-index）                        |
| `NEXT_PUBLIC_AGENT_OS_URL` | `http://localhost:7777`   | 浏览器端调 AgentOS（目前没有）                                     |
| `DATABASE_URL`             | （Postgres URL）          | `dashboard-radar`（直接读 DB）                                     |
| `NEXT_SIGNAL_DATABASE_URL` | `DATABASE_URL`            | 可选的 dashboard 专用 Postgres URL                                 |
| `INFO_RADAR_TIMEZONE`      | `America/Los_Angeles`     | `/radar` 按日历天分组 + recap 区间                                 |
| _(`FOLO_TOKEN`)_           | 不是环境变量              | 在设置 → 凭据里填；`/subscriptions` 用                             |
| `FOLO_CLI_ARGV`            | `npx --yes folocli@0.0.5` | 可选，覆盖 Folo CLI 启动方式                                       |

## 视觉设计系统

design system 的事实源是应用内的 [`/design`](./app/design) 展示路由 —— token、
组件、状态、brand mark，全部由真实 primitive 渲染。token 在
[`app/globals.css`](./app/globals.css)，组件在
[`components/ui/`](./components/ui/)。

**`/design` 的 nav 入口只在 `NODE_ENV === "development"` 时渲染**（见
[`components/nav.tsx`](./components/nav.tsx)），所以部署出去的 dashboard 上看不到。
路由本身没有拦截 —— 任何 build 下直接访问 `/design` 都能打开，这是检查生产构建时
的逃生口。

### 品牌 mark

三个族都在 [`components/brand/`](./components/brand/) 下，全部由同一个原子
（node）加上各自唯一的连接形态构成：

| 族                    | 模块                 | 场       | 连接形态 |
| --------------------- | -------------------- | -------- | -------- |
| next-signal（父品牌） | `signal-mark.tsx`    | 线性场   | chevron  |
| info-radar            | `radar-mark.tsx`     | 极坐标场 | wedge    |
| knowledge-base        | `knowledge-mark.tsx` | 网络场   | link     |

每个模块导出一个扁平 **mark** 和一个带动画的 **emblem**。细节量随尺寸变化，
而档位是显式 prop —— 绝不从 `size` 推断：

```tsx
<RadarMark size={44} />                  // icon 档：双环、十字线、扇形、blip
<RadarMark size={16} variant="nav" />    // nav 档：单环、扇形、核心
<RadarEmblem size={72} />                // emblem：再加方位刻度、扫描、3 个 blip
```

紫色（`--accent`）在三个 mark 里都承担结构。每个模块 mark 只花一种次要颜色，
且只用在「这个模块在干的事」本身上 —— 捕获到的 blip、索引 hub —— 取自
`--brand-spark-radar` / `--brand-spark-kb`。它们刻意独立于语义 verdict 色阶：
品牌色和状态色必须能各自独立修改。

emblem 是透明底、颜色全部走 token（所以明暗两套主题共用一份资产），并且保持
server component —— 动效来自 `app/globals.css` 里的 `.brand-*` 钩子，其中每个
雷达 blip 的延迟是由方位角**推导**出来的（`t = (bearing - 45) / 90`），不是手调
的。每个 emblem 在 `prefers-reduced-motion: reduce` 下都有一张构好图的静态帧。

唯一不走 token 的是 [`app/icon.svg`](./app/icon.svg)（favicon）：它在文档之外被
栅格化，读不到 CSS 变量，所以颜色是写死的。

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

dashboard 的界面文案**默认英文**，通过 nav 上的语言选择器切换：触发器显示**当前**
语言，菜单列出所有可选语言。菜单里的语言名一律自称、绝不翻译（`English`、`中文`）
—— 语言菜单必须让读不懂当前界面语言的人也能看懂。选择存在 `ns_locale` cookie 里
（`en` / `zh`），`app/layout.tsx` 会设置对应的文档 `lang`。

翻译文本在 [`lib/i18n/dictionaries.ts`](./lib/i18n/dictionaries.ts)。**只有界面文案
被本地化**：标签、按钮、空状态、toast、相对时间和日期显示。用户/数据内容 —— 文章
标题、分析摘要、tag、YAML 值、wiki 文档正文、feed / 分类名 —— 一律按存储原样渲染。

## 设置

nav 上的**齿轮按钮**现在链接到 `/settings`——一个带固定侧栏的页面，分四组：内容语言、
定时运行、模型引擎、向量嵌入。它取代了原来的 nav 弹层：几段内容堆在 22rem 的面板里，
引擎那一组根本没地方展开。

所有值都在 `app/settings/page.tsx` 里服务端解析，所以控件首次渲染就显示真实状态，挂载
时不发请求。什么时候落盘由控件本身决定，而不是由所在的 section 决定：

| 控件 | 提交时机 | 为什么 |
|---|---|---|
| Segmented（语言、开关、跳过/补跑、并发） | 点击即提交 | 一次交互本身就是一个完整、合法的意图 |
| 定时的时间 | 失焦 / 回车 | 原生 time 输入每编辑一段就发出一个完整值，逐次保存会写进半截时间 |
| 某个引擎或 embedder 自己的参数 | 显式 **保存** | 部分组合是非法的，不能发出去 |

无论哪条路径，写成功都会弹 toast，写失败会把控件回滚——乐观更新的控件不管有没有落盘
都会动。

## 内容语言

第一组是*内容*语言：pipeline 用什么语言写 radar 分析和 wiki frontmatter。它写入
`~/.next-signal/language.json` 的 `content_language`，所有走 `global` policy 的
`next-signal` agent 都读这个文件（见
[`docs/zh/modules/core.md`](../docs/zh/modules/core.md#输出语言)）。

这和上面的界面语言刻意保持独立。用一种语言看界面、用另一种语言生成内容是被支持的
状态；两者不一致时不会同步也不会告警。

## 模型引擎

第三组选 next-signal 调用哪个引擎，四个平级呈现——**本地模型**、**DeepSeek**、
**Codex CLI**、**Claude Code CLI**——选中哪个就在下面展开哪个的设置，再加一条"连不上
时"的回落。屏幕上永远只有被选中那一个的表单；四张表单堆在一起，正是这套设置需要一个
独立页面的原因。

它们对使用者是平级的，在磁盘上不是。拆分方式跟着"谁本来就拥有这个值"走：

| 设置 | 写到哪 | 运行时行为 |
|---|---|---|
| Codex CLI · Claude Code CLI 的模型 / 强度 / 速度 | `~/.next-signal/coding-agents.json` | 调用对应 CLI 时校验 |
| 主引擎、回落、OMLX 和 DeepSeek 设置 | `~/.next-signal/engine.json` | 每个 production job 开始时读取一次；修改从下一单生效 |

`engine.json` 里没设过的字段会回落到 `configs/models.yaml` 和 `OMLX_BASE_URL` 的值，
所以全新安装看到的是真实的端点和模型，而不是 dashboard 编出来的默认值。
`DEEPSEEK_API_KEY` 来自凭据仓库（设置 → 凭据）——页面只报告它有没有配置，不读取也不存储密钥本身。
同一个 production job 的所有 LLM stage 都使用同一个选定引擎。只有第一次成功响应之前的
provider 故障可以触发配置的回落；一旦成功，后续 stage 和 schema 修复都固定在该引擎。
卡片状态只反映 dashboard 能观察到的事实（密钥是否存在、模型是否选了）；这里不去
探测端点，所以也不会声称某个引擎"可连接"。

两个 CLI 都不提供“继承”：用户必须显式填写模型和强度，Codex 还必须选择速度，
next-signal 才能调用。这里刻意不硬编码 CLI 默认值，因为 provider 默认值会随时间变化。
模型输入框会建议当前模型名，但不限制未来的新模型 ID。快速模式只对支持它的 Codex
模型和账号生效，并会更快消耗额度。Claude 模型支持 `opus`、`sonnet`、`haiku` 等 alias、
完整模型名和受支持的 `[1m]` alias；思考强度可以是 `low`、`medium`、`high`、`xhigh`
或 `max`，最终兼容行为由所选模型与 Claude Code 决定。

保存某一个引擎会保留其他所有引擎的设置。Dashboard 不会修改 `~/.codex/config.toml` 或
`~/.claude/settings.json`。在官方 Docker 部署中，每个 CLI 面板还会显示真实的已保存登录
状态，并提供有边界的连接/重新连接/断开流程。它只调用固定的 provider 认证命令，生成的
文件仍留在 provider 自己的 auth volume；模型设置继续放在 `coding-agents.json`。

## 向量嵌入

第四组选的是雷达去重背后的 embedder，只写 `~/.next-signal/embedding.json`。它复用引擎那
组的卡片和面板，因为交互是同一套；但后果不是：换 LLM 只是换谁来回答问题，换 embedder
换的是*向量空间*——上一个身份下记住的所有主题都会被搁置，直到你切回去。这一组在点击之前
就把这件事说清楚，并原样显示当前的身份（`omlx:<model>`、`openai:<model>` 或
`openai_compatible:<space_id>`）。

三个平级选项——**本地模型**、**OpenAI**、**自定义端点**——其中有一处不对称值得知道：

| 卡片 | 选中它时 |
|---|---|
| 本地模型、OpenAI | 点击即提交，用该 provider 上次保存的参数 |
| 自定义端点，在第一次保存之前 | **只展开面板，什么都不写**——没有 baseline 可选 |
| 自定义端点，保存之后 | 和其他卡片一样点击即提交 |

自定义端点在整个仓库里都没有出厂默认值，所以它的面板是全有或全无：**保存**会把
`base_url`、`model`、`api_key_env`、`space_id` 一起存下来，并在同一次写入里让它生效。
`space_id` 是你自己给这个端点产出的向量起的名字——权重、分词器、pooling 或量化变了就换
一个；同一个服务换个 URL 不需要换。

没有任何凭据经过这个页面。自定义端点收的是环境变量的*名字*，不是密钥；它的 URL 被限制
为纯 API 根地址，所以密钥没法藏在 userinfo、query 或 fragment 里被存下来。密钥在不在是
服务端算好的，传到浏览器的只是一个布尔值。因为取值是从流水线自己的进程环境读的，改完
`.env` 要重启宿主进程或重建 Compose 服务它才存在——面板里写着这一点。云端 provider 还会
说明：每条留下来的条目，摘要都会离开本机，而且可能计费，包括无人值守的定时运行。

## 定时运行

第二组管无人值守的雷达计划：开关、每天的一个或多个时间点、以及停机期间错过的运行要不
要补跑。它写 `~/.next-signal/schedule.json`，`scheduler` 容器每 30 秒轮询时重读——
所以在这里改完不需要重启就生效。

时间点是一个列表，**每一个每天都会触发**。它们渲染成一行会自动换行的 chip，而不是每
个时间占一整行输入框，这样三个每日运行读起来是"一组"而不是"一张表"。最后一个时间点
不能删除，因为"开着但没有任何可触发的时间"不是一个值得存在的状态；要停就用"关闭"。

时区是**写出来给你看的，不是让你选的**。这一组显示 `next_signal.core.clock` 从
`INFO_RADAR_TIMEZONE` 解析出的时区并点名这个变量；要改就改环境变量再重启整个栈。这一个
值同时被雷达按天分组和复习到期时间共用，所以一个自带时区的 schedule 会出现"按某个时区的
08:00 触发、结果却归进另一个时区画出的那一天"。

早先的版本确实给过一个下拉框（存成 `tz`），旁边配一条"调度器并不读它"的警告——一个唯一可
观测效果就是那条"我没有效果"警告的控件。两者都已删掉。旧版本留在文件里的 `tz` 读取时被
忽略、下次写入时被丢弃；`next_signal.core.schedule` 用 `.get` 按名取字段，所以它在与不在
都不会报错。"下次运行"那一行按调度器实际解析出的时区计算——用一个不决定任何事的时区去写下
次运行时刻，正是这一页上操作者最可能不加核对就直接采信的数字。

这一组还会显示上次运行处在什么状态，读自 `schedule_state` 表：尚未运行、正在运行（连同已经
跑了多久）、成功、失败。调度器没跑完就中断的运行，在它再次启动后读作失败，而不是仍在飞行中。
补跑覆盖所有真正错过的运行，不管是怎么错过的——容器停了、机器睡过了那个点，或者上一趟运行
压过了它。改动计划——或者刚打开开关——都不会触发一个刚刚过去的时间点。见
[`docs/zh/operations.md`](../docs/zh/operations.md#无人值守运行)。

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
- `yaml` —— 给 `/goals` 解析和渲染运行时 goals 文件。
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

`Pull + Analyze` 先 await `uv run next-signal info-radar pull`，然后以 detached 方式启动
`uv run next-signal info-radar analyze`。pull 失败会在 toast 里显示；analyze 失败进入
dashboard 的 action log，事实源是刷新后的 Postgres 状态。dashboard 还会写
`~/.next-signal/radar-state.json`，这样零结果的点击和 `Last feed` 视图反映的是
操作者最近一次点击，而不是数据库里陈旧的聚簇。单条的 `Ingest` 会按 id 重新读取该
item 后创建一个受跟踪的 knowledge ingest job；Folo 行会先 stage 成全文 HTML，
非 Folo 行则使用校验过的 `radar_items.url`。

## Goals

`/goals` 通过 server action 直接编辑 `~/.next-signal/goals.yaml` —— 用户状态，
所以 scheduler 读的是同一份，rebuild 也不会丢。渲染页面永远不写文件：文件由容器
bootstrap 填好，或者由显式的 **从示例开始** 按钮写入。空的 `goals:` 列表是可以保存
的（清空示例是正当操作），但在重新加上目标之前 analysis 会 loud fail。dashboard
镜像了 Python loader 的契约：顶层 `goals`、goal 名唯一且只读、description
必填、topics/keywords 为字符串列表、weight 为数字、不允许未知字段。非法的保存在
写入前就被拒绝；合法的保存走原子 temp-file rename。

已有的 goal 名是只读的。重命名被**有意**建模成「删除 + 新增」，这样下游的分析历史
永远不会被静默地重新指向别的目标。

## Subscriptions

`/subscriptions` 是只读的。它调用
`uv run next-signal info-radar subscriptions --json`，把 Folo CLI 的信封结构归一化成
dashboard 行，然后在客户端做搜索/分类过滤。这个页面**从不**新增、编辑、删除或以
任何方式修改 Folo 订阅。

未读数来自第二个 folocli 命令。`subscription list` 不带 unread 字段，所以集成层
额外跑一次 `unread list`（它会列出所有有未读的 feed），再按 `feedId` join。没出现在
这个响应里的 feed 就是真的零未读——所以 `unread` 永远是数字，不会是 null。
`unread list` 失败时直接抛错，不降级成缺失的计数：一整列 0 看起来就像真数据。

没有「最后更新」这一列。Folo 的订阅列表不带每个 feed 的更新时间，只有
`createdAt`（你订阅的日期）；真正的更新时间要为每个 feed 各跑一次
`folo feed get <feedId>` 才拿得到。

## 构建脚本授权

pnpm 11 要求对运行安装脚本的包显式授权。`esbuild`、`sharp`（Next.js 图片优化）和
`unrs-resolver`（Next.js 内部依赖）已在
[`pnpm-workspace.yaml`](./pnpm-workspace.yaml) 里加入白名单。
