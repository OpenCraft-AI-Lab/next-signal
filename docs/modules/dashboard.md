# 模块：dashboard（操作台）

## 解决什么

单用户、桌面端的本地操作台：阅读 info-radar 输出、管理知识库、
编辑 goals、盘点 Folo 订阅。独立 Next.js 15 进程（`:3000`），**不依赖 `paca serve`**——
所有功能要么直接读 Postgres，要么 spawn 一次性 `paca` CLI 子进程。

> 运行方式、env 变量、design system、i18n、依赖策略、radar/goals/subscriptions
> 页面行为的完整说明在 [`dashboard/README.md`](../../dashboard/README.md)——那是
> dashboard 自己的主文档，本页只给全景和跨模块约定。

## 页面族

| 路由 | 功能 | 详细行为见 |
|---|---|---|
| `/radar` | info-radar 阅读器：今日 tracker、过滤排序、Pull + Analyze（带实时进度）、单条 Ingest to wiki | [info_filter.md](./info_filter.md)、dashboard/README |
| `/knowledge` | wiki tree + 文件管理、ANN search、预览、Re-index、URL 入库表单 + 实时进度面板 | [knowledge.md](./knowledge.md) |
| `/goals` | 编辑 `configs/info_radar/goals.yaml`（镜像 Python loader 契约，原子写） | dashboard/README |
| `/subscriptions` | Folo 订阅只读盘点 | dashboard/README |

## 代码结构

```
dashboard/
  app/            页面（App Router；数据页 force-dynamic）+ app/api/ 的 3 个 route
                  （knowledge ingest SSE 流 / radar run 轮询 / radar export）
  components/     按页面族分组 + components/ui/（Radix-backed primitives）
  lib/            db.ts（pg 直连）、actions/（server actions）、ingest/jobs.ts
                  （内存 job registry）、radar/ wiki.ts taxonomy.ts i18n/
  design/         提交进 repo 的视觉 mock —— 实现跟 mock 走，不自由发挥
```

## 跨模块约定

- **server action 两种 spawn 模式**（`lib/actions/`）：长任务（analyze）detached
  spawn，页面靠轮询（`/api/radar/run`）收敛；短任务（goals 保存）`execFile`
  同步等待。
- **入库进度是单进程内存态**：两个入库入口（`/knowledge` 表单、`/radar` Ingest）共用
  `lib/ingest/jobs.ts` 的 job registry，spawn `paca knowledge ingest --progress` 并经
  SSE 推到面板。dashboard 重启会丢进行中 job 的**进度视图**（子进程和 artifact 写入
  不受影响）；`/radar` 的 analyze 进度同理 best-effort（`radar-state.json`）。
- **数据语言不翻译**：i18n 只覆盖界面文案（`paca_locale` cookie，默认中文）；文章标题、
  分析摘要、tag、YAML 值按原样渲染。
- **写配置走原子写 + loader 契约镜像**：`/goals` 与 `/knowledge` 的 taxonomy 改写都先按
  Python loader 的 schema 校验、再 temp-file rename / 文本行 splice，不整篇 reserialize。

## 开发注意（不变量）

- **不要起第二个 `next dev`**——和已在跑的 dev server 共用 `.next`，互写缓存会损坏
  build manifest（典型报错 `Cannot read properties of undefined (reading 'call')`）。
  验证完即停；大改动收尾 `rm -rf dashboard/.next` 清增量缓存。
- 新功能放新页 / 新组件，复用 design-system primitives 与 tokens，不为单页硬改 app shell。
- `/knowledge` 的 re-index 用 POST，不要 GET query。
- server action 里解析的路径要过穿越校验（见 `lib/actions/knowledge.ts` 先例）。

## 规范与状态

规范：[`openspec/specs/dashboard-shell/`](../../openspec/specs/dashboard-shell/)、
`dashboard-radar-reader`、`dashboard-knowledge-ingest`、`dashboard-goals`、
`dashboard-folo-subscriptions`。

当前状态：四个页面族全部就位；`pnpm test` 跑 `lib/` 聚焦测试（wiki / taxonomy /
goals / radar-ingest），`pnpm typecheck` 全绿。
