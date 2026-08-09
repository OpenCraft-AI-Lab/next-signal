<div align="center">

<img src="dashboard/app/icon.svg" width="64" height="64" alt="next-signal" />

# next-signal

**判断什么值得占用你的注意力，再把重要内容存进你自己的知识库。**

[English](./README.md) · [简体中文](./README.zh-CN.md)

<sub>Apache-2.0 · 本地优先 · 跑在你自己的机器上</sub>

</div>

---

你订阅了几百个信息源，因为真正重要的那一条可能来自任何地方。结果是，待读列表越积
越长，你根本看不过来。

摘要只能让每条内容变短，不能替你判断什么值得花时间。next-signal 会按照一份你能读、
能改的策略评估新内容。这份策略写明你正在研究什么，也写明哪些内容应该被排除。面对
每一条信息，系统只问一个问题：

> **这条信息会在多大程度上改变我的判断或行动？**

相关性决定一条内容是否属于你的关注范围，证据决定其中的结论有多可信，分数则只衡量
它对判断和行动的影响。仓库里的示例策略明确规定，已经发布的旗舰模型可以排在一篇严谨
但影响范围很窄的论文之前。你也可以写出完全不同的排序标准。

<div align="center">
  <img src="./visual_assets/front_page-CN.png" alt="next-signal 雷达页面" width="100%" />
  <br />
  <sub>这是另一次真实运行的页面截图。下方 978 条的统计来自不同的一次运行。</sub>
</div>

## 一次真实的 978 条运行

以下数据来自一个个人信息流。拉取和分析之间没有人工筛选：

| 数量 | 结果 | 含义 |
|---:|---|---|
| **978** | 拉取 | 已启用信息源返回的全部内容 |
| **977** | 完成分析 | 当时有 1 条尚未完成分析 |
| **568** | 第一层丢弃 | 58.1% 不值得进入完整分析 |
| **409** | 保留 | 其中 276 条低于默认高信号阈值 |
| **133** | 分数不低于 75 | 13.6% 进入默认高信号视图 |

系统没有把中间部分藏起来。调低阈值仍然可以查看 75 分以下的保留项，第一层丢弃的内容
也保留了判断理由。

### 被丢弃的内容

下面是那次运行中留存的理由：

| 信息流送来的内容 | 为什么被丢弃 |
|---|---|
| HarmonyOS 7（API 26）Beta 2 新特性解读：AI 赋能应用故障分析 | *纯厂商技术博客，无新 benchmark 或能力突破数据* |
| DNS 战场再起变化：Cloudflare 开始挑战 AWS Route 53 | *通用云基础设施产品发布，非 AI 核心能力或特定 AI 算力/推理优化，偏离目标* |
| 中国出口增长保持强劲，尽管美中紧张关系再度升温 | *纯宏观出口数据盘点，缺乏具体产业链或公司层面的验证细节* |
| 荣耀 YOYO 智能体的产品化实践｜AICon 深圳 | *会议出席软文，标题明确指向 AICon 演讲分享* |
| 热狗华丽转身：从平民美食卖到 100 美元 | *与 AI、机器人、太空及科学突破完全无关* |

第一条的标题明明写着 **AI 赋能**，仍然被过滤。系统读取正文，对照读者自己的判断策略，
确认其中没有足以改变判断的新信息。

### 被保留的内容

