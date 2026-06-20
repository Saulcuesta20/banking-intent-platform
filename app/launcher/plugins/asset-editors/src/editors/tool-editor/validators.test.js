import test from 'node:test'
import assert from 'node:assert/strict'

import {
  createDefaultToolDefinition,
  toolDefinitionZodSchema,
  normalizeToolDefinition,
  validateToolDocument,
} from './helpers.js'

test('normalizeToolDefinition keeps contract fields aligned', () => {
  const definition = normalizeToolDefinition({
    tool_id: 'tool.api.transfer',
    tool_type: 'backend_tool',
    operation: 'create',
    resource: '/api/transfer',
    label: 'Transfer Funds',
    description: 'Initiates a fund transfer',
  })

  assert.equal(definition.tool_id, 'tool.api.transfer')
  assert.equal(definition.tool_type, 'backend_tool')
  assert.equal(definition.operation, 'create')
  assert.equal(definition.resource, '/api/transfer')
  assert.equal(definition.label, 'Transfer Funds')
  assert.equal(definition.description, 'Initiates a fund transfer')
})

test('validateToolDocument accepts a valid tool', () => {
  const result = validateToolDocument({
    payload: {
      tool_id: 'tool.api.transfer',
      tool_type: 'backend_tool',
      operation: 'create',
      resource: '/api/transfer',
      label: 'Transfer',
      description: 'test',
    },
  })

  assert.equal(result.valid, true)
  assert.equal(result.errors.length, 0)
})

test('validateToolDocument flags missing required fields', () => {
  const result = validateToolDocument({
    payload: {
      tool_id: '',
      tool_type: '',
      operation: '',
      resource: '',
    },
  })

  assert.equal(result.valid, false)
  assert.ok(result.errors.some((error) => error.includes('tool_id')))
  assert.ok(result.errors.some((error) => error.includes('tool_type')))
  assert.ok(result.errors.some((error) => error.includes('operation')))
  assert.ok(result.errors.some((error) => error.includes('resource')))
})

test('validateToolDocument flags invalid tool_type', () => {
  const result = validateToolDocument({
    payload: {
      tool_id: 'tool.test',
      tool_type: 'invalid_type',
      operation: 'read',
      resource: '/test',
    },
  })

  assert.equal(result.valid, false)
  assert.ok(result.errors.some((error) => error.includes('tool_type')))
})

test('validateToolDocument warns about missing label', () => {
  const result = validateToolDocument({
    payload: {
      tool_id: 'tool.test',
      tool_type: 'llm_tool',
      operation: 'summarize',
      resource: 'llm-gpt4',
    },
  })

  assert.ok(result.warnings.some((warning) => warning.includes('label')))
})

test('createDefaultToolDefinition creates valid shape', () => {
  const def = createDefaultToolDefinition()
  assert.equal(def.tool_id, 'tool-new')
  assert.equal(def.tool_type, 'backend_tool')
  assert.equal(def.operation, '')
  assert.equal(def.resource, '')
  assert.equal(def.label, '')
  assert.equal(def.description, '')
})

test('normalizeToolDefinition handles undefined input', () => {
  const definition = normalizeToolDefinition({})
  assert.equal(definition.tool_id, '')
  assert.equal(definition.tool_type, '')
  assert.equal(definition.operation, '')
  assert.equal(definition.resource, '')
  assert.equal(definition.label, '')
  assert.equal(definition.description, '')
})
