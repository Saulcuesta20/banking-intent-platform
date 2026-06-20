import { z } from 'zod'

export const RULE_TYPES = ['validation', 'constraint', 'business_logic', 'gate', 'transformation']

export const OPERATORS = ['equals', 'not_equals', 'greater_than', 'less_than', 'contains', 'not_contains', 'in', 'not_in', 'is_empty', 'is_not_empty']

export const ACTION_TYPES = ['reject', 'approve', 'flag', 'transform', 'route', 'notify', 'block', 'allow']

export const conditionZodSchema = z.object({
  field: z.string().min(1, 'field is required'),
  operator: z.string().min(1, 'operator is required'),
  value: z.string().min(1, 'value is required'),
  description: z.string().default(''),
})

export const actionZodSchema = z.object({
  type: z.string().min(1, 'action type is required'),
  target: z.string().min(1, 'target is required'),
  value: z.string().default(''),
  description: z.string().default(''),
})

export const ruleDefinitionZodSchema = z.object({
  rule_id: z.string().min(1, 'rule_id is required'),
  rule_name: z.string().min(1, 'rule_name is required'),
  description: z.string().min(1, 'description is required'),
  domain: z.string().min(1, 'domain is required'),
  rule_type: z.enum(RULE_TYPES),
  priority: z.number().int().min(0).default(0),
  conditions: z.array(conditionZodSchema).default([]),
  actions: z.array(actionZodSchema).default([]),
  metadata: z.object({
    version: z.string().default('1.0.0'),
    author: z.string().default(''),
    tags: z.array(z.string()).default([]),
  }).default({}),
})

function asString(value) {
  return String(value ?? '').trim()
}

export function normalizeArray(value) {
  return Array.isArray(value)
    ? value.map((item) => asString(item)).filter(Boolean)
    : []
}

export function normalizeCondition(condition, index = 0) {
  const record = condition && typeof condition === 'object' ? condition : {}
  return {
    field: asString(record.field),
    operator: asString(record.operator || 'equals'),
    value: asString(record.value),
    description: asString(record.description),
  }
}

export function normalizeRuleAction(action, index = 0) {
  const record = action && typeof action === 'object' ? action : {}
  return {
    type: asString(record.type || 'allow'),
    target: asString(record.target),
    value: asString(record.value),
    description: asString(record.description),
  }
}

export function normalizeRuleDefinition(payload = {}) {
  const metadata = payload.metadata && typeof payload.metadata === 'object' ? payload.metadata : {}
  return {
    rule_id: asString(payload.rule_id),
    rule_name: asString(payload.rule_name),
    description: asString(payload.description),
    domain: asString(payload.domain),
    rule_type: RULE_TYPES.includes(asString(payload.rule_type)) ? asString(payload.rule_type) : 'validation',
    priority: Number(payload.priority) || 0,
    conditions: Array.isArray(payload.conditions)
      ? payload.conditions.map((cond, index) => normalizeCondition(cond, index))
      : [],
    actions: Array.isArray(payload.actions)
      ? payload.actions.map((action, index) => normalizeRuleAction(action, index))
      : [],
    metadata: {
      version: asString(metadata.version || '1.0.0'),
      author: asString(metadata.author),
      tags: normalizeArray(metadata.tags),
    },
  }
}

export function createDefaultCondition(index = 0) {
  return {
    field: '',
    operator: 'equals',
    value: '',
    description: '',
  }
}

export function createDefaultRuleAction(index = 0) {
  return {
    type: 'allow',
    target: '',
    value: '',
    description: '',
  }
}

export function validateRuleDocument(document = {}) {
  const payload = document.payload && typeof document.payload === 'object' ? document.payload : document
  const rule = normalizeRuleDefinition(payload)
  const errors = []
  const warnings = []

  const result = ruleDefinitionZodSchema.safeParse(rule)
  if (!result.success) {
    errors.push(...result.error.issues.map((issue) => `${issue.path.join('.')} ${issue.message}`.trim()))
  }

  if (rule.conditions.length === 0) {
    warnings.push('Rule has no conditions defined')
  }

  if (rule.actions.length === 0) {
    warnings.push('Rule has no actions defined')
  }

  rule.conditions.forEach((condition, index) => {
    if (!condition.field) {
      warnings.push(`conditions[${index}] has no field defined`)
    }
  })

  return {
    valid: errors.length === 0,
    rule,
    errors,
    warnings,
  }
}