> **小红书 dots-note-3.0 经 IMO 2026 官方评阅获得 42/42** · **92** ·
> `release` `benchmark` `reasoning` `agent` `math`
>
> 小红书内部版本 dots-note-3.0 在六道题上都获得满分，经官方评阅得到 42/42。共有
> 7 位人类选手也取得 42 分，因此它与这些选手并列。该系统使用自然语言推理和 Python
> 辅助，没有依赖 Lean 一类的形式化证明系统。
>
> [公开解题记录](https://huggingface.co/datasets/dots-studio/dots-imo2026) ·
> [人类选手官方成绩](https://www.imo-official.com/results/individual/year/2026/)

同一次运行还保留了另一条完全不同目标下的内容：

> **HORIZON-Breast01：瑞康曲妥珠单抗（SHR-A1811）治疗 HER2 阳性晚期乳腺癌** ·
> **88** · `clinical-trial` `regulatory-approval` `oncology` `adc`
>
> 《柳叶刀·肿瘤学》发表的 3 期临床期中分析显示，中位无进展生存期为 30.6 个月，
> 标准治疗组为 8.3 个月（HR 0.22），客观缓解率为 81.7%。2026 年 3 月，中国批准
> 该药用于二线及以上 HER2 阳性晚期乳腺癌。
>
> [临床试验论文](https://www.sciencedirect.com/science/article/pii/S1470204526001932) ·
> [公司年度业绩](https://www.hengrui.com/images/investor/%E6%81%92%E7%91%9E%E9%86%AB%E8%97%A5%202025%E5%B9%B4%E5%A0%B1.pdf)

下面的科学突破策略要求内容说得出临床期别、具体结果，以及一个已经发生的临床或工程
动作。这条内容通过了这道门槛。

---

## 过滤过程可以检查

可信度不来自一句“AI 过滤”。你可以检查判断标准、每一条内容对应的理由，以及调试这套
过滤器时使用的评测。

### 1. 判断标准写在你自己的文件里

`configs/info_radar/goals.yaml` 是一份编辑策略，不是一排话题滑块。它支持反目标和硬性
否决规则，可以纳入版本控制，也可以在网页控制台里直接修改：

```yaml
- name: science_breakthrough
  description: |
    追踪 AI 之外的重大科学与医学突破。……
    一票否决清单：任何一条成立就不是突破，无论这个发现听起来多重要。
      (1) 受试对象是动物、细胞或类器官，没有人体结果；
      (2) 结论包含“或可、有望、潜在、仍处于临床前”；
      (3) 说不出一个已经发生的临床或工程动作，例如获批、进入三期、
          完成装机、正式发货或写入指南；
      (4) 属于机制发现、老药新用、单篇队列或流行病学相关性。
    这是硬门槛，不是偏好。修辞不是证据。
```

“发在 Nature 上本身不构成突破”这样的规则，就应该写在这里。策略可以使用任何语言，
因为模型把它当作普通文本读取。

### 2. 每次修改都在标注集上测量

`scripts/radar_eval.py` 会用生产管线重放三套数据：60 条对抗样本、36 条决策边界样本，
以及一套 55 条的留出集。三名互相独立的模型标注者只读取 `goals.yaml`，不读取生产
提示词；只有三方意见一致的样本才进入留出集。因此它是一套模型共识参考集，不是人工
标注基准。

文章正文会先生成快照再重放，上游抓取的波动不会污染提示词对比。每次运行都会记录两份
提示词和目标文件的哈希。

生产配置在这套留出集上的通过率为 **75%**。一次评测包含多轮重复运行时，只有每轮都给出
预期的保留或丢弃判断，而且保留项的平均分落在预期区间内，这条样本才算通过。这个结果
只适用于当前的目标文件和语料，不是通用准确率。

### 3. 失败的实验也会留下记录

有一轮调优提高了对抗集表现，却把留出集通过率从 75% 降到 **40%**，因此没有进入生产
配置。对应的提示词、测量结果和回归原因都记录在
[`docs/zh/modules/info_filter.md`](./docs/zh/modules/info_filter.md#调优与评测) 中。

个人过滤器很容易在熟悉的样本上显得更好，却在下一批内容上变差。这套留出集正好抓住了
这样一次回归。

---

## 信号只是一半

过滤决定什么能到你面前，知识管线则决定你关掉页面以后，哪些内容还能继续发挥作用。

```
   信息源 ──▶ 雷达 ──▶ 阅读 ──▶ 入库 ──▶ Markdown ──▶ 定期回顾
                 │                              │              │
          按决策影响评分                  文件保存在本地      第 1、3、7、
          跨次运行去重                    + 混合检索          15、30、60、120 天
          按需生成回顾
```

一个按钮或一条命令就能把雷达中的内容保存为长期知识条目。管线会抓取并清洗原文、生成
摘要、按照你的分类树归档、建立混合检索索引，并安排它在第 1、3、7、15、30、60 和
120 天重新出现。

知识库是**你自己文件夹里的纯 Markdown**。它可以直接作为 Obsidian vault 使用，但
Obsidian 不是必需品。是否通过 Git、其他同步工具或完全不同步，都由你决定。知识库不
需要导出步骤，因为这些文件从一开始就属于你。

知识入库目前支持网页文章、YouTube、B 站、微信公众号、GitHub 仓库、PDF 和 Office
文件。雷达输入由 `configs/info_radar/sources.yaml` 下的信息源适配器配置，因此接入新
来源时，不需要改动过滤和知识管线。

---

## next-signal 的不同之处

摘要、打标和话题优先级已经很常见。下面这些选择才定义了 next-signal：

| 问题 | next-signal 的答案 |
|---|---|
| 谁来定义什么重要？ | 你自己。标准写在带目标、反目标和否决规则的版本化策略里。 |
| 能不能检查一次判断？ | 丢弃项会保留理由；保留项会保留摘要、影响分析和评分。 |
| 能不能测试提示词改动？ | 仓库自带标注集、重放工具、提示词哈希和被否决实验的记录。 |
| 什么决定排序？ | 按策略中的锚点衡量对判断和行动的影响，而不只看相关性。 |
| 留下的知识存在哪里？ | 存在本地 Markdown 文件里，可选接入 Obsidian 和 Git。 |
| 模型在哪里运行？ | 可以通过 OMLX 跑在自己的 Apple 芯片机器上，也可以使用自行配置的云模型。 |

软件以 Apache-2.0 免费提供。本地推理使用你的硬件，云推理费用由模型提供商收取。

---

## 快速开始

推荐使用 Docker Compose。它会启动 Postgres 和 pgvector、初始化数据库结构，并启动
网页控制台。镜像已经包含配套的命令行工具，项目的命令行名称是 `next-signal`。

```bash
git clone https://github.com/OpenCraft-AI-Lab/next-signal.git
cd next-signal
cp .env.example .env
$EDITOR .env
docker compose up --build
```

然后打开 <http://localhost:3000>。

### 需要配置什么

Docker Compose 启动前需要以下宿主机路径：

| 配置项 | 用途 |
|---|---|
| `WIKI_DIR` | 清洗后 Markdown 知识库的绝对宿主机路径，以读写方式挂载 |
| `WIKI_RAW_DIR` | 原始内容归档的绝对宿主机路径，以读写方式挂载 |

开始分析前，选择一种模型运行方式：

| 方式 | 配置 |
|---|---|
| 默认云模型 | 设置 `DEEPSEEK_API_KEY` |
| Apple 芯片本地模型 | 在宿主机启动 OMLX 并设置 `OMLX_BASE_URL`；服务端点需要提供 `configs/models.yaml` 中指定的对话模型和嵌入模型 |

为你启用的信息源适配器配置所需凭据。完整列表和说明见
[`.env.example`](./.env.example)。`DATABASE_URL` 以及容器内的知识库和状态路径由
`docker-compose.yml` 设置，不要在 `.env` 中覆盖。

```bash
docker compose exec dashboard next-signal doctor        # 检查当前配置
docker compose run --rm dashboard next-signal info-radar pull
docker compose run --rm dashboard next-signal info-radar analyze
docker compose down                              # 停止并保留卷
```

当前版本没有后台调度器。拉取和分析可以从网页控制台、CLI 或你自己的调度器触发。端到端
验证应该在容器内执行，以确保验证环境和发布镜像一致。卷和环境变量的完整映射见
[`docs/zh/containerized-deployment.md`](./docs/zh/containerized-deployment.md)。

### 选择模型运行方式

**在 Apple 芯片上本地运行。** OMLX/MLX 跑在宿主机上，以便使用 Metal GPU。当分析模型
和嵌入模型都在本地提供时，提示词、目标和文章正文不会发送给第三方模型 API。抓取来源
内容，以及你自行配置的同步服务，仍然会使用网络。

```bash
OMLX_BASE_URL=http://host.docker.internal:<port>/v1   # 写进 .env
```

**使用 DeepSeek。** 这种方式不需要本地 GPU。一次实测的 100 条运行成本约为
**¥0.5 / $0.07**，但这不是固定价格。文章长度、缓存命中、输出长度以及提供商的当前
[Token 计价](https://api-docs.deepseek.com/quick_start/pricing/)都会影响最终费用。如果没有
配置 OMLX 服务，分析仍然可以运行，但跨次语义去重会把条目视为新内容，因为它目前只支持
本地嵌入模型。

```bash
DEEPSEEK_API_KEY=sk-...                               # 写进 .env
```

[宿主机原生安装](./docs/zh/operations.md#安装)则把本地模型跑在进程内。

## 常用命令

在容器里可以省略 `uv run` 前缀，因为 `next-signal` 已经在 `PATH` 上。

```bash
uv run next-signal doctor                                    # 检查环境、Postgres、模型和工具
uv run next-signal info-radar pull [--source NAME]           # 拉取已启用信息源并写入 radar_items
uv run next-signal info-radar analyze [--limit N]            # 运行两层分析
uv run next-signal info-radar recap --since D --until D      # 生成带引用的主题回顾
uv run next-signal knowledge ingest <url|staged-file>        # 保存进知识库
uv run next-signal knowledge review                          # 对齐定期回顾队列
uv run next-signal run-workflow knowledge_ingest             # 为 Markdown 重建向量索引
uv run next-signal list                                      # 列出智能体和工作流
uv run next-signal serve [--port 7777]                       # 启动 AgentOS
```

---

## 文档

| 你想了解什么 | 对应文档 |
|---|---|
| 架构和设计取舍 | [docs/zh/architecture.md](./docs/zh/architecture.md) |
| 如何添加 agent、tool、integration、model 或领域 | [docs/zh/development.md](./docs/zh/development.md) |
| 安装、环境配置、`next-signal doctor` 和故障排查 | [docs/zh/operations.md](./docs/zh/operations.md) |
| 容器部署 | [docs/zh/containerized-deployment.md](./docs/zh/containerized-deployment.md) |
| 过滤器设计和调优记录 | [docs/zh/modules/info_filter.md](./docs/zh/modules/info_filter.md) |
| 知识管线设计 | [docs/zh/modules/knowledge.md](./docs/zh/modules/knowledge.md) |
| 能力契约和待处理变更 | [openspec/specs/](./openspec/specs/) · [openspec/changes/](./openspec/changes/) |

**文档提供中英文版本。** 英文是标准版本。中文镜像位于 [`docs/zh/`](./docs/zh/)、
本文件以及 [`dashboard/README.zh-CN.md`](./dashboard/README.zh-CN.md)，每页顶部都有
语言切换入口。`CLAUDE.md` 和 `openspec/specs/` 有意只保留一种语言，因为它们会跟着
代码频繁变化，维护第二份副本容易产生偏差。

## 技术栈

[Agno](https://github.com/agno-agi/agno) 提供智能体运行框架 ·
[gbrain](https://github.com/garrytan/gbrain) 提供 Markdown 优先的混合检索和类型化
链接图 · Postgres + pgvector · Next.js · Qwen3 通过
[MLX](https://github.com/ml-explore/mlx) 在本地推理。

Apache-2.0.
