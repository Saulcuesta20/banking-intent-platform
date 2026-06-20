import test from 'node:test'
import assert from 'node:assert/strict'

import {
  createDefaultPlanDefinition,
  planDefinitionZodSchema,
  normalizePlanDefinition,
  validatePlanDocument,
} from './helpers.js'

test('normalizePlanDefinition keeps contract fields aligned', () => {
  const definition = normalizePlanDefinition({
    plan_id: 'plan-loan-apply',
    description: 'Loan application plan',
    steps: [
      { step_id: 's1', name: 'Validate identity', type: 'check' },
      { step_id: 's2', name: 'Submit application', type: 'action' },
    ],
    tools: ['identity-checker', 'loan-api'],
    dependencies: ['auth-service'],
    execution_options: { parallel: false },
  })

  assert.equal(definition.plan_id, 'plan-loan-apply')
  assert.equal(definition.description, 'Loan application plan')
  assert.equal(definition.steps.length, 2)
  assert.equal(definition.steps[0].step_id, 's1')
  assert.equal(definition.steps[0].name, 'Validate identity')
  assert.equal(definition.steps[0].type, 'check')
  assert.equal(definition.tools.length, 2)
  assert.equal(definition.dependencies.length, 1)
})

test('validatePlanDocument accepts a valid plan', () => {
  const result = validatePlanDocument({
    payload: {
      plan_id: 'plan-loan-apply',
      description: 'Loan application plan',
      steps: [
        { step_id: 's1', name: 'Validate identity', type: 'check' },
      ],
      tools: ['identity-checker'],
      dependencies: ['auth-service'],
    },
  })

  assert.equal(result.valid, true)
  assert.equal(result.errors.length, 0)
})

test('validatePlanDocument flags missing plan_id', () => {
  const result = validatePlanDocument({
    payload: {
      plan_id: '',
      description: 'Loan application plan',
      steps: [],
      tools: [],
      dependencies: [],
    },
  })

  assert.equal(result.valid, false)
  assert.ok(result.errors.some((error) => error.includes('plan_id')))
})

test('validatePlanDocument warns about empty steps', () => {
  const result = validatePlanDocument({
    payload: {
      plan_id: 'plan-loan-apply',
      description: 'Loan application plan',
      steps: [],
      tools: ['identity-checker'],
      dependencies: [],
    },
  })

  assert.ok(result.warnings.some((warning) => warning.includes('steps')))
})

test('validatePlanDocument warns about empty tools', () => {
  const result = validatePlanDocument({
    payload: {
      plan_id: 'plan-loan-apply',
      description: 'Loan application plan',
      steps: [{ step_id: 's1', name: 'Validate', type: 'check' }],
      tools: [],
      dependencies: [],
    },
  })

  assert.ok(result.warnings.some((warning) => warning.includes('tools')))
})

test('createDefaultPlanDefinition creates valid shape', () => {
  const plan = createDefaultPlanDefinition()
  assert.equal(plan.plan_id, 'plan-new')
  assert.equal(plan.description, '')
  assert.deepEqual(plan.steps, [])
  assert.deepEqual(plan.tools, [])
  assert.deepEqual(plan.dependencies, [])
  assert.deepEqual(plan.execution_options, {})
})

test('normalizePlanDefinition handles missing fields', () => {
  const definition = normalizePlanDefinition({})
  assert.equal(definition.plan_id, '')
  assert.equal(definition.description, '')
  assert.deepEqual(definition.steps, [])
  assert.deepEqual(definition.tools, [])
  assert.deepEqual(definition.dependencies, [])
  assert.deepEqual(definition.execution_options, {})
})

test('normalizePlanDefinition normalizes steps correctly', () => {
  const definition = normalizePlanDefinition({
    plan_id: 'plan-test',
    steps: [
      { step_id: 's1', name: 'Step 1', type: 'action' },
      { step_id: 's2', name: 'Step 2', type: 'check' },
    ],
  })
  assert.equal(definition.steps[0].step_id, 's1')
  assert.equal(definition.steps[0].name, 'Step 1')
  assert.equal(definition.steps[0].type, 'action')
  assert.equal(definition.steps[1].step_id, 's2')
  assert.equal(definition.steps[1].name, 'Step 2')
  assert.equal(definition.steps[1].type, 'check')
})
