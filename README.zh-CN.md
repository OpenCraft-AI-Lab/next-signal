<div align="center">

<img src="dashboard/app/icon.svg" width="64" height="64" alt="next-signal" />

# next-signal

**别的 AI 阅读器把所有东西都摘要一遍。
这个决定什么值得你看——然后让你不会再弄丢它。**

[English](./README.md) · [简体中文](./README.zh-CN.md)

<sub>Apache-2.0 · 本地优先 · 跑在你自己的机器上</sub>

</div>

---

你订了 200 个源，因为怕漏掉那一条重要的。然后你一个都没看。

市面上所有阅读器给的答案都是摘要——同样那批文章的缩短版。next-signal 给的答案
是**判断**。你把自己要搞懂的事写下来——*以及不想看的是什么*——然后模型对每一条
进来的信息只问一个问题：

> **这条东西该在多大程度上改变你的想法或行动？**

不是它写得好不好。不是有多少人转发。不是方法论多严谨。是**后果**。一次旗舰模型
发布的分数一定高过一篇严谨的单实验室论文，评分标准里就是这么明写的。

<div align="center">
  <img src="./visual_assets/front_page-CN.png" alt="next-signal 雷达" width="100%" />
</div>

## 最近一次运行，未经挑选

个人 Folo timeline 上的 978 条。回来的是：

| | | |
|---:|---|---|
| **978** | 拉取 | feed 送来的全部 |
| **977** | 分析 | 两层管线 |
| **409** | 保留 | 58% 在 tier 1 被丢掉 |
| **133** | 分数 ≥ 75 | 真正出现在页面顶部的 |

**你拿回 14% 的 feed。剩下那 86% 才是产品。**

### 它丢掉了什么，为什么

每一条丢弃都存了理由：

| feed 送来的 | 为什么被丢 |
|---|---|
| HarmonyOS 7（API 26）Beta 2 新特性解读：AI 赋能应用故障分析 | *纯厂商技术博客，无新 benchmark 或能力突破数据* |
| DNS 战场再起变化：Cloudflare 开始挑战 AWS Route 53 | *通用云基础设施产品发布，非 AI 核心能力或特定 AI 算力/推理优化，偏离目标* |
| 中国出口增长保持强劲，尽管美中紧张关系再度升温 | *纯宏观出口数据盘点，缺乏具体产业链或公司层面的验证细节* |
| 荣耀 YOYO 智能体的产品化实践｜AICon 深圳 | *会议出席软文，标题明确指向 AICon 演讲分享* |
| 热狗华丽转身：从平民美食卖到 100 美元 | *与 AI、机器人、太空及科学突破完全无关* |

看第一条。标题里明明白白写着 **AI 赋能**，照样被砍——因为这里做的根本不是关键词
匹配。它读了正文，对照这个读者到底想搞懂什么，然后发现里面没有任何能改变他判断
的东西。

### 活下来的

> **AI 首次在国际数学奥林匹克（IMO）获官方满分金牌** —— **92** ·
> `release` `benchmark` `reasoning` `agent` `math`
>
> 在 2026 年第 67 届 IMO 中，小红书的 dots-note-3.0 成为首个经官方评阅获得 42 分
> 满分的 AI 系统，击败了包括人类选手在内的所有竞争者。该模型未依赖 Lean 这类
> 形式化证明系统，而是通过自然语言推理结合 Python 辅助，采用"证明-验证-修正"的
> 递归自我批判循环。

同一次运行里，来自完全不同的一条 goal：

> **HORIZON-Breast01：瑞康曲妥珠单抗（SHR-A1811）在 HER2 阳性晚期乳腺癌** ——
> **88** · `clinical-trial` `regulatory-approval` `oncology` `adc`
>
> 《柳叶刀·肿瘤学》发表的 3 期临床期中分析。中位 PFS 从 8.3 个月延长至 30.6 个月
> （HR=0.22），ORR 81.7%，且已推动该药获批。

第二条正是下面那份一票否决清单在起作用——它说得出期别、说得出数字、说得出一个
**已经发生**的获批动作。

---

## 凭什么相信这个过滤器

这是别的阅读器没有的部分。

**1. 标准是一个你自己拥有的文件。** `configs/info_radar/goals.yaml` 不是一组话题
滑块，而是一份带**反目标**和硬性一票否决清单的编辑策略，进 git、也能在 dashboard
里直接改：

