import test from 'node:test'
import assert from 'node:assert/strict'

import {
  createDefaultEntity,
  createDefaultRelation,
  normalizeBusinessModelDocument,
  validateBusinessModelDocument,
} from './helpers.js'

test('normalizeBusinessModelDocument hydrates legacy payloads', () => {
  const normalized = normalizeBusinessModelDocument({
    payload: {
      entity_id: 'entity.loan',
      entity_name: 'Loan',
      description: 'Legacy loan description',
      domain: 'capability',
    },
  })

  assert.equal(normalized.payload.entities.length, 1)
  assert.equal(normalized.payload.entities[0].id, 'entity.loan')
  assert.equal(normalized.payload.entities[0].layer, 'capability')
  assert.equal(Array.isArray(normalized.payload.relations), true)
  assert.equal(Object.keys(normalized.payload.layout.nodes).length, 1)
})

test('validateBusinessModelDocument catches invalid references', () => {
  const result = validateBusinessModelDocument({
    payload: {
      entities: [
        {
          id: 'entity.customer',
          name: 'Customer',
          layer: 'capability',
          role: 'core',
          description: '',
          aliases: [],
          attributes: [],
        },
      ],
      relations: [
        {
          id: 'relation.one',
          source_entity_id: 'entity.customer',
          target_entity_id: 'missing.entity',
          relation_type: 'supports',
          description: '',
        },
      ],
      layout: { nodes: {} },
    },
  })

  assert.equal(result.valid, true)
  assert.ok(result.warnings.some((warning) => warning.includes('missing from entities')))
})

test('createDefaultEntity produces unique identifiers', () => {
  const first = createDefaultEntity(0)
  const second = createDefaultEntity(1, [first.id])
  assert.notEqual(first.id, second.id)
  assert.equal(first.layer, 'capability')
  assert.equal(first.role, 'core')
})

test('createDefaultRelation includes defaults', () => {
  const rel = createDefaultRelation(0, 'entity.a', 'entity.b')
  assert.equal(rel.source_entity_id, 'entity.a')
  assert.equal(rel.target_entity_id, 'entity.b')
  assert.equal(typeof rel.relation_type, 'string')
})

test('normalizeBusinessModelDocument preserves technical stereotypes and relation aliases', () => {
  const normalized = normalizeBusinessModelDocument({
    payload: {
      entities: [
        {
          id: 'entity.gold_customers',
          name: 'gold.customers',
          structural_layer: 'business_resource',
          subtype: 'table',
          technical_type: 'table',
          role: 'core',
          attributes: [],
        },
      ],
      relations: [
        {
          id: 'relation.table.customer',
          source_entity_id: 'entity.customer',
          target_entity_id: 'entity.gold_customers',
          relation_type: 'materialized_in',
        },
      ],
    },
  })

  assert.equal(normalized.payload.entities[0].subtype, 'table')
  assert.equal(normalized.payload.entities[0].technical_type, 'table')
  assert.equal(normalized.payload.relations[0].relation_type, 'represented_by')
})
