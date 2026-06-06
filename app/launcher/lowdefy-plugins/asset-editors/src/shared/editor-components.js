import React, { useEffect, useMemo, useState } from 'react'
import { parse as parseYaml, stringify as stringifyYaml } from 'yaml'
import { withBlockDefaults } from '@lowdefy/block-utils'

const h = React.createElement
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
}
const baseFont = 'Inter, ui-sans-serif, system-ui, sans-serif'
const buttonStyle = (primary = false) => ({
  border: `1px solid ${primary ? colors.blue : colors.line}`,
  background: primary ? colors.blue : colors.panel,
  color: primary ? '#fff' : colors.ink,
  borderRadius: 6,
  padding: '8px 12px',
  fontWeight: 700,
  cursor: 'pointer',
  fontFamily: baseFont,
})
const inputStyle = {
  border: `1px solid ${colors.line}`,
  borderRadius: 6,
  padding: '8px 10px',
  color: colors.ink,
  background: '#fff',
  fontFamily: baseFont,
  minWidth: 0,
}

function clone(value) {
  return JSON.parse(JSON.stringify(value ?? {}))
}

function setPayload(document, nextPayload) {
  return { ...document, payload: nextPayload }
}

function emit(methods, value) {
  methods?.setValue?.(value)
  methods?.triggerEvent?.({ name: 'onChange', event: { value } })
}

