import test from 'node:test'
import assert from 'node:assert/strict'

import {
  createDefaultConfiguration,
  configurationDefinitionZodSchema,
  normalizeConfigurationDefinition,
  validateConfigurationDocument,
} from './helpers.js'

test('normalizeConfigurationDefinition keeps contract fields aligned', () => {
  const definition = normalizeConfigurationDefinition({
    config_id: 'config.lending.rate',
    scope: 'global',
    settings: { max_rate: 12.5 },
    environment: 'production',
    owner: 'lending-team',
  })

  assert.equal(definition.config_id, 'config.lending.rate')
  assert.equal(definition.scope, 'global')
  assert.deepEqual(definition.settings, { max_rate: 12.5 })
  assert.equal(definition.environment, 'production')
  assert.equal(definition.owner, 'lending-team')
})

test('validateConfigurationDocument accepts a valid configuration', () => {
  const result = validateConfigurationDocument({
    payload: {
      config_id: 'config.lending.rate',
      scope: 'global',
      settings: { max_rate: 12.5 },
      environment: 'production',
      owner: 'lending-team',
    },
  })

  assert.equal(result.valid, true)
  assert.equal(result.errors.length, 0)
})

test('validateConfigurationDocument flags missing required fields', () => {
  const result = validateConfigurationDocument({
    payload: {
      config_id: '',
      scope: '',
      settings: {},
      environment: '',
      owner: '',
    },
  })

  assert.equal(result.valid, false)
  assert.ok(result.errors.some((error) => error.includes('config_id')))
})

test('validateConfigurationDocument warns about missing environment', () => {
  const result = validateConfigurationDocument({
    payload: {
      config_id: 'config.lending.rate',
      scope: 'global',
      settings: {},
      environment: '',
      owner: 'lending-team',
    },
  })

  assert.ok(result.warnings.some((warning) => warning.includes('environment')))
})

test('validateConfigurationDocument warns about missing owner', () => {
  const result = validateConfigurationDocument({
    payload: {
      config_id: 'config.lending.rate',
      scope: 'global',
      settings: {},
      environment: 'production',
      owner: '',
    },
  })

  assert.ok(result.warnings.some((warning) => warning.includes('owner')))
})

test('validateConfigurationDocument warns about config_id without dot prefix', () => {
  const result = validateConfigurationDocument({
    payload: {
      config_id: 'config-lending-rate',
      scope: 'global',
      settings: {},
      environment: 'production',
      owner: 'lending-team',
    },
  })

  assert.ok(result.warnings.some((warning) => warning.includes('config_id')))
})

test('createDefaultConfiguration creates valid shape', () => {
  const item = createDefaultConfiguration()
  assert.equal(item.config_id, 'config-new')
  assert.equal(item.scope, '')
  assert.deepEqual(item.settings, {})
  assert.equal(item.environment, '')
  assert.equal(item.owner, '')
})
