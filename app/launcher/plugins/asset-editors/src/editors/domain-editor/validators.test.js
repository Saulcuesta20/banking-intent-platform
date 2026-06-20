import test from 'node:test'
import assert from 'node:assert/strict'

import {
  createDefaultDomain,
  domainDefinitionZodSchema,
  normalizeDomain,
  normalizeDomainDefinition,
  validateDomainDocument,
} from './helpers.js'

test('normalizeDomainDefinition keeps contract fields aligned', () => {
  const definition = normalizeDomainDefinition({
    domainId: 'lending',
    label: 'Colocacion',
    description: 'Prestamos, creditos, originacion, pagos y desembolsos.',
    order: 30,
  })

  assert.equal(definition.domainId, 'lending')
  assert.equal(definition.label, 'Colocacion')
  assert.equal(definition.description, 'Prestamos, creditos, originacion, pagos y desembolsos.')
  assert.equal(definition.order, 30)
})

test('validateDomainDocument accepts a valid domain', () => {
  const result = validateDomainDocument({
    payload: {
      domainId: 'lending',
      label: 'Colocacion',
      description: 'Prestamos, creditos, originacion, pagos y desembolsos.',
      order: 30,
    },
  })

  assert.equal(result.valid, true)
  assert.equal(result.errors.length, 0)
})

test('validateDomainDocument flags missing required fields', () => {
  const result = validateDomainDocument({
    payload: {
      domainId: '',
      label: '',
      description: '',
    },
  })

  assert.equal(result.valid, false)
  assert.ok(result.errors.some((error) => error.includes('domainId')))
})

test('validateDomainDocument warns about empty order', () => {
  const result = validateDomainDocument({
    payload: {
      domainId: 'lending',
      label: 'Colocacion',
      description: 'Prestamos, creditos, originacion, pagos y desembolsos.',
      order: 0,
    },
  })

  assert.ok(result.warnings.some((warning) => warning.includes('order')))
})

test('createDefaultDomain creates valid shape', () => {
  const domain = createDefaultDomain()
  assert.equal(domain.domainId, '')
  assert.equal(domain.label, '')
  assert.equal(domain.description, '')
  assert.equal(domain.order, 0)
})

test('normalizeDomain normalizes correctly', () => {
  const normalized = normalizeDomain({
    asset_id: 'domain.lending',
    asset_type: 'domain',
    name: 'Colocacion',
    payload: {
      domainId: 'lending',
      label: 'Colocacion',
      description: 'Prestamos.',
      order: 30,
    },
  })

  assert.equal(normalized.payload.domainId, 'lending')
  assert.equal(normalized.payload.label, 'Colocacion')
  assert.equal(normalized.asset_id, 'domain.lending')
})
