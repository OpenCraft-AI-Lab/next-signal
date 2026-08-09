<div align="center">

<img src="dashboard/app/icon.svg" width="64" height="64" alt="next-signal" />

# next-signal

**Decide what deserves your attention, then keep the best material in a
knowledge base you own.**

[English](./README.md) · [简体中文](./README.zh-CN.md)

<sub>Apache-2.0 · local-first · runs on your own machine</sub>

</div>

---

You follow hundreds of sources because the one important item could come from
anywhere. The queue grows faster than you can read it.

Summaries make each item shorter, but they do not decide which items deserve
your time. next-signal evaluates incoming material against a policy you can read
and edit. That policy describes what you are trying to understand, including
what should be excluded. For each item, the system asks:

> **How much should this change what I think or do?**

Relevance determines whether an item belongs. Evidence tells you how much to
trust its claims. The score is reserved for decision impact. The example policy
in this repository explicitly allows a released flagship model to outrank a
rigorous but narrow paper. Your policy can encode a different order.

<div align="center">
  <img src="./visual_assets/frontpage.png" alt="The next-signal radar dashboard" width="100%" />
  <br />
  <sub>Dashboard example from a separate live run. The 978-item measurement below comes from a different run.</sub>
</div>

## A real 978-item run

These figures came from a personal feed with no manual filtering between pull
and analysis:

| Count | Result | What it means |
|---:|---|---|
| **978** | pulled | everything the enabled sources returned |
| **977** | analyzed | one item had not completed analysis |
| **568** | dropped at tier 1 | 58.1% did not justify full analysis |
| **409** | kept | 276 remained below the default high-signal threshold |
| **133** | scored at least 75 | 13.6% reached the default high-signal view |

The system did not hide the middle. Items below 75 remain available if you lower
the threshold, while tier-1 drops retain their reasons.

### What it dropped

These are stored reasons from that run:

| The feed sent | Why it was dropped |
|---|---|
| HarmonyOS 7 Beta 2: AI-powered app fault analysis | *vendor tech blog, no new benchmark or capability data* |
| Cloudflare takes on AWS Route 53 in the DNS wars | *general cloud infrastructure launch, not core AI capability or inference optimization* |
| China's exports stay strong despite renewed US tensions | *macro export figures only, no company- or supply-chain-level verification* |
| Productizing the Honor YOYO agent \| AICon Shenzhen | *conference-attendance advertorial* |
| How the humble hot dog became a $100 delicacy | *entirely unrelated to AI, robotics, space, or scientific breakthroughs* |

The first headline contains **AI-powered** and still gets cut. The filter reads
the article, compares it with the reader's policy, and finds no information that
would change the reader's judgment.

### What it kept