```yaml
- name: science_breakthrough
  description: |
    追踪 AI 之外的重大科学与医学突破。……
    **一票否决清单（任何一条成立就不是突破，无论这个发现听起来多重要、
    多"颠覆传统认知"）**：(1) 受试对象是动物 / 细胞 / 类器官，没有人体结果；
    (2) 结论里出现"或可 / 有望 / 潜在 / 仍处于临床前 / 未来可能"；(3) 说不出
    一个**已经发生**的临床或工程动作（获批上市、进入三期、装机、量产、写进
    指南）；(4) 属于机制与通路发现、老药新用、单篇队列或 meta 分析、流行病学
    相关性。这是硬门槛不是偏好。修辞不是证据。
```

没有别的产品让你说得出*"发在 Nature 上本身不构成突破"*这句话。用什么语言写都行
——这个文件是给模型读的，不是给代码解析的。

**2. 它是被测量的，不是凭感觉调的。** `scripts/radar_eval.py` 拿真实管线在三套
手工标注集上重放——60 条对抗集、36 条决策边界集，以及一套 **55 条盲标 holdout**：
由三个只被允许读 `goals.yaml`、不许看任何 prompt 的 agent 独立标注，只保留三方
一致的条目。文章正文在加载时快照下来重放，所以两个变体的差异归因于 prompt，而不是
folocli 那天答没答上来。每次运行都记录两个 prompt 加 goals 文件的哈希，任何一组
数字都能追回产生它的那段文本。

生产配置在这套 holdout 上测得 **75%**。

**3. 失败的记录也在文档里。** 有一轮调优在对抗集上看着是干净的胜利，在 holdout 上
把 75% 打到了 **40%**。它写在
[`docs/zh/modules/info_filter.md`](./docs/zh/modules/info_filter.md) 的
*已测量并否决——不要在读记录之前重试* 一节里，连同"那个从不回归的护栏桶本身才是
bug"的分析。

一个带 holdout set、还记着自己被否决实验的个人新闻工具，是个奇怪的东西。它也是唯一
能让你知道过滤器没在悄悄骗你的办法。

---

## 信号只是一半

过滤决定什么能到你面前。另一半决定什么被你留下。

```
   feeds ──▶ radar ──▶ 你读了 ──▶ ingest ──▶ wiki ──▶ 间隔重复
                │                              │            │
          按后果打分                    干净 markdown    在第 1、3、7、
          跨周去重                       落在你磁盘上    15、30、60、120 天
          每周 recap                     + 向量索引      回到你眼前
```

一条命令就能把 radar 里的一条信息提升为永久产物：抓取、清洗、摘要、按你的分类树
自动归档、建好混合检索索引，并挂上艾宾浩斯曲线，在你忘掉它之前送回来。

所有东西都落成**你自己文件夹里的纯 markdown**——一个真正的 Obsidian vault，由
Obsidian Git 插件同步到 GitHub。这里没有导出按钮，因为没有什么需要导出。

目前支持的来源：网页文章、YouTube（原生字幕）、B 站（字幕，没有字幕时本地转写）、
微信公众号、GitHub 仓库、PDF 与 Office 文件。

---

## 和市面上的产品比

这张表上每一个阅读器现在都有 AI。Feedly 的 Leo 会做优先级和静音，Inoreader 上了
多 provider 的摘要与打标，Readwise 的 Ghostreader 在单篇文档里工作，Khoj 能跨你的
文件回答问题。把语言模型接到 feed 上，大概在 2025 年的某个时候就不再是差异点了。

它们都不会告诉你的是：**为什么**。

| | Feedly Pro+ | Inoreader Pro | Readwise Reader | Khoj | **next-signal** |
|---|:---:|:---:|:---:|:---:|:---:|
| 在你读之前就过滤 | 优先话题、静音 | 规则 + AI 打标 | — | — | **目标 + 反目标** |
| 判断标准是你自己拥有的文件 | — | — | — | — | **进 git 的 YAML** |
| 告诉你每条为什么被留下或砍掉 | — | — | — | — | **逐条存了理由** |
| 过滤质量在标注集上被测量 | — | — | — | — | **55 条盲标 holdout** |
| 按后果排序，而不是相关性 | — | — | — | — | **✔** |
| 可以完全跑在自己机器上 | — | — | — | ✔ | **✔** |
| 对留下的内容做间隔重复 | — | — | ✔ | — | **✔ 艾宾浩斯** |
| 资料库是你自己的纯 markdown | — | — | — | ✔ | **✔ Obsidian vault** |
| 价格 | $99/年 | $90/年 | $120/年 | 自托管免费 | **自托管免费** |

<sub>价格为 2026 年 8 月的年付价。</sub>

---

## 快速开始

容器是受支持的路径。Postgres + pgvector、schema bootstrap 和 dashboard 一起起来，
镜像里已经打包好了配套 CLI（`gbrain`、`opencli`、`folocli`）。

