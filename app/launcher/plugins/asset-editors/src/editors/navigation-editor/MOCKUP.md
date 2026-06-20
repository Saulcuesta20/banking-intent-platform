# Navigation Editor - Visual Mockup

## Layout Structure

```
┌─────────────────────────────────────────────────────────────────────┐
│ [Structured Editor] [Raw Source] [History]                    ●valid│
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Navigation Definition                                       │   │
│  │ ┌─────────────────┐ ┌─────────────────┐ ┌───────────────┐  │   │
│  │ │ Navigation ID   │ │ Navigation Name │ │ Domain        │  │   │
│  │ └─────────────────┘ └─────────────────┘ └───────────────┘  │   │
│  │ ┌─────────────────┐ ┌─────────────────┐ ┌───────────────┐  │   │
│  │ │ Module          │ │                 │ │               │  │   │
│  │ └─────────────────┘ └─────────────────┘ └───────────────┘  │   │
│  │ ┌─────────────────────────────────────────────────────────┐ │   │
│  │ │ Description                                             │ │   │
│  │ └─────────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Navigation Items                                            │   │
│  │ ┌─────────────────────────────────────────────────────────┐ │   │
│  │ │ + Add Item                                              │ │   │
│  │ ├─────────────────────────────────────────────────────────┤ │   │
│  │ │ ID          │ Label       │ Type      │ Route           │ │   │
│  │ │ ─────────────────────────────────────────────────────── │ │   │
│  │ │ nav_1       │ Dashboard   │ link      │ /dashboard      │ │   │
│  │ │ nav_2       │ Loans       │ menu      │                 │ │   │
│  │ │   └─child_1 │ Create Loan │ link      │ /loans/create   │ │   │
│  │ └─────────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## GridLayout Structure

```json
{
  "type": "GridLayout",
  "elements": [
    {
      "type": "GridLayout",
      "columns": 3,
      "elements": [
        { "type": "Control", "scope": "#/properties/navigation_id" },
        { "type": "Control", "scope": "#/properties/navigation_name" },
        { "type": "Control", "scope": "#/properties/domain" }
      ]
    },
    {
      "type": "GridLayout",
      "columns": 3,
      "elements": [
        { "type": "Control", "scope": "#/properties/module" },
        { "type": "Control", "scope": "#/properties/description" },
        { "type": "Control", "scope": "#/properties/metadata" }
      ]
    },
    { "type": "Control", "scope": "#/properties/items" }
  ]
}
```

## Tab Flow

1. **Structured Editor** → JSON Forms with GridLayout
2. **Raw Source** → JSON textarea editor
3. **History** → Lifecycle snapshot and validation status
