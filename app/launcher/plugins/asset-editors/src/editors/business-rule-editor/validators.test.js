import test from 'node:test'
import assert from 'node:assert/strict'

import {
  createDefaultCondition,
  createDefaultRuleAction,
  ruleDefinitionZodSchema,
  normalizeRuleDefinition,
  validateRuleDocument,
} from './helpers.js'

test('normalizeRuleDefinition keeps contract fields aligned', () => {
  const definition = normalizeRuleDefinition({
    rule_id: 'rule.loan.amount',
    rule_name: 'Loan Amount Validation',
    description: 'Validates loan amount limits',
    domain: 'lending',
    rule_type: 'validation',
    priority: 1,
    conditions: [
      { field: 'amount', operator: 'greater_than', value: '1000000' },
    ],
    actions: [
      { type: 'reject', target: 'loan', description: 'Reject if amount too high' },
    ],
    metadata: {
      version: '1.0.0',
      author: 'admin',
      tags: ['validation', 'lending'],
    },
  })

  assert.equal(definition.rule_id, 'rule.loan.amount')
  assert.equal(definition.rule_type, 'validation')
  assert.equal(definition.conditions.length, 1)
  assert.equal(definition.actions.length, 1)
  assert.equal(definition.metadata.version, '1.0.0')
})

test('validateRuleDocument accepts a valid rule', () => {
  const result = validateRuleDocument({
    payload: {
      rule_id: 'rule.loan.amount',
      rule_name: 'Loan Amount Validation',
      description: 'Validates loan amount limits',
      domain: 'lending',
      rule_type: 'validation',
      priority: 1,
      conditions: [
        { field: 'amount', operator: 'greater_than', value: '1000000' },
      ],
      actions: [
        { type: 'reject', target: 'loan', description: 'Reject if amount too high' },
      ],
    },
  })

  assert.equal(result.valid, true)
  assert.equal(result.errors.length, 0)
})

test('validateRuleDocument flags missing required fields', () => {
  const result = validateRuleDocument({
    payload: {
      rule_id: '',
      rule_name: '',
      description: '',
      domain: '',
      rule_type: 'invalid',
    },
  })

  assert.equal(result.valid, false)
  assert.ok(result.errors.some((error) => error.includes('rule_id')))
})

test('validateRuleDocument warns about empty conditions and actions', () => {
  const result = validateRuleDocument({
    payload: {
      rule_id: 'rule.loan.amount',
      rule_name: 'Loan Amount Validation',
      description: 'Validates loan amount limits',
      domain: 'lending',
      rule_type: 'validation',
      conditions: [],
      actions: [],
    },
  })

  assert.ok(result.warnings.some((warning) => warning.includes('conditions')))
  assert.ok(result.warnings.some((warning) => warning.includes('actions')))
})

test('createDefaultCondition creates valid shape', () => {
  const cond = createDefaultCondition(0)
  assert.equal(cond.field, '')
  assert.equal(cond.operator, 'equals')
  assert.equal(cond.value, '')
})

test('createDefaultRuleAction creates valid shape', () => {
  const action = createDefaultRuleAction(0)
  assert.equal(action.type, 'allow')
  assert.equal(action.target, '')
})
