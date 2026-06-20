# Launcher Asset Editor Integration Plan

## Status

This migration is now complete for the launcher runtime architecture.

## Final Direction

Asset editing is launcher-native:

- React/shadcn owns the shell
- JSON Forms owns the structured flow editor surface
- Zod validates local editor state
- FastAPI validates and versions assets
- Unified Catalog remains the source of truth

## Current Reference Editor

The flow editor package lives at:

```text
app/launcher/plugins/asset-editors/src/editors/flow-editor/
```

## Removed During Migration

- standalone Lowdefy editor runtime
- launcher proxying to port `3002`
- generated Lowdefy editor pages
- `lowdefyPage`, `lowdefy_page`, and `lowdefy_url` launcher metadata
- Lowdefy block-wrapper package files used only by the old runtime

## Next Editor Work

Future asset editors should follow the same pattern as the flow editor:

```text
asset-specific package
-> JSON Schema
-> JSON Forms
-> Zod
-> FastAPI contract validation
```
