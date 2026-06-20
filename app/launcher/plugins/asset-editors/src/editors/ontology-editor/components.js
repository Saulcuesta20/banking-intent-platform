import React, { useEffect, useMemo, useRef, useState } from 'react'
import { JsonForms } from '@jsonforms/react'
import { vanillaCells, vanillaRenderers } from '@jsonforms/vanilla-renderers'
import { Tldraw, createTLStore, toRichText } from 'tldraw'
import 'tldraw/tldraw.css'

import definitionSchema from './ontology-editor.schema.json'
import definitionUiSchema from './ontology-editor.ui-schema.json'
import {
  BUSINESS_LAYERS,
  STRUCTURAL_LAYERS,
  SEMANTIC_SPACES,
  RELATION_TYPES,
  computeDefaultPosition,
  createDefaultEntity,
  createDefaultRelation,
  normalizeBusinessModelDocument,
  normalizeBusinessModelPayload,
  validateBusinessModelDocument,
  knowledgeBaseFromDocument,
} from './helpers.js'

const h = React.createElement
const API_BASE_URL = import.meta.env.VITE_LAUNCHER_API_URL ?? 'http://127.0.0.1:8030'

const colors = {
  ink: '#10213d',
  muted: '#667892',
  line: '#d7dfeb',
  panel: '#ffffff',
  canvas: '#f4f7fb',
  blue: '#1463ff',
  blueSoft: '#eaf1ff',
  green: '#147d64',
  greenSoft: '#e8f6f1',
  red: '#b42318',
  redSoft: '#fff0ee',
  amber: '#9a6700',
  amberSoft: '#fff7df',
  purple: '#7f56d9',
}

const baseFont = 'Inter, ui-sans-serif, system-ui, sans-serif'
const NODE_WIDTH = 220
const NODE_HEIGHT = 110
const MAX_OVERVIEW_RELATIONS = 90

function buttonStyle(primary = false) {
  return {
    border: `1px solid ${primary ? colors.blue : colors.line}`,
    background: primary ? colors.blue : colors.panel,
    color: primary ? '#fff' : colors.ink,
    borderRadius: 8,
    padding: '8px 14px',
    fontWeight: 700,
    cursor: primary ? 'pointer' : 'pointer',
    fontFamily: baseFont,
  }
}

function inputStyle() {
  return {
    width: '100%',
    border: `1px solid ${colors.line}`,
    borderRadius: 6,
    padding: '8px 10px',
    fontFamily: baseFont,
    fontSize: 13,
  }
}

function labelStyle() {
  return {
    display: 'block',
    fontSize: 12,
    fontWeight: 600,
    color: colors.muted,
    marginBottom: 4,
  }
}

function clone(value) {
  return JSON.parse(JSON.stringify(value ?? {}))
}

function EditorFrame({ title, subtitle, children, actions }) {
  return h(
    'section',
    {
      style: {
        border: `1px solid ${colors.line}`,
        borderRadius: 12,
        background: colors.panel,
        overflow: 'hidden',
        fontFamily: baseFont,
      },
    },
    h(
      'header',
      {
        style: {
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 16,
          padding: '14px 16px',
          borderBottom: `1px solid ${colors.line}`,
        },
      },
      h('div', null, h('strong', { style: { color: colors.ink, fontSize: 15 } }, title), subtitle
        ? h('div', { style: { color: colors.muted, fontSize: 12, marginTop: 3 } }, subtitle)
        : null),
      actions,
    ),
    h('div', { style: { padding: 16 } }, children),
  )
}

function Pill({ tone = colors.blueSoft, textColor = colors.blue, label }) {
  return h(
    'span',
    {
      style: {
        display: 'inline-flex',
        alignItems: 'center',
        minHeight: 22,
        padding: '2px 8px',
        borderRadius: 999,
        background: tone,
        color: textColor,
        fontSize: 11,
        fontWeight: 800,
      },
    },
    label,
  )
}

function TabButton({ active, children, onClick }) {
  return h(
    'button',
    {
      type: 'button',
      onClick,
      style: {
        ...buttonStyle(active),
        background: active ? colors.blue : colors.panel,
      },
    },
    children,
  )
}

function BusinessModelJsonFormsView({ value, onChange, readOnly = false }) {
  const payload = clone(value?.payload)
  const data = useMemo(() => normalizeBusinessModelPayload(payload), [payload])
  return h(
    EditorFrame,
    {
      title: 'Business Model Definition',
      subtitle: 'JSON Forms surface for entities and relations.',
    },
    h(JsonForms, {
      data,
      schema: definitionSchema,
      uischema: definitionUiSchema,
      renderers: vanillaRenderers,
      cells: vanillaCells,
      readonly: readOnly,
      onChange: ({ data: nextData }) => {
        onChange(normalizeBusinessModelPayload(nextData))
      },
    }),
  )
}

const GRAPH_DEFAULT_FILTERS = {
  layer: 'all',
  assetType: 'all',
  representation: 'all',
  relationFamily: 'all',
  text: '',
  view: 'complete',
  quick: 'all',
}

