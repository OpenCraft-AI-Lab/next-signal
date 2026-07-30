## ADDED Requirements

### Requirement: `radar_eval_*` tables are development-only and not bootstrap-provisioned

`scripts/radar_eval.py` SHALL create its own three tables — `radar_eval_cases`, `radar_eval_runs`, `radar_eval_results` — via its `init` subcommand. `scripts/bootstrap_db.py` MUST NOT create them. They exist to measure prompt changes offline and carry no runtime behaviour, so a production deployment has no reason to hold them.

Like the business tables, they SHALL be reached through short-lived `psycopg.connect(database_url())` connections.

`radar_eval_cases` holds the hand-labelled expectation per item (`label_set`, `radar_item_id` referencing `radar_items` with `ON DELETE CASCADE`, `bucket`, `expect_verdict`, `expect_min`, `expect_max`, `rationale`) plus a frozen snapshot of the article `content` and `content_status`, unique on `(label_set, radar_item_id)`. Snapshotting content is what makes a variant comparison attributable to the prompt rather than to whether the fetch succeeded that day.

`radar_eval_runs` holds one row per invocation, including `prompt_digest` — a hash of both radar prompts plus `goals.yaml` — so a set of numbers can always be traced to the exact text that produced it.

`radar_eval_results` holds one row per `(run_id, case_id, repeat_idx)`, unique on that triple, so repeated runs of the same item are retained rather than overwritten. Retention is required because the scoring agent is sampled, not deterministic.

#### Scenario: bootstrap does not create the eval tables

- **WHEN** `scripts/bootstrap_db.py` runs against an empty database
- **THEN** the `radar_items`, `radar_analyses`, `radar_pushed_topics`, `radar_recaps`, and `knowledge_reviews` tables exist and no `radar_eval_*` table is created

#### Scenario: repeated evaluation of one item is retained

- **WHEN** the eval harness scores the same case three times within one run
- **THEN** three `radar_eval_results` rows exist for that case, distinguished by `repeat_idx`, and none has overwritten another

#### Scenario: deleting a radar_items row cascades to its eval case

- **WHEN** the 30-day sweep deletes a `radar_items` row referenced by a `radar_eval_cases` row
- **THEN** the eval case row is deleted along with it via `ON DELETE CASCADE`
