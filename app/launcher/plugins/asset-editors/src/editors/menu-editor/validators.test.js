import test from 'node:test'
import assert from 'node:assert/strict'

import {
  createDefaultMenuItem,
  menuDefinitionZodSchema,
  normalizeMenuDefinition,
  normalizeMenuItem,
  validateMenuDocument,
} from './helpers.js'

test('normalizeMenuDefinition keeps contract fields aligned', () => {
  const definition = normalizeMenuDefinition({
    id: 'loan-create',
    label: 'Crear prestamo',
    path: '/lending/loan/loan-create',
    module_id: 'loan',
    domain_id: 'lending',
  })

  assert.equal(definition.id, 'loan-create')
  assert.equal(definition.label, 'Crear prestamo')
  assert.equal(definition.path, '/lending/loan/loan-create')
  assert.equal(definition.module_id, 'loan')
  assert.equal(definition.domain_id, 'lending')
})

test('validateMenuDocument accepts a valid menu', () => {
  const result = validateMenuDocument({
    payload: {
      id: 'loan-create',
      label: 'Crear prestamo',
      path: '/lending/loan/loan-create',
      module_id: 'loan',
      domain_id: 'lending',
    },
  })

  assert.equal(result.valid, true)
  assert.equal(result.errors.length, 0)
})

test('validateMenuDocument flags missing required fields', () => {
  const result = validateMenuDocument({
    payload: {
      id: '',
      label: '',
      path: '',
      module_id: '',
      domain_id: '',
    },
  })

  assert.equal(result.valid, false)
  assert.ok(result.errors.some((error) => error.includes('id')))
  assert.ok(result.errors.some((error) => error.includes('label')))
})

test('validateMenuDocument warns about path without leading slash', () => {
  const result = validateMenuDocument({
    payload: {
      id: 'loan-create',
      label: 'Crear prestamo',
      path: 'lending/loan/loan-create',
      module_id: 'loan',
      domain_id: 'lending',
    },
  })

  assert.ok(result.warnings.some((warning) => warning.includes('path')))
})

test('createDefaultMenuItem creates valid shape', () => {
  const item = createDefaultMenuItem()
  assert.equal(item.id, 'menu-new')
  assert.equal(item.label, 'New Menu')
  assert.equal(item.path, '/new/menu')
  assert.equal(item.module_id, '')
  assert.equal(item.domain_id, '')
})

test('normalizeMenuItem normalizes correctly', () => {
  const item = normalizeMenuItem({
    id: 'loan-create',
    label: 'Crear prestamo',
    path: '/lending/loan/loan-create',
    module_id: 'loan',
    domain_id: 'lending',
  })

  assert.equal(item.id, 'loan-create')
  assert.equal(item.label, 'Crear prestamo')
  assert.equal(item.path, '/lending/loan/loan-create')
  assert.equal(item.module_id, 'loan')
  assert.equal(item.domain_id, 'lending')
})
