# Business Model Graph Editor – Design & Tooling Conclusion

## 1. Context

- **Objetivo**: brindar a los analistas de negocio una vista gráfica editable de entidades y relaciones (ontología/business model) dentro del launcher sin romper el contrato JSON existente.
- **Stack launcher**: React 19 + TypeScript 6 (Vite), shadcn/ui, JSON Forms, Zod, TanStack Query; cada editor vive en `app/launcher/plugins/asset-editors/src/editors/<asset>-editor/`.
- **Usuarios**: analistas que refinan y validan el modelo generado por ingest.
- **Contrato actual**: `payload.entities[]`, `payload.relations[]`, metadata y (nuevo) `payload.layout` para posiciones.

## 2. Requerimientos compartidos

1. Tabs existentes (Structured, Raw, Relations, History) permanecen.
2. Props `{ value, onChange, readOnly }` y normalización vía `helpers.js`.
3. Validación con Zod + `validateBusinessModelDocument()`.
4. Sincronización completa entre formulario JSON Forms y vista gráfica.
5. Estados: loading, empty, success, error, readOnly.
6. Filtros por capa, rol, tipo de relación, búsqueda textual.
7. Persistencia layout: `payload.layout.nodes[entityId] = { x, y, collapsed? }`.
8. Datos iniciales provienen del `business_model_kb`/ingest.

## 3. Opciones evaluadas

| Criterio | JSON Forms (solo) | JSON Forms + **tldraw** | JSON Forms + diagrams.net (JGraph) | JSON Forms + React Flow |
| --- | --- | --- | --- | --- |
| Enfoque gráfico | Bajo | **Alto** | Medio | Alto |
| Esfuerzo integración | N/A | **Medio (npm React)** | Alto (iframe/mensajería) | Medio |
| Persistencia JSON | Nativa | **Nativa (shapes/bindings)** | Conversión XML/JSON | Nativa |
| Offline/self-host | Sí | **Sí** | Complejo sin SaaS | Sí |
| UX analistas | Limitado | **Muy alto (whiteboard)** | UI recargada | Alto pero más técnico |
| Colaboración futura | N/A | API lista | Depende de SaaS | Requiere implementación |
| Riesgos | No cumple requisito | **Bundle ~450 KB (solución: lazy load)** | Theming/state difícil | Layout adicional |

## 4. Decisión

- **Opción preferida**: JSON Forms + tldraw (Opción B). Equilibra UX, control en React, persistencia JSON y facilidad de incrustación.
- **Alternativa documentada**: JSON Forms + React Flow (Opción D) para comparar si se requiere un grafo más direccional.

## 5. Prototipos propuestos

### 5.1 Prototipo A – tldraw

**Layout**: panel dividido (Formulario 60% / Canvas 40%). En móviles se ofrecen tabs.

**Componentes**:
- `GraphToolbar`: +Entidad, +Relación, Filtros, Auto-layout, Fit View.
- `GraphPalette`: chips por capa.
- `LazyTldrawCanvas`: shapes personalizadas por layer, bindings para relaciones.
- `GraphDetailsDrawer`: edición rápida + botón “Ver en formulario”.
- `EmptyStateOverlay`, `GraphAlertBanner`.

**Flujo**:
1. `toGraphDocument(value.payload)` crea shapes/bindings.
2. Ediciones en tldraw → `fromGraphDocument()` → `normalizeBusinessModelDocument()` → `onChange`.
3. Ediciones en JSON Forms actualizan grafo gracias a `payload.layout`.

**Persistencia**: `payload.layout.nodes` guarda coordenadas; se añade opcional `collapsed`.

**Validación**: se extiende Zod con objeto `layout`; se asegura que relaciones apunten a entidades válidas y que los tipos concuerden con el contrato.

### 5.2 Prototipo B – React Flow

**Layout**: Formulario 55% / Canvas 45% con inspector lateral.

**Componentes**:
- `ReactFlowCanvas` (grid, minimap, controls).
- `CustomNode` (badge layer/role).
- `RelationEdge` (label con tipo).
- `SideInspector` para nodo/relación.
- `FilterPanel`, `EmptyState`.

**Flujo**:
- `entities` → `nodes`, `relations` → `edges`.
- `onNodesChange`/`onEdgesChange` proyectan de vuelta al payload.
- Auto-layout con `dagre`/`elkjs` opcional.

**Persistencia**: `payload.layout.nodes[entityId] = { x, y }` mapea directo a `node.position`.

**Validación**: idéntica, con ayuda de `isValidConnection` para prevenir edges inválidos.

## 6. HTML mockups

- `docs/launcher/designs/prototype-tldraw.html` (Opción B).
- `docs/launcher/designs/prototype-reactflow.html` (Opción D).

Cada archivo contiene un mock visual (HTML/CSS) que se puede abrir en navegador para revisar la propuesta.

## 7. Próximos pasos

1. Revisar y aprobar este diseño.
2. Implementar prototipo tldraw dentro del editor `business-model` (con adaptadores, toolbar y validaciones).
3. Opcional: implementar prototipo React Flow en rama separada para comparación.
4. Ejecutar pruebas obligatorias (`node --test validators.test.js`, `npm --prefix app/launcher run lint`, `npm --prefix app/launcher run build`) y actualizar `docs/launcher/implementation-tracker.md`.
