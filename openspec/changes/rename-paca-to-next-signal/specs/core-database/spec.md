## MODIFIED Requirements

### Requirement: agno tables go through the singleton `PostgresDb`

Code that touches agno-managed tables (sessions, memory, knowledge, traces) SHALL acquire the database via `next_signal.core.db.get_db()`. Direct construction of `agno.db.PostgresDb` is prohibited.

#### Scenario: agno tables are auto-provisioned

- **WHEN** the AgentOS app starts with a configured `DATABASE_URL`
- **THEN** agno provisions its own tables; no application code defines or migrates them

### Requirement: SQLAlchemy URL adapter rewrites scheme

`next_signal.core.db.database_url(for_sqlalchemy=True)` SHALL rewrite the URL scheme to use the psycopg v3 driver (`postgresql+psycopg://`).

#### Scenario: agno consumes the SQLAlchemy URL

- **WHEN** agno requests the SQLAlchemy URL
- **THEN** the returned URL forces the psycopg v3 dialect; the v2 driver is never used
