## ADDED Requirements

### Requirement: Search fails loudly when GBrain is not initialised

`search_knowledge` SHALL raise an error naming the cause when GBrain has not
been initialised. It SHALL NOT return an empty result list, a partial result
set, or a lexical-only fallback presented as a search result.

An empty list is indistinguishable from "the knowledge base holds nothing about
this", which would let an unconfigured deployment look like an unhelpful one.
This is the default behaviour unless guarded: the underlying GBrain CLI reports
no results and exits zero when no brain exists, so the absence of an error from
the tool SHALL NOT be taken as evidence that a brain is present.

The error SHALL name the uninitialised brain and point at how to initialise it,
in the same shape as every other missing-configuration message.

A state that cannot be determined SHALL NOT be treated as a failure. Only a
definite "not initialised" blocks the search, so that an unreadable
configuration degrades to attempting the search rather than to refusing it.

#### Scenario: uninitialised GBrain is reported, not swallowed

- **WHEN** `search_knowledge` is called and no GBrain brain has been initialised
- **THEN** it raises an error naming the uninitialised brain, and returns no
  results

#### Scenario: a genuinely empty result stays empty

- **WHEN** `search_knowledge` runs against an initialised GBrain that holds no
  matching document
- **THEN** it returns an empty list without raising

#### Scenario: an indeterminate state does not block the search

- **WHEN** `search_knowledge` cannot determine whether GBrain is initialised
- **THEN** it proceeds with the search rather than raising