function EditorFrame({ title, subtitle, children, actions }) {
  return h(
    'section',
    {
      style: {
        border: `1px solid ${colors.line}`,
        borderRadius: 8,
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

function AssetCodeEditorView({ value, onChange, readOnly = false }) {
  const [format, setFormat] = useState('yaml')
  const [text, setText] = useState('')
  const [error, setError] = useState('')
  useEffect(() => {
    setText(format === 'yaml' ? stringifyYaml(value ?? {}) : JSON.stringify(value ?? {}, null, 2))
    setError('')
  }, [value, format])
  function update(nextText) {
    setText(nextText)
    try {
      const parsed = format === 'yaml' ? parseYaml(nextText) : JSON.parse(nextText)
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
      title: 'Asset source',
      subtitle: 'Edit the canonical definition as YAML or JSON.',
      actions: h(
        'select',
        { value: format, onChange: (event) => setFormat(event.target.value), style: inputStyle },
        h('option', { value: 'yaml' }, 'YAML'),
        h('option', { value: 'json' }, 'JSON'),
      ),
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

function ProcessCanvasView({ value, onChange, readOnly = false }) {
  const payload = clone(value?.payload)
  const sourceSteps = payload.nodes || payload.steps || payload.user_tasks || []
  const steps = sourceSteps.map((item, index) =>
    typeof item === 'string'
      ? { id: `step-${index + 1}`, name: item, type: 'user_task' }
      : { id: item.id || item.node_id || `step-${index + 1}`, name: item.name || item.label || item.task || `Step ${index + 1}`, type: item.type || 'task', ...item },
  )
  function commit(nextSteps) {
    const nextPayload = {
      ...payload,
      nodes: nextSteps,
      user_tasks: nextSteps
        .filter((step) => step.type === 'user_task')
        .map((step) => step.name),
    }
    delete nextPayload.steps
    onChange(setPayload(value, nextPayload))
  }
  return h(
    EditorFrame,
    {
      title: value?.asset_type === 'flow' ? 'Flow canvas' : 'Process canvas',
      subtitle: 'Sequence, rename, add, and remove executable nodes.',
      actions: !readOnly
        ? h('button', { style: buttonStyle(), onClick: () => commit([...steps, { id: `step-${Date.now()}`, name: 'New step', type: 'user_task' }]) }, '+ Add step')
        : null,
    },
    h(
      'div',
      { style: { background: colors.canvas, border: `1px solid ${colors.line}`, borderRadius: 6, padding: 24, minHeight: 360, overflowX: 'auto' } },
      h(
        'div',
        { style: { display: 'flex', alignItems: 'center', gap: 10, minWidth: 'max-content' } },
        steps.length
          ? steps.flatMap((step, index) => [
              h(
                'div',
                {
                  key: step.id,
                  style: {
                    width: 190,
                    border: `1px solid ${colors.line}`,
                    borderTop: `4px solid ${step.type === 'user_task' ? colors.blue : colors.green}`,
                    borderRadius: 7,
                    padding: 12,
                    background: '#fff',
                    boxShadow: '0 3px 12px rgba(16,33,61,.08)',
                  },
                },
                h('div', { style: { color: colors.muted, fontSize: 11, textTransform: 'uppercase', marginBottom: 7 } }, step.type),
                h('input', {
                  value: step.name,
                  readOnly,
                  onChange: (event) => commit(steps.map((item, itemIndex) => itemIndex === index ? { ...item, name: event.target.value } : item)),
                  style: { ...inputStyle, width: '100%', boxSizing: 'border-box', fontWeight: 700 },
                }),
                !readOnly
                  ? h('button', {
                      onClick: () => commit(steps.filter((_, itemIndex) => itemIndex !== index)),
                      style: { border: 0, background: 'transparent', color: colors.red, padding: '8px 0 0', cursor: 'pointer' },
                    }, 'Remove')
                  : null,
              ),
              index < steps.length - 1
                ? h('div', { key: `${step.id}-arrow`, style: { color: colors.blue, fontSize: 22, fontWeight: 700 } }, '→')
                : null,
            ])
          : h('div', { style: { color: colors.muted } }, 'No process nodes are defined.'),
      ),
    ),
  )
}

function OntologyGraphView({ value, onChange, readOnly = false }) {
  const relations = clone(value?.relations || [])
  const [relationType, setRelationType] = useState('related_to')
  const [target, setTarget] = useState('')
  function commit(nextRelations) {
    onChange({ ...value, relations: nextRelations })
  }
  return h(
    EditorFrame,
    {
      title: 'Ontology graph',
      subtitle: 'Navigate the selected node and edit its outbound relationships.',
    },
    h(
      'div',
      { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(320px, 100%), 1fr))', gap: 18 } },
      h(
        'div',
        { style: { background: colors.canvas, border: `1px solid ${colors.line}`, borderRadius: 6, minHeight: 340, padding: 24, position: 'relative' } },
        h('div', { style: { border: `2px solid ${colors.blue}`, background: colors.blueSoft, borderRadius: 8, padding: 14, color: colors.ink, fontWeight: 800 } }, value?.name || value?.asset_id),
        relations.map((relation, index) =>
          h(
            'div',
            { key: `${relation.type}-${relation.target_asset_id}-${index}`, style: { marginTop: 22, marginLeft: 38, position: 'relative' } },
            h('div', { style: { position: 'absolute', left: -24, top: -18, color: colors.muted, fontSize: 11 } }, relation.type),
            h('div', { style: { border: `1px solid ${colors.green}`, background: colors.greenSoft, borderRadius: 8, padding: 11, color: colors.ink } }, relation.target_asset_id),
          ),
        ),
      ),
      h(
        'div',
        null,
        h('strong', { style: { color: colors.ink } }, 'Relationships'),
        relations.map((relation, index) =>
          h(
            'div',
            { key: index, style: { display: 'grid', gridTemplateColumns: '1fr 1.5fr auto', gap: 8, marginTop: 10 } },
            h('input', {
              value: relation.type,
              readOnly,
              onChange: (event) => commit(relations.map((item, itemIndex) => itemIndex === index ? { ...item, type: event.target.value } : item)),
              style: inputStyle,
            }),
            h('input', {
              value: relation.target_asset_id,
              readOnly,
              onChange: (event) => commit(relations.map((item, itemIndex) => itemIndex === index ? { ...item, target_asset_id: event.target.value } : item)),
              style: inputStyle,
            }),
            !readOnly ? h('button', { style: buttonStyle(), onClick: () => commit(relations.filter((_, itemIndex) => itemIndex !== index)) }, 'Remove') : null,
          ),
        ),
        !readOnly
          ? h(
              'div',
              { style: { display: 'grid', gridTemplateColumns: '1fr 1.5fr auto', gap: 8, marginTop: 16, paddingTop: 16, borderTop: `1px solid ${colors.line}` } },
              h('input', { value: relationType, onChange: (event) => setRelationType(event.target.value), style: inputStyle, placeholder: 'relation type' }),
              h('input', { value: target, onChange: (event) => setTarget(event.target.value), style: inputStyle, placeholder: 'target asset id' }),
              h('button', {
                style: buttonStyle(true),
                disabled: !relationType.trim() || !target.trim(),
                onClick: () => {
                  commit([...relations, { type: relationType.trim(), target_asset_id: target.trim(), metadata: {} }])
                  setTarget('')
                },
              }, 'Add'),
            )
          : null,
      ),
    ),
  )
}

function RuleBuilderView({ value, onChange, readOnly = false }) {
  const payload = clone(value?.payload)
  const conditions = clone(payload.conditions || parseCondition(payload.condition))
  const outcome = payload.outcome || ''
  function commit(nextConditions, nextOutcome = outcome) {
    const conditionText = nextConditions
      .map((condition) => `${condition.field} ${condition.operator} ${condition.value}`)
      .join(' and ')
    onChange(setPayload(value, { ...payload, conditions: nextConditions, condition: conditionText, outcome: nextOutcome }))
  }
  return h(
    EditorFrame,
    {
      title: 'Rule builder',
      subtitle: 'Compose deterministic conditions and their business outcome.',
      actions: !readOnly ? h('button', { style: buttonStyle(), onClick: () => commit([...conditions, { field: '', operator: 'equals', value: '' }]) }, '+ Condition') : null,
    },
    h(
      'div',
      { style: { display: 'grid', gap: 10 } },
      conditions.map((condition, index) =>
        h(
          'div',
          { key: index, style: { display: 'grid', gridTemplateColumns: '1.2fr .8fr 1.2fr auto', gap: 8, alignItems: 'center', background: colors.canvas, padding: 10, borderRadius: 6 } },
          h('input', {
            value: condition.field,
            readOnly,
            placeholder: 'Field',
            onChange: (event) => commit(conditions.map((item, itemIndex) => itemIndex === index ? { ...item, field: event.target.value } : item)),
            style: inputStyle,
          }),
          h(
            'select',
            {
              value: condition.operator,
              disabled: readOnly,
              onChange: (event) => commit(conditions.map((item, itemIndex) => itemIndex === index ? { ...item, operator: event.target.value } : item)),
              style: inputStyle,
            },
              ['equals', 'not_equals', 'in', 'not_in', 'greater_than', 'greater_than_or_equal', 'less_than', 'less_than_or_equal', 'contains'].map((operator) => h('option', { key: operator, value: operator }, operator)),
          ),
          h('input', {
            value: condition.value,
            readOnly,
            placeholder: 'Value',
            onChange: (event) => commit(conditions.map((item, itemIndex) => itemIndex === index ? { ...item, value: event.target.value } : item)),
            style: inputStyle,
          }),
          !readOnly ? h('button', { style: buttonStyle(), onClick: () => commit(conditions.filter((_, itemIndex) => itemIndex !== index)) }, 'Remove') : null,
        ),
      ),
      h('label', { style: { display: 'grid', gap: 6, marginTop: 10, color: colors.ink, fontWeight: 700 } }, 'Outcome',
        h('input', { value: outcome, readOnly, onChange: (event) => commit(conditions, event.target.value), style: inputStyle })),
    ),
  )
}

function parseCondition(condition) {
  if (!condition) return [{ field: '', operator: 'equals', value: '' }]
  const operatorMap = [
    [' not in ', 'not_in'],
    [' in ', 'in'],
    [' != ', 'not_equals'],
    [' == ', 'equals'],
    [' >= ', 'greater_than_or_equal'],
    [' <= ', 'less_than_or_equal'],
    [' > ', 'greater_than'],
    [' < ', 'less_than'],
  ]
  return String(condition).split(/\s+and\s+/i).map((part) => {
    for (const [token, operator] of operatorMap) {
      const index = part.indexOf(token)
      if (index >= 0) {
        return {
          field: part.slice(0, index).trim(),
          operator,
          value: part.slice(index + token.length).trim(),
        }
      }
    }
    return { field: part.trim(), operator: 'equals', value: '' }
  })
}

function FormDesignerView({ value, onChange, readOnly = false }) {
  const payload = clone(value?.payload)
  const fields = clone(payload.fields || [])
  function commit(nextFields) {
    onChange(setPayload(value, { ...payload, fields: nextFields }))
  }
  return h(
    EditorFrame,
    {
      title: 'Form designer',
      subtitle: 'Manage fields, validation, order, and input behavior.',
      actions: !readOnly ? h('button', { style: buttonStyle(true), onClick: () => commit([...fields, { id: `field_${fields.length + 1}`, label: 'New field', type: 'text', required: false }]) }, '+ Add field') : null,
    },
    h(
      'div',
      { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(360px, 100%), 1fr))', gap: 18 } },
      h(
        'div',
        { style: { display: 'grid', gap: 9 } },
        fields.map((field, index) =>
          h(
            'div',
            { key: field.id || index, style: { display: 'grid', gridTemplateColumns: '34px 1fr 1fr .7fr 70px', gap: 7, alignItems: 'center', border: `1px solid ${colors.line}`, padding: 9, borderRadius: 6 } },
            h('strong', { style: { color: colors.muted, textAlign: 'center' } }, index + 1),
            h('input', { value: field.id || '', readOnly, onChange: (event) => commit(fields.map((item, itemIndex) => itemIndex === index ? { ...item, id: event.target.value } : item)), style: inputStyle }),
            h('input', { value: field.label || '', readOnly, onChange: (event) => commit(fields.map((item, itemIndex) => itemIndex === index ? { ...item, label: event.target.value } : item)), style: inputStyle }),
            h('select', { value: field.type || 'text', disabled: readOnly, onChange: (event) => commit(fields.map((item, itemIndex) => itemIndex === index ? { ...item, type: event.target.value } : item)), style: inputStyle },
              ['text', 'number', 'email', 'textarea', 'date', 'select', 'checkbox'].map((type) => h('option', { key: type, value: type }, type))),
            !readOnly ? h('button', { style: { ...buttonStyle(), padding: 7 }, onClick: () => commit(fields.filter((_, itemIndex) => itemIndex !== index)) }, 'Remove') : null,
          ),
        ),
      ),
      h(
        'div',
        { style: { background: colors.canvas, border: `1px solid ${colors.line}`, borderRadius: 6, padding: 16 } },
        h('strong', { style: { color: colors.ink } }, payload.title || value?.name || 'Form preview'),
        fields.map((field) =>
          h('label', { key: field.id, style: { display: 'grid', gap: 5, marginTop: 14, color: colors.ink, fontSize: 13, fontWeight: 700 } },
            `${field.label || field.id}${field.required ? ' *' : ''}`,
            field.type === 'textarea'
              ? h('textarea', { disabled: true, placeholder: field.placeholder || '', style: { ...inputStyle, minHeight: 70 } })
              : h('input', { disabled: true, placeholder: field.placeholder || '', style: inputStyle })),
        ),
      ),
    ),
  )
}

function NavigationTreeView({ value, onChange, readOnly = false }) {
  const payload = clone(value?.payload)
  const key = Array.isArray(payload.items)
    ? 'items'
    : Array.isArray(payload.menus)
      ? 'menus'
      : Array.isArray(payload.topMenus)
        ? 'topMenus'
        : 'items'
  const items = clone(payload[key] || [])
  function commit(nextItems) {
    onChange(setPayload(value, { ...payload, [key]: nextItems }))
  }
  function updateAt(index, patch) {
    commit(items.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item))
  }
  return h(
    EditorFrame,
    {
      title: 'Navigation tree',
      subtitle: 'Edit domain, module, menu, and submenu navigation metadata.',
      actions: !readOnly ? h('button', { style: buttonStyle(true), onClick: () => commit([...items, { id: `item-${items.length + 1}`, label: 'New item', path: '/' }]) }, '+ Add item') : null,
    },
    h(
      'div',
      { style: { display: 'grid', gridTemplateColumns: '1fr 1.4fr 1.6fr', gap: 8, marginBottom: 16, paddingBottom: 16, borderBottom: `1px solid ${colors.line}` } },
      h('label', { style: { display: 'grid', gap: 5, color: colors.muted, fontSize: 11, fontWeight: 800 } }, 'ID',
        h('input', {
          value: payload.id || payload.moduleId || payload.domainId || '',
          readOnly,
          onChange: (event) => {
            const idKey = payload.moduleId != null ? 'moduleId' : payload.domainId != null ? 'domainId' : 'id'
            onChange(setPayload(value, { ...payload, [idKey]: event.target.value }))
          },
          style: inputStyle,
        })),
      h('label', { style: { display: 'grid', gap: 5, color: colors.muted, fontSize: 11, fontWeight: 800 } }, 'LABEL',
        h('input', { value: payload.label || value?.name || '', readOnly, onChange: (event) => onChange({ ...value, name: event.target.value, payload: { ...payload, label: event.target.value } }), style: inputStyle })),
      h('label', { style: { display: 'grid', gap: 5, color: colors.muted, fontSize: 11, fontWeight: 800 } }, 'PATH / DESCRIPTION',
        h('input', {
          value: payload.path || payload.description || value?.description || '',
          readOnly,
          onChange: (event) => {
            const next = payload.path != null
              ? { ...value, payload: { ...payload, path: event.target.value } }
              : { ...value, description: event.target.value, payload: { ...payload, description: event.target.value } }
            onChange(next)
          },
          style: inputStyle,
        })),
    ),
    h(
      'div',
      { style: { borderLeft: `2px solid ${colors.line}`, marginLeft: 12, paddingLeft: 18, display: 'grid', gap: 10 } },
      items.length
        ? items.map((item, index) =>
            h(
              'div',
              { key: item.id || index, style: { display: 'grid', gridTemplateColumns: '1fr 1.3fr 1.3fr auto', gap: 8, alignItems: 'center' } },
              h('input', { value: item.id || '', readOnly, onChange: (event) => updateAt(index, { id: event.target.value }), style: inputStyle }),
              h('input', { value: item.label || '', readOnly, onChange: (event) => updateAt(index, { label: event.target.value }), style: inputStyle }),
              h('input', { value: item.path || '', readOnly, onChange: (event) => updateAt(index, { path: event.target.value }), style: inputStyle, placeholder: 'Path' }),
              !readOnly ? h('button', { style: buttonStyle(), onClick: () => commit(items.filter((_, itemIndex) => itemIndex !== index)) }, 'Remove') : null,
            ),
          )
        : h('div', { style: { color: colors.muted } }, 'No navigation items are defined.'),
    ),
  )
}

function wrapInput(View) {
  const Block = ({ blockId, classNames = {}, methods, properties = {}, styles = {}, value }) =>
    h('div', { id: blockId, className: classNames.element, style: styles.element },
      h(View, { value: value || {}, readOnly: properties.readOnly, onChange: (next) => emit(methods, next) }))
  return withBlockDefaults(Block)
}

export const AssetCodeEditor = wrapInput(AssetCodeEditorView)
export const ProcessCanvas = wrapInput(ProcessCanvasView)
export const OntologyGraph = wrapInput(OntologyGraphView)
export const RuleBuilder = wrapInput(RuleBuilderView)
export const FormDesigner = wrapInput(FormDesignerView)
export const NavigationTree = wrapInput(NavigationTreeView)

function editorFor(document) {
  const type = String(document?.asset_type || '')
  if (['flow', 'process'].includes(type)) return ProcessCanvasView
  if (['ontology', 'entity', 'concept', 'relationship'].includes(type)) return OntologyGraphView
  if (['business_rule', 'rule', 'ruleset'].includes(type)) return RuleBuilderView
  if (type === 'form') return FormDesignerView
  if (['domain', 'module', 'menu', 'submenu', 'navigation'].includes(type)) return NavigationTreeView
  return AssetCodeEditorView
}

function sourceDocument(asset) {
  const stored = asset?.payload && asset.payload.asset_id ? clone(asset.payload) : {
    asset_id: asset.asset_id,
    asset_type: asset.asset_type,
    name: asset.name,
    version: asset.version,
    tags: asset.tags,
    relations: asset.relationships,
    payload: asset.payload,
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

function AssetStudioBlock({ blockId, classNames = {}, properties = {}, styles = {} }) {
  const api = properties.apiBaseUrl || 'http://127.0.0.1:8030'
  const environment = properties.environment || 'dev'
  const actor = properties.actor || 'saul'
  const [assets, setAssets] = useState([])
  const [metadata, setMetadata] = useState({ asset_types: [], knowledge_bases: [], statuses: [], tags: [] })
  const [selected, setSelected] = useState(null)
  const [document, setDocument] = useState(null)
  const [mode, setMode] = useState('visual')
  const [filters, setFilters] = useState({ query: '', asset_type: '', knowledge_base: '', status: '', tag: '' })
  const [notice, setNotice] = useState(null)
  const [busy, setBusy] = useState(false)

  async function request(path, options) {
    const response = await fetch(`${api}${path}`, {
      headers: { 'Content-Type': 'application/json', ...(options?.headers || {}) },
      ...options,
    })
    const body = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(body.detail || `${response.status} ${response.statusText}`)
    return body
  }
  async function loadAssets() {
    const params = new URLSearchParams({ environment, limit: '1000' })
    Object.entries(filters).forEach(([key, value]) => value && params.set(key, value))
    const body = await request(`/catalog/assets?${params}`)
    setAssets(body.assets || [])
  }
  useEffect(() => {
    Promise.all([
      request(`/catalog/metadata?environment=${encodeURIComponent(environment)}`),
      request(`/catalog/assets?environment=${encodeURIComponent(environment)}&limit=1000`),
    ]).then(([meta, body]) => {
      setMetadata(meta)
      setAssets(body.assets || [])
    }).catch((error) => setNotice({ type: 'error', text: error.message }))
  }, [api, environment])

  async function selectAsset(asset) {
    setBusy(true)
    setNotice(null)
    try {
      const detail = await request(`/catalog/assets/${encodeURIComponent(asset.asset_id)}?version=${encodeURIComponent(asset.version)}`)
      setSelected(detail)
      setDocument(sourceDocument(detail))
      setMode('visual')
    } catch (error) {
      setNotice({ type: 'error', text: error.message })
    } finally {
      setBusy(false)
    }
  }
  async function validate() {
    const result = await request('/catalog/assets/validate', {
      method: 'POST',
      body: JSON.stringify({
        document,
        expected_asset_id: selected.asset_id,
        expected_asset_type: selected.asset_type,
      }),
    })
    setNotice({ type: 'success', text: `Valid asset. ${result.relation_count} relations; projections: ${(result.stores || []).join(', ') || 'repository'}.` })
  }
  async function save() {
    setBusy(true)
    setNotice(null)
    try {
      await validate()
      const result = await request(`/catalog/assets/${encodeURIComponent(selected.asset_id)}/versions`, {
        method: 'POST',
        body: JSON.stringify({ base_version: selected.version, actor, document }),
      })
      setNotice({ type: 'success', text: `Created ${result.asset_set_id}@${result.version} and submitted it for review.` })
      await loadAssets()
      const created = (result.members || []).find((item) => item.asset_id === selected.asset_id)
      if (created) await selectAsset(created)
    } catch (error) {
      setNotice({ type: 'error', text: error.message })
    } finally {
      setBusy(false)
    }
  }
  async function lifecycle(action, comment = '') {
    if (!selected?.asset_set_id || !selected?.asset_set_version) return
    setBusy(true)
    setNotice(null)
    try {
      const result = await request(`/catalog/asset-sets/${encodeURIComponent(selected.asset_set_id)}/transition`, {
        method: 'POST',
        body: JSON.stringify({
          version: selected.asset_set_version,
          action,
          actor,
          comment: comment || `Lifecycle action from Asset Studio: ${action}`,
        }),
      })
      setSelected({ ...selected, status: result.status })
      setNotice({ type: 'success', text: `${selected.asset_set_id}@${selected.asset_set_version} is now ${result.status}.` })
      await loadAssets()
    } catch (error) {
      setNotice({ type: 'error', text: error.message })
    } finally {
      setBusy(false)
    }
  }
  async function deploy() {
    if (!selected?.asset_set_id || !selected?.asset_set_version) return
    setBusy(true)
    setNotice(null)
    try {
      await request(`/catalog/asset-sets/${encodeURIComponent(selected.asset_set_id)}/deploy`, {
        method: 'POST',
        body: JSON.stringify({ version: selected.asset_set_version, environment, actor }),
      })
      setSelected({ ...selected, status: 'active', active: true, active_environment: environment })
      setNotice({ type: 'success', text: `${selected.asset_set_id}@${selected.asset_set_version} deployed to ${environment}.` })
      await loadAssets()
    } catch (error) {
      setNotice({ type: 'error', text: error.message })
    } finally {
      setBusy(false)
    }
  }
  const filteredAssets = useMemo(() => assets, [assets])
  const Editor = editorFor(document)
  return h(
    'div',
    { id: blockId, className: classNames.element, style: { ...styles.element, fontFamily: baseFont, color: colors.ink, background: colors.canvas, minHeight: 'calc(100vh - 70px)', padding: 18, boxSizing: 'border-box' } },
    h('style', null, `
      #${blockId} .asset-studio-grid {
        display: grid;
        grid-template-columns: minmax(250px, 310px) minmax(520px, 1fr);
        gap: 14px;
        min-height: 650px;
      }
      @media (max-width: 820px) {
        #${blockId} { padding: 10px !important; }
        #${blockId} .asset-studio-grid { grid-template-columns: minmax(0, 1fr); }
        #${blockId} .asset-studio-list { max-height: 280px !important; }
        #${blockId} .asset-toolbar { align-items: flex-start !important; flex-direction: column; }
      }
    `),
    h(
      'div',
      { style: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, marginBottom: 14 } },
      h('div', null, h('div', { style: { color: colors.muted, fontSize: 11, fontWeight: 800, textTransform: 'uppercase' } }, 'Unified Catalog'), h('h1', { style: { margin: '2px 0 0', fontSize: 25 } }, 'Asset Studio')),
      h('div', { style: { color: colors.muted, fontSize: 12 } }, `Environment: ${environment.toUpperCase()}`),
    ),
    h(
      'div',
      { className: 'asset-studio-grid' },
      h(
        'aside',
        { style: { background: '#fff', border: `1px solid ${colors.line}`, borderRadius: 8, overflow: 'hidden' } },
        h(
          'div',
          { style: { padding: 12, borderBottom: `1px solid ${colors.line}`, display: 'grid', gap: 8 } },
          h('input', { value: filters.query, onChange: (event) => setFilters({ ...filters, query: event.target.value }), placeholder: 'Search assets', style: inputStyle }),
          h(
            'div',
            { style: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 7 } },
            [['asset_type', metadata.asset_types], ['status', metadata.statuses], ['knowledge_base', metadata.knowledge_bases], ['tag', metadata.tags]].map(([key, values]) =>
              h('select', { key, value: filters[key], onChange: (event) => setFilters({ ...filters, [key]: event.target.value }), style: inputStyle },
                h('option', { value: '' }, key.replace('_', ' ')),
                (values || []).map((value) => h('option', { key: value, value }, value))),
            ),
          ),
          h('button', { style: buttonStyle(true), onClick: loadAssets }, 'Apply filters'),
        ),
        h(
          'div',
          { className: 'asset-studio-list', style: { maxHeight: 610, overflowY: 'auto' } },
          filteredAssets.map((asset) =>
            h(
              'button',
              {
                key: `${asset.asset_id}:${asset.version}`,
                onClick: () => selectAsset(asset),
                style: {
                  width: '100%',
                  textAlign: 'left',
                  border: 0,
                  borderBottom: `1px solid ${colors.line}`,
                  background: selected?.asset_id === asset.asset_id && selected?.version === asset.version ? colors.blueSoft : '#fff',
                  padding: '11px 12px',
                  cursor: 'pointer',
                  fontFamily: baseFont,
                },
              },
              h('strong', { style: { display: 'block', color: colors.ink, fontSize: 13 } }, asset.name || asset.asset_id),
              h('span', { style: { color: colors.muted, fontSize: 11 } }, `${asset.asset_type} · ${asset.version} · ${asset.status}`),
            ),
          ),
        ),
      ),
      h(
        'main',
        { style: { minWidth: 0 } },
        notice
          ? h('div', { style: { marginBottom: 10, borderRadius: 6, padding: 10, color: notice.type === 'error' ? colors.red : colors.green, background: notice.type === 'error' ? colors.redSoft : colors.greenSoft } }, notice.text)
          : null,
        selected && document
          ? h(
              React.Fragment,
              null,
              h(
                'div',
                { className: 'asset-toolbar', style: { background: '#fff', border: `1px solid ${colors.line}`, borderRadius: 8, padding: 13, marginBottom: 10, display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', gap: 14, alignItems: 'center' } },
                h('div', null,
                  h('strong', { style: { display: 'block' } }, selected.name || selected.asset_id),
                  h('span', { style: { color: colors.muted, fontSize: 12 } }, `${selected.asset_id} · ${selected.asset_type} · v${selected.version}`)),
                h(
                  'div',
                  { style: { display: 'flex', flexWrap: 'wrap', gap: 7 } },
                  h('button', { style: buttonStyle(mode === 'visual'), onClick: () => setMode('visual') }, 'Visual'),
                  h('button', { style: buttonStyle(mode === 'source'), onClick: () => setMode('source') }, 'YAML / JSON'),
                  h('button', { style: buttonStyle(), disabled: busy, onClick: validate }, 'Validate'),
                  h('button', { style: buttonStyle(true), disabled: busy, onClick: save }, busy ? 'Working...' : 'Save new version'),
                ),
              ),
              h(
                'div',
                { style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8, marginBottom: 10, padding: '9px 11px', background: '#fff', border: `1px solid ${colors.line}`, borderRadius: 8 } },
                h('strong', { style: { fontSize: 12, marginRight: 'auto' } }, `Lifecycle: ${selected.status}`),
                selected.status === 'ready_for_review'
                  ? h('button', { style: buttonStyle(), disabled: busy, onClick: () => lifecycle('start_review') }, 'Start review')
                  : null,
                selected.status === 'in_review'
                  ? h(React.Fragment, null,
                      h('button', { style: buttonStyle(true), disabled: busy, onClick: () => lifecycle('validate') }, 'Complete validation'),
                      h('button', { style: buttonStyle(), disabled: busy, onClick: () => lifecycle('request_changes', 'Changes requested from Asset Studio.') }, 'Request changes'))
                  : null,
                selected.status === 'validated'
                  ? h('button', { style: buttonStyle(true), disabled: busy, onClick: deploy }, `Deploy to ${environment.toUpperCase()}`)
                  : null,
              ),
              mode === 'source'
                ? h(AssetCodeEditorView, { value: document, onChange: setDocument })
                : h(Editor, { value: document, onChange: setDocument }),
            )
          : h('div', { style: { height: 500, display: 'grid', placeItems: 'center', background: '#fff', border: `1px solid ${colors.line}`, borderRadius: 8, color: colors.muted } }, busy ? 'Loading asset...' : 'Select an asset to open its editor.'),
      ),
    ),
  )
}

export const AssetStudio = withBlockDefaults(AssetStudioBlock)

export {
  AssetCodeEditorView,
  ProcessCanvasView,
  OntologyGraphView,
  RuleBuilderView,
  FormDesignerView,
  NavigationTreeView,
  editorFor,
  sourceDocument,
  colors,
  baseFont,
  buttonStyle,
  inputStyle,
}
