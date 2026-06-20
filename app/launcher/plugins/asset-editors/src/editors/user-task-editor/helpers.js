import { z } from 'zod'

export const userTaskDefinitionZodSchema = z.object({
  user_task_id: z.string().min(1, 'user_task_id is required'),
  task: z.string().min(1, 'task is required'),
  type: z.string().optional().default(''),
  name: z.string().optional().default(''),
  description: z.string().optional().default(''),
  user_actions: z.array(z.string()).optional().default([]),
  tools: z.array(z.string()).optional().default([]),
})

function asString(value) {
  return String(value ?? '').trim()
}

export function normalizeUserTaskDefinition(payload = {}) {
  return {
    user_task_id: asString(payload.user_task_id),
    task: asString(payload.task),
    type: asString(payload.type),
    name: asString(payload.name),
    description: asString(payload.description),
    user_actions: Array.isArray(payload.user_actions) ? payload.user_actions.map(asString) : [],
    tools: Array.isArray(payload.tools) ? payload.tools.map(asString) : [],
  }
}

export function createDefaultUserTaskDefinition() {
  return {
    user_task_id: 'user-task-new',
    task: '',
    type: '',
    name: '',
    description: '',
    user_actions: [],
    tools: [],
  }
}

export function validateUserTaskDocument(document = {}) {
  const payload = document.payload && typeof document.payload === 'object' ? document.payload : document
  const userTask = normalizeUserTaskDefinition(payload)
  const errors = []
  const warnings = []

  const result = userTaskDefinitionZodSchema.safeParse(userTask)
  if (!result.success) {
    errors.push(...result.error.issues.map((issue) => `${issue.path.join('.')} ${issue.message}`.trim()))
  }

  if (userTask.user_actions.length === 0) {
    warnings.push('user task has no user_actions defined')
  }

  if (userTask.tools.length === 0) {
    warnings.push('user task has no tools defined')
  }

  return {
    valid: errors.length === 0,
    userTask,
    errors,
    warnings,
  }
}
