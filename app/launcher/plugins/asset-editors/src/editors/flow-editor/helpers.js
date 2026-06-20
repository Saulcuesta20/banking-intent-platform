import { z } from 'zod'

export const FLOW_LIFECYCLE_STATES = ['not_started', 'on_user_enter', 'cancelled', 'completed']

export const FLOW_ACTION_TYPES = ['front', 'back']

export const FRONT_IMPLEMENTATION_TYPES = ['show_form', 'open_panel', 'submit_search', 'custom']

export const BACK_IMPLEMENTATION_TYPES = ['tool_call', 'llm_tool', 'service_call', 'custom']

export const TOOL_TYPES = ['frontend_tool', 'backend_tool', 'llm_tool']

export const flowDefinitionZodSchema = z.object({
  flow_id: z.string().min(1, 'flow_id is required'),
  flow_name: z.string().min(1, 'flow_name is required'),
  purpose: z.string().min(1, 'purpose is required'),
  business_event: z.string().min(1, 'business_event is required'),
  user_task_refs: z.array(z.string().min(1)).min(1, 'user_task_refs must include at least one reference'),
  related_process_ids: z.array(z.string().min(1)).default([]),
  inputs: z.array(z.string().min(1)).default([]),
  outputs: z.array(z.string().min(1)).default([]),
  explanation: z.string().min(1, 'explanation is required'),
})

export const actionZodSchema = z.object({
  action_id: z.string().min(1, 'action_id is required'),
  type: z.enum(['front', 'back']),
  implementation_type: z.string().min(1, 'implementation_type is required'),
  label: z.string().default(''),
  triggers: z.string().default(''),
  description: z.string().default(''),
  lifecycle_state: z.enum(FLOW_LIFECYCLE_STATES),
  tool_id: z.string().nullable().optional(),
  tool_ids: z.array(z.string().min(1)).default([]),
})

export const toolZodSchema = z.object({
  tool_id: z.string().min(1, 'tool_id is required'),
  tool_type: z.enum(TOOL_TYPES),
  operation: z.string().min(1, 'operation is required'),
  resource: z.string().default(''),
  label: z.string().default(''),
  description: z.string().default(''),
  frontend_event: z.string().default(''),
  backend_protocol: z.string().default(''),
  endpoint: z.string().default(''),
  requires_approval: z.boolean().default(false),
})

export const userTaskZodSchema = z.object({
  user_task_id: z.string().min(1, 'user_task_id is required'),
  task: z.string().min(1, 'task is required'),
  type: z.literal('user_task'),
  name: z.string().min(1, 'name is required'),
  description: z.string().min(1, 'description is required'),
  user_actions: z.array(actionZodSchema).default([]),
  tools: z.array(toolZodSchema).default([]),
})

function asString(value) {
  return String(value ?? '').trim()
}

export function normalizeArray(value) {
  return Array.isArray(value)
    ? value.map((item) => asString(item)).filter(Boolean)
    : []
}

export function normalizeLifecycleState(value) {
  const candidate = asString(value).toLowerCase().replace(/-/g, '_')
  return FLOW_LIFECYCLE_STATES.includes(candidate) ? candidate : 'not_started'
}

export function normalizeImplementationType(value, actionType = '') {
  const candidate = asString(value).toLowerCase().replace(/-/g, '_')
  if (candidate) return candidate
  return actionType === 'back' ? 'tool_call' : 'show_form'
}

export function normalizeAction(action, index = 0) {
  const record = action && typeof action === 'object' ? action : {}
  const type = FLOW_ACTION_TYPES.includes(asString(record.type).toLowerCase()) ? asString(record.type).toLowerCase() : 'front'
  const toolIds = normalizeArray(record.tool_ids || record.toolIds)
  const toolId = asString(record.tool_id || toolIds[0] || '')
  return {
    action_id: asString(record.action_id || `action_${index + 1}`),
    type,
    implementation_type: normalizeImplementationType(record.implementation_type, type),
    label: asString(record.label),
    triggers: asString(record.triggers),
    description: asString(record.description),
    lifecycle_state: normalizeLifecycleState(record.lifecycle_state),
    tool_id: toolId || null,
    tool_ids: toolIds.length ? toolIds : (toolId ? [toolId] : []),
  }
}

