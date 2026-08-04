## REMOVED Requirements

### Requirement: Bilingual UI via a locale cookie

**Reason**: It specified two independent settings as one. Alongside the UI-chrome
locale it also required that the same picker drive the pipeline's
content-language preference — the coupling this change exists to undo. Narrowing
it in place is not possible without leaving behind a scenario asserting that
changing the interface language rewrites `language.json`, so the requirement is
split rather than modified.

**Migration**: Replaced by the two requirements added below, which between them
carry every scenario this one had except the coupling itself. "UI locale via a
locale cookie" keeps the `paca_locale` cookie, the picker's behavior, and the
dictionaries — unchanged. "A nav settings panel owns the content-language
preference" takes the preference file, its writer and reader, and the
container-start seed hook.

## ADDED Requirements

### Requirement: UI locale via a locale cookie

The dashboard SHALL support English and Chinese UI text via `dashboard/lib/i18n/` (dictionaries + a `getDictionary(locale)` lookup), an `I18nProvider` (`dashboard/components/i18n-provider.tsx`) exposing `useI18n() -> {locale, t}` to client components, and a `LanguageToggle` component (`dashboard/components/language-toggle.tsx`) that sets the locale. The active locale SHALL be persisted in a `paca_locale` cookie (`LOCALE_COOKIE`, 1-year `max-age`, `path=/`, `samesite=lax`) and applied on the server for the initial render.

`LanguageToggle` SHALL be a picker rather than a blind toggle: its trigger SHALL show the **current** locale, and its menu SHALL list every available locale with the active one marked. Locale names in the menu SHALL be self-labelled and never translated (`English`, `中文`) — a language menu has to be readable to someone who cannot read the language the UI is currently in. It SHALL be built on the Radix Select primitive, since it picks a value rather than firing a command.

`LanguageToggle` SHALL govern **UI chrome only**. It SHALL NOT read or write the pipeline's content-language preference file (`~/.next-signal/language.json`); that preference is owned by the settings panel specified below. The two settings are independent and MAY hold different values — an operator reading the interface in one language while generating content in another is a supported state, not a drift bug, and the dashboard SHALL NOT reconcile them, warn about the difference, or offer to sync them.

#### Scenario: operator changes language

- **WHEN** the operator opens the language picker and chooses a locale different from the current one
- **THEN** the `paca_locale` cookie is set to that locale, the router refreshes, and subsequently rendered text uses the new locale's dictionary

#### Scenario: changing the UI locale leaves the content language alone

- **WHEN** the operator opens the language picker and chooses a locale different from the current one
- **THEN** no write to `~/.next-signal/language.json` occurs, and the pipeline's content language is unchanged

#### Scenario: the two settings may disagree

- **WHEN** the UI locale is `zh` and the content-language setting is `en`
- **THEN** the dashboard renders its chrome in Chinese and continues to resolve the `global` policy to English, with no warning, badge, or reconciliation prompt

#### Scenario: the picker shows current state, not a target

- **WHEN** the operator looks at the language control while the UI is in English
- **THEN** the trigger reads `EN` (the active locale) and the open menu marks `English` as selected — the control never labels itself with the locale it would switch *to*

#### Scenario: choosing the active locale is a no-op

- **WHEN** the operator opens the picker and selects the locale that is already active
- **THEN** no cookie write and no router refresh occur

#### Scenario: locale persists across reloads

- **WHEN** the operator reloads the dashboard after toggling language
- **THEN** the same locale (read from the `paca_locale` cookie) is used for the initial server render, with no flash of the other language

### Requirement: A nav settings panel owns the content-language preference

The dashboard SHALL provide a settings control in the nav tools cluster: a gear-icon trigger that opens a panel containing the pipeline's **content language** setting. The panel SHALL be built on a `Popover` primitive at `dashboard/components/ui/popover.tsx`, backed by `@radix-ui/react-popover` per the dashboard's rule that a primitive with a Radix equivalent uses it, and SHALL be added to the `/design` catalogue in the same change that introduces it.

The control SHALL be labelled by what it governs — the language of generated content (radar analyses, wiki frontmatter) — and SHALL NOT be labelled merely "language", so it is distinguishable from the adjacent UI-locale picker. Language names inside it SHALL be self-labelled and never translated, for the same reason the locale picker's are.

Selecting a value SHALL write it as `content_language` into `~/.next-signal/language.json` via the `setContentLanguage` server action, the file `core-output-language`'s `global` policy reads. The write SHALL be atomic (temp file + rename) so a concurrent pipeline read never observes a torn file.

The panel's current value SHALL be resolved on the server and passed into the nav for the initial render, so the panel shows its active state on first paint with no loading state. The reader SHALL tolerate a missing or unreadable preference file by falling back to `DEFAULT_LOCALE` and logging, rather than raising: the nav renders on every page, so raising would take down the whole dashboard — including the panel the operator would use to correct the value. This is a deliberate asymmetry with `paca.core.language`, which SHALL continue to raise on the pipeline side.

Once per dashboard container start, a startup hook SHALL create the preference file — seeded with `DEFAULT_LOCALE` — if it does not already exist, so a freshly started dashboard with no prior preference still leaves the pipeline in a defined state. It SHALL NOT overwrite an existing file, and SHALL NOT re-run per request.

#### Scenario: operator changes the content language

- **WHEN** the operator opens the settings panel and selects a content language different from the current one
- **THEN** `~/.next-signal/language.json`'s `content_language` is written to that value, and the next agent build resolving the `global` policy observes it

#### Scenario: panel shows current state on first paint

- **WHEN** the operator opens the settings panel
- **THEN** the currently configured content language is already marked as selected, with no spinner or flash of a default value

#### Scenario: unreadable preference file does not break the nav

- **WHEN** `~/.next-signal/language.json` is missing, corrupt, or holds an unrecognized value, and any dashboard page is rendered
- **THEN** the nav and settings panel render normally showing `DEFAULT_LOCALE`, the error is logged, and no page render fails

#### Scenario: the setting is independent of the UI locale

- **WHEN** the operator changes the content language in the settings panel
- **THEN** the `paca_locale` cookie is unchanged and the UI chrome stays in its current language

#### Scenario: first launch with no preference file

- **WHEN** the dashboard container starts and `~/.next-signal/language.json` does not exist
- **THEN** the startup hook creates it, seeded with `DEFAULT_LOCALE`, before any request is served

#### Scenario: preference file untouched by ordinary page loads

- **WHEN** the operator navigates between pages without opening the settings panel
- **THEN** no write to `~/.next-signal/language.json` occurs
