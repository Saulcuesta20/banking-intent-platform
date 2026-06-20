import test from 'node:test'
import assert from 'node:assert/strict'

import {
  createDefaultDocumentDefinition,
  documentDefinitionZodSchema,
  normalizeDocumentDefinition,
  validateDocumentDefinition,
} from './helpers.js'

test('normalizeDocumentDefinition keeps contract fields aligned', () => {
  const definition = normalizeDocumentDefinition({
    document_id: 'doc-loan-policy',
    title: 'Loan Policy Document',
    source: 'https://example.com/policy',
    content: 'This document outlines the loan policy for all borrowers.',
    citations: ['https://example.com/ref1', 'https://example.com/ref2'],
  })

  assert.equal(definition.document_id, 'doc-loan-policy')
  assert.equal(definition.title, 'Loan Policy Document')
  assert.equal(definition.source, 'https://example.com/policy')
  assert.equal(definition.content, 'This document outlines the loan policy for all borrowers.')
  assert.equal(definition.citations.length, 2)
  assert.equal(definition.citations[0], 'https://example.com/ref1')
  assert.equal(definition.citations[1], 'https://example.com/ref2')
})

test('validateDocumentDefinition accepts a valid document', () => {
  const result = validateDocumentDefinition({
    payload: {
      document_id: 'doc-loan-policy',
      title: 'Loan Policy Document',
      source: 'https://example.com/policy',
      content: 'Loan policy content',
      citations: ['https://example.com/ref1'],
    },
  })

  assert.equal(result.valid, true)
  assert.equal(result.errors.length, 0)
})

test('validateDocumentDefinition flags missing required fields', () => {
  const result = validateDocumentDefinition({
    payload: {
      document_id: '',
      title: '',
      source: '',
      content: '',
      citations: [],
    },
  })

  assert.equal(result.valid, false)
  assert.ok(result.errors.some((error) => error.includes('document_id')))
  assert.ok(result.errors.some((error) => error.includes('title')))
})

test('validateDocumentDefinition warns about empty source', () => {
  const result = validateDocumentDefinition({
    payload: {
      document_id: 'doc-loan-policy',
      title: 'Loan Policy Document',
      source: '',
      content: 'Loan policy content',
      citations: ['https://example.com/ref1'],
    },
  })

  assert.ok(result.warnings.some((warning) => warning.includes('source')))
})

test('validateDocumentDefinition warns about empty content', () => {
  const result = validateDocumentDefinition({
    payload: {
      document_id: 'doc-loan-policy',
      title: 'Loan Policy Document',
      source: 'https://example.com/policy',
      content: '',
      citations: ['https://example.com/ref1'],
    },
  })

  assert.ok(result.warnings.some((warning) => warning.includes('content')))
})

test('validateDocumentDefinition warns about empty citations', () => {
  const result = validateDocumentDefinition({
    payload: {
      document_id: 'doc-loan-policy',
      title: 'Loan Policy Document',
      source: 'https://example.com/policy',
      content: 'Loan policy content',
      citations: [],
    },
  })

  assert.ok(result.warnings.some((warning) => warning.includes('citations')))
})

test('createDefaultDocumentDefinition creates valid shape', () => {
  const doc = createDefaultDocumentDefinition()
  assert.equal(doc.document_id, 'doc-new')
  assert.equal(doc.title, '')
  assert.equal(doc.source, '')
  assert.equal(doc.content, '')
  assert.deepEqual(doc.citations, [])
})

test('normalizeDocumentDefinition handles missing fields', () => {
  const definition = normalizeDocumentDefinition({})
  assert.equal(definition.document_id, '')
  assert.equal(definition.title, '')
  assert.equal(definition.source, '')
  assert.equal(definition.content, '')
  assert.deepEqual(definition.citations, [])
})

test('normalizeDocumentDefinition normalizes citations correctly', () => {
  const definition = normalizeDocumentDefinition({
    document_id: 'doc-test',
    title: 'Test Document',
    citations: ['https://ref1.com', 'https://ref2.com', 'https://ref3.com'],
  })
  assert.equal(definition.citations.length, 3)
  assert.equal(definition.citations[0], 'https://ref1.com')
  assert.equal(definition.citations[1], 'https://ref2.com')
  assert.equal(definition.citations[2], 'https://ref3.com')
})
