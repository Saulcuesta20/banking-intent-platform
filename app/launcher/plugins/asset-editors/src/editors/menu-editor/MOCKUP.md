# Menu Editor - Visual Mockup

## Layout Structure

```
┌─────────────────────────────────────────────────────────────────────┐
│ [Structured Editor] [Raw Source] [Relations] [History]        ●valid│
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Menu Definition                                              │   │
│  │ ┌──────────────────────────┐ ┌──────────────────────────┐   │   │
│  │ │ Menu ID                  │ │ Label                    │   │   │
│  │ │ loan-create              │ │ Crear prestamo           │   │   │
│  │ └──────────────────────────┘ └──────────────────────────┘   │   │
│  │ ┌──────────────────────────┐ ┌──────────────────────────┐   │   │
│  │ │ Path                     │ │ Module ID                │   │   │
│  │ │ /lending/loan/loan-create│ │ loan                     │   │   │
│  │ └──────────────────────────┘ └──────────────────────────┘   │   │
│  │ ┌─────────────────────────────────────────────────────────┐ │   │
│  │ │ Domain ID                                               │ │   │
│  │ │ lending                                                 │ │   │
│  │ └─────────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Relations Tab

```
┌─────────────────────────────────────────────────────────────────────┐
│ Relations                                                           │
│ Associated module and domain links.                                 │
│                                                                     │
│  ┌──────────┐                                                       │
│  │belongs_to│  module.loan                                          │
│  │_module   │                                                       │
│  └──────────┘                                                       │
│                                                                     │
│  Module: loan  ·  Domain: lending                                   │
└─────────────────────────────────────────────────────────────────────┘
```

## GridLayout Structure

```json
{
  "type": "GridLayout",
  "elements": [
    {
      "type": "Group",
      "label": "Menu Definition",
      "elements": [
        {
          "type": "GridLayout",
          "columns": 2,
          "elements": [
            { "type": "Control", "scope": "#/properties/id" },
            { "type": "Control", "scope": "#/properties/label" }
          ]
        },
        {
          "type": "GridLayout",
          "columns": 2,
          "elements": [
            { "type": "Control", "scope": "#/properties/path" },
            { "type": "Control", "scope": "#/properties/module_id" }
          ]
        },
        {
          "type": "GridLayout",
          "columns": 1,
          "elements": [
            { "type": "Control", "scope": "#/properties/domain_id" }
          ]
        }
      ]
    }
  ]
}
```

## Tab Flow

1. **Structured Editor** → JSON Forms with GridLayout (2-2-1 columns)
2. **Raw Source** → JSON textarea editor
3. **Relations** → Module and domain relationship display
4. **History** → Lifecycle snapshot and validation status
