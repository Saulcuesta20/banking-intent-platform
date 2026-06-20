import test from 'node:test'
import assert from 'node:assert/strict'

import {
  createDefaultProcessDefinition,
  processDefinitionZodSchema,
  normalizeProcessDefinition,
  validateProcessDocument,
} from './helpers.js'

test('normalizeProcessDefinition keeps contract fields aligned', () => {
  const definition = normalizeProcessDefinition({
    process_id: 'process.loan.apply',
    description: 'Loan application process',
    nodes: [
      { node_id: 'start', name: 'Start', type: 'action' },
      { node_id: 'review', name: 'Review', type: 'decision' },
    ],
    edges: [
      { from_node: 'start', to_node: 'review' },
    ],
    decisions: [],
    systems: ['core-banking'],
    exceptions: [],
  })

  assert.equal(definition.process_id, 'process.loan.apply')
  assert.equal(definition.description, 'Loan application process')
  assert.equal(definition.nodes.length, 2)
  assert.equal(definition.edges.length, 1)
  assert.equal(definition.systems[0], 'core-banking')
})

test('validateProcessDocument accepts a valid process', () => {
  const result = validateProcessDocument({
    payload: {
      process_id: 'process.loan.apply',
      description: 'Loan application',
      nodes: [
        { node_id: 'n1', name: 'Submit', type: 'action' },
      ],
      edges: [],
    },
  })

  assert.equal(result.valid, true)
  assert.equal(result.errors.length, 0)
})

test('validateProcessDocument flags missing process_id', () => {
  const result = validateProcessDocument({
    payload: {
      process_id: '',
      description: 'test',
      nodes: [],
      edges: [],
    },
  })

  assert.equal(result.valid, false)
  assert.ok(result.errors.some((error) => error.includes('process_id')))
})

test('validateProcessDocument warns about empty nodes', () => {
  const result = validateProcessDocument({
    payload: {
      process_id: 'process.test',
      nodes: [],
      edges: [],
    },
  })

  assert.ok(result.warnings.some((warning) => warning.includes('execution nodes')))
})

test('validateProcessDocument warns about missing prefix', () => {
  const result = validateProcessDocument({
    payload: {
      process_id: 'loan',
      nodes: [{ node_id: 'n1', name: 'N1', type: 'action' }],
      edges: [],
    },
  })

  assert.ok(result.warnings.some((warning) => warning.includes('dot-separated prefix')))
})

test('createDefaultProcessDefinition creates valid shape', () => {
  const def = createDefaultProcessDefinition()
  assert.equal(def.process_id, 'process-new')
  assert.equal(def.description, '')
  assert.deepEqual(def.nodes, [])
  assert.deepEqual(def.edges, [])
  assert.deepEqual(def.decisions, [])
  assert.deepEqual(def.systems, [])
  assert.deepEqual(def.exceptions, [])
})

test('normalizeProcessDefinition handles undefined input', () => {
  const definition = normalizeProcessDefinition({})
  assert.equal(definition.process_id, '')
  assert.deepEqual(definition.nodes, [])
  assert.deepEqual(definition.edges, [])
})
