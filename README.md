<div align="center">

<img src="dashboard/app/icon.svg" width="64" height="64" alt="next-signal" />

# next-signal

**Most AI readers summarize everything.
This one decides what deserves your attention — then makes sure you never lose it.**

[English](./README.md) · [简体中文](./README.zh-CN.md)

<sub>Apache-2.0 · local-first · runs on your own machine</sub>

</div>

---

You subscribe to 200 feeds because you are afraid of missing the one thing that
matters. Then you read none of them.

Every reader on the market answers this with summarization: shorter versions of
all the same articles. next-signal answers it with **judgment**. You write down
what you are trying to understand — *and what you are not* — and the model scores
every incoming item on one question:

> **How much should this change what you think or do?**

Not how well-written it is. Not how many people shared it. Not how rigorous the
methodology is. **Consequence.** A flagship model release outranks a careful
single-lab paper, every time, and the rubric says so out loud.

<div align="center">
  <img src="./visual_assets/frontpage.png" alt="The next-signal radar" width="100%" />
</div>

## The last run, unedited

978 items off a personal Folo timeline. Here is what came back:

| | | |
|---:|---|---|
| **978** | pulled | everything the feed sent |
| **977** | analyzed | two-tier pipeline |
| **409** | kept | 58% dropped at tier 1 |
| **133** | scored ≥ 75 | what actually reaches the top of the page |

**You get back 14% of your feed.** The other 86% is the product.

### What it threw away, and why

Every drop carries a stored reason:

| The feed sent | Why it was dropped |
|---|---|
| HarmonyOS 7 Beta 2: AI-powered app fault analysis | *vendor tech blog, no new benchmark or capability data* |
| Cloudflare takes on AWS Route 53 in the DNS wars | *general cloud infrastructure launch, not core AI capability or inference optimization* |
| China's exports stay strong despite renewed US tensions | *macro export figures only, no company- or supply-chain-level verification* |
| Productizing the Honor YOYO agent \| AICon Shenzhen | *conference-attendance advertorial* |
| How the humble hot dog became a $100 delicacy | *entirely unrelated to AI, robotics, space, or scientific breakthroughs* |

Look at the first one. The headline says **AI-powered**, and it still gets cut —
because keyword matching is not what is happening here. It read the article,
checked it against what this reader is trying to understand, and found nothing
that would change their mind.

### What survived

> **AI takes an official perfect score at the International Mathematical
> Olympiad** — **92** · `release` `benchmark` `reasoning` `agent` `math`
>
> First AI system to earn an officially graded 42/42 at IMO 2026, beating every
> human competitor. Notably it did *not* rely on a formal proof system like
> Lean — natural-language reasoning with Python assistance, in a recursive
> prove-verify-correct loop.

And from a completely different goal, on the same run:

> **HORIZON-Breast01: SHR-A1811 in HER2-positive advanced breast cancer** —
> **88** · `clinical-trial` `regulatory-approval` `oncology` `adc`
>
> Phase 3 interim analysis in *Lancet Oncology*. Median PFS 8.3 → 30.6 months
> versus standard of care (HR 0.22), ORR 81.7%. Already moved the drug through
> regulatory approval.

That second one is the veto list below doing its job — it names a phase, a
number, and an approval that has already happened.

---

## Why you should believe the filter

This is the part no other reader has.

**1. Your standard is a file you own.** `configs/info_radar/goals.yaml` is not a
set of topic sliders. It is an editorial policy — with **anti-goals** and hard
veto lists — that you version-control and edit in the dashboard:

```yaml
- name: science_breakthrough
  description: |
    Track major scientific and medical breakthroughs outside AI. …
    Hard veto list — any one of these and it is not a breakthrough, no matter
    how important it sounds:
      (1) subject is animals / cells / organoids, no human result;
      (2) the conclusion contains "may / promising / potential / preclinical";
      (3) it cannot name one action that has already happened (approved,
          entered phase III, installed, shipped, written into guidelines);
      (4) it is mechanism discovery, drug repurposing, a single cohort,
          or an epidemiological correlation.
    This is a hard gate, not a preference. Rhetoric is not evidence.
```

