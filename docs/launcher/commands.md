# Launcher And Platform Commands

## Purpose

This document defines the preferred command vocabulary for operating the launcher and its supporting services.

## Command Vocabulary

Use these commands instead of legacy Makefile targets in launcher-facing documentation:

- `launcher` for the launcher engine and launcher-related operations
- `ask` for runtime question answering
- `ingest` for corpus ingestion and KB loading
- `database` for database container operations
- `kb` for knowledge-base inspection and routing

## Launcher

Start the launcher engine:

```bash
launcher start engine
```

Show launcher module status:

```bash
launcher status
```

Start the shadcn launcher shell from `app/launcher/`:

```bash
npm run dev
```

This starts the React shell on `http://localhost:3000` and mounts the dynamic editor routes under the launcher origin.

The `launcher` command is the backend engine and launcher helper. The React + TypeScript shell now lives in `app/launcher/`, and its dynamic editor config lives in `app/launcher/pages/`.

You can also use:

```bash
launcher start ui
```

## Ask

Ask a question:

```bash
ask "Quiero refinanciar mi prestamo"
```

Ask with trace:

```bash
ask "Quiero refinanciar mi prestamo" --trace
```

## Ingest

Load a raw corpus into the knowledge bases:

```bash
ingest --raw data/raw/enterprise_dump_2026
```

Reload and clear existing generated assets:

```bash
ingest --raw data/raw/enterprise_dump_2026 --apply
```

## Database

Start the database containers:

```bash
database up
```

Check database containers:

```bash
database ps
```

Show database logs:

```bash
database logs neo4j
```

Stop the database containers:

```bash
database down
```

## KB

Inspect the knowledge base engines:

```bash
kb query --engines
```

Show a knowledge base view:

```bash
kb query --text "mora"
```
