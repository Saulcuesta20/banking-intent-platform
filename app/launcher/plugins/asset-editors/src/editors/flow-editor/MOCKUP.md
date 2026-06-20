# Flow Editor — Visual Mockup

## 4-Tab Layout

```
┌──────────────────────────────────────────────────────────────────┐
│ Flow: transfer_funds                            [Validate] [Save]│
├──────────────────────────────────────────────────────────────────┤
│ [Structured Editor] [Raw Source] [Relations] [History]           │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  STRUCTURED EDITOR TAB                                           │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ JSON Forms: Flow definition fields                          │ │
│  │   - flow_id (text)                                          │ │
│  │   - name (text)                                             │ │
│  │   - description (textarea)                                  │ │
│  │   - version (number)                                        │ │
│  │   - tags (array of text)                                    │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌──────────────────────┐  ┌──────────────────────────────────┐ │
│  │ User Tasks (3 tasks) │  │ Edit user task                   │ │
│  │ ┌──────────────────┐ │  │                                  │ │
│  │ │ user_task.1      │ │  │ Task Identity                    │ │
│  │ │ select_account   │ │  │ ┌──────┐ ┌──────┐ ┌────┐ ┌────┐│ │
│  │ │ in_progress  [E] │ │  │ │UT ID │ │ Task │ │Type│ │Name││ │
│  │ └──────────────────┘ │  │ └──────┘ └──────┘ └────┘ └────┘│ │
│  │ ┌──────────────────┐ │  │ ┌──────────────────────────────┐│ │
│  │ │ user_task.2      │ │  │ │ Description                  ││ │
│  │ │ confirm_transfer │ │  │ └──────────────────────────────┘│ │
│  │ │ not_started  [E] │ │  ├──────────────────────────────────┤ │
│  │ └──────────────────┘ │  │ Lifecycle and Binding            │ │
│  │ ┌──────────────────┐ │  │ ┌──────┐ ┌──────┐ ┌──────────┐ │ │
│  │ │ user_task.3      │ │  │ │not_st│ │in_pr │ │completed │ │ │
│  │ │ review_transfer  │ │  │ └──────┘ └──────┘ └──────────┘ │ │
│  │ │ completed    [E] │ │  ├──────────────────────────────────┤ │
│  │ └──────────────────┘ │  │ User Actions        [+ Add]     │ │
│  │        [+ Add]       │  │ ┌─ Action ID ──┬─ type ─┬─────┐│ │
│  └──────────────────────┘  │ │ front_btn    │ front  │ form ││ │
│                            │ ├──────────────┴────────┴─────┤│ │
│                            │ │ Label: Show Account Picker   ││ │
│                            │ │ Desc:  Opens account form... ││ │
│                            │ │ Tool IDs: account_lookup     ││ │
│                            │ │ [completed]          [Remove] ││ │
│                            │ └──────────────────────────────┘│ │
│                            ├──────────────────────────────────┤ │
│                            │ Tools                 [+ Add]   │ │
│                            │ ┌─ Tool ID ──┬─ type ──┬───────┐│ │
│                            │ │ account_   │backend  │lookup ││ │
│                            │ ├────────────┴─────────┴───────┤│ │
│                            │ │ Label: Account Lookup Tool    ││ │
│                            │ │ [backend_tool]       [Remove] ││ │
│                            │ └──────────────────────────────┘│ │
│                            └──────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

## Component Hierarchy

```
FlowCanvasView (exported as editor)
├── Header bar (flow metadata + Validate/Save buttons)
├── Tab bar (Structured Editor | Raw Source | Relations | History)
└── Tab content:
    ├── StructuredEditorTab
    │   ├── JSON Forms (flow definition fields)
    │   └── Split view
    │       ├── FlowTaskList (left sidebar)
    │       │   └── FlowTaskSummaryCard[] + Add button
    │       └── FlowTaskModal (right panel)
    │           ├── FlowTaskIdentitySection
    │           ├── FlowTaskLifecycleSection
    │           ├── FlowTaskActionsSection
    │           │   └── FlowTaskActionCard[]
    │           └── FlowTaskToolsSection
    │               └── FlowTaskToolCard[]
    ├── RawSourceTab (JSON textarea)
    ├── RelationsTab (asset relationships)
    └── HistoryTab (version history)
```

## Data Flow

```
AssetDocument
  ↓
FlowCanvasView receives { value, onChange, readOnly }
  ↓
normalizeFlowDefinition(value.payload)
  ↓
JSON Forms renders flow-level fields
User Tasks rendered via FlowTaskList + FlowTaskModal
  ↓
onChange(updatedAssetDocument)
```

## Validation

- Flow-level: Zod schema (flow_id, name required)
- Task-level: validateTaskDraft() checks action bindings, tool references
- Visual errors shown inline in lifecycle section
