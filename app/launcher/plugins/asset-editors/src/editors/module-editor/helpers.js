import { z } from 'zod'

export const moduleDefinitionZodSchema = z.object({
  module_id: z.string().min(1, 'module_id is required'),
  domain_id: z.string().min(1, 'domain_id is required'),
  label: z.string().min(1, 'label is required'),
  description: z.string().optional(),
  menus: z.array(z.string()).optional(),
})

function asString(value) {
  return String(value ?? '').trim()
}

export function normalizeModuleDefinition(payload = {}) {
  return {
    module_id: asString(payload.module_id),
    domain_id: asString(payload.domain_id),
    label: asString(payload.label),
    description: asString(payload.description),
    menus: Array.isArray(payload.menus) ? payload.menus : [],
  }
}

export function createDefaultModule() {
  return {
    module_id: 'module-new',
    domain_id: '',
    label: 'New Module',
    description: '',
    menus: [],
  }
}

export function validateModuleDocument(document = {}) {
  const payload = document.payload && typeof document.payload === 'object' ? document.payload : document
  const module_ = normalizeModuleDefinition(payload)
  const errors = []
  const warnings = []

  const result = moduleDefinitionZodSchema.safeParse(module_)
  if (!result.success) {
    errors.push(...result.error.issues.map((issue) => `${issue.path.join('.')} ${issue.message}`.trim()))
  }

  if (!module_.module_id.includes('.')) {
    warnings.push('module_id may be missing a dot-separated prefix (e.g. module.lending)')
  }

  if (module_.menus.length === 0) {
    warnings.push('no menus linked to this module')
  }

  return {
    valid: errors.length === 0,
    module: module_,
    errors,
    warnings,
  }
}
