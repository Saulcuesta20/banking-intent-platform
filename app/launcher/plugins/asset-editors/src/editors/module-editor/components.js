import React, { useMemo, useState } from 'react'
import { JsonForms } from '@jsonforms/react'
import { vanillaCells, vanillaRenderers } from '@jsonforms/vanilla-renderers'

import definitionSchema from './module-editor.schema.json'
import definitionUiSchema from './module-editor.ui-schema.json'
import {
  normalizeModuleDefinition,
  validateModuleDocument,
} from './helpers.js'

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

function buttonStyle(primary = false) {
  return {
    border: `1px solid ${primary ? colors.blue : colors.line}`,
    background: primary ? colors.blue : colors.panel,
    color: primary ? '#fff' : colors.ink,
    borderRadius: 6,
    padding: '8px 12px',
    fontWeight: 700,
    cursor: 'pointer',
    fontFamily: baseFont,
  }
}

const inputStyle = {
  border: `1px solid ${colors.line}`,
  borderRadius: 6,
  padding: '8px 10px',
  fontSize: 13,
  fontFamily: baseFont,
  outline: 'none',
}

function shellCardStyle() {
  return {
    border: `1px solid ${colors.line}`,
    borderRadius: 8,
    background: colors.panel,
    overflow: 'hidden',
    fontFamily: baseFont,
  }
}

function clone(value) {
  return JSON.parse(JSON.stringify(value ?? {}))
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
        padding: '8px 12px',
        background: active ? colors.blue : colors.panel,
      },
    },
    children,
  )
}

function EditorFrame({ title, subtitle, children, actions }) {
  return h(
    'section',
    {
      style: {
        ...shellCardStyle(),
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

function normalizeDocument(value) {
  const document = clone(value)
  const payload = clone(document.payload || {})
  const module_ = normalizeModuleDefinition(payload)
  const relations = Array.isArray(document.relations) ? document.relations : []
  return {
    ...document,
    relations,
    payload: {
      ...payload,
      ...module_,
    },
  }
}

function ModuleDefinitionJsonFormsView({ value, onChange, readOnly = false }) {
  const payload = clone(value?.payload)
  const definition = useMemo(() => normalizeModuleDefinition(payload), [payload])
  return h(
    EditorFrame,
    {
      title: 'Module Definition',
      subtitle: 'Schema-driven editor powered by JSON Forms.',
    },
    h(JsonForms, {
      data: definition,
      schema: definitionSchema,
      uischema: definitionUiSchema,
      renderers: vanillaRenderers,
      cells: vanillaCells,
      readonly: readOnly,
      onChange: ({ data }) => {
        const nextPayload = {
          ...payload,
          ...data,
        }
        onChange({ ...value, payload: nextPayload })
      },
    }),
  )
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

function RelationsPanel({ value }) {
  const relations = Array.isArray(value?.relations) ? value.relations : []
  const payload = value?.payload || {}
  return h(
    EditorFrame,
    {
      title: 'Relations',
      subtitle: 'Associated domain and menu links.',
    },
    relations.length === 0
      ? h('div', { style: { color: colors.muted, fontSize: 12 } }, 'No relations defined on this asset.')
      : h('ul', { style: { listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: 8 } },
          relations.map((rel, idx) =>
            h('li', { key: idx, style: { display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 } },
              h(Pill, { label: rel.type || 'relation', tone: colors.blueSoft, textColor: colors.blue }),
              h('span', { style: { color: colors.ink } }, rel.target_asset_id || rel.target || ''),
            )
          )
        ),
    h('div', { style: { marginTop: 12, fontSize: 12, color: colors.muted } },
      `Domain: ${payload.domain_id || '—'}  ·  Menus: ${Array.isArray(payload.menus) ? payload.menus.length : 0}`,
    ),
  )
}

function HistoryPanel({ value, validation }) {
  const payload = value?.payload || {}
  return h(
    EditorFrame,
    {
      title: 'Lifecycle snapshot',
      subtitle: 'Module structure overview.',
    },
    h('div', { style: { color: colors.muted, fontSize: 12, lineHeight: 1.6 } },
      `Module ID: ${payload.module_id || '—'}. Label: ${payload.label || '—'}. Validation: ${validation.valid ? 'ok' : 'review needed'}.`,
    ),
    validation.errors.length ? h('div', { style: { color: colors.red, background: colors.redSoft, padding: 10, borderRadius: 6, marginTop: 10, fontSize: 12 } }, validation.errors[0]) : null,
    validation.warnings.length ? h('div', { style: { color: colors.amber, background: colors.amberSoft, padding: 10, borderRadius: 6, marginTop: 10, fontSize: 12 } }, validation.warnings[0]) : null,
  )
}

export function ModuleEditorView({ value, onChange, readOnly = false }) {
  const document = useMemo(() => normalizeDocument(value), [value])
  const [tab, setTab] = useState('structured')
  const validation = useMemo(() => validateModuleDocument(document), [document])

  function commit(nextDocument) {
    onChange(nextDocument)
  }

  return h(
    'div',
    { style: { display: 'grid', gap: 14 } },
    h(
      'div',
      { style: { display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' } },
      h(TabButton, { active: tab === 'structured', onClick: () => setTab('structured') }, 'Structured Editor'),
      h(TabButton, { active: tab === 'source', onClick: () => setTab('source') }, 'Raw Source'),
      h(TabButton, { active: tab === 'relations', onClick: () => setTab('relations') }, 'Relations'),
      h(TabButton, { active: tab === 'history', onClick: () => setTab('history') }, 'History'),
      h('div', { style: { marginLeft: 'auto', display: 'flex', gap: 8, flexWrap: 'wrap' } },
        h(Pill, { label: validation.valid ? 'valid' : 'needs review', tone: validation.valid ? colors.greenSoft : colors.redSoft, textColor: validation.valid ? colors.green : colors.red }),
      ),
    ),
    tab === 'structured'
      ? h(
          'div',
          { style: { display: 'grid', gap: 14 } },
          h(ModuleDefinitionJsonFormsView, { value: document, onChange: commit, readOnly }),
        )
      : null,
    tab === 'source' ? h(RawSourceEditor, { value: document, onChange: commit, readOnly }) : null,
    tab === 'relations' ? h(RelationsPanel, { value: document }) : null,
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
    relations: asset.relations,
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

export { colors, buttonStyle, inputStyle, shellCardStyle, Pill }
