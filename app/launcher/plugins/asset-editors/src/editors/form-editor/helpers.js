import { z } from 'zod'

const formFieldZodSchema = z.object({
  field_id: z.string().optional(),
  name: z.string().optional(),
  type: z.string().optional(),
  required: z.boolean().optional(),
})

export const formDefinitionZodSchema = z.object({
  form_id: z.string().min(1, 'form_id is required'),
  module_id: z.string().min(1, 'module_id is required'),
  fields: z.array(formFieldZodSchema).optional(),
  layout: z.string().optional(),
  validation: z.string().optional(),
})

function asString(value) {
  return String(value ?? '').trim()
}

export function normalizeFormField(field = {}) {
  return {
    field_id: asString(field.field_id),
    name: asString(field.name),
    type: asString(field.type),
    required: Boolean(field.required),
  }
}

export function normalizeFormDefinition(payload = {}) {
  return {
    form_id: asString(payload.form_id),
    module_id: asString(payload.module_id),
    fields: Array.isArray(payload.fields) ? payload.fields.map(normalizeFormField) : [],
    layout: asString(payload.layout),
    validation: asString(payload.validation),
  }
}

export function createDefaultForm() {
  return {
    form_id: 'form-new',
    module_id: '',
    fields: [],
    layout: '',
    validation: '',
  }
}

export function validateFormDocument(document = {}) {
  const payload = document.payload && typeof document.payload === 'object' ? document.payload : document
  const form = normalizeFormDefinition(payload)
  const errors = []
  const warnings = []

  const result = formDefinitionZodSchema.safeParse(form)
  if (!result.success) {
    errors.push(...result.error.issues.map((issue) => `${issue.path.join('.')} ${issue.message}`.trim()))
  }

  if (!form.form_id.includes('.')) {
    warnings.push('form_id may be missing a dot-separated prefix (e.g. form.lending.apply)')
  }

  if (form.fields.length === 0) {
    warnings.push('no fields defined for this form')
  }

  if (!form.layout) {
    warnings.push('layout is not set')
  }

  return {
    valid: errors.length === 0,
    form,
    errors,
    warnings,
  }
}
