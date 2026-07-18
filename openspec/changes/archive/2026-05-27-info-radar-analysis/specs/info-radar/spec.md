## ADDED Requirements

### Requirement: seen_at is owned by the analysis layer

The collector (`paca/collectors/info_radar/`) SHALL NOT write to `radar_items.seen_at`. Only the analysis workflow (`paca/workflows/info_radar_analysis/`) SHALL set `seen_at` — either when tier-1 drops an item, when tier-2 completes (success or fallback), or when a per-item tier-2 error is persisted. The 30-day retention sweep operates on `fetched_at`, not `seen_at`, and is unchanged.

#### Scenario: collector pull does not mark items seen

- **WHEN** `paca info-radar pull` runs against any source
- **THEN** no `radar_items.seen_at` column is set or modified by the collector code path

#### Scenario: tier 1 drop sets seen_at

- **WHEN** the analysis workflow's tier-1 stage returns `verdict='drop'` for an item
- **THEN** that `radar_items.seen_at` is set to `now()` after the `radar_analyses` row is committed