```bash
git clone https://github.com/OpenCraft-AI-Lab/next-signal.git
cd next-signal
cp .env.example .env && $EDITOR .env
docker compose up --build
```

然后打开 <http://localhost:3000>。

**最小 `.env`** —— 缺这几个会直接构建失败：

| Key | 为什么 |
|---|---|
| 一个 LLM key：`DEEPSEEK_API_KEY`（首选），或 `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | 默认路径——免费的本地方案见[两种跑模型的方式](#两种跑模型的方式) |
| `PACA_WIKI_DIR` | 你干净 wiki 仓库的宿主机路径——读写 bind mount |
| `PACA_WIKI_RAW_DIR` | 你原始归档仓库的宿主机路径——读写 bind mount |

`DATABASE_URL` 和容器内的 wiki / state 路径由 `docker-compose.yml` 设置，不要在
`.env` 里覆盖。

```bash
docker compose exec dashboard paca doctor        # 在容器里自检
docker compose run --rm dashboard paca info-radar pull
docker compose run --rm dashboard paca info-radar analyze
docker compose down                              # 停止，保留卷
```

> 端到端验证走容器，不在宿主机裸跑——这样验证环境和真正 ship 的东西完全一致。
> 完整设计与卷 / 环境变量映射见
> [docs/zh/containerized-deployment.md](./docs/zh/containerized-deployment.md)。

### 两种跑模型的方式

**本地——免费，什么都不出这台机器。** OMLX/MLX 跑在宿主机上以便调用 Metal GPU。
把容器指过去，整条过滤管线就是本地的：你的阅读兴趣、你读过的每一篇文章，都留在
你这儿。embedder 也在这里跑，所以跨周去重同样是本地的。

```bash
OMLX_BASE_URL=http://host.docker.internal:<port>/v1   # 写进 .env
```

**DeepSeek——100 条新闻约 5 毛钱。** 不需要 GPU，不需要本地部署。过滤 100 条的
feed 大约花 **¥0.5 / $0.07**。按一天一百条算，一个月约 **¥15**——比你现在正在付费
的任何一个阅读器都便宜。

```bash
DEEPSEEK_API_KEY=sk-...                               # 写进 .env
```

[宿主机原生安装](./docs/zh/operations.md#安装)则把本地模型跑在进程内。

## 常用命令

在容器里可以省掉 `uv run` 前缀——`paca` 已经在 `PATH` 上。

```bash
uv run paca doctor                                    # 检查 env / Postgres / OMLX / 工具
uv run paca info-radar pull [--source NAME]           # 拉取各 source 写入 radar_items
uv run paca info-radar analyze [--limit N]            # 两层分析
uv run paca info-radar recap --since D --until D      # 带引用的主题归纳
uv run paca knowledge ingest <url|staged-file>        # 提升进知识库
uv run paca knowledge review                          # 对齐间隔重复队列
uv run paca run-workflow knowledge_ingest             # wiki → 向量索引重建
uv run paca list                                      # 列出 agents / workflows
uv run paca serve [--port 7777]                       # 启动 AgentOS
```

---

## 文档

| 你想… | 读 |
|---|---|
| 理解系统怎么搭的，以及为什么 | [docs/zh/architecture.md](./docs/zh/architecture.md) |
| 加 agent / tool / integration / model / 领域 | [docs/zh/development.md](./docs/zh/development.md) |
| 安装、配 env、跑 `paca doctor`、排错 | [docs/zh/operations.md](./docs/zh/operations.md) |
| 用容器部署 | [docs/zh/containerized-deployment.md](./docs/zh/containerized-deployment.md) |
| 深入过滤器，包括每一次调优结果 | [docs/zh/modules/info_filter.md](./docs/zh/modules/info_filter.md) |
| 深入知识管线 | [docs/zh/modules/knowledge.md](./docs/zh/modules/knowledge.md) |
| 读能力契约 / 待办变更 | [openspec/specs/](./openspec/specs/) · [openspec/changes/](./openspec/changes/) |

**文档是双语的。** 英文是标准版本，中文镜像在 [`docs/zh/`](./docs/zh/) 加上本文件，
每页顶部都有语言切换链接。有意不翻的两处：`CLAUDE.md`（agent 指令）和
`openspec/specs/`（能力契约）——它们跟着代码一起变，第二份副本只会漂移。

## 构建于

[gbrain](https://github.com/garrytan/gbrain) 提供 markdown 优先的混合检索与类型化
链接图 · Postgres + pgvector · Next.js ·
[Folo](https://github.com/RSSNext/Folo) 作为 feed 来源 · Qwen3 跑在
[MLX](https://github.com/ml-explore/mlx) 上做本地推理。

Apache-2.0.