> **dots-note-3.0 scores 42/42 under official IMO 2026 marking** · **92** ·
> `release` `benchmark` `reasoning` `agent` `math`
>
> Xiaohongshu's internal dots-note-3.0 received full credit on all six problems
> under official marking. Its 42/42 tied the seven human contestants who also
> earned a perfect score. The system used natural-language reasoning with Python
> assistance rather than a formal proof system such as Lean.
>
> [Published solutions](https://huggingface.co/datasets/dots-studio/dots-imo2026) ·
> [Official human results](https://www.imo-official.com/results/individual/year/2026/)

The same run kept an item from a completely different goal:

> **HORIZON-Breast01: SHR-A1811 in HER2-positive advanced breast cancer** ·
> **88** · `clinical-trial` `regulatory-approval` `oncology` `adc`
>
> A phase 3 interim analysis in *The Lancet Oncology* reported median PFS of
> 30.6 months versus 8.3 months with standard care (HR 0.22), with an ORR of
> 81.7%. China approved the drug in March 2026 for second-line or later
> HER2-positive advanced breast cancer.
>
> [Trial report](https://www.sciencedirect.com/science/article/pii/S1470204526001932) ·
> [Company results](https://www.hengrui.com/images/investor/%E6%81%92%E7%91%9E%E9%86%AB%E8%97%A5%202025%E5%B9%B4%E5%A0%B1.pdf)

The science policy below requires a named phase, concrete results, and a
clinical or engineering action that has already happened. This item clears that
gate.

---

## The filter is inspectable

Its quality does not rest on the phrase "AI-powered filtering." You can inspect
the standard, the decision attached to each item, and the tests used to tune it.

### 1. The standard is a file you own

`configs/info_radar/goals.yaml` is an editorial policy, not a row of topic
sliders. It supports anti-goals and hard vetoes, lives in version control, and is
editable from the dashboard:

```yaml
- name: science_breakthrough
  description: |
    Track major scientific and medical breakthroughs outside AI. …
    Hard veto list: any one of these means it is not a breakthrough,
    regardless of how important it sounds:
      (1) the subject is animals, cells, or organoids, with no human result;
      (2) the conclusion says "may", "promising", "potential", or "preclinical";
      (3) it cannot name an action that has already happened, such as approval,
          phase III entry, installation, shipment, or inclusion in guidelines;
      (4) it is mechanism discovery, drug repurposing, a single cohort,
          or an epidemiological correlation.
    This is a hard gate, not a preference. Rhetoric is not evidence.
```

This is where you can write a rule as specific as "a Nature byline is not by
itself a breakthrough." The policy can be written in any language because the
model reads it as prose.

### 2. Changes are measured on labelled sets

`scripts/radar_eval.py` replays the production pipeline against three sets: 60
adversarial cases, 36 decision-boundary cases, and a 55-item holdout. Three
independent model annotators labelled the holdout after reading `goals.yaml` and
nothing from the production prompts; only unanimous cases were retained. This
is a model-consensus reference set, not a human-labelled benchmark.

Article content is snapshotted before replay, so upstream fetch variation does
not contaminate prompt comparisons. Each run records a hash of both prompts and
the goals file.

On this holdout, the production configuration passed **75%** of cases. When a
run uses repeats, a case passes only when every repeat returns the expected
keep/drop verdict and, for kept items, the mean score lands inside the expected
band. This result applies to this goals file and corpus; it is not a universal
accuracy claim.

### 3. Failed experiments stay in the record

One tuning round improved the adversarial set while taking the holdout pass rate
from 75% to **40%**. The change was rejected. The prompts, measurements, and
reason for the regression are documented in
[`docs/modules/info_filter.md`](./docs/modules/info_filter.md#tuning-and-evaluation).

That record matters because a personal filter can look better on familiar
examples while getting worse on the next batch. The holdout caught exactly that.

---

## Signal is only half of it

Filtering decides what reaches you. The knowledge pipeline decides what stays
useful after you close the tab.

```
   sources ──▶ radar ──▶ you read it ──▶ ingest ──▶ markdown ──▶ scheduled review
                 │                                     │               │
          score by decision impact              files on your disk    days 1, 3, 7,
          deduplicate across runs                + hybrid search       15, 30, 60, 120
          generate recaps on demand
```

One click or command saves a radar item as a long-term knowledge entry. The
pipeline fetches and cleans the source, writes a summary, files it into your
taxonomy, indexes it for hybrid search, and schedules it to resurface on days 1,
3, 7, 15, 30, 60, and 120.

The library is **plain markdown in a folder you own**. It works as an Obsidian
vault, but Obsidian is optional. You choose whether to sync it with Git, another
sync tool, or nothing at all. The library needs no export step because the files
are already yours.

Knowledge ingest currently accepts web articles, YouTube, Bilibili, WeChat
Official Accounts, GitHub repositories, PDFs, and Office files. Radar inputs are
configured as source adapters under `configs/info_radar/sources.yaml`, so new
sources do not change the filtering or knowledge layers.

---

## What is different

Summarization, tagging, and topic prioritization are widely available. The
choices below are what define next-signal:

| Question | next-signal's answer |
|---|---|
| Who defines what matters? | You do, in a versioned policy with goals, anti-goals, and vetoes. |
| Can I inspect a decision? | Drops retain their reasons; keeps retain the summary, impact analysis, and score behind the decision. |
| Can I test a prompt change? | The repository ships labelled sets, a replay harness, prompt hashes, and rejected experiments. |
| What determines rank? | Decision impact, using anchors written in your policy, rather than relevance alone. |
| Where does retained knowledge live? | In markdown files on your disk, with optional Obsidian and Git workflows. |
| Where does inference run? | On your own Apple Silicon machine with OMLX, or through a cloud model you configure. |

The software is free under Apache-2.0. Local inference uses your hardware. Cloud
inference is billed by the provider.

---

## Quick start

Docker Compose is the recommended setup. It starts Postgres with pgvector,
initializes the schema, and launches the dashboard. Helper CLIs are already in
the image. The project CLI is named `next-signal`.

```bash
git clone https://github.com/OpenCraft-AI-Lab/next-signal.git
cd next-signal
cp .env.example .env
$EDITOR .env
docker compose up --build
```

Then open <http://localhost:3000>.

### What to configure

Docker Compose requires these host paths before it starts:

| Key | Purpose |
|---|---|
| `WIKI_DIR` | absolute host path for the clean markdown library; mounted read-write |
| `WIKI_RAW_DIR` | absolute host path for the raw archive; mounted read-write |

Before analysis, choose one model path:

| Path | Configuration |
|---|---|
| Default cloud path | set `DEEPSEEK_API_KEY` |
| Local Apple Silicon path | run OMLX on the host and set `OMLX_BASE_URL`; the endpoint must serve the chat model and embedding model named in `configs/models.yaml` |

Configure credentials required by the source adapters you enable. The complete
list and comments live in [`.env.example`](./.env.example). `DATABASE_URL` and
the in-container wiki and state paths are set by `docker-compose.yml`; do not
override them in `.env`.

```bash
docker compose exec dashboard next-signal doctor        # inspect the configured stack
docker compose run --rm dashboard next-signal info-radar pull
docker compose run --rm dashboard next-signal info-radar analyze
docker compose down                              # stop and keep the volumes
```

The current release has no background scheduler. Pull and analysis run from the
dashboard, the CLI, or a scheduler you provide. End-to-end verification should
run through the container so it uses the same environment as the released
image. See
[`docs/containerized-deployment.md`](./docs/containerized-deployment.md) for the
volume and environment mapping.

### Choose where models run

**Local on Apple Silicon.** OMLX/MLX runs on the host to access the Metal GPU.
When both the analysis model and embedder are served locally, prompts, goals,
and article text are not sent to a third-party model API. Source retrieval and
any sync service you configure still use the network.

```bash
OMLX_BASE_URL=http://host.docker.internal:<port>/v1   # in .env
```

**DeepSeek.** This path needs no local GPU. A measured 100-item run cost roughly
**$0.07 / ¥0.5**, but this is an estimate, not a fixed price. Cost varies with
article length, cache hits, output length, and the provider's current
[token pricing](https://api-docs.deepseek.com/quick_start/pricing/). Without an
OMLX endpoint, analysis still runs, but cross-run semantic deduplication treats
items as novel because its embedder is local-only.

```bash
DEEPSEEK_API_KEY=sk-...                               # in .env
```

[Host-native setup](./docs/operations.md#installation) runs the local model
in-process instead.

## Common commands

Inside the container, omit the `uv run` prefix because `next-signal` is already on
`PATH`.

```bash
uv run next-signal doctor                                    # check env / Postgres / models / tools
uv run next-signal info-radar pull [--source NAME]           # pull enabled sources into radar_items
uv run next-signal info-radar analyze [--limit N]            # run two-tier analysis
uv run next-signal info-radar recap --since D --until D      # synthesize themes with citations
uv run next-signal knowledge ingest <url|staged-file>        # save an item into the knowledge base
uv run next-signal knowledge review                          # reconcile the review schedule
uv run next-signal run-workflow knowledge_ingest             # re-index markdown for vector search
uv run next-signal list                                      # list agents and workflows
uv run next-signal serve [--port 7777]                       # start AgentOS
```

---

## Documentation

| You want to… | Read |
|---|---|
| Understand the architecture and its trade-offs | [docs/architecture.md](./docs/architecture.md) |
| Add an agent, tool, integration, model, or domain | [docs/development.md](./docs/development.md) |
| Install, configure the environment, run `next-signal doctor`, or troubleshoot | [docs/operations.md](./docs/operations.md) |
| Deploy in containers | [docs/containerized-deployment.md](./docs/containerized-deployment.md) |
| Read the filter design and tuning record | [docs/modules/info_filter.md](./docs/modules/info_filter.md) |
| Read the knowledge pipeline design | [docs/modules/knowledge.md](./docs/modules/knowledge.md) |
| Read capability contracts or pending changes | [openspec/specs/](./openspec/specs/) · [openspec/changes/](./openspec/changes/) |

**Docs are bilingual.** English is canonical. The Chinese mirrors live in
[`docs/zh/`](./docs/zh/), [`README.zh-CN.md`](./README.zh-CN.md), and
[`dashboard/README.zh-CN.md`](./dashboard/README.zh-CN.md). Each page has a
language switcher. `CLAUDE.md` and `openspec/specs/` are deliberately kept in a
single language because they change with the code and a second copy would drift.

## Built with

[Agno](https://github.com/agno-agi/agno) for the agent runtime ·
[gbrain](https://github.com/garrytan/gbrain) for markdown-first hybrid search
and the typed-link graph · Postgres + pgvector · Next.js · Qwen3 on
[MLX](https://github.com/ml-explore/mlx) for local inference.

Apache-2.0.