function BusinessModelCanvasView({
  knowledgeBase,
  readOnly = false,
  focusAssetId,
  onAddEntity,
  onAddRelation,
  onRequestFormView,
  onSelectionChange,
}) {
  const store = useMemo(() => createTLStore(), [])
  const editorRef = useRef(null)
  const layoutRef = useRef({})
  const initialFitDoneRef = useRef(false)
  const lastSelectionKeyRef = useRef('')
  const [filters, setFilters] = useState(GRAPH_DEFAULT_FILTERS)
  const [fetchToken, setFetchToken] = useState(0)
  const [graphState, setGraphState] = useState({ entities: [], relations: [], loading: false, error: null })
  const [selectedEntityId, setSelectedEntityId] = useState(null)
  const [matrixMode, setMatrixMode] = useState(false)
  const [relationScope, setRelationScope] = useState('focus')

  useEffect(() => {
    let cancelled = false
    initialFitDoneRef.current = false
    async function loadGraph() {
      if (!knowledgeBase) {
        setGraphState({ entities: [], relations: [], loading: false, error: 'Selecciona una knowledge base.' })
        onSelectionChange?.(null)
        return
      }
      setGraphState((previous) => ({ ...previous, loading: true, error: null }))
      try {
        const response = await fetch(
          `${API_BASE_URL}/catalog/knowledge-bases/${encodeURIComponent(knowledgeBase)}/ontology?environment=dev`,
        )
        const contentType = response.headers.get('content-type') || ''
        const body = await response.text()
        if (!response.ok) {
          throw new Error(body || `HTTP ${response.status}`)
        }
        if (!contentType.includes('application/json')) {
          throw new Error('Respuesta no válida del backend. Verifica FastAPI en http://127.0.0.1:8030.')
        }
        const data = JSON.parse(body)
        if (cancelled) return
        const entities = Array.isArray(data.entities) ? data.entities : []
        layoutRef.current = ensureLayoutPositions(layoutRef.current, entities)
        setGraphState({
          entities,
          relations: Array.isArray(data.relations) ? data.relations : [],
          loading: false,
          error: null,
        })
      } catch (error) {
        if (!cancelled) {
          setGraphState({
            entities: [],
            relations: [],
            loading: false,
            error: error instanceof Error ? error.message : String(error),
          })
          onSelectionChange?.(null)
        }
      }
    }
    void loadGraph()
    return () => {
      cancelled = true
    }
  }, [knowledgeBase, fetchToken, onSelectionChange])

  useEffect(() => {
    if (graphState.entities.length && !selectedEntityId) {
      setSelectedEntityId(graphState.entities[0].asset_id)
    }
    if (!graphState.entities.length) {
      setSelectedEntityId(null)
    }
  }, [graphState.entities, selectedEntityId])

  const relationIndex = useMemo(() => buildRelationIndex(graphState.relations), [graphState.relations])
  const filteredEntities = useMemo(
    () => applyGraphFilters(graphState.entities, filters, relationIndex),
    [graphState.entities, filters, relationIndex],
  )
  const filteredRelations = useMemo(
    () =>
      filterVisibleRelations(
        graphState.relations,
        filteredEntities,
        relationScope === 'focus' ? selectedEntityId : null,
        filters.relationFamily,
      ),
    [graphState.relations, filteredEntities, relationScope, selectedEntityId, filters.relationFamily],
  )

  useEffect(() => {
    if (!editorRef.current || matrixMode) return
    renderOntologyGraph(
      editorRef.current,
      filteredEntities,
      filteredRelations,
      layoutRef.current,
      selectedEntityId || focusAssetId,
    )
    if (!initialFitDoneRef.current && filteredEntities.length) {
      initialFitDoneRef.current = true
      window.setTimeout(() => {
        try {
          editorRef.current?.zoomToFit({ animation: { duration: 220 } })
        } catch (error) {
          // ignore zoom errors while tldraw settles
        }
      }, 50)
    }
  }, [filteredEntities, filteredRelations, focusAssetId, matrixMode, selectedEntityId])

  const knowledgeBaseLabel = knowledgeBase || 'catalog'
  const selectedEntity = selectedEntityId
    ? graphState.entities.find((entity) => entity.asset_id === selectedEntityId)
    : null
  const selectedRelations = selectedEntity ? relationIndex[selectedEntity.asset_id] || [] : []
  const updateFilters = (changes) => setFilters((current) => ({ ...current, ...changes }))
  const handleSelectEntity = (assetId) => {
    setSelectedEntityId(assetId)
    setFilters((current) => ({ ...current, text: '' }))
    window.setTimeout(() => focusEntityInCanvas(editorRef.current, assetId, layoutRef.current), 80)
  }

  useEffect(() => {
    if (!onSelectionChange) return
    if (selectedEntity) {
      const selectionKey = `${selectedEntity.asset_id}:${selectedRelations.map((relation) => relation.id).join('|')}`
      if (lastSelectionKeyRef.current === selectionKey) return
      lastSelectionKeyRef.current = selectionKey
      onSelectionChange({
        entity: {
          asset_id: selectedEntity.asset_id,
          name: selectedEntity.name,
          structural_layer: selectedEntity.structural_layer || selectedEntity.layer,
          layer: selectedEntity.layer,
          role: selectedEntity.role,
          semantic_space: selectedEntity.semantic_space,
          subtype: selectedEntity.subtype,
          technical_type: selectedEntity.technical_type,
          description: selectedEntity.description,
          aliases: selectedEntity.aliases,
        },
        relations: selectedRelations.map((relation) => ({
          id: relation.id,
          relation_type: relation.relation_type,
          relation_family: relation.relation_family,
          direction: relation.direction,
          source_entity_id: relation.source_entity_id,
          source_name: relation.source_name,
          target_entity_id: relation.target_entity_id,
          target_name: relation.target_name,
        })),
      })
    } else {
      if (lastSelectionKeyRef.current === 'none') return
      lastSelectionKeyRef.current = 'none'
      onSelectionChange(null)
    }
  }, [onSelectionChange, selectedEntity, selectedRelations])

  const handleReload = () => setFetchToken((token) => token + 1)
  const handleFitView = () => {
    if (!editorRef.current) return
    try {
      editorRef.current.zoomToFit({ animation: { duration: 240 } })
    } catch (error) {
      // ignore zoom errors when graph is empty
    }
  }
  const handleZoomIn = () => {
    try {
      editorRef.current?.zoomIn(undefined, { animation: { duration: 140 } })
    } catch (error) {
      // ignore zoom errors while tldraw is mounting
    }
  }
  const handleZoomOut = () => {
    try {
      editorRef.current?.zoomOut(undefined, { animation: { duration: 140 } })
    } catch (error) {
      // ignore zoom errors while tldraw is mounting
    }
  }

  const toolbarButtons = [
    {
      label: '+ Entidad',
      primary: true,
      onClick: onAddEntity,
      disabled: readOnly || !onAddEntity,
    },
    {
      label: '+ Relación',
      onClick: onAddRelation,
      disabled: readOnly || !onAddRelation,
    },
    {
      label: relationScope === 'focus' ? 'Ver todas' : 'Enfoque',
      title: relationScope === 'focus' ? 'Mostrar todas las relaciones visibles' : 'Mostrar relaciones de la entidad seleccionada',
      onClick: () => setRelationScope((value) => (value === 'focus' ? 'all' : 'focus')),
    },
    {
      label: 'Exportar JSON',
      onClick: () => handleExportGraph(knowledgeBaseLabel, graphState),
    },
    {
      label: 'Recargar',
      onClick: handleReload,
    },
    {
      label: '−',
      title: 'Alejar',
      onClick: handleZoomOut,
    },
    {
      label: '+',
      title: 'Acercar',
      onClick: handleZoomIn,
    },
    {
      label: 'Ajustar vista',
      onClick: handleFitView,
    },
  ]

  return h(
    'div',
    {
      style: {
        border: `1px solid ${colors.line}`,
        borderRadius: 18,
        overflow: 'hidden',
        background: colors.canvas,
      },
    },
    h(
      'div',
      {
        style: {
          display: 'grid',
          gridTemplateColumns: '280px minmax(0, 1fr)',
          minHeight: 560,
        },
      },
      h(CanvasSidebar, {
        knowledgeBase: knowledgeBaseLabel,
        filters,
        onFiltersChange: updateFilters,
        entities: graphState.entities,
        relations: graphState.relations,
        visibleEntities: filteredEntities,
        selectedEntityId,
        onSelectEntity: handleSelectEntity,
      }),
      h(
        'section',
        {
          style: {
            display: 'flex',
            flexDirection: 'column',
            borderLeft: `1px solid ${colors.line}`,
            background: '#eef3ff',
          },
        },
        h(
          'div',
          {
            style: {
              position: 'relative',
              flex: 1,
              margin: 18,
              borderRadius: 28,
              border: `1px solid ${colors.line}`,
              background: '#eef3ff',
              overflow: 'hidden',
            },
          },
          h(
            'div',
            {
              style: {
                position: 'absolute',
                top: 18,
                left: 18,
                display: 'flex',
                gap: 8,
                zIndex: 2,
              },
            },
            toolbarButtons.map((button, index) =>
              h(
                'button',
                {
                  type: 'button',
                  key: `${button.label}-${index}`,
                  disabled: button.disabled,
                  onClick: button.onClick,
                  title: button.title || button.label,
                  style: graphToolbarButtonStyle(Boolean(button.primary)),
                },
                button.label,
              ),
            ),
          ),
          matrixMode
            ? h(
                'div',
                {
                  style: {
                    position: 'absolute',
                    inset: 0,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: 32,
                    textAlign: 'center',
                    color: colors.muted,
                    fontSize: 15,
                    background: 'rgba(250,252,255,0.9)',
                  },
                },
                'La vista matrix estará disponible pronto. Usa la vista canvas para editar.',
              )
            : graphState.error
              ? h(
                  'div',
                  {
                    style: {
                      position: 'absolute',
                      inset: 0,
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 12,
                      padding: 32,
                      color: colors.red,
                      background: colors.panel,
                      textAlign: 'center',
                    },
                  },
                  h('strong', null, 'No pudimos cargar el grafo'),
                  h('p', { style: { margin: 0, color: colors.muted } }, graphState.error),
                  h(
                    'button',
                    {
                      type: 'button',
                      style: graphToolbarButtonStyle(false),
                      onClick: handleReload,
                    },
                    'Reintentar',
                  ),
                )
              : h(
                  'div',
                  { style: { position: 'absolute', inset: 0 } },
                  h(Tldraw, {
                    store,
                    readOnly: true,
                    hideUi: true,
                    onMount: (editor) => {
                      editorRef.current = editor
                      renderOntologyGraph(editor, filteredEntities, filteredRelations, layoutRef.current, focusAssetId)
                    },
                  }),
                ),
          graphState.loading && !graphState.error
            ? h(
                'div',
                {
                  style: {
                    position: 'absolute',
                    top: 16,
                    right: 16,
                    background: '#fff',
                    borderRadius: 8,
                    padding: '6px 12px',
                    color: colors.muted,
                    boxShadow: '0 8px 24px rgba(15,33,61,0.08)',
                  },
                },
                'Cargando grafo…',
              )
            : null,
          !graphState.loading && !graphState.error && !matrixMode && !filteredEntities.length
            ? h(
                'div',
                {
                  style: {
                    position: 'absolute',
                    inset: 0,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: colors.muted,
                    fontSize: 14,
                    textAlign: 'center',
                    padding: 32,
                  },
                },
                'No hay entidades para mostrar con los filtros actuales.',
              )
            : null,
        ),
        h(GraphStatsStrip, {
          entities: graphState.entities.length,
          relations: graphState.relations.length,
        filteredEntities: filteredEntities.length,
        filteredRelations: filteredRelations.length,
        relationScope,
      }),
      ),
    ),
  )
}

