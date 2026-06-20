import { z } from 'zod'

export const qaDefinitionZodSchema = z.object({
  question: z.string().min(1, 'question is required'),
  answer: z.string().min(1, 'answer is required'),
  intent: z.string().optional().default(''),
  source: z.string().optional().default(''),
  citations: z.array(z.string()).optional().default([]),
})

function asString(value) {
  return String(value ?? '').trim()
}

function asArray(value) {
  return Array.isArray(value) ? value : []
}

export function normalizeQaDefinition(payload = {}) {
  return {
    question: asString(payload.question),
    answer: asString(payload.answer),
    intent: asString(payload.intent),
    source: asString(payload.source),
    citations: asArray(payload.citations).map((c) => asString(c)).filter(Boolean),
  }
}

export function createDefaultQaDefinition() {
  return {
    question: '',
    answer: '',
    intent: '',
    source: '',
    citations: [],
  }
}

export function validateQaDocument(document = {}) {
  const payload = document.payload && typeof document.payload === 'object' ? document.payload : document
  const qa = normalizeQaDefinition(payload)
  const errors = []
  const warnings = []

  const result = qaDefinitionZodSchema.safeParse(qa)
  if (!result.success) {
    errors.push(...result.error.issues.map((issue) => `${issue.path.join('.')} ${issue.message}`.trim()))
  }

  if (!qa.intent) {
    warnings.push('intent is recommended for categorization')
  }

  if (!qa.source) {
    warnings.push('source is recommended for traceability')
  }

  if (qa.citations.length === 0) {
    warnings.push('No citations defined')
  }

  return {
    valid: errors.length === 0,
    qa,
    errors,
    warnings,
  }
}
