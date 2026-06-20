# Unified Catalog And AssetSet Roadmap

## Decisions

- `AssetSet` is the only term used for the versioned deployment bundle.
- An AssetSet is the atomic unit of validation, deployment, activation, and rollback.
- Domain and module are catalog metadata used for classification and launcher navigation.
- Each AssetSet normally contains one primary asset type.
- Git/YAML is the authoring and transport representation.
- Unified Catalog is the launcher runtime source of truth.
- Neo4j and the other KBs are projections for retrieval, reasoning, lineage, and execution.
- Human review is required before activation.
- Flow/user-task/form binding is phase two.

## Current Gap

| Area | Current implementation | Target | Status |
|---|---|---|---|
| Launcher registry | Reads launcher assets from Neo4j | Reads active assets from Unified Catalog | Pending |
| Asset authoring | JSON domain/module/process/form folders | Versioned AssetSet YAML folders | Pending |
| AssetSet meaning | Generated transaction bundle | Explicit deployment unit | Must change |
| Catalog storage | Assets and relationships | Versions, reviews, deployments, environments, active releases | Partial |
| Lifecycle | Generic asset status | Governed review and deployment state machine | Partial |
| Human review | Ingestion review artifacts exist | Catalog-backed review decisions and audit | Partial |
| KB publication | Ingestion writes projections | Staging and active projections governed by lifecycle | Partial |
| Dynamic editor generation | Reads repository JSON forms | Reads active form definitions from Unified Catalog | Pending |
| Flow/form binding | Provisional direct fields | Explicit user-task binding asset | Phase two |

## Phase One: Catalog And Launcher

### 1. Canonical Contracts

- [x] Define the `AssetSet` YAML schema.
- [x] Define common asset metadata: id, type, version, domain, module, status, owner, tags, and source.
- [x] Define immutable asset-version identifiers.
- [x] Define checksum and Git commit metadata.
- [x] Define allowed lifecycle transitions.
- [x] Update the asset registry description for `asset_set`.
- [ ] Remove the legacy transaction-scoped AssetSet generator from the ingestion pipeline.

### 2. Unified Catalog Persistence

- [x] Add AssetSet records and AssetSet versions.
- [x] Add membership records linking AssetSets to exact asset versions.
- [x] Add review requests, review decisions, comments, reviewer, and timestamps.
- [x] Add deployment records by environment.
- [x] Add an active AssetSet version pointer per environment.
- [x] Preserve deployment and rollback history.
- [x] Reject content changes to an existing immutable version.
- [x] Add catalog indexes for domain, module, type, status, and environment.

### 3. Lifecycle And Human Review

- [x] Implement `draft -> ready_for_review`.
- [x] Implement `ready_for_review -> in_review`.
- [x] Implement `in_review -> validated | rejected`.
- [x] Implement `validated -> active` only through deployment.
- [x] Implement `active -> deprecated -> retired`.
- [x] Require a reviewer identity and comments for rejection or requested changes.
- [x] Prevent AssetSet ingestion from assigning `validated` or `active`.
- [x] Record every transition in lifecycle history.

### 4. AssetSet Tooling

- [x] Implement AssetSet discovery under `app/launcher/modules/*/assetsets/`.
- [x] Implement schema and reference validation.
- [x] Implement content checksum calculation.
- [x] Implement CLI `status`, `plan`, `diff`, `transition`, `deploy`, and `rollback`.
- [x] Implement catalog-to-YAML pull/export for arbitrary deployed versions.
- [x] Implement repository JSON-to-AssetSet YAML export.
- [x] Make load and deployment idempotent.
- [x] Make activation atomic after required projections succeed.

### 5. Ingestion Integration

- [ ] Group normalized assets into configured AssetSets by primary asset type.
- [ ] Upsert asset and AssetSet versions into Unified Catalog.
- [ ] Mark new or changed records `ready_for_review` after technical validation.
- [ ] Publish review-only KB projections.
- [ ] Publish active KB projections only after validated deployment.
- [ ] Remove stale projections when an AssetSet version is replaced or retired.
- [ ] Preserve source lineage from ingestion through deployment.

