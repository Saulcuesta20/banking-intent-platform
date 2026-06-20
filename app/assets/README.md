# Governed Assets

`app/assets` is the source-controlled home for governed Enterprise AI assets.

- `catalog/modules/`: reviewed AssetSet YAML definitions and immutable versions.
- `staging/ingest-runs/`: candidate assets generated from corpus ingestion before human review.

The Unified Catalog indexes these YAML assets and tracks lifecycle state. Specialized KBs
such as graph, vector, document, relational, and repository stores are updated only when
an AssetSet is deployed.