function CanvasSidebar({
  knowledgeBase,
  filters,
  onFiltersChange,
  entities,
  relations,
  visibleEntities,
  selectedEntityId,
  onSelectEntity,
}) {
  const searchText = (filters.text || '').trim().toLowerCase()
  const searchResults = searchText ? searchEntities(entities, searchText) : []
  const featured = (searchText ? searchResults : visibleEntities.length ? visibleEntities : entities).slice(0, 12)
  const availableLayers = getAvailableLayers(entities)
  const availableAssetTypes = [...new Set(entities.map((e) => e.asset_type || 'entity'))].sort()
  const availableRelationFamilies = getAvailableRelationFamilies(relations)

  return h(
    'aside',
    {
      style: {
        background: colors.panel,
        borderRight: `1px solid ${colors.line}`,
        padding: 20,
        display: 'grid',
        gap: 16,
        alignContent: 'start',
      },
    },
    h('div', null,
      h('h2', { style: { margin: 0, fontSize: 18 } }, knowledgeBase),
      h('p', { style: { margin: '4px 0 0', color: colors.muted, fontSize: 13 } }, 'Ontología empresarial'),
    ),
    h('div', null,
      h('label', { style: labelStyle() }, 'Tipo de activo'),
      h(
        'div',
        { style: { display: 'flex', flexWrap: 'wrap', gap: 6 } },
        h(
          'button',
          {
            type: 'button',
            onClick: () => onFiltersChange({ assetType: 'all' }),
            style: layerChipStyle(filters.assetType === 'all' || !filters.assetType),
          },
          'Todos',
        ),
        availableAssetTypes.map((at) =>
          h(
            'button',
            {
              type: 'button',
              key: at,
              onClick: () => onFiltersChange({ assetType: at }),
              style: layerChipStyle(filters.assetType === at),
            },
            at === 'entity' ? 'entidad' : at === 'tool' ? 'herramienta' : at === 'user_task' ? 'tarea' : at,
          ),
        ),
      ),
    ),
    h('div', null,
      h('label', { style: labelStyle() }, 'Representación'),
      h(
        'div',
        { style: { display: 'flex', flexWrap: 'wrap', gap: 6 } },
        [
          ['all', 'Todas'],
          ['business', 'Negocio'],
          ['technical', 'Técnica'],
        ].map(([value, label]) =>
          h(
            'button',
            {
              type: 'button',
              key: value,
              onClick: () => onFiltersChange({ representation: value }),
              style: layerChipStyle((filters.representation || 'all') === value),
            },
            label,
          ),
        ),
      ),
    ),
    h('div', null,
      h('label', { style: labelStyle() }, 'Familia de relación'),
      h(
        'div',
        { style: { display: 'flex', flexWrap: 'wrap', gap: 6 } },
        h(
          'button',
          {
            type: 'button',
            onClick: () => onFiltersChange({ relationFamily: 'all' }),
            style: layerChipStyle((filters.relationFamily || 'all') === 'all'),
          },
          'Todas',
        ),
        availableRelationFamilies.map((family) =>
          h(
            'button',
            {
              type: 'button',
              key: family,
              onClick: () => onFiltersChange({ relationFamily: family }),
              style: layerChipStyle(filters.relationFamily === family),
            },
            relationFamilyLabel(family),
          ),
        ),
      ),
    ),
    h('div', null,
      h('label', { style: labelStyle() }, 'Structural Layer'),
      h(
        'div',
        { style: { display: 'flex', flexWrap: 'wrap', gap: 6 } },
        h(
          'button',
          {
            type: 'button',
            onClick: () => onFiltersChange({ layer: 'all' }),
            style: layerChipStyle(filters.layer === 'all'),
          },
          'Todas',
        ),
        availableLayers.map((layer) =>
          h(
            'button',
            {
              type: 'button',
              key: layer,
              onClick: () => onFiltersChange({ layer }),
              style: layerChipStyle(filters.layer === layer),
            },
            layer === 'unclassified' ? 'sin capa' : layer,
          ),
        ),
      ),
    ),
    h('div', null,
      h(
        'div',
        { style: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 } },
        h('label', { style: { ...labelStyle(), marginBottom: 0 } }, 'Buscar entidad'),
        searchText
          ? h(
              'button',
              {
                type: 'button',
                onClick: () => onFiltersChange({ text: '' }),
                style: textButtonStyle(),
              },
              'Limpiar',
            )
          : null,
      ),
      h('input', {
        placeholder: 'prestamo, cliente, cuenta...',
        value: filters.text,
        onChange: (event) => onFiltersChange({ text: event.target.value }),
        style: { ...inputStyle(), marginTop: 6 },
      }),
      searchText
        ? h(
            'p',
            { style: { margin: '6px 0 0', color: colors.muted, fontSize: 12 } },
            `${searchResults.length} coincidencia${searchResults.length === 1 ? '' : 's'}. Selecciona una para enfocar.`,
          )
        : null,
    ),
    h('div', null,
      h('label', { style: labelStyle() }, 'Entidades'),
      featured.length
        ? h(
            'div',
            { style: { display: 'flex', flexDirection: 'column', gap: 6 } },
            featured.map((entity) =>
              h(
                'button',
                {
                  key: entity.asset_id,
                  type: 'button',
                  onClick: () => onSelectEntity(entity.asset_id),
                  style: entityListButtonStyle(selectedEntityId === entity.asset_id),
                },
                entityListLabel(entity),
              ),
            ),
          )
        : h(
            'p',
            { style: { color: colors.muted, fontSize: 13, margin: 0 } },
            searchText ? 'No hay entidades con ese nombre.' : 'No hay entidades visibles.',
          ),
    ),
  )
}

