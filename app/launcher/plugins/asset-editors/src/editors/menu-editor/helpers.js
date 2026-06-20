import { z } from 'zod'

export const menuDefinitionZodSchema = z.object({
  id: z.string().min(1, 'id is required'),
  label: z.string().min(1, 'label is required'),
  path: z.string().min(1, 'path is required'),
  module_id: z.string().min(1, 'module_id is required'),
  domain_id: z.string().min(1, 'domain_id is required'),
})

function asString(value) {
  return String(value ?? '').trim()
}

export function normalizeMenuItem(item = {}) {
  return {
    id: asString(item.id),
    label: asString(item.label),
    path: asString(item.path),
    module_id: asString(item.module_id),
    domain_id: asString(item.domain_id),
  }
}

export function normalizeMenuDefinition(payload = {}) {
  return {
    id: asString(payload.id),
    label: asString(payload.label),
    path: asString(payload.path),
    module_id: asString(payload.module_id),
    domain_id: asString(payload.domain_id),
  }
}

export function createDefaultMenuItem() {
  return {
    id: 'menu-new',
    label: 'New Menu',
    path: '/new/menu',
    module_id: '',
    domain_id: '',
  }
}

export function validateMenuDocument(document = {}) {
  const payload = document.payload && typeof document.payload === 'object' ? document.payload : document
  const menu = normalizeMenuDefinition(payload)
  const errors = []
  const warnings = []

  const result = menuDefinitionZodSchema.safeParse(menu)
  if (!result.success) {
    errors.push(...result.error.issues.map((issue) => `${issue.path.join('.')} ${issue.message}`.trim()))
  }

  if (!menu.path.startsWith('/')) {
    warnings.push('path should start with /')
  }

  if (!menu.id.includes('.')) {
    warnings.push('id may be missing a dot-separated prefix (e.g. menu.loan.create)')
  }

  return {
    valid: errors.length === 0,
    menu,
    errors,
    warnings,
  }
}
