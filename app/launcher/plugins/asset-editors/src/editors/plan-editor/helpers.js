import { z } from 'zod'

export const planDefinitionZodSchema = z.object({
  plan_id: z.string().min(1, 'plan_id is required'),
  description: z.string().optional().default(''),
  steps: z.array(z.object({
    step_id: z.string().optional().default(''),
    name: z.string().optional().default(''),
    type: z.string().optional().default(''),
  })).optional().default([]),
  tools: z.array(z.string()).optional().default([]),
  dependencies: z.array(z.string()).optional().default([]),
  execution_options: z.record(z.unknown()).optional().default({}),
})

function asString(value) {
  return String(value ?? '').trim()
}

export function normalizePlanDefinition(payload = {}) {
  return {
    plan_id: asString(payload.plan_id),
    description: asString(payload.description),
    steps: Array.isArray(payload.steps) ? payload.steps.map((s) => ({
      step_id: asString(s.step_id),
      name: asString(s.name),
      type: asString(s.type),
    })) : [],
    tools: Array.isArray(payload.tools) ? payload.tools.map(asString) : [],
    dependencies: Array.isArray(payload.dependencies) ? payload.dependencies.map(asString) : [],
    execution_options: payload.execution_options && typeof payload.execution_options === 'object'
      ? payload.execution_options
      : {},
  }
}

export function createDefaultPlanDefinition() {
  return {
    plan_id: 'plan-new',
    description: '',
    steps: [],
    tools: [],
    dependencies: [],
    execution_options: {},
  }
}

export function validatePlanDocument(document = {}) {
  const payload = document.payload && typeof document.payload === 'object' ? document.payload : document
  const plan = normalizePlanDefinition(payload)
  const errors = []
  const warnings = []

  const result = planDefinitionZodSchema.safeParse(plan)
  if (!result.success) {
    errors.push(...result.error.issues.map((issue) => `${issue.path.join('.')} ${issue.message}`.trim()))
  }

  if (plan.steps.length === 0) {
    warnings.push('plan has no steps defined')
  }

  if (plan.tools.length === 0) {
    warnings.push('plan has no tools defined')
  }

  return {
    valid: errors.length === 0,
    plan,
    errors,
    warnings,
  }
}