function GraphStatsStrip({ entities, relations, filteredEntities, filteredRelations, relationScope }) {
  const items = [
    { label: 'Entidades', value: filteredEntities, total: entities },
    { label: 'Relaciones', value: filteredRelations, total: relations },
  ]
  return h(
    'div',
    {
      style: {
        display: 'flex',
        gap: 18,
        padding: '14px 20px',
        borderTop: `1px solid ${colors.line}`,
        background: 'rgba(255,255,255,0.85)',
        fontSize: 13,
        color: colors.muted,
      },
    },
    h(
      'span',
      {
        style: {
          border: `1px solid ${colors.line}`,
          borderRadius: 999,
          padding: '3px 8px',
          background: '#fff',
          color: colors.muted,
        },
      },
      relationScope === 'focus' ? 'Foco seleccionado' : 'Impacto completo',
    ),
    items.map((item) =>
      h(
        'div',
        { key: item.label },
        h('strong', { style: { color: colors.ink } }, item.value),
        ` ${item.label}`,
        item.value !== item.total
          ? h('span', { style: { marginLeft: 4, color: colors.muted } }, `(total ${item.total})`)
          : null,
      ),
    ),
  )
}

function applyGraphFilters(entities, filters, relationIndex) {
  if (!Array.isArray(entities)) return []
  const activeFilters = { ...GRAPH_DEFAULT_FILTERS, ...(filters || {}) }
  return entities.filter((entity) => {
    const entityLayer = (entity.structural_layer || entity.layer || 'unclassified').toLowerCase()
    const matchesLayer = activeFilters.layer === 'all' || entityLayer === activeFilters.layer
    if (!matchesLayer) return false
    const entityType = (entity.asset_type || 'entity').toLowerCase()
    const matchesAssetType = activeFilters.assetType === 'all' || entityType === activeFilters.assetType
    if (!matchesAssetType) return false
    const representation = activeFilters.representation || 'all'
    const technical = isTechnicalEntity(entity)
    if (representation === 'business' && technical) return false
    if (representation === 'technical' && !technical) return false
    if (!matchesQuickFilter(activeFilters.quick, relationIndex[entity.asset_id] || [])) {
      return false
    }
    return true
  })
}

