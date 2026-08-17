## MODIFIED Requirements

### Requirement: One credential store owns every provider credential

The system SHALL persist provider credentials in exactly one file,
`$NEXT_SIGNAL_STATE_DIR/secrets.json` (`/state/secrets.json` in a container), as
a flat JSON object mapping a credential name to its string value.

The credentials the system resolves by name SHALL be `ANTHROPIC_API_KEY`,
`OPENAI_API_KEY`, `GOOGLE_API_KEY`, `DEEPSEEK_API_KEY`, `OMLX_API_KEY`,
`EMBEDDING_API_KEY`, `GITHUB_TOKEN`, and `FOLO_TOKEN`. Names match the
environment variables they replace because child processes require the literal
string; `EMBEDDING_API_KEY` replaces no environment variable and names the
credential an operator-defined OpenAI-compatible embedding endpoint uses.

The set of resolved names SHALL be closed. Every credential the system resolves
SHALL appear in that enumeration, so an interface that renders one control per
credential covers all of them and no configurable credential can exist without a
place to enter it. Names SHALL still be validated against a documented pattern.

An absent file SHALL read as an empty store, since a fresh install has no
credentials and that is a valid state. A file that is present but unreadable,
not a JSON object, or holds a non-string value SHALL raise `RuntimeError`
naming the file — the same loud-failure rule the other state files follow.

System connection configuration — `DATABASE_URL`, `GBRAIN_*`, `POSTGRES_*`,
`*_BIN` paths, and CLI version pins — SHALL NOT move into the store.

#### Scenario: fresh install has no store

- **WHEN** no `secrets.json` exists and a credential is requested
- **THEN** the store reads as empty and the caller raises a missing-credential
  error naming the credential and pointing at the settings page

#### Scenario: malformed store fails loud

- **WHEN** `secrets.json` exists but does not parse as a JSON object of strings
- **THEN** reading it raises `RuntimeError` naming the file, rather than
  degrading to an empty store

#### Scenario: every resolved credential has an entry point

- **WHEN** an interface renders one control per credential the system resolves
- **THEN** every credential any feature can require is present in that list,
  including the one an OpenAI-compatible embedding endpoint uses
