import { z } from 'zod'

export const domainDefinitionZodSchema = z.object({
  domainId: z.string().min(1, 'domainId is required'),
  label: z.string().min(1, 'label is required'),
  description: z.string().min(1, 'description is required'),
  order: z.number().int().default(0),
})

function asString(value) {
  return String(value ?? '').trim()
}

function asInt(value) {
  const n = Number(value)
  return Number.isFinite(n) ? Math.floor(n) : 0
}

export function normalizeDomainDefinition(payload = {}) {
  return {
    domainId: asString(payload.domainId),
    label: asString(payload.label),
    description: asString(payload.description),
    order: asInt(payload.order),
  }
}

export function createDefaultDomain() {
  return {
    domainId: '',
    label: '',
    description: '',
    order: 0,
  }
}

export function normalizeDomain(domain = {}) {
  const payload = domain.payload && typeof domain.payload === 'object' ? domain.payload : domain
  return {
    ...domain,
    payload: {
      ...payload,
      ...normalizeDomainDefinition(payload),
    },
  }
}

export function validateDomainDocument(document = {}) {
  const payload = document.payload && typeof document.payload === 'object' ? document.payload : document
  const domain = normalizeDomainDefinition(payload)
  const errors = []
  const warnings = []

  const result = domainDefinitionZodSchema.safeParse(domain)
  if (!result.success) {
    errors.push(...result.error.issues.map((issue) => `${issue.path.join('.')} ${issue.message}`.trim()))
  }

  if (domain.order === 0) {
    warnings.push('order is set to 0, consider assigning a meaningful display order')
  }

  return {
    valid: errors.length === 0,
    domain,
    errors,
    warnings,
  }
}