### 6. Launcher Catalog Runtime

- [x] Replace `LauncherGraphPublisher` with an AssetSet catalog deployment service.
- [x] Change `LauncherRuntimeService` to query Unified Catalog.
- [x] Remove domain, module, menu, form, and launcher navigation dependency on Neo4j.
- [x] Add catalog APIs for metadata, AssetSets, assets, review, deployment, and rollback.
- [x] Return only active assets for the selected environment to launcher runtime APIs.
- [x] Keep Ask flow resolution backed by the governed KB projection.
- [x] Resolve Ask assets through the governed catalog search repository.
- [x] Add lifecycle and AssetSet version details to the right context panel.

### 7. Asset Governance Workspace

- [x] Add an `Assets` option to the launcher sidebar.
- [x] Build a declarative asset explorer and embed it in the center workspace.
- [x] Support tree, route, and editor views grouped by knowledge-base projection.
- [x] Filter by asset name, asset type, knowledge base, lifecycle status, and tags.
- [x] Display expandable AssetSet and projection nodes.
- [x] Display canonical version, AssetSet, checksum, lifecycle status, and projection status.
- [x] Add review actions: start review, validate, reject, and request changes.
- [x] Require reviewer comments for rejection and requested changes.
- [x] Display lifecycle and deployment history.
- [x] Allow deployment only for a validated AssetSet version.
- [x] Show target environment, current state, and candidate version.
- [x] Show projection results for graph, vector, document, repository, and relational stores.
- [x] Keep all mutations in catalog/review/deployment APIs.

### 8. Launcher Authoring Migration

- [ ] Create English-only YAML folders and identifiers.
- [ ] Migrate current domain and module metadata.
- [ ] Migrate flow definitions into flow AssetSets.
- [ ] Migrate process definitions into process AssetSets.
- [ ] Migrate rules into rule AssetSets.
- [ ] Migrate forms into form AssetSets without final bindings.
- [ ] Migrate menus and submenus into menu AssetSets.
- [ ] Remove obsolete JSON publication after parity tests pass.

### 9. Testing And Acceptance

- [ ] Test every lifecycle transition and invalid transition.
- [ ] Test review authorization and audit history.
- [ ] Test idempotent deployment and rollback.
- [ ] Test that partial deployment never changes the active version.
- [ ] Test staging versus active KB visibility.
- [ ] Test launcher domain/module/menu discovery from Unified Catalog.
- [ ] Test that repository YAML changes do not affect runtime before deployment.
- [ ] Test Ask selection against active graph projections.
- [ ] Run visual launcher tests at desktop and mobile sizes.

## Phase Two: User Task And Form Binding

- [ ] Define renderer-neutral `FormDefinition`.
- [ ] Define `TaskFormBinding` as a catalog asset type.
- [ ] Bind process id and user-task node id to a form id and version policy.
- [ ] Define input mapping from process context to form state.
- [ ] Define output mapping from submitted form data to process context.
- [ ] Define validation, conditional selection, resume, and migration behavior.
- [ ] Generate dynamic editor pages from active catalog form definitions.
- [ ] Resolve the active user task through the orchestrator.
- [ ] Resolve its binding through Unified Catalog.
- [ ] Render and submit through the editor runtime without launcher hardcoding.
- [ ] Support multiple forms across a process lifecycle.

## Phase One Acceptance Result

Phase one is complete when:

1. A developer commits an AssetSet YAML change.
2. The AssetSet validates and is stored as a new catalog version.
3. A human reviews and validates it.
4. Deployment activates the complete AssetSet version atomically.
5. Required KB projections are updated.
6. The launcher displays the change by querying Unified Catalog.
7. Rollback restores the previous active version.
8. No launcher menu, module, or asset is loaded directly from repository files or Neo4j.