function isTechnicalEntity(entity) {
  const layer = (entity.structural_layer || entity.layer || '').toLowerCase()
  return layer === 'business_resource' && Boolean((entity.technical_type || '').trim())
}

function entityListLabel(entity) {
  const layer = entity.structural_layer || entity.layer || 'sin capa'
  const subtype = entity.subtype ? `/${entity.subtype}` : ''
  const technical = entity.technical_type ? ` · ${entity.technical_type}` : ''
  return `${entity.name || entity.asset_id} [${layer}${subtype}${technical}]`
}

function entityNodeLabel(entity) {
  const layer = entity.structural_layer || entity.layer || 'sin capa'
  const subtype = entity.subtype ? `/${entity.subtype}` : ''
  const technical = entity.technical_type ? `\n${entity.technical_type}` : ''
  return `${entity.name || entity.asset_id}\n${layer}${subtype}${technical}`
}

function relationFamilyLabel(family) {
  const labels = {
    business_technical_mapping: 'Negocio-técnica',
    business_fact: 'Negocio',
    search_context: 'Espacio',
    classification: 'Clasificación',
    governance: 'Gobierno',
    unknown: 'Sin clasificar',
  }
  return labels[family] || family
}

function getAvailableRelationFamilies(relations) {
  const families = new Set()
  ;(relations || []).forEach((relation) => families.add(relation.relation_family || 'unknown'))
  return Array.from(families).sort()
}

function searchEntities(entities, text) {
  if (!text) return []
  return entities.filter((entity) =>
    (entity.name || '').toLowerCase().includes(text) ||
    (entity.description || '').toLowerCase().includes(text) ||
    (entity.asset_id || '').toLowerCase().includes(text),
  )
}

function getAvailableLayers(entities) {
  const layers = new Set()
  entities.forEach((entity) => layers.add((entity.structural_layer || entity.layer || 'unclassified').toLowerCase()))
  return Array.from(layers).sort((left, right) => {
    if (left === 'unclassified') return 1
    if (right === 'unclassified') return -1
    return STRUCTURAL_LAYERS.indexOf(left) - STRUCTURAL_LAYERS.indexOf(right)
  })
}

function ensureLayoutPositions(layout, entities) {
  const next = { ...(layout || {}) }
  entities.forEach((entity, index) => {
    if (!next[entity.asset_id]) {
      next[entity.asset_id] = computeDefaultPosition(index)
    }
  })
  return next
}

function renderOntologyGraph(editor, entities, relations, layout, focusAssetId) {
  if (!editor) return
  const existingIds = Array.from(editor.getCurrentPageShapeIds())
  if (existingIds.length) {
    editor.deleteShapes(existingIds)
  }
  const nodes = layout || {}
  const visibleEntityIds = new Set(entities.map((entity) => entity.asset_id))
  const graphPositions = {}
  entities.forEach((entity, index) => {
    const position = nodes[entity.asset_id] || computeDefaultPosition(index)
    graphPositions[entity.asset_id] = position
    const isFocused = focusAssetId && entity.asset_id === focusAssetId
    editor.createShape({
      id: safeShapeId('entity', entity.asset_id),
      type: 'geo',
      x: position.x,
      y: position.y,
      props: {
        w: NODE_WIDTH,
        h: NODE_HEIGHT,
        geo: 'rectangle',
        color: mapLayerToColor(entity.structural_layer || entity.layer),
        fill: isFocused ? 'pattern' : 'solid',
        dash: isFocused ? 'dashed' : 'draw',
        align: 'middle',
        verticalAlign: 'middle',
        font: 'sans',
        labelColor: 'black',
        richText: toRichText(entityNodeLabel(entity)),
      },
    })
  })

  const externalNodes = buildExternalRelationNodes(relations, visibleEntityIds, graphPositions)
  externalNodes.forEach((node) => {
    graphPositions[node.asset_id] = node.position
    editor.createShape({
      id: safeShapeId('external', node.asset_id),
      type: 'geo',
      x: node.position.x,
      y: node.position.y,
      props: {
        w: 210,
        h: 64,
        geo: 'ellipse',
        color: mapAssetTypeToColor(node.asset_type),
        fill: 'none',
        dash: 'dashed',
        size: 's',
        align: 'middle',
        verticalAlign: 'middle',
        font: 'sans',
        labelColor: 'black',
        richText: toRichText(`${compactLabel(node.name || node.asset_id)}\n${node.asset_type || 'asset'}`),
      },
    })
  })

  relations.forEach((relation, index) => {
    const source = graphPositions[relation.source_entity_id] || computeDefaultPosition(index)
    const target = graphPositions[relation.target_entity_id] || computeDefaultPosition(index + 1)
    const sourceShapeId = visibleEntityIds.has(relation.source_entity_id)
      ? safeShapeId('entity', relation.source_entity_id)
      : safeShapeId('external', relation.source_entity_id)
    const targetShapeId = visibleEntityIds.has(relation.target_entity_id)
      ? safeShapeId('entity', relation.target_entity_id)
      : safeShapeId('external', relation.target_entity_id)
    const arrowShapeId = safeShapeId('relation', `${index}-${relation.id}`)
    if (!editor.getShape(sourceShapeId) || !editor.getShape(targetShapeId)) return
    editor.createShape({
      id: arrowShapeId,
      type: 'arrow',
      x: source.x + NODE_WIDTH / 2,
      y: source.y + NODE_HEIGHT / 2,
      props: {
        start: { x: 0, y: 0 },
        end: { x: 0, y: 0 },
        color: 'grey',
        size: 's',
        fill: 'none',
        arrowheadStart: 'none',
        arrowheadEnd: 'arrow',
        labelColor: 'grey',
        richText: toRichText(''),
      },
    })
    editor.createBindings([
      {
        type: 'arrow',
        fromId: arrowShapeId,
        toId: sourceShapeId,
        props: {
          terminal: 'start',
          normalizedAnchor: { x: 0.5, y: 0.5 },
          isExact: false,
          isPrecise: false,
          snap: 'edge',
        },
      },
      {
        type: 'arrow',
        fromId: arrowShapeId,
        toId: targetShapeId,
        props: {
          terminal: 'end',
          normalizedAnchor: { x: 0.5, y: 0.5 },
          isExact: false,
          isPrecise: false,
          snap: 'edge',
        },
      },
    ])
  })
}