export function normalizeTool(tool, index = 0, taskId = 'task') {
  const record = tool && typeof tool === 'object' ? tool : {}
  const toolType = TOOL_TYPES.includes(asString(record.tool_type).toLowerCase()) ? asString(record.tool_type).toLowerCase() : 'backend_tool'
  return {
    tool_id: asString(record.tool_id || `tool.${taskId}.${index + 1}`),
    tool_type: toolType,
    operation: asString(record.operation),
    resource: asString(record.resource),
    label: asString(record.label),
    description: asString(record.description),
    frontend_event: asString(record.frontend_event),
    backend_protocol: asString(record.backend_protocol),
    endpoint: asString(record.endpoint),
    requires_approval: Boolean(record.requires_approval),
  }
}

export function normalizeFlowTask(task, index = 0, flowId = 'flow') {
  if (typeof task === 'string') {
    return {
      id: `task-${index + 1}`,
      label: task,
      description: '',
      actions: [],
      tools: [],
      raw: {
        task,
        name: task,
        type: 'user_task',
        user_actions: [],
        tools: [],
      },
    }
  }
  const record = task && typeof task === 'object' ? task : {}
  const normalizedActions = Array.isArray(record.user_actions)
    ? record.user_actions.map((action, actionIndex) => normalizeAction(action, actionIndex))
    : []
  const normalizedTools = Array.isArray(record.tools)
    ? record.tools.map((tool, toolIndex) => normalizeTool(tool, toolIndex, record.user_task_id || record.task || flowId))
    : []
  return {
    id: asString(record.user_task_id || record.task || record.name || `task-${index + 1}`),
    label: asString(record.name || record.task || `Task ${index + 1}`),
    description: asString(record.description),
    actions: normalizedActions,
    tools: normalizedTools,
    raw: {
      ...record,
      user_task_id: asString(record.user_task_id || record.task || record.name || `task-${index + 1}`),
      task: asString(record.task || record.name || `task_${index + 1}`),
      type: asString(record.type || 'user_task'),
      name: asString(record.name || record.task || `Task ${index + 1}`),
      description: asString(record.description),
      user_actions: normalizedActions,
      tools: normalizedTools,
    },
  }
}

export function normalizeFlowDefinition(payload = {}) {
  return {
    flow_id: asString(payload.flow_id),
    flow_name: asString(payload.flow_name),
    purpose: asString(payload.purpose || payload.intent),
    business_event: asString(payload.business_event),
    user_task_refs: normalizeArray(payload.user_task_refs || payload.user_tasks),
    related_process_ids: normalizeArray(payload.related_process_ids),
    inputs: normalizeArray(payload.inputs),
    outputs: normalizeArray(payload.outputs),
    explanation: asString(payload.explanation),
  }
}

export function mergeFlowDefinition(payload = {}, definition = {}) {
  return {
    ...payload,
    ...definition,
    user_task_refs: normalizeArray(definition.user_task_refs),
    related_process_ids: normalizeArray(definition.related_process_ids),
    inputs: normalizeArray(definition.inputs),
    outputs: normalizeArray(definition.outputs),
  }
}

export function createDefaultFlowTask(flowId = 'flow', index = 0) {
  const taskId = `user_task.${flowId}.${index + 1}`
  return {
    user_task_id: taskId,
    task: `task_${index + 1}`,
    type: 'user_task',
    name: `New user task ${index + 1}`,
    description: '',
    user_actions: [
      {
        action_id: `action_${index + 1}.1`,
        type: 'front',
        implementation_type: 'show_form',
        label: '',
        triggers: '',
        description: '',
        lifecycle_state: 'not_started',
        tool_ids: [],
        tool_id: null,
      },
    ],
    tools: [],
  }
}

