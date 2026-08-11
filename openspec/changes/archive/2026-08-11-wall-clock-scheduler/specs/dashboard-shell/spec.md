## RENAMED Requirements

- FROM: `### Requirement: A nav settings panel owns the content-language preference`
- TO: `### Requirement: The settings page owns the content-language preference`

## MODIFIED Requirements

### Requirement: Global app shell

The dashboard SHALL render a global app shell — top navigation bar (`Radar`, `Knowledge`, `Goals`, `Subscriptions`, `Design System` entries; `Goals` and `Subscriptions` MAY be placeholder links until their pages land), a brand block (`SignalMark` on the signal gradient tile + `next-signal` wordmark), a theme toggle, a settings entry, and a `sonner` `<Toaster />` root — that is shared by every page under `app/`.

The `Radar` and `Knowledge` nav entries SHALL use their brand marks at `variant="nav"`. The remaining entries have no brand mark and SHALL use lucide icons; a brand glyph in the nav signifies a product with its own identity, and SHALL NOT be introduced for sections that lack one.

The settings entry SHALL sit in the nav's tools cluster rather than among the page links, and SHALL be a link to `/settings` that marks itself as the current page while that route is active. It is chrome that follows the operator between products rather than being one of them.

The shell SHALL NOT carry a host or environment chip. It was the shell's only client-resolved state, requiring a mount effect to read `window.location.host` on every page, and it reported to the operator of a loopback-bound dashboard the address they had just typed.

#### Scenario: every page renders inside the shell

- **WHEN** the operator visits any `app/<page>` route
- **THEN** the top nav, the brand block, the theme toggle, the settings entry, and the toast root are present in the rendered HTML

#### Scenario: the shell carries the next-signal wordmark

- **WHEN** the operator loads any page
- **THEN** the brand block reads `next-signal` beside the signal mark, and the document title is `next-signal · local dashboard`

#### Scenario: brand glyphs are scoped to branded sections

- **WHEN** a reviewer inspects the nav entries
- **THEN** `Radar` and `Knowledge` render brand marks while `Goals`, `Subscriptions`, and `Design System` render lucide icons

#### Scenario: theme toggle persists

- **WHEN** the operator clicks the theme toggle and reloads
- **THEN** the previously selected theme (light / dark / system) is restored without a flash of incorrect theme

#### Scenario: the settings entry navigates rather than opening a panel

- **WHEN** the operator activates the nav's settings control
- **THEN** the browser navigates to `/settings`, and the control renders as the active page while there

### Requirement: The settings page owns the content-language preference

The dashboard SHALL own its settings on a page at `/settings`, reached from the nav's settings entry, carrying the pipeline's **content language** setting among the others specified below. A page rather than a panel anchored to the nav: the settings outgrew what an anchored panel can hold, and a page is the only surface on which they can be laid out and scrolled. The page SHALL introduce no new UI primitive, and the `Popover` primitive and `/design` catalogue entry that the anchored panel required SHALL be retired with it, since nothing else uses them.

The page SHALL be organised into labelled sections, one per setting it owns, separated so that no control is mistaken for a qualifier of another. Sections SHALL be independent: changing one SHALL NOT read, write, or invalidate another's state.

The control SHALL be labelled by what it governs — the language of generated content (radar analyses, wiki frontmatter) — and SHALL NOT be labelled merely "language", so it is distinguishable from the UI-locale picker in the nav. Language names inside it SHALL be self-labelled and never translated, for the same reason the locale picker's are.

Selecting a value SHALL write it as `content_language` into `~/.next-signal/language.json` via the `setContentLanguage` server action, the file `core-output-language`'s `global` policy reads. The write SHALL be atomic (temp file + rename) so a concurrent pipeline read never observes a torn file.

Every value the page displays SHALL be resolved on the server by the page itself, so each control paints its active state on first render with no loading state. The app shell SHALL NOT read these settings: only `/settings` needs them, and a header that reads several state files and a database row to render is a cost every other page would pay. The reader SHALL tolerate a missing or unreadable preference file by falling back to `DEFAULT_LOCALE` and logging, rather than raising, because the page that would repair the file is the page that raising would take down. This is a deliberate asymmetry with `next_signal.core.language`, which SHALL continue to raise on the pipeline side.