function focusEntityInCanvas(editor, assetId, layout) {
  if (!editor || !assetId) return
  try {
    const shapeId = safeShapeId('entity', assetId)
    if (!editor.getShape(shapeId)) return
    editor.select(shapeId)
    editor.zoomToFit({ animation: { duration: 220 } })
  } catch (error) {
    // ignore focus errors while tldraw is mounting
  }
}

function handleExportGraph(knowledgeBase, graphState) {
  const payload = JSON.stringify({ knowledge_base: knowledgeBase, ...graphState }, null, 2)
  const blob = new Blob([payload], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${knowledgeBase}-ontology.json`
  link.click()
  URL.revokeObjectURL(url)
}

function layerChipStyle(active) {
  return {
    border: `1px solid ${active ? colors.blue : colors.line}`,
    background: active ? colors.blueSoft : colors.panel,
    color: active ? colors.blue : colors.muted,
    borderRadius: 999,
    padding: '6px 10px',
    fontSize: 11,
    cursor: 'pointer',
  }
}

function quickChipStyle(active) {
  return {
    border: `1px solid ${active ? colors.green : colors.line}`,
    background: active ? colors.greenSoft : colors.panel,
    color: active ? colors.green : colors.muted,
    borderRadius: 999,
    padding: '6px 10px',
    fontSize: 11,
    cursor: 'pointer',
  }
}

function entityListButtonStyle(active) {
  return {
    border: `1px solid ${active ? colors.purple : colors.line}`,
    background: active ? colors.purple : colors.panel,
    color: active ? '#fff' : colors.ink,
    borderRadius: 8,
    padding: '6px 10px',
    textAlign: 'left',
    fontSize: 13,
    cursor: 'pointer',
  }
}

function textButtonStyle() {
  return {
    border: 0,
    background: 'transparent',
    color: colors.blue,
    padding: 0,
    fontSize: 12,
    fontWeight: 700,
    cursor: 'pointer',
  }
}

function graphToolbarButtonStyle(primary) {
  return {
    ...buttonStyle(primary),
    minHeight: 0,
    padding: '7px 14px',
    borderRadius: 10,
    background: primary ? colors.blue : 'rgba(255,255,255,0.92)',
    borderColor: primary ? colors.blue : 'rgba(15,33,61,0.12)',
    color: primary ? '#fff' : colors.ink,
    fontSize: 13,
  }
}

const CRITICAL_RELATION_TYPES = new Set(['governed_by', 'affects', 'increases', 'decreases', 'represented_by', 'represents'])

function matchesQuickFilter(mode, relations) {
  const activeMode = mode || 'all'
  if (!relations.length || activeMode === 'all') return true
  if (activeMode === 'critical') {
    return relations.some((relation) => CRITICAL_RELATION_TYPES.has((relation.relation_type || '').toLowerCase()))
  }
  if (activeMode === 'withRules') {
    return relations.some((relation) =>
      ['business_rule', 'ruleset'].includes((relation.source_asset_type || '').toLowerCase()) ||
      ['business_rule', 'ruleset'].includes((relation.target_asset_type || '').toLowerCase()),
    )
  }
  if (activeMode === 'withTools') {
    return relations.some((relation) =>
      (relation.source_asset_type || '').toLowerCase() === 'tool' ||
      (relation.target_asset_type || '').toLowerCase() === 'tool',
    )
  }
  return true
}

function buildRelationIndex(relations = []) {
  return relations.reduce((acc, relation) => {
    const outgoing = acc[relation.source_entity_id] || []
    outgoing.push({ ...relation, direction: 'outgoing' })
    acc[relation.source_entity_id] = outgoing
    const incoming = acc[relation.target_entity_id] || []
    incoming.push({ ...relation, direction: 'incoming' })
    acc[relation.target_entity_id] = incoming
    return acc
  }, {})
}

function filterVisibleRelations(relations, entities, focusedEntityId = null, relationFamily = 'all') {
  const visibleIds = new Set(entities.map((entity) => entity.asset_id))
  const visibleRelations = relations.filter(
    (relation) =>
      (visibleIds.has(relation.source_entity_id) || visibleIds.has(relation.target_entity_id)) &&
      ((relationFamily || 'all') === 'all' || (relation.relation_family || 'unknown') === relationFamily) &&
      (!focusedEntityId ||
        relation.source_entity_id === focusedEntityId ||
        relation.target_entity_id === focusedEntityId),
  )
  return focusedEntityId ? visibleRelations : visibleRelations.slice(0, MAX_OVERVIEW_RELATIONS)
}

function buildExternalRelationNodes(relations, visibleEntityIds, graphPositions) {
  const nodes = new Map()
  relations.forEach((relation) => {
    const endpoints = [
      {
        asset_id: relation.source_entity_id,
        asset_type: relation.source_asset_type,
        name: relation.source_name,
        anchor_id: relation.target_entity_id,
        side: 'left',
      },
      {
        asset_id: relation.target_entity_id,
        asset_type: relation.target_asset_type,
        name: relation.target_name,
        anchor_id: relation.source_entity_id,
        side: 'right',
      },
    ]
    endpoints.forEach((endpoint) => {
      if (!endpoint.asset_id || visibleEntityIds.has(endpoint.asset_id) || nodes.has(endpoint.asset_id)) return
      nodes.set(endpoint.asset_id, {
        ...endpoint,
      })
    })
  })
  const groups = Array.from(nodes.values()).reduce((acc, node) => {
    const key = `${node.anchor_id}:${node.side}`
    const group = acc.get(key) || []
    group.push(node)
    acc.set(key, group)
    return acc
  }, new Map())
  groups.forEach((group) => {
    group
      .sort((left, right) =>
        `${left.asset_type || ''}:${left.name || left.asset_id}`.localeCompare(
          `${right.asset_type || ''}:${right.name || right.asset_id}`,
        ),
      )
      .forEach((node, index) => {
        const anchor = graphPositions[node.anchor_id] || computeDefaultPosition(index)
        const perColumn = 9
        const column = Math.floor(index / perColumn)
        const row = index % perColumn
        const rowsInColumn = Math.min(perColumn, group.length - column * perColumn)
        const yOffset = (row - (rowsInColumn - 1) / 2) * 104
        node.position = {
          x: anchor.x + (node.side === 'left' ? -320 - column * 235 : 345 + column * 235),
          y: anchor.y + NODE_HEIGHT / 2 - 39 + yOffset,
        }
      })
  })
  return Array.from(nodes.values())
}

function safeShapeId(prefix, id) {
  const value = String(id || prefix).replace(/[^a-zA-Z0-9_-]+/g, '_').replace(/^_+|_+$/g, '')
  return `shape:${prefix}-${value || 'item'}`
}

function compactLabel(value, maxLength = 30) {
  const text = String(value || '').trim()
  if (text.length <= maxLength) return text
  return `${text.slice(0, maxLength - 1)}…`
}

function mapAssetTypeToColor(assetType) {
  const normalized = (assetType || '').toLowerCase()
  if (normalized.includes('flow') || normalized.includes('process')) return 'blue'
  if (normalized.includes('rule')) return 'red'
  if (normalized.includes('asset_set')) return 'orange'
  if (normalized.includes('qa')) return 'violet'
  if (normalized.includes('plan')) return 'light-blue'
  return 'grey'
}

function mapLayerToColor(layer) {
  const normalized = (layer || '').toLowerCase()
  if (normalized.includes('portfolio')) return 'orange'
  if (normalized.includes('offering')) return 'violet'
  if (normalized.includes('channel')) return 'light-blue'
  if (normalized.includes('capability')) return 'green'
  if (normalized.includes('agreement')) return 'yellow'
  if (normalized.includes('event')) return 'red'
  return 'grey'
}

function RawSourceEditor({ value, onChange, readOnly = false }) {
  const [text, setText] = useState(() => JSON.stringify(value ?? {}, null, 2))
  const [error, setError] = useState('')

  React.useEffect(() => {
    setText(JSON.stringify(value ?? {}, null, 2))
    setError('')
  }, [value])

  function update(nextText) {
    setText(nextText)
    try {
      const parsed = JSON.parse(nextText)
      if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
        throw new Error('The asset document must be an object.')
      }
      setError('')
      onChange(parsed)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason))
    }
  }

  return h(
    EditorFrame,
    {
      title: 'Raw Source',
      subtitle: 'Edit the canonical document in JSON form.',
    },
    h('textarea', {
      value: text,
      readOnly,
      spellCheck: false,
      onChange: (event) => update(event.target.value),
      style: {
        width: '100%',
        minHeight: 430,
        resize: 'vertical',
        border: `1px solid ${error ? colors.red : colors.line}`,
        borderRadius: 6,
        padding: 14,
        boxSizing: 'border-box',
        background: '#0f172a',
        color: '#dbeafe',
        font: '13px/1.55 ui-monospace, SFMono-Regular, Menlo, monospace',
        tabSize: 2,
      },
    }),
    error
      ? h('div', { style: { color: colors.red, background: colors.redSoft, padding: 10, marginTop: 10, borderRadius: 6 } }, error)
      : h('div', { style: { color: colors.green, fontSize: 12, marginTop: 9 } }, 'Syntax is valid.'),
  )
}

function RelationshipPreview({ value }) {
  const payload = value?.payload || { entities: [], relations: [] }
  const entityById = new Map(payload.entities.map((entity) => [entity.id, entity]))
  return h(
    EditorFrame,
    {
      title: 'Relations Overview',
      subtitle: 'Summaries for currently defined links.',
    },
    payload.relations.length
      ? payload.relations.map((relation) =>
          h(
            'div',
            {
              key: relation.id,
              style: {
                display: 'grid',
                gridTemplateColumns: 'minmax(120px, 200px) 24px minmax(120px, 200px)',
                gap: 8,
                alignItems: 'center',
                border: `1px solid ${colors.line}`,
                borderRadius: 8,
                padding: '8px 12px',
                marginBottom: 8,
              },
            },
            h('div', { style: { color: colors.ink, fontSize: 13 } }, entityById.get(relation.source_entity_id)?.name || relation.source_entity_id),
            h('div', { style: { textAlign: 'center', color: colors.blue, fontWeight: 600 } }, relation.relation_type),
            h('div', { style: { color: colors.ink, fontSize: 13 } }, entityById.get(relation.target_entity_id)?.name || relation.target_entity_id),
          ),
        )
      : h('div', { style: { color: colors.muted, fontSize: 13 } }, 'No relations captured yet.'),
  )
}

function HistoryPanel({ value, validation }) {
  const payload = value?.payload || { entities: [], relations: [] }
  return h(
    EditorFrame,
    {
      title: 'Model Snapshot',
      subtitle: 'Counts & validation summary.',
    },
    h('div', { style: { color: colors.ink, fontSize: 13, lineHeight: 1.6 } }, `Entities: ${payload.entities.length}. Relations: ${payload.relations.length}. Validation: ${validation.valid ? 'ok' : 'needs review'}.`),
    validation.errors.length ? h('div', { style: { color: colors.red, background: colors.redSoft, padding: 10, borderRadius: 6, marginTop: 10, fontSize: 12 } }, validation.errors[0]) : null,
    validation.warnings.length ? h('div', { style: { color: colors.amber, background: colors.amberSoft, padding: 10, borderRadius: 6, marginTop: 10, fontSize: 12 } }, validation.warnings[0]) : null,
  )
}

export function OntologyEditorView({
  value,
  onChange,
  readOnly = false,
  knowledgeBase: knowledgeBaseOverride,
  onSelectionChange,
  onRegisterFormHandler,
}) {
  const document = useMemo(() => normalizeBusinessModelDocument(value), [value])
  const [tab, setTab] = useState('structured')
  const [structuredSurface, setStructuredSurface] = useState('canvas')
  const [formHint, setFormHint] = useState('')
  const [activeSelection, setActiveSelection] = useState(null)
  const validation = useMemo(() => validateBusinessModelDocument(document), [document])
  const knowledgeBase = knowledgeBaseOverride || knowledgeBaseFromDocument(document)

  function commit(nextDocument) {
    onChange(nextDocument)
  }

  function commitPayload(nextPayload) {
    commit({ ...document, payload: normalizeBusinessModelPayload(nextPayload) })
  }

  useEffect(() => {
    onSelectionChange?.(activeSelection)
  }, [activeSelection, onSelectionChange])

  useEffect(() => {
    if (!onRegisterFormHandler) return
    const handler = (context) => {
      const label = context?.entityName
        ? `Edita ${context.entityName} en el formulario.`
        : 'Abre el formulario para editar la ontología.'
      focusFormSurface(label)
    }
    onRegisterFormHandler(handler)
    return () => onRegisterFormHandler(null)
  }, [onRegisterFormHandler])

  function focusFormSurface(hint = '') {
    setStructuredSurface('form')
    setFormHint(hint)
  }

  function focusCanvasSurface() {
    setStructuredSurface('canvas')
    setFormHint('')
  }

  function handleAddEntity() {
    if (readOnly) return
    const payloadSource = document.payload || { entities: [], relations: [], layout: { nodes: {} } }
    const existingIds = payloadSource.entities.map((entity) => entity.id)
    const nextEntity = createDefaultEntity(payloadSource.entities.length, existingIds)
    const nextLayoutNodes = { ...(payloadSource.layout?.nodes ?? {}) }
    nextLayoutNodes[nextEntity.id] = computeDefaultPosition(payloadSource.entities.length)
    const nextPayload = {
      ...payloadSource,
      entities: [...payloadSource.entities, nextEntity],
      layout: { nodes: nextLayoutNodes },
    }
    commitPayload(nextPayload)
    focusFormSurface(`Nueva entidad ${nextEntity.name}. Completa los atributos en el formulario.`)
  }

  function handleAddRelation() {
    if (readOnly) return
    const payloadSource = document.payload || { entities: [], relations: [], layout: { nodes: {} } }
    if (!payloadSource.entities.length) {
      if (typeof window !== 'undefined') {
        window.alert('Crea al menos una entidad antes de agregar relaciones.')
      }
      return
    }
    const entityIds = payloadSource.entities.map((entity) => entity.id)
    const sourceId = entityIds[0]
    const targetId = entityIds[1] || entityIds[0]
    const nextRelation = createDefaultRelation(payloadSource.relations.length, sourceId, targetId)
    const nextPayload = {
      ...payloadSource,
      relations: [...payloadSource.relations, nextRelation],
    }
    commitPayload(nextPayload)
    focusFormSurface('Nueva relación creada. Ajusta los extremos en el formulario.')
  }

  function handleRequestFormView(context = {}) {
    const hint =
      context.hint ||
      (context.entityName
        ? `Edita los atributos de ${context.entityName} en el formulario.`
        : 'Edita la entidad desde el formulario estructurado.')
    focusFormSurface(hint)
  }

  return h(
    'div',
    { style: { display: 'grid', gap: 14 } },
    h(
      'div',
      { style: { display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' } },
      h(TabButton, { active: tab === 'structured', onClick: () => setTab('structured') }, 'Structured Editor'),
      h(TabButton, { active: tab === 'source', onClick: () => setTab('source') }, 'Raw Source'),
      h(TabButton, { active: tab === 'relationships', onClick: () => setTab('relationships') }, 'Relations'),
      h(TabButton, { active: tab === 'history', onClick: () => setTab('history') }, 'History'),
      h('div', { style: { marginLeft: 'auto' } }, h(Pill, { label: validation.valid ? 'valid' : 'needs review', tone: validation.valid ? colors.greenSoft : colors.redSoft, textColor: validation.valid ? colors.green : colors.red })),
    ),
    tab === 'structured'
      ? h(
          'div',
          { style: { display: 'grid', gap: 16 } },
          h(
            'div',
            { style: { display: 'flex', gap: 8, flexWrap: 'wrap' } },
            h(TabButton, { active: structuredSurface === 'canvas', onClick: () => focusCanvasSurface() }, 'Canvas KB'),
            h(TabButton, { active: structuredSurface === 'form', onClick: () => setStructuredSurface('form') }, 'Formulario'),
          ),
          structuredSurface === 'canvas'
            ? h(BusinessModelCanvasView, {
                knowledgeBase,
                readOnly,
                focusAssetId: document?.asset_id,
                onAddEntity: readOnly ? undefined : handleAddEntity,
                onAddRelation: readOnly ? undefined : handleAddRelation,
                onRequestFormView: handleRequestFormView,
                onSelectionChange: setActiveSelection,
              })
            : h(
                'div',
                { style: { display: 'grid', gap: 12 } },
                formHint
                  ? h(
                      'div',
                      {
                        style: {
                          background: colors.blueSoft,
                          color: colors.blue,
                          padding: '10px 12px',
                          borderRadius: 8,
                          fontSize: 12,
                        },
                      },
                      formHint,
                    )
                  : null,
                h(BusinessModelJsonFormsView, { value: document, onChange: (payload) => commitPayload(payload), readOnly }),
              ),
        )
      : null,
    tab === 'source' ? h(RawSourceEditor, { value: document, onChange: commit, readOnly }) : null,
    tab === 'relationships' ? h(RelationshipPreview, { value: document }) : null,
    tab === 'history' ? h(HistoryPanel, { value: document, validation }) : null,
  )
}

export function sourceDocument(asset) {
  const stored = asset?.payload && asset.payload.asset_id ? clone(asset.payload) : {
    asset_id: asset.asset_id,
    asset_type: asset.asset_type,
    name: asset.name,
    version: asset.version,
    tags: asset.tags,
    relations: asset.relationships,
    payload: asset.payload,
  }
  if (asset?.primary_kb && !stored.primary_kb) {
    stored.primary_kb = asset.primary_kb
  }
  delete stored.status
  delete stored.source_refs
  delete stored.evidence
  if (stored.payload) {
    delete stored.payload.asset_set_id
    delete stored.payload.asset_set_version
  }
  return stored
}