Nobody else lets you say *"a Nature byline is not by itself a breakthrough."*
Write it in any language — the file is read by the model, not parsed by code.

**2. It is measured, not vibed.** `scripts/radar_eval.py` replays the real
pipeline against three hand-labelled sets — 60 adversarial, 36 decision-boundary,
and a **55-item holdout labelled blind** by three agents that were allowed to read
`goals.yaml` and nothing else, keeping only unanimous items. Article content is
snapshotted so a comparison is attributable to the prompt, not to whether the
feed answered that day. Every run records a hash of both prompts plus the goals
file, so a number always traces back to the text that produced it.

Production measures **75% against that holdout.**

**3. The failures are in the docs too.** One tuning round looked like a clean win
on the adversarial set and took holdout from 75% down to **40%**. It is written
up in
[`docs/modules/info_filter.md`](./docs/modules/info_filter.md#tuning-and-evaluation)
under *measured and rejected — do not retry without reading the record*, along
with why the guardrail bucket that never regressed was itself the bug.

A personal news tool with a holdout set and a record of its own rejected
experiments is a strange thing to build. It is also the only way to know your
filter is not quietly lying to you.

---

## Signal is only half of it

Filtering decides what reaches you. The other half decides what you keep.

```
   feeds ──▶ radar ──▶ you read it ──▶ ingest ──▶ wiki ──▶ spaced repetition
                │                                   │              │
         score by consequence            clean markdown       back on your
         dedup across weeks              on your disk        screen at 1, 3, 7,
         weekly recap                    + vector index      15, 30, 60, 120d
```

One command promotes an item from the radar into a permanent artifact: fetched,
cleaned, summarized, auto-filed into your taxonomy, indexed for hybrid search,
and enrolled on an Ebbinghaus curve so it comes back before you forget it.

Everything lands as **plain markdown in a folder you own** — a real Obsidian
vault, synced to GitHub by the Obsidian Git plugin. There is no export button
because there is nothing to export from.

Sources handled today: web articles, YouTube (native subtitles), Bilibili
(subtitles, or local transcription when there are none), WeChat Official
Accounts, GitHub repos, PDFs and Office files.

---

## How this compares

Every reader on this list has AI now. Feedly's Leo prioritizes and mutes topics,
Inoreader added multi-provider summarization and tagging, Readwise's Ghostreader
works inside a document, Khoj answers questions across your files. Putting a
language model on a feed stopped being a differentiator somewhere in 2025.

What none of them will tell you is **why**.

| | Feedly Pro+ | Inoreader Pro | Readwise Reader | Khoj | **next-signal** |
|---|:---:|:---:|:---:|:---:|:---:|
| Filters before you read | priority topics, mute | rules + AI tags | — | — | **goals + anti-goals** |
| The standard is a file you own | — | — | — | — | **versioned YAML** |
| Shows why each item was kept or cut | — | — | — | — | **stored, per item** |
| Filter quality measured on a labelled set | — | — | — | — | **55-item blind holdout** |
| Ranks by consequence, not relevance | — | — | — | — | **✔** |
| Runs entirely on your own machine | — | — | — | ✔ | **✔** |
| Spaced repetition on what you keep | — | — | ✔ | — | **✔ Ebbinghaus** |
| Library is plain markdown you own | — | — | — | ✔ | **✔ Obsidian vault** |
| Price | $99/yr | $90/yr | $120/yr | free self-host | **free self-host** |

<sub>Prices as of August 2026, annual billing.</sub>

---

## Quick start

Containers are the supported path. Postgres + pgvector, schema bootstrap, and
the dashboard come up together, and the image already bundles the peer CLIs
(`gbrain`, `opencli`, `folocli`).

```bash
git clone https://github.com/OpenCraft-AI-Lab/next-signal.git
cd next-signal
cp .env.example .env && $EDITOR .env
docker compose up --build
```

Then open <http://localhost:3000>.

**Minimum `.env`** — the build fails fast without these:

| Key | Why |
|---|---|
| One LLM key: `DEEPSEEK_API_KEY` (primary), or `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | The default path — see [Two ways to run the models](#two-ways-to-run-the-models) for the free local option |
| `PACA_WIKI_DIR` | Host path of your clean wiki repo — bind-mounted read-write |
| `PACA_WIKI_RAW_DIR` | Host path of your raw archive repo — bind-mounted read-write |

`DATABASE_URL` and the in-container wiki/state paths are set by
`docker-compose.yml`; do not override them in `.env`.

```bash
docker compose exec dashboard paca doctor        # self-check inside the container
docker compose run --rm dashboard paca info-radar pull
docker compose run --rm dashboard paca info-radar analyze
docker compose down                              # stop, keep the volumes
```

> Run end-to-end verification through the container, not on the host — that
> keeps the verification environment identical to what ships. Full design,
> volume and env-var mapping:
> [docs/containerized-deployment.md](./docs/containerized-deployment.md).

### Two ways to run the models

**Local — free, and nothing leaves the machine.** OMLX/MLX runs on the host so it
can reach the Metal GPU. Point the container at it and the whole filtering
pipeline is local: your reading interests, and every article you read, stay with
you. The embedder runs here too, so cross-week dedup is local as well.

```bash
OMLX_BASE_URL=http://host.docker.internal:<port>/v1   # in .env
```

**DeepSeek — about 7 cents per 100 articles.** No GPU, no local setup. Filtering
a 100-item feed costs roughly **$0.07 / ¥0.5**. At a hundred articles a day, that
is around **$2 a month** — less than any reader you are paying for now.

```bash
DEEPSEEK_API_KEY=sk-...                               # in .env
```

[Host-native setup](./docs/operations.md#installation) runs the local model
in-process instead.

## Common commands

Inside the container, drop the `uv run` prefix — `paca` is already on `PATH`.

```bash
uv run paca doctor                                    # check env / Postgres / OMLX / tools
uv run paca info-radar pull [--source NAME]           # pull sources into radar_items
uv run paca info-radar analyze [--limit N]            # two-tier analysis
uv run paca info-radar recap --since D --until D      # themed narratives with citations
uv run paca knowledge ingest <url|staged-file>        # promote into the knowledge base
uv run paca knowledge review                          # reconcile the spaced-repetition queue
uv run paca run-workflow knowledge_ingest             # wiki → vector index re-ingest
uv run paca list                                      # list agents / workflows
uv run paca serve [--port 7777]                       # start AgentOS
```

---

## Documentation

| You want to… | Read |
|---|---|
| Understand how the system is built, and why | [docs/architecture.md](./docs/architecture.md) |
| Add an agent / tool / integration / model / domain | [docs/development.md](./docs/development.md) |
| Install, configure env, run `paca doctor`, troubleshoot | [docs/operations.md](./docs/operations.md) |
| Deploy in containers | [docs/containerized-deployment.md](./docs/containerized-deployment.md) |
| Go deep on the filter, including every tuning result | [docs/modules/info_filter.md](./docs/modules/info_filter.md) |
| Go deep on the knowledge pipeline | [docs/modules/knowledge.md](./docs/modules/knowledge.md) |
| Read capability contracts / pending changes | [openspec/specs/](./openspec/specs/) · [openspec/changes/](./openspec/changes/) |

**Docs are bilingual.** English is canonical; the Chinese mirror lives under
[`docs/zh/`](./docs/zh/) plus [`README.zh-CN.md`](./README.zh-CN.md), and every
page carries a switcher at the top. Deliberately untranslated:
`CLAUDE.md` (agent instructions) and `openspec/specs/` (capability contracts) —
both churn with the code, where a second copy would drift rather than help.

## Built with

[gbrain](https://github.com/garrytan/gbrain) for markdown-first hybrid search
and the typed-link graph · Postgres + pgvector · Next.js ·
[Folo](https://github.com/RSSNext/Folo) as the feed source · Qwen3 on
[MLX](https://github.com/ml-explore/mlx) for local inference.

Apache-2.0.