Once per dashboard container start, a startup hook SHALL create the preference file — seeded with `DEFAULT_LOCALE` — if it does not already exist, so a freshly started dashboard with no prior preference still leaves the pipeline in a defined state. It SHALL NOT overwrite an existing file, and SHALL NOT re-run per request.

#### Scenario: operator changes the content language

- **WHEN** the operator opens `/settings` and selects a content language different from the current one
- **THEN** `~/.next-signal/language.json`'s `content_language` is written to that value, and the next agent build resolving the `global` policy observes it

#### Scenario: the page shows current state on first paint

- **WHEN** the operator opens `/settings`
- **THEN** the currently configured content language is already marked as selected, with no spinner or flash of a default value

#### Scenario: unreadable preference file does not break the settings page

- **WHEN** `~/.next-signal/language.json` is missing, corrupt, or holds an unrecognized value, and `/settings` is rendered
- **THEN** the section renders normally showing `DEFAULT_LOCALE`, the error is logged, and no page render fails

#### Scenario: the setting is independent of the UI locale

- **WHEN** the operator changes the content language on `/settings`
- **THEN** the `ns_locale` cookie is unchanged and the UI chrome stays in its current language

#### Scenario: first launch with no preference file

- **WHEN** the dashboard container starts and `~/.next-signal/language.json` does not exist
- **THEN** the startup hook creates it, seeded with `DEFAULT_LOCALE`, before any request is served

#### Scenario: preference file untouched by ordinary page loads

- **WHEN** the operator navigates between pages other than `/settings`
- **THEN** no read or write of `~/.next-signal/language.json` occurs

#### Scenario: settings sections do not interfere

- **WHEN** the operator changes a value in one section of the page
- **THEN** the other sections' stored state is unread and unwritten, and their displayed values are unchanged

## ADDED Requirements

### Requirement: Settings persist on commit, and every commit is acknowledged

Each control on the settings page SHALL persist when the user *commits* it, and what counts as a commit SHALL be determined by the control:

- A **discrete choice** (a segmented control such as the content language, the schedule's enable, or its catch-up policy) SHALL commit on click. One interaction already expresses one complete, valid intent, so it SHALL NOT require a separate confirm step.
- A **typed value** (the schedule time) SHALL commit on blur or Enter, and SHALL NOT persist per keystroke. A native time input emits a complete value for every segment edited, so persisting each change would publish values the operator never chose — and the scheduler reads the file within one poll, so such a value can become the live schedule.
- An **interdependent group** whose partial states are invalid (the Codex and Claude settings) SHALL commit through an explicit Save control.

Regardless of path, a successful write SHALL be acknowledged to the operator, and a failed one SHALL roll the control back to the last value known to be stored and report the failure. These controls update optimistically, so they move whether or not the write landed; without an acknowledgement the operator cannot distinguish a saved setting from an unsaved one, and a section with no Save control reads as not wired up at all.

A commit that would not change the stored value SHALL be a no-op: no write, no acknowledgement.

Every state file the page owns SHALL be published through one shared atomic writer rather than a copy per setting, and its temp path SHALL be unique per write. Two commits in flight at once — which optimistic controls produce whenever one commits while another is still writing — otherwise collide on a single temp path: the first rename consumes it and the second fails for want of it. The file left behind is intact; what breaks is the second caller, which reports a failed save and rolls its control back to a value that is no longer what is on disk.

#### Scenario: a discrete choice saves on click

- **WHEN** the operator clicks a segmented option different from the current one
- **THEN** the new value is written and the save is acknowledged, with no further confirmation step

#### Scenario: typing a time does not publish intermediate values

- **WHEN** the operator edits the schedule time from 13:55 to 09:30, which the control reports as 09:55 and then 09:30
- **THEN** nothing is written while the field is being edited, and exactly one write of 09:30 occurs when it commits

#### Scenario: a failed write rolls the control back

- **WHEN** a write fails
- **THEN** the control returns to the last value known to be stored and the failure is reported

#### Scenario: re-selecting the current value writes nothing

- **WHEN** the operator commits a value identical to the stored one
- **THEN** no write occurs and no acknowledgement is shown

#### Scenario: concurrent commits do not report a failure neither had

- **WHEN** two commits to the same state file are in flight at once
- **THEN** both report success and one of the two payloads is left in place in full, rather than one being told its save failed because the other got there first

### Requirement: The settings page owns the unattended run schedule

The settings page SHALL carry a section, visually separated from the sections around it, that owns the wall-clock schedule specified by `core-schedule`. It SHALL expose three controls — whether the schedule is enabled, the daily times, and whether a missed run is caught up — SHALL state the zone those times fire in without offering to change it, and SHALL read back the outcome of the last run.

The times SHALL be editable as a list, added and removed one row at a time, since the schedule is a set of daily times rather than a single one. A newly added row SHALL be a draft: it SHALL NOT be written until it holds a time and commits. The last remaining time SHALL NOT be removable — an enabled schedule with nothing to fire is not a reachable state, and the enable control is how the schedule is stopped. Adding a row SHALL choose the first hour not already taken, and SHALL do nothing once every hour is; a search for a free value SHALL be bounded by the values it can return.

Writes SHALL go to `~/.next-signal/schedule.json` through a server action, atomically, mirroring how the content-language setting writes its own file. The section SHALL NOT write on render.

The time control SHALL express a wall-clock time of day and nothing else, so that every value the file can hold is a value the page can display.

The timezone SHALL be displayed, not chosen: the section SHALL name the zone `core-schedule` resolves from `INFO_RADAR_TIMEZONE` and say where it is set, and SHALL NOT offer a control that records a zone of its own. The same value fixes radar day grouping and review due dates, so a schedule carrying its own zone would fire at 08:00 in one zone while its results were filed under a day boundary drawn in another. A stored zone that steers nothing is worse than none: its only observable effect is the warning that it has no effect.

The section SHALL display the next time a slot comes round, and SHALL compute it in the zone the scheduler resolves rather than the browser's. A next-run stated in a zone that decides nothing is confidently wrong, and it is the one value on this page an operator would act on without checking.

The times and catch-up controls SHALL be hidden while the schedule is disabled, since neither has meaning then.

The section SHALL state, in its hint text, that catch-up applies only to runs missed while the scheduler was not running and that changing the schedule never triggers a run for a time that has just passed. This distinction is not discoverable from the controls themselves.

The last-run read-back SHALL come from the `schedule_state` row via the dashboard's existing Postgres pool, rendered with the existing relative-time helper, and SHALL distinguish never-run from succeeded from failed. When the last run failed, the recorded error SHALL be reachable from the section rather than only from container logs.

The section SHALL reuse existing UI primitives rather than introducing new ones, so it inherits the page's visual language and incurs no `/design` catalogue addition.

Reads SHALL be forgiving in the same way, and for the same reason, as the content-language reader: a missing, corrupt, or invalid `schedule.json` SHALL render the section as disabled and log, never raise, so the page that would fix the file still renders. The pipeline-side reader SHALL continue to raise.

#### Scenario: operator schedules a daily run

- **WHEN** the operator enables the schedule and sets the time to 08:00
- **THEN** `~/.next-signal/schedule.json` is written atomically with `enabled: true` and `at: ["08:00"]`, and the running scheduler observes it on its next poll

#### Scenario: disabled schedule hides its details

- **WHEN** the schedule is disabled
- **THEN** the times, timezone line, and catch-up control are not rendered, and only the enable control and the section's hint remain

#### Scenario: the zone is stated rather than offered

- **WHEN** the operator opens an enabled schedule
- **THEN** the section shows the zone `core-schedule` resolves as read-only text, names the environment variable that sets it, offers no way to record a different one, and states the next run in that same zone

#### Scenario: adding a time terminates when every hour is taken

- **WHEN** the operator adds times until all twenty-four hours are occupied and adds once more
- **THEN** nothing is added and the page remains responsive

#### Scenario: last run is reported

- **WHEN** the most recent scheduled run failed
- **THEN** the section reports the failure and its time, and the recorded error text is reachable from the section

#### Scenario: never-run schedule reads as such

- **WHEN** a schedule is enabled but has not yet reached its first slot
- **THEN** the section reports that no run has happened yet, rather than showing an empty or zeroed timestamp

#### Scenario: unreadable schedule file does not break the settings page

- **WHEN** `~/.next-signal/schedule.json` is corrupt or holds an invalid time, and `/settings` is rendered
- **THEN** the section renders as disabled, the error is logged, and no page render fails

#### Scenario: rendering the page does not write the schedule

- **WHEN** the operator opens `/settings` without changing anything
- **THEN** no write to `~/.next-signal/schedule.json` occurs
