## MODIFIED Requirements

### Requirement: Bilingual UI via a locale cookie

The dashboard SHALL support English and Chinese UI text via `dashboard/lib/i18n/` (dictionaries + a `getDictionary(locale)` lookup), an `I18nProvider` (`dashboard/components/i18n-provider.tsx`) exposing `useI18n() -> {locale, t}` to client components, and a `LanguageToggle` component (`dashboard/components/language-toggle.tsx`) that sets the locale. The active locale SHALL be persisted in a `paca_locale` cookie (`LOCALE_COOKIE`, 1-year `max-age`, `path=/`, `samesite=lax`) and applied on the server for the initial render.

`LanguageToggle` SHALL be a picker rather than a blind toggle: its trigger SHALL show the **current** locale, and its menu SHALL list every available locale with the active one marked. Locale names in the menu SHALL be self-labelled and never translated (`English`, `中文`) — a language menu has to be readable to someone who cannot read the language the UI is currently in. It SHALL be built on the Radix Select primitive, since it picks a value rather than firing a command.

Changing the locale SHALL also drive info-radar's content-language preference: the same picker's `onValueChange` handler that sets the `paca_locale` cookie SHALL also call a server action (`setContentLanguage`) that writes the resolved locale as `content_language` into the shared runtime preference file (`~/.next-signal/language.json`, the file `core-output-language`'s `global` policy reads), so the cookie and the file are driven from the same user action and don't drift out of sync in practice. This is deliberate — the UI-chrome locale and the info-radar content-language preference are the same control, not two independent settings. The preference-file write SHALL NOT block the UI's own language switch — a failed write is logged, not surfaced as a blocking error, since the cookie/dictionary swap the user is watching happen does not depend on it.

Separately, once per dashboard container start, a startup hook SHALL create the preference file — seeded with the dashboard's own `DEFAULT_LOCALE` — if it does not already exist, so a freshly started dashboard with no prior preference still leaves the pipeline in a defined state. This startup check SHALL NOT re-run on every request; only container start and an actual locale change write the file.

#### Scenario: operator changes language

- **WHEN** the operator opens the language picker and chooses a locale different from the current one
- **THEN** the `paca_locale` cookie is set to that locale, the router refreshes, and subsequently rendered text uses the new locale's dictionary

#### Scenario: changing language also updates the content-language preference

- **WHEN** the operator opens the language picker and chooses a locale different from the current one
- **THEN** `~/.next-signal/language.json`'s `content_language` is updated to match, from the same handler that writes the `paca_locale` cookie

#### Scenario: the picker shows current state, not a target

- **WHEN** the operator looks at the language control while the UI is in English
- **THEN** the trigger reads `EN` (the active locale) and the open menu marks `English` as selected — the control never labels itself with the locale it would switch *to*

#### Scenario: choosing the active locale is a no-op

- **WHEN** the operator opens the picker and selects the locale that is already active
- **THEN** no cookie write, no preference-file write, and no router refresh occur

#### Scenario: locale persists across reloads

- **WHEN** the operator reloads the dashboard after toggling language
- **THEN** the same locale (read from the `paca_locale` cookie) is used for the initial server render, with no flash of the other language

#### Scenario: first launch with no preference file

- **WHEN** the dashboard container starts and `~/.next-signal/language.json` does not exist
- **THEN** the startup hook creates it, seeded with `DEFAULT_LOCALE`, before any request is served

#### Scenario: preference file untouched by ordinary page loads

- **WHEN** the operator navigates between pages without touching the language picker
- **THEN** no write to `~/.next-signal/language.json` occurs
