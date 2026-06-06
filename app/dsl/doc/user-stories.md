# DSL User Stories

## Purpose

Capture the first user journeys for the asset DSL.

These stories focus on how a business analyst creates assets, how knowledge is
ingested, and how the platform turns DSL statements into governed knowledge
bases and repository artifacts.

## Story 1: Create A Rule

As a business analyst, I want to create a `Rule` with business language so that
I can describe eligibility or policy logic without editing raw YAML.

Acceptance criteria:

- Given a valid `CREATE RULE` statement, when the user validates it, then the
  parser returns a successful AST.
- Given a valid rule draft, when the user applies it, then the rule is written
  to the governed asset repository.
- Given a rule references invalid relations or an unknown owner KB, when the
  user validates it, then the system returns actionable errors.
- Given an approved rule already exists, when a major change is applied, then
  the platform creates a new version rather than silently overwriting history.

## Story 2: Create A Flow

As a business analyst, I want to create a `Flow` so that I can represent a
customer intent in the same language used by the runtime model.

Acceptance criteria:

- Given a valid `CREATE FLOW` statement, when the user applies it, then the
  flow asset is generated and registered.
- Given a flow references a process or plan, when the compiler runs, then the
  references are validated before apply.

## Story 3: Create A Process

As a knowledge engineer, I want to create a `Process` so that I can define the
execution structure behind a flow.

Acceptance criteria:

- Given a valid `CREATE PROCESS` statement, when it is applied, then the
  process artifact is created in the repository model.
- Given the process references tasks or rules, when validation runs, then the
  compiler verifies that the referenced assets already exist or are staged.

## Story 4: Create A Knowledge Base

As a platform engineer, I want to declare a `Knowledge Base` so that the
platform knows which assets it owns and which stores it can project into.

Acceptance criteria:

- Given a `CREATE KNOWLEDGE_BASE` statement, when it is validated, then the
  owner KB and its allowed asset types are registered.
- Given a knowledge base declaration includes corpus input, when the apply step
  runs, then the ingestion pipeline is triggered.
- Given the knowledge base already exists, when new corpus content is applied,
  then the platform stages a new iteration with versioned lineage.

## Story 5: Ingest A Corpus Into Assets

As a knowledge engineer, I want to run ingestion from a raw corpus so that the
platform can create governed assets from source material.

Acceptance criteria:

- Given a corpus path, when ingestion runs, then supported documents are
  scanned and parsed.
- Given extraction succeeds, when the compiler runs, then generated assets are
  written to repository artifacts.
- Given a corpus-based build completes, when the sync step runs, then processed
  indexes are refreshed.
- Given the LLM proposes a draft shape, when the reviewer changes it, then the
  final version reflects the reviewer-approved structure.

## Story 6: Preview A Change Set

As a business analyst, I want to preview my DSL changes so that I can review
the impact before applying them.

Acceptance criteria:

- Given a draft DSL document, when preview is selected, then the system shows
  the parsed AST and the compiled asset changes.
- Given the preview reveals a delete or ownership conflict, when the user
  reviews it, then the issue is clearly displayed.

## Story 7: Delete A Draft Asset

As a platform engineer, I want to delete a draft asset so that incomplete work
does not pollute the governed repository.

Acceptance criteria:

- Given a draft or rejected asset, when delete is executed, then the asset is
  removed from the repository model and projections are updated.
- Given an approved asset, when delete is attempted, then the system requires
  explicit confirmation or blocks the action according to policy.
- Given an approved asset has dependent relations, when delete is attempted,
  then the system shows the impact on related assets and projections.

## Story 8: Browse The Asset Dictionary In VS Code

As a business analyst, I want to browse the asset dictionary in VS Code so that
I can discover what already exists before creating new assets.

Acceptance criteria:

- Given the extension is connected to the local authoring API, when the user
  opens the tree view, then the dictionary is grouped by KB and asset type.
- Given an asset is selected, when the user opens details, then the editor shows
  the asset metadata and relationships.

## Story 9: Validate Before Apply

As a compliance reviewer, I want every DSL document to validate before apply
so that invalid assets never reach the governed repository.

Acceptance criteria:

- Given a DSL document, when validation is run, then ownership, naming, and
  relation rules are checked.
- Given validation fails, when the user applies the document, then the action
  is blocked with actionable diagnostics.
- Given the document changes an approved asset, when validation runs, then the
  system shows version impact and whether a new version will be created.

## Story 10: Regenerate From Corpus

As a knowledge engineer, I want to regenerate assets from the full corpus so
that the platform can rebuild knowledge from source material when needed.

Acceptance criteria:

- Given a corpus regeneration command, when it runs, then extraction
  instructions, parsing, validation, repository write, and sync are executed in
  order.
- Given the regenerated output differs from the current repository state, when
  the process finishes, then the diff is visible for review.
- Given relations change across versions, when regeneration completes, then the
  impacted references are visible before the changes become canonical.
