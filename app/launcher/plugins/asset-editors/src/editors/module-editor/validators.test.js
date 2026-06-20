import test from 'node:test'
import assert from 'node:assert/strict'

import {
  createDefaultModule,
  moduleDefinitionZodSchema,
  normalizeModuleDefinition,
  validateModuleDocument,
} from './helpers.js'

test('normalizeModuleDefinition keeps contract fields aligned', () => {
  const definition = normalizeModuleDefinition({
    module_id: 'module.lending',
    domain_id: 'domain.lending',
    label: 'Lending Module',
    description: 'Handles loan origination',
    menus: ['menu.loan.create', 'menu.loan.list'],
  })

  assert.equal(definition.module_id, 'module.lending')
  assert.equal(definition.domain_id, 'domain.lending')
  assert.equal(definition.label, 'Lending Module')
  assert.equal(definition.description, 'Handles loan origination')
  assert.deepEqual(definition.menus, ['menu.loan.create', 'menu.loan.list'])
})

test('validateModuleDocument accepts a valid module', () => {
  const result = validateModuleDocument({
    payload: {
      module_id: 'module.lending',
      domain_id: 'domain.lending',
      label: 'Lending Module',
      description: 'Handles loan origination',
      menus: ['menu.loan.create'],
    },
  })

  assert.equal(result.valid, true)
  assert.equal(result.errors.length, 0)
})

test('validateModuleDocument flags missing required fields', () => {
  const result = validateModuleDocument({
    payload: {
      module_id: '',
      domain_id: '',
      label: '',
      description: '',
      menus: [],
    },
  })

  assert.equal(result.valid, false)
  assert.ok(result.errors.some((error) => error.includes('module_id')))
  assert.ok(result.errors.some((error) => error.includes('domain_id')))
  assert.ok(result.errors.some((error) => error.includes('label')))
})

test('validateModuleDocument warns about empty menus', () => {
  const result = validateModuleDocument({
    payload: {
      module_id: 'module.lending',
      domain_id: 'domain.lending',
      label: 'Lending Module',
      description: '',
      menus: [],
    },
  })

  assert.ok(result.warnings.some((warning) => warning.includes('menus')))
})

test('validateModuleDocument warns about module_id without dot prefix', () => {
  const result = validateModuleDocument({
    payload: {
      module_id: 'module-lending',
      domain_id: 'domain.lending',
      label: 'Lending Module',
      description: '',
      menus: ['menu.loan.create'],
    },
  })

  assert.ok(result.warnings.some((warning) => warning.includes('module_id')))
})

test('createDefaultModule creates valid shape', () => {
  const item = createDefaultModule()
  assert.equal(item.module_id, 'module-new')
  assert.equal(item.domain_id, '')
  assert.equal(item.label, 'New Module')
  assert.equal(item.description, '')
  assert.deepEqual(item.menus, [])
})
