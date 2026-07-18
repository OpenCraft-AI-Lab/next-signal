## 1. Workflow

- [ ] 1.1 Finalize `src/paca/workflows/daily_portfolio_brief.py` (Step + Parallel; brief writer agent).
- [ ] 1.2 `configs/workflows/daily_portfolio_brief.yaml` (inputs schema).
- [ ] 1.3 Register workflow via `configs/workflows/` (auto-loaded by `orchestrator/runnable_loader.py::load_runnables()`).
- [ ] 1.4 Verify single trigger via HTTP POST.

## 2. Scheduler runtime

- [ ] 2.1 `src/paca/scheduler/runs.py` — CRUD helpers for `job_runs`.
- [ ] 2.2 `src/paca/scheduler/dispatcher.py` — read job config, POST AgentOS, write `job_runs`, trigger notify.
- [ ] 2.3 `src/paca/scheduler/plist.py` — generate launchd plist XML from `WhenSpec`.

## 3. CLI

- [ ] 3.1 `paca schedule install / list / remove / run-now`.
- [ ] 3.2 Sync `configs/schedules.yaml` ↔ `scheduled_jobs` table.

## 4. Verify

- [ ] 4.1 Set system clock to before the trigger, sleep through it, wake — observe single catch-up run.
- [ ] 4.2 `job_runs` contains the run row.
- [ ] 4.3 Notification arrives in Discord (when discord-interface is wired).
