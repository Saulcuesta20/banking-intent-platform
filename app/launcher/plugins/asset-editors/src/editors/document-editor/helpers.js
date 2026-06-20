import { z } from 'zod'

export const documentDefinitionZodSchema = z.object({
  document_id: z.string().min(1, 'document_id is required'),
  title: z.string().min(1, 'title is required'),
  source: z.string().optional().default(''),
  content: z.string().optional().default(''),
  citations: z.array(z.string()).optional().default([]),
})

function asString(value) {
  return String(value ?? '').trim()
}

export function normalizeDocumentDefinition(payload = {}) {
  return {
    document_id: asString(payload.document_id),
    title: asString(payload.title),
    source: asString(payload.source),
    content: asString(payload.content),
    citations: Array.isArray(payload.citations) ? payload.citations.map(asString) : [],
  }
}

export function createDefaultDocumentDefinition() {
  return {
    document_id: 'doc-new',
    title: '',
    source: '',
    content: '',
    citations: [],
  }
}

export function validateDocumentDefinition(document = {}) {
  const payload = document.payload && typeof document.payload === 'object' ? document.payload : document
  const doc = normalizeDocumentDefinition(payload)
  const errors = []
  const warnings = []

  const result = documentDefinitionZodSchema.safeParse(doc)
  if (!result.success) {
    errors.push(...result.error.issues.map((issue) => `${issue.path.join('.')} ${issue.message}`.trim()))
  }

  if (!doc.source) {
    warnings.push('document has no source defined')
  }

  if (!doc.content) {
    warnings.push('document has no content defined')
  }

  if (doc.citations.length === 0) {
    warnings.push('document has no citations defined')
  }

  return {
    valid: errors.length === 0,
    doc,
    errors,
    warnings,
  }
}
