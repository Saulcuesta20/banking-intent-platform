import React, { useMemo, useState } from 'react'
import { JsonForms } from '@jsonforms/react'
import { vanillaCells, vanillaRenderers } from '@jsonforms/vanilla-renderers'

import definitionSchema from './flow-editor.schema.json'
import definitionUiSchema from './flow-editor.ui-schema.json'
import {
  actionImplementationTypesFor,
  BACK_IMPLEMENTATION_TYPES,
  createDefaultAction,
  createDefaultFlowTask,
  createDefaultTool,
  FLOW_ACTION_TYPES,
  FLOW_LIFECYCLE_STATES,
  normalizeAction,
  normalizeArray,
  normalizeFlowDefinition,
  normalizeFlowTask,
  normalizeLifecycleState,
  normalizeTool,
  validateFlowDocument,
  validateTaskDraft,
} from './helpers.js'

const h = React.createElement

export const colors = {
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

export function buttonStyle(primary = false) {
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

export const inputStyle = {
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

function asString(value) {
  return String(value ?? '').trim()
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

function normalizeDocument(value) {
  const document = clone(value)
  const payload = clone(document.payload || {})
  const flow = normalizeFlowDefinition(payload)
  const tasks = Array.isArray(payload.user_tasks)
    ? payload.user_tasks.map((task, index) => normalizeFlowTask(task, index, flow.flow_id))
    : []
  const relations = Array.isArray(document.relations) ? document.relations : []
  return {
    ...document,
    relations,
    payload: {
      ...payload,
      ...flow,
      user_tasks: tasks.map((task) => task.raw),
      user_task_refs: flow.user_task_refs,
      related_process_ids: flow.related_process_ids,
    },
  }
}

function FlowDefinitionJsonFormsView({ value, onChange, readOnly = false }) {
  const payload = clone(value?.payload)
  const definition = useMemo(() => normalizeFlowDefinition(payload), [payload])
  return h(
    EditorFrame,
    {
      title: 'Flow Definition',
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
          user_task_refs: normalizeArray(data?.user_task_refs),
          related_process_ids: normalizeArray(data?.related_process_ids),
          inputs: normalizeArray(data?.inputs),
          outputs: normalizeArray(data?.outputs),
        }
        onChange({ ...value, payload: nextPayload })
      },
    }),
  )
}

function RawSourceEditor({ value, onChange, readOnly = false }) {
  const [format, setFormat] = useState('json')
  const [text, setText] = useState(() => JSON.stringify(value ?? {}, null, 2))
  const [error, setError] = useState('')

  React.useEffect(() => {
    setText(format === 'json' ? JSON.stringify(value ?? {}, null, 2) : JSON.stringify(value ?? {}, null, 2))
    setError('')
  }, [value, format])

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
      actions: h(
        'select',
        { value: format, onChange: (event) => setFormat(event.target.value), style: inputStyle },
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

function RelationshipPreview({ value }) {
  const relations = Array.isArray(value?.relations) ? value.relations : []
  return h(
    EditorFrame,
    {
      title: 'Relationships',
      subtitle: 'Derived and allowed relations for the flow.',
    },
    relations.length
      ? relations.map((relation, index) =>
          h(
            'div',
            {
              key: `${relation.type}-${relation.target_asset_id}-${index}`,
              style: {
                display: 'grid',
                gridTemplateColumns: 'minmax(160px,.8fr) 26px minmax(0,1fr)',
                gap: 8,
                alignItems: 'center',
                padding: '8px 10px',
                border: `1px solid ${colors.line}`,
                borderRadius: 6,
                marginBottom: 8,
                background: '#fff',
              },
            },
            h('span', { style: { color: colors.ink, fontSize: 12 } }, relation.type),
            h('span', { style: { color: colors.muted, textAlign: 'center' } }, '→'),
            h('span', { style: { color: colors.muted, fontSize: 12 } }, relation.target_asset_id),
          ),
        )
      : h('div', { style: { color: colors.muted, fontSize: 12 } }, 'No relationships to preview.'),
  )
}

function TaskSummaryCard({ task, active, onEdit, onDuplicate, onRemove, readOnly }) {
  const primaryAction = task.actions[0] || null
  const lifecycle = primaryAction?.lifecycle_state || 'not_started'
  return h(
    'div',
    {
      style: {
        width: '100%',
        textAlign: 'left',
        border: `1px solid ${active ? colors.blue : colors.line}`,
        background: active ? colors.blueSoft : '#fff',
        borderRadius: 8,
        padding: 12,
        cursor: 'pointer',
      },
      onClick: onEdit,
    },
    h(
      'div',
      { style: { display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 } },
      h(
        'div',
        null,
        h('strong', { style: { color: colors.ink, display: 'block', marginBottom: 4 } }, task.label),
        h('div', { style: { color: colors.muted, fontSize: 12, lineHeight: 1.4 } }, task.description || task.id),
      ),
      h(Pill, { label: lifecycle }),
    ),
    h(
      'div',
      { style: { display: 'flex', gap: 6, marginTop: 10, flexWrap: 'wrap' } },
      h(Pill, { tone: colors.greenSoft, textColor: colors.green, label: `${task.actions.length} actions` }),
      h(Pill, { tone: colors.amberSoft, textColor: colors.amber, label: `${task.tools.length} tools` }),
      h(Pill, { tone: colors.blueSoft, textColor: colors.blue, label: task.id }),
    ),
    h(
      'div',
      { style: { display: 'flex', gap: 8, marginTop: 12 } },
      h('button', { type: 'button', style: buttonStyle(), onClick: (event) => { event.stopPropagation(); onEdit() } }, 'Edit'),
      !readOnly
        ? h('button', { type: 'button', style: { ...buttonStyle(), color: colors.ink, opacity: 0.75 }, onClick: (event) => { event.stopPropagation(); onDuplicate() } }, 'Duplicate')
        : null,
      !readOnly
        ? h('button', { type: 'button', style: { ...buttonStyle(), color: colors.red, opacity: 0.85 }, onClick: (event) => { event.stopPropagation(); onRemove() } }, 'Remove')
        : null,
    ),
  )
}

function actionDefaults(action, index) {
  const normalized = normalizeAction(action, index)
  return {
    ...normalized,
    implementation_type: normalized.implementation_type || 'show_form',
    lifecycle_state: normalizeLifecycleState(normalized.lifecycle_state),
  }
}

function toolDefaults(tool, index, taskId) {
  return normalizeTool(tool, index, taskId)
}

function FlowTaskIdentitySection({ draft, updateField, readOnly, validation }) {
  return h('section', { style: { border: `1px solid ${colors.line}`, borderRadius: 8, padding: 14 } },
    h('div', { style: { color: colors.ink, fontWeight: 800, marginBottom: 12 } }, 'Task identity'),
    h('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 } },
      h('label', { style: { display: 'grid', gap: 6, color: colors.muted, fontSize: 11, fontWeight: 800 } },
        'User Task ID',
        h('input', { value: draft.user_task_id || '', onChange: (e) => updateField('user_task_id', e.target.value), style: inputStyle, readOnly })
      ),
      h('label', { style: { display: 'grid', gap: 6, color: colors.muted, fontSize: 11, fontWeight: 800 } },
        'Task',
        h('input', { value: draft.task || '', onChange: (e) => updateField('task', e.target.value), style: inputStyle, readOnly })
      ),
      h('label', { style: { display: 'grid', gap: 6, color: colors.muted, fontSize: 11, fontWeight: 800 } },
        'Type',
        h('input', { value: draft.type || 'user_task', onChange: (e) => updateField('type', e.target.value), style: inputStyle, readOnly })
      ),
      h('label', { style: { display: 'grid', gap: 6, color: colors.muted, fontSize: 11, fontWeight: 800 } },
        'Name',
        h('input', { value: draft.name || '', onChange: (e) => updateField('name', e.target.value), style: inputStyle, readOnly })
      )
    ),
    h('label', { style: { display: 'grid', gap: 6, color: colors.muted, fontSize: 11, fontWeight: 800, marginTop: 12 } },
      'Description',
      h('textarea', { value: draft.description || '', onChange: (e) => updateField('description', e.target.value), style: { ...inputStyle, minHeight: 92, resize: 'vertical' }, readOnly })
    )
  )
}

function FlowTaskLifecycleSection({ validation }) {
  const lifecyclePills = FLOW_LIFECYCLE_STATES.map((state) => {
    const tone = state === 'completed' ? colors.greenSoft : state === 'cancelled' ? colors.redSoft : colors.blueSoft
    const textColor = state === 'completed' ? colors.green : state === 'cancelled' ? colors.red : colors.blue
    return h(Pill, { key: state, label: state, tone, textColor })
  })

  return h('section', { style: { border: `1px solid ${colors.line}`, borderRadius: 8, padding: 14, background: colors.canvas } },
    h('div', { style: { color: colors.ink, fontWeight: 800, marginBottom: 12 } }, 'Lifecycle and binding'),
    h('div', { style: { display: 'grid', gap: 10 } },
      h('div', null,
        h('div', { style: { color: colors.muted, fontSize: 11, fontWeight: 800, marginBottom: 6 } }, 'User action lifecycle'),
        h('div', { style: { display: 'flex', gap: 8, flexWrap: 'wrap' } }, ...lifecyclePills)
      ),
      h('div', null,
        h('div', { style: { color: colors.muted, fontSize: 11, fontWeight: 800, marginBottom: 6 } }, 'Back action binds to tools through tool_id / tool_ids'),
        h('div', { style: { color: colors.muted, fontSize: 12, lineHeight: 1.5 } }, 'The lifecycle belongs to the user action. Tool bindings point to the task tools and are validated together when the task is saved.')
      ),
      validation.errors.length
        ? h('div', { style: { color: colors.red, background: colors.redSoft, padding: 10, borderRadius: 6, fontSize: 12 } }, validation.errors[0])
        : null
    )
  )
}

function FlowTaskActionsSection({ actions, updateAction, readOnly, setDraft, addAction }) {
  return h('section', { style: { border: `1px solid ${colors.line}`, borderRadius: 8, padding: 14 } },
    h('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 12 } },
      h('div', { style: { color: colors.ink, fontWeight: 800 } }, 'User actions'),
      h('button', { type: 'button', style: buttonStyle(true), onClick: addAction, disabled: readOnly }, '+ Add action')
    ),
    actions.length
      ? h('div', { style: { display: 'grid', gap: 12 } },
          ...actions.map((action, index) => FlowTaskActionCard({ action, index, updateAction, readOnly, setDraft }))
        )
      : h('div', { style: { color: colors.muted, fontSize: 12 } }, 'No user actions yet.')
  )
}

function FlowTaskActionCard({ action, index, updateAction, readOnly, setDraft }) {
  return h('div', { key: action.action_id || index, style: { border: `1px solid ${colors.line}`, borderRadius: 8, padding: 12, background: colors.canvas } },
    h('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 8 } },
      h('input', { value: action.action_id || '', onChange: (e) => updateAction(index, { action_id: e.target.value }), style: inputStyle, placeholder: 'Action ID' }),
      h('select', { value: action.type || 'front', onChange: (e) => updateAction(index, { type: e.target.value }), style: inputStyle },
        FLOW_ACTION_TYPES.map((option) => h('option', { key: option, value: option }, option))
      ),
      h('select', { value: action.implementation_type || (action.type === 'back' ? 'tool_call' : 'show_form'), onChange: (e) => updateAction(index, { implementation_type: e.target.value }), style: inputStyle },
        actionImplementationTypesFor(action.type).map((option) => h('option', { key: option, value: option }, option))
      ),
      h('select', { value: normalizeLifecycleState(action.lifecycle_state), onChange: (e) => updateAction(index, { lifecycle_state: e.target.value }), style: inputStyle },
        FLOW_LIFECYCLE_STATES.map((option) => h('option', { key: option, value: option }, option))
      )
    ),
    h('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 8, marginTop: 10 } },
      h('input', { value: action.label || '', onChange: (e) => updateAction(index, { label: e.target.value }), style: inputStyle, placeholder: 'Label' }),
      h('input', { value: action.triggers || '', onChange: (e) => updateAction(index, { triggers: e.target.value }), style: inputStyle, placeholder: 'Trigger / condition' })
    ),
    h('textarea', { value: action.description || '', onChange: (e) => updateAction(index, { description: e.target.value }), style: { ...inputStyle, minHeight: 68, resize: 'vertical', marginTop: 8 }, placeholder: 'Description' }),
    h('input', {
      value: Array.isArray(action.tool_ids) ? action.tool_ids.join(', ') : '',
      onChange: (e) => {
        const toolIds = e.target.value.split(',').map((part) => part.trim()).filter(Boolean)
        updateAction(index, { tool_ids: toolIds, tool_id: toolIds[0] || null })
      },
      style: inputStyle,
      placeholder: 'Tool IDs separated by commas'
    }),
    h('div', { style: { display: 'flex', justifyContent: 'space-between', marginTop: 10, alignItems: 'center' } },
      h(Pill, { tone: action.lifecycle_state === 'completed' ? colors.greenSoft : colors.blueSoft, textColor: action.lifecycle_state === 'completed' ? colors.green : colors.blue, label: action.lifecycle_state || 'not_started' }),
      !readOnly ? h('button', { type: 'button', style: buttonStyle(), onClick: () => setDraft((current) => ({ ...current, user_actions: current.user_actions.filter((_, i) => i !== index) })) }, 'Remove') : null
    )
  )
}

function FlowTaskToolsSection({ tools, updateTool, readOnly, setDraft, addTool }) {
  return h('section', { style: { border: `1px solid ${colors.line}`, borderRadius: 8, padding: 14 } },
    h('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 12 } },
      h('div', { style: { color: colors.ink, fontWeight: 800 } }, 'Tools'),
      h('button', { type: 'button', style: buttonStyle(true), onClick: addTool, disabled: readOnly }, '+ Add tool')
    ),
    tools.length
      ? h('div', { style: { display: 'grid', gap: 12 } },
          ...tools.map((tool, index) => FlowTaskToolCard({ tool, index, updateTool, readOnly, setDraft }))
        )
      : h('div', { style: { color: colors.muted, fontSize: 12 } }, 'No tools yet.')
  )
}

function FlowTaskToolCard({ tool, index, updateTool, readOnly, setDraft }) {
  return h('div', { key: tool.tool_id || index, style: { border: `1px solid ${colors.line}`, borderRadius: 8, padding: 12, background: colors.canvas } },
    h('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 8 } },
      h('input', { value: tool.tool_id || '', onChange: (e) => updateTool(index, { tool_id: e.target.value }), style: inputStyle, placeholder: 'Tool ID' }),
      h('select', { value: tool.tool_type || 'backend_tool', onChange: (e) => updateTool(index, { tool_type: e.target.value }), style: inputStyle },
        ['frontend_tool', 'backend_tool', 'llm_tool'].map((option) => h('option', { key: option, value: option }, option))
      ),
      h('input', { value: tool.operation || '', onChange: (e) => updateTool(index, { operation: e.target.value }), style: inputStyle, placeholder: 'Operation' }),
      h('input', { value: tool.resource || '', onChange: (e) => updateTool(index, { resource: e.target.value }), style: inputStyle, placeholder: 'Resource' })
    ),
    h('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 8, marginTop: 10 } },
      h('input', { value: tool.label || '', onChange: (e) => updateTool(index, { label: e.target.value }), style: inputStyle, placeholder: 'Label' }),
      h('input', { value: tool.description || '', onChange: (e) => updateTool(index, { description: e.target.value }), style: inputStyle, placeholder: 'Description' })
    ),
    h('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 8, marginTop: 8 } },
      h('input', { value: tool.frontend_event || '', onChange: (e) => updateTool(index, { frontend_event: e.target.value }), style: inputStyle, placeholder: 'Frontend event' }),
      h('input', { value: tool.backend_protocol || '', onChange: (e) => updateTool(index, { backend_protocol: e.target.value }), style: inputStyle, placeholder: 'Backend protocol' }),
      h('input', { value: tool.endpoint || '', onChange: (e) => updateTool(index, { endpoint: e.target.value }), style: inputStyle, placeholder: 'Endpoint' })
    ),
    h('div', { style: { display: 'flex', justifyContent: 'space-between', marginTop: 10, alignItems: 'center' } },
      h(Pill, { tone: colors.greenSoft, textColor: colors.green, label: tool.tool_type || 'backend_tool' }),
      !readOnly ? h('button', { type: 'button', style: buttonStyle(), onClick: () => setDraft((current) => ({ ...current, tools: current.tools.filter((_, i) => i !== index) })) }, 'Remove') : null
    )
  )
}

function FlowTaskModal({ open, task, taskIndex, flowId, onClose, onSave, readOnly = false }) {
  const [draft, setDraft] = useState(() => normalizeFlowTask(task || createDefaultFlowTask(flowId, 0), 0, flowId).raw)

  React.useEffect(() => {
    setDraft(normalizeFlowTask(task || createDefaultFlowTask(flowId, 0), taskIndex >= 0 ? taskIndex : 0, flowId).raw)
  }, [flowId, task, taskIndex, open])

  const actions = Array.isArray(draft.user_actions) ? draft.user_actions : []
  const tools = Array.isArray(draft.tools) ? draft.tools : []
  const validation = useMemo(() => {
    return validateTaskDraft(draft, taskIndex >= 0 ? taskIndex : 0, flowId)
  }, [draft, flowId])

  function updateField(key, value) {
    setDraft((current) => ({ ...current, [key]: value }))
  }

  function updateAction(index, patch) {
    setDraft((current) => ({
      ...current,
      user_actions: current.user_actions.map((action, actionIndex) => {
        if (actionIndex !== index) return action
        const next = { ...action, ...patch }
        if (next.type === 'back' && !BACK_IMPLEMENTATION_TYPES.includes(next.implementation_type)) {
          next.implementation_type = 'tool_call'
        }
        if (next.type === 'front' && !['show_form', 'open_panel', 'submit_search', 'custom'].includes(next.implementation_type)) {
          next.implementation_type = 'show_form'
        }
        next.lifecycle_state = normalizeLifecycleState(next.lifecycle_state)
        const toolIds = normalizeArray(next.tool_ids)
        next.tool_ids = toolIds
        next.tool_id = toolIds[0] || asString(next.tool_id) || null
        return next
      }),
    }))
  }

  function updateTool(index, patch) {
    setDraft((current) => ({
      ...current,
      tools: current.tools.map((tool, toolIndex) => (toolIndex === index ? { ...tool, ...patch } : tool)),
    }))
  }

  function addAction() {
    setDraft((current) => ({
      ...current,
      user_actions: [...current.user_actions, createDefaultAction(current.user_actions.length, 'front')],
    }))
  }

  function addTool() {
    setDraft((current) => ({
      ...current,
      tools: [...current.tools, createDefaultTool(current.user_task_id || current.task || flowId, current.tools.length)],
    }))
  }

  function save() {
    const normalized = {
      ...draft,
      user_task_id: asString(draft.user_task_id || `user_task.${flowId}.${taskIndex >= 0 ? taskIndex + 1 : 1}`),
      task: asString(draft.task || draft.name || `task_${taskIndex >= 0 ? taskIndex + 1 : 1}`),
      type: asString(draft.type || 'user_task'),
      name: asString(draft.name || draft.task || 'New user task'),
      description: asString(draft.description),
      user_actions: (draft.user_actions || []).map((action, index) => actionDefaults(action, index)),
      tools: (draft.tools || []).map((tool, index) => toolDefaults(tool, index, draft.user_task_id || draft.task || flowId)),
    }
    onSave(normalized, taskIndex)
  }

  if (!open) return null

  const overlayStyle = {
    position: 'fixed',
    inset: 0,
    background: 'rgba(8,15,28,.42)',
    display: 'grid',
    placeItems: 'center',
    zIndex: 80,
    padding: 24,
  }

  const dialogStyle = {
    width: 'min(1180px, 100%)',
    maxHeight: '92vh',
    overflow: 'auto',
    background: '#fff',
    borderRadius: 12,
    border: `1px solid ${colors.line}`,
    boxShadow: '0 30px 90px rgba(16,33,61,.25)',
  }

  return h('div', { style: overlayStyle, onClick: onClose },
    h('div', { role: 'dialog', 'aria-modal': 'true', onClick: (e) => e.stopPropagation(), style: dialogStyle },
      h('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16, padding: '16px 18px', borderBottom: `1px solid ${colors.line}` } },
        h('div', null,
          h('strong', { style: { color: colors.ink, fontSize: 16 } }, 'Edit user task'),
          h('div', { style: { color: colors.muted, fontSize: 12, marginTop: 4 } }, 'Task bindings, lifecycle, actions, and tools.')
        ),
        h('div', { style: { display: 'flex', gap: 8 } },
          h('button', { type: 'button', style: buttonStyle(), onClick: onClose }, 'Cancel'),
          h('button', { type: 'button', style: buttonStyle(true), disabled: readOnly, onClick: save }, 'Save draft')
        )
      ),
      h('div', { style: { padding: 18, display: 'grid', gap: 18 } },
        h('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 18 } },
          FlowTaskIdentitySection({ draft, updateField, readOnly, validation }),
          FlowTaskLifecycleSection({ validation })
        ),
        FlowTaskActionsSection({ actions, updateAction, readOnly, setDraft, addAction }),
        FlowTaskToolsSection({ tools, updateTool, readOnly, setDraft, addTool })
      )
    )
  )
}

function FlowTaskList({ tasks, activeIndex, onEdit, onDuplicate, onRemove, readOnly }) {
  return h(
    'section',
    {
      style: {
        border: `1px solid ${colors.line}`,
        borderRadius: 8,
        background: colors.panel,
        padding: 16,
      },
    },
    h(
      'div',
      { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 } },
      h('div', { style: { color: colors.ink, fontSize: 14, fontWeight: 800 } }, 'User Tasks'),
      h('div', { style: { display: 'flex', gap: 8 } }, h(Pill, { label: `${tasks.length} tasks`, tone: colors.blueSoft, textColor: colors.blue })),
    ),
    tasks.length
      ? h(
          'div',
          { style: { display: 'grid', gap: 10 } },
          ...tasks.map((task, index) =>
            h(TaskSummaryCard, {
              key: task.id || index,
              task,
              active: index === activeIndex,
              onEdit: () => onEdit(index),
              onDuplicate: () => onDuplicate(index),
              onRemove: () => onRemove(index),
              readOnly,
            }),
          ),
        )
      : h('div', { style: { color: colors.muted, fontSize: 12 } }, 'No user tasks yet.'),
    !readOnly
      ? h('div', { style: { marginTop: 12, display: 'flex', justifyContent: 'flex-end' } }, h('button', { type: 'button', style: buttonStyle(true), onClick: () => onEdit(tasks.length) }, '+ Add task'))
      : null,
  )
}

function HistoryPanel({ value, validation }) {
  const payload = value?.payload || {}
  const tasks = Array.isArray(payload.user_tasks) ? payload.user_tasks.map((task, index) => normalizeFlowTask(task, index, payload.flow_id)) : []
  return h(
    'section',
    {
      style: {
        border: `1px solid ${colors.line}`,
        borderRadius: 8,
        background: colors.panel,
        padding: 16,
      },
    },
    h('div', { style: { color: colors.ink, fontSize: 14, fontWeight: 800, marginBottom: 10 } }, 'Lifecycle snapshot'),
    h('div', { style: { color: colors.muted, fontSize: 12, lineHeight: 1.6 } }, `Tasks: ${tasks.length}. Validation: ${validation.valid ? 'ok' : 'review needed'}.`),
    validation.errors.length ? h('div', { style: { color: colors.red, background: colors.redSoft, padding: 10, borderRadius: 6, marginTop: 10, fontSize: 12 } }, validation.errors[0]) : null,
    validation.warnings.length ? h('div', { style: { color: colors.amber, background: colors.amberSoft, padding: 10, borderRadius: 6, marginTop: 10, fontSize: 12 } }, validation.warnings[0]) : null,
  )
}

export function FlowCanvasView({ value, onChange, readOnly = false }) {
  const document = useMemo(() => normalizeDocument(value), [value])
  const payload = document.payload || {}
  const tasks = Array.isArray(payload.user_tasks)
    ? payload.user_tasks.map((task, index) => normalizeFlowTask(task, index, payload.flow_id))
    : []
  const [tab, setTab] = useState('structured')
  const [activeTaskIndex, setActiveTaskIndex] = useState(0)
  const [taskEditorIndex, setTaskEditorIndex] = useState(null)
  const validation = useMemo(() => validateFlowDocument(document), [document])
  const activeIndex = Math.min(activeTaskIndex, Math.max(tasks.length - 1, 0))
  const activeTask = tasks[activeIndex] || null
  const editingTask = taskEditorIndex == null ? null : tasks[taskEditorIndex] || null

  function commit(nextDocument) {
    onChange(nextDocument)
  }

  function commitPayload(nextPayload) {
    commit({ ...document, payload: nextPayload })
  }

  function commitTasks(nextTasks) {
    const nextPayload = {
      ...payload,
      user_tasks: nextTasks.map((task) => task.raw),
      user_task_refs: normalizeArray(payload.user_task_refs.length ? payload.user_task_refs : nextTasks.map((task) => task.id)),
    }
    commitPayload(nextPayload)
  }

  function openTaskEditor(index) {
    setTaskEditorIndex(index)
    setActiveTaskIndex(Math.max(0, Math.min(index, tasks.length - 1)))
  }

  function saveTaskDraft(nextTask, index) {
    const nextTasks = [...tasks]
    if (index >= 0 && index < nextTasks.length) {
      nextTasks[index] = normalizeFlowTask(nextTask, index, payload.flow_id)
    } else {
      nextTasks.push(normalizeFlowTask(nextTask, nextTasks.length, payload.flow_id))
      setActiveTaskIndex(nextTasks.length - 1)
    }
    commitTasks(nextTasks)
    setTaskEditorIndex(null)
  }

  function duplicateTask(index) {
    const task = tasks[index]
    if (!task) return
    const nextTask = normalizeFlowTask({
      ...task.raw,
      user_task_id: `${task.id}.copy`,
      task: `${task.raw.task || task.label} copy`,
      name: `${task.label} copy`,
    }, tasks.length, payload.flow_id)
    commitTasks([...tasks, nextTask])
  }

  function removeTask(index) {
    const nextTasks = tasks.filter((_, taskIndex) => taskIndex !== index)
    commitTasks(nextTasks)
    setActiveTaskIndex(Math.max(0, index - 1))
  }

  return h(
    'div',
    { style: { display: 'grid', gap: 14 } },
    h(
      'div',
      { style: { display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' } },
      h(TabButton, { active: tab === 'structured', onClick: () => setTab('structured') }, 'Structured Editor'),
      h(TabButton, { active: tab === 'source', onClick: () => setTab('source') }, 'Raw Source'),
      h(TabButton, { active: tab === 'relationships', onClick: () => setTab('relationships') }, 'Relationships'),
      h(TabButton, { active: tab === 'history', onClick: () => setTab('history') }, 'History'),
      h('div', { style: { marginLeft: 'auto', display: 'flex', gap: 8, flexWrap: 'wrap' } }, h(Pill, { label: validation.valid ? 'valid' : 'needs review', tone: validation.valid ? colors.greenSoft : colors.redSoft, textColor: validation.valid ? colors.green : colors.red }), h(Pill, { label: `${tasks.length} user tasks` })),
    ),
    tab === 'structured'
      ? h(
          'div',
          { style: { display: 'grid', gap: 14 } },
          h(FlowDefinitionJsonFormsView, { value: document, onChange: commit, readOnly }),
          h(
            'div',
            { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 14 } },
            h(FlowTaskList, {
              tasks,
              activeIndex,
              onEdit: (index) => openTaskEditor(index),
              onDuplicate: duplicateTask,
              onRemove: removeTask,
              readOnly,
            }),
            h(
              'div',
              { style: { display: 'grid', gap: 14 } },
              h(RelationshipPreview, { value: document }),
              h(HistoryPanel, { value: document, validation }),
            ),
          ),
        )
      : null,
    tab === 'source' ? h(RawSourceEditor, { value: document, onChange: commit, readOnly }) : null,
    tab === 'relationships' ? h(RelationshipPreview, { value: document }) : null,
    tab === 'history' ? h(HistoryPanel, { value: document, validation }) : null,
    h(FlowTaskModal, {
      open: taskEditorIndex !== null,
      task: editingTask ? editingTask.raw : createDefaultFlowTask(payload.flow_id || 'flow', tasks.length),
      taskIndex: taskEditorIndex == null ? -1 : taskEditorIndex,
      flowId: payload.flow_id || 'flow',
      onClose: () => setTaskEditorIndex(null),
      onSave: saveTaskDraft,
      readOnly,
    }),
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
  delete stored.status
  delete stored.source_refs
  delete stored.evidence
  if (stored.payload) {
    delete stored.payload.asset_set_id
    delete stored.payload.asset_set_version
  }
  return stored
}