export function createDefaultAction(index = 0, actionType = 'front') {
  return {
    action_id: `action_${index + 1}`,
    type: actionType,
    implementation_type: actionType === 'back' ? 'tool_call' : 'show_form',
    label: '',
    triggers: '',
    description: '',
    lifecycle_state: 'not_started',
    tool_ids: [],
    tool_id: null,
  }
}

export function createDefaultTool(taskId = 'task', index = 0) {
  return {
    tool_id: `tool.${taskId}.${index + 1}`,
    tool_type: 'backend_tool',
    operation: '',
    resource: '',
    label: '',
    description: '',
    frontend_event: '',
    backend_protocol: '',
    endpoint: '',
    requires_approval: false,
  }
}

export function actionImplementationTypesFor(actionType = 'front') {
  return actionType === 'back' ? BACK_IMPLEMENTATION_TYPES : FRONT_IMPLEMENTATION_TYPES
}

export function validateFlowDocument(document = {}) {
  const payload = document.payload && typeof document.payload === 'object' ? document.payload : document
  const flow = normalizeFlowDefinition(payload)
  const tasks = Array.isArray(payload.user_tasks) ? payload.user_tasks.map((task, index) => normalizeFlowTask(task, index, flow.flow_id)) : []
  const errors = []
  const warnings = []

  const flowResult = flowDefinitionZodSchema.safeParse(flow)
  if (!flowResult.success) {
    errors.push(...flowResult.error.issues.map((issue) => `flow.${issue.path.join('.')} ${issue.message}`.trim()))
  }

  tasks.forEach((task, taskIndex) => {
    const result = validateTaskDraft(task.raw, taskIndex, flow.flow_id)
    result.errors.forEach((message) => errors.push(`user_tasks[${taskIndex}].${message}`))
    result.warnings.forEach((message) => warnings.push(`user_tasks[${taskIndex}].${message}`))
  })

  return {
    valid: errors.length === 0,
    flow,
    taskCount: tasks.length,
    errors,
    warnings,
  }
}

export function validateTaskDraft(task = {}, taskIndex = 0, flowId = 'flow') {
  const normalized = normalizeFlowTask(task, taskIndex, flowId)
  const errors = []
  const warnings = []

  const taskResult = userTaskZodSchema.safeParse({
    ...normalized.raw,
    user_actions: normalized.actions.map((action) => ({ ...action })),
    tools: normalized.tools.map((tool) => ({ ...tool })),
  })
  if (!taskResult.success) {
    errors.push(...taskResult.error.issues.map((issue) => `${issue.path.join('.')} ${issue.message}`.trim()))
  }

  normalized.actions.forEach((action, actionIndex) => {
    if (action.type === 'back') {
      const knownToolIds = new Set(normalized.tools.map((tool) => tool.tool_id))
      const referencedToolIds = action.tool_ids.length ? action.tool_ids : (action.tool_id ? [action.tool_id] : [])
      if (!referencedToolIds.length) {
        warnings.push(`user_actions[${actionIndex}] has no bound tool`)
      }
      referencedToolIds.forEach((toolId) => {
        if (toolId && !knownToolIds.has(toolId)) {
          warnings.push(`user_actions[${actionIndex}] references missing tool_id ${toolId}`)
        }
      })
    }
  })

  normalized.tools.forEach((tool, toolIndex) => {
    const result = toolZodSchema.safeParse(tool)
    if (!result.success) {
      errors.push(...result.error.issues.map((issue) => `tools[${toolIndex}].${issue.path.join('.')} ${issue.message}`.trim()))
    }
  })

  return {
    valid: errors.length === 0,
    errors,
    warnings,
    task: normalized,
  }
}
