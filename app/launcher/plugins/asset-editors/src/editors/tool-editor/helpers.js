import { z } from 'zod'

const toolTypeEnum = z.enum(['frontend_tool', 'backend_tool', 'llm_tool'])

export const toolDefinitionZodSchema = z.object({
  tool_id: z.string().min(1, 'tool_id is required'),
  tool_type: toolTypeEnum,
  operation: z.string().min(1, 'operation is required'),
  resource: z.string().min(1, 'resource is required'),
  label: z.string().optional().default(''),
  description: z.string().optional().default(''),
})

function asString(value) {
  return String(value ?? '').trim()
}

export function normalizeToolDefinition(payload = {}) {
  return {
    tool_id: asString(payload.tool_id),
    tool_type: asString(payload.tool_type),
    operation: asString(payload.operation),
    resource: asString(payload.resource),
    label: asString(payload.label),
    description: asString(payload.description),
  }
}

export function createDefaultToolDefinition() {
  return {
    tool_id: 'tool-new',
    tool_type: 'backend_tool',
    operation: '',
    resource: '',
    label: '',
    description: '',
  }
}

export function validateToolDocument(document = {}) {
  const payload = document.payload && typeof document.payload === 'object' ? document.payload : document
  const tool = normalizeToolDefinition(payload)
  const errors = []
  const warnings = []

  const result = toolDefinitionZodSchema.safeParse(tool)
  if (!result.success) {
    errors.push(...result.error.issues.map((issue) => `${issue.path.join('.')} ${issue.message}`.trim()))
  }

  if (tool.tool_id && !tool.tool_id.includes('.')) {
    warnings.push('tool_id may be missing a dot-separated prefix (e.g. tool.api.transfer)')
  }

  if (!tool.label) {
    warnings.push('label is recommended for display purposes')
  }

  return {
    valid: errors.length === 0,
    tool,
    errors,
    warnings,
  }
}
