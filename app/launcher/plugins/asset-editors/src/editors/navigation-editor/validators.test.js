import test from 'node:test'
import assert from 'node:assert/strict'

import {
  createDefaultNavigationItem,
  navigationDefinitionZodSchema,
  normalizeNavigationDefinition,
  validateNavigationDocument,
} from './helpers.js'

test('normalizeNavigationDefinition keeps contract fields aligned', () => {
  const definition = normalizeNavigationDefinition({
    navigation_id: 'nav.lending',
    navigation_name: 'Lending Navigation',
    description: 'Navigation for lending module',
    domain: 'lending',
    module: 'loan',
    items: [
      { id: 'nav_1', label: 'Dashboard', type: 'link', route: '/dashboard' },
      { id: 'nav_2', label: 'Loans', type: 'menu', children: [
        { id: 'child_1', label: 'Create Loan', type: 'link', route: '/loans/create' },
      ]},
    ],
    metadata: {
      version: '1.0.0',
      author: 'admin',
    },
  })

  assert.equal(definition.navigation_id, 'nav.lending')
  assert.equal(definition.module, 'loan')
  assert.equal(definition.items.length, 2)
  assert.equal(definition.items[1].children.length, 1)
})

test('validateNavigationDocument accepts a valid navigation', () => {
  const result = validateNavigationDocument({
    payload: {
      navigation_id: 'nav.lending',
      navigation_name: 'Lending Navigation',
      description: 'Navigation for lending module',
      domain: 'lending',
      module: 'loan',
      items: [
        { id: 'nav_1', label: 'Dashboard', type: 'link', route: '/dashboard' },
      ],
    },
  })

  assert.equal(result.valid, true)
  assert.equal(result.errors.length, 0)
})

test('validateNavigationDocument flags missing required fields', () => {
  const result = validateNavigationDocument({
    payload: {
      navigation_id: '',
      navigation_name: '',
      description: '',
      domain: '',
      module: '',
    },
  })

  assert.equal(result.valid, false)
  assert.ok(result.errors.some((error) => error.includes('navigation_id')))
})

test('validateNavigationDocument warns about empty items', () => {
  const result = validateNavigationDocument({
    payload: {
      navigation_id: 'nav.lending',
      navigation_name: 'Lending Navigation',
      description: 'Navigation for lending module',
      domain: 'lending',
      module: 'loan',
      items: [],
    },
  })

  assert.ok(result.warnings.some((warning) => warning.includes('items')))
})

test('validateNavigationDocument warns about links without routes', () => {
  const result = validateNavigationDocument({
    payload: {
      navigation_id: 'nav.lending',
      navigation_name: 'Lending Navigation',
      description: 'Navigation for lending module',
      domain: 'lending',
      module: 'loan',
      items: [
        { id: 'nav_1', label: 'Dashboard', type: 'link', route: '' },
      ],
    },
  })

  assert.ok(result.warnings.some((warning) => warning.includes('route')))
})

test('createDefaultNavigationItem creates valid shape', () => {
  const item = createDefaultNavigationItem(0)
  assert.equal(item.id, 'nav_1')
  assert.equal(item.label, 'Item 1')
  assert.equal(item.type, 'menu')
})
