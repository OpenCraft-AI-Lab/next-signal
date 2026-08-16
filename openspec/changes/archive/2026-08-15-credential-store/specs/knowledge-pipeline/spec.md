## MODIFIED Requirements

### Requirement: GitHub adapter authenticates only when a token is configured

The github fetcher SHALL read `GITHUB_TOKEN` from the credential store at call
time and send authenticated requests when it is present; when absent, it SHALL
fall back to anonymous GitHub REST access and not require any configuration.

#### Scenario: token absent

- **WHEN** the credential store holds no `GITHUB_TOKEN` and the input is a public repo
- **THEN** the fetcher completes successfully using anonymous GitHub REST access

#### Scenario: token present

- **WHEN** `GITHUB_TOKEN` is present in the credential store
- **THEN** the fetcher sends an `Authorization: Bearer <token>` header on each request

#### Scenario: environment does not supply the token

- **WHEN** `GITHUB_TOKEN` is set in the process environment but absent from the store
- **THEN** the fetcher uses anonymous access, as though no token were configured
