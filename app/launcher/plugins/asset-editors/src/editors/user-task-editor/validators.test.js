import test from 'node:test'
import assert from 'node:assert/strict'

import {
  createDefaultUserTaskDefinition,
  userTaskDefinitionZodSchema,
  normalizeUserTaskDefinition,
  validateUserTaskDocument,
} from './helpers.js'

test('normalizeUserTaskDefinition keeps contract fields aligned', () => {
  const definition = normalizeUserTaskDefinition({
    user_task_id: 'ut-review-docs',
    task: 'Review loan documents',
    type: 'approval',
    name: 'Document Review',
    description: 'Review and approve loan documents before disbursement',
    user_actions: ['approve', 'reject', 'request_info'],
    tools: ['doc-viewer', 'comment-system'],
  })

  assert.equal(definition.user_task_id, 'ut-review-docs')
  assert.equal(definition.task, 'Review loan documents')
  assert.equal(definition.type, 'approval')
  assert.equal(definition.name, 'Document Review')
  assert.equal(definition.description, 'Review and approve loan documents before disbursement')
  assert.equal(definition.user_actions.length, 3)
  assert.equal(definition.user_actions[0], 'approve')
  assert.equal(definition.tools.length, 2)
})

test('validateUserTaskDocument accepts a valid user task', () => {
  const result = validateUserTaskDocument({
    payload: {
      user_task_id: 'ut-review-docs',
      task: 'Review loan documents',
      type: 'approval',
      name: 'Document Review',
      description: 'Review and approve loan documents',
      user_actions: ['approve', 'reject'],
      tools: ['doc-viewer'],
    },
  })

  assert.equal(result.valid, true)
  assert.equal(result.errors.length, 0)
})

test('validateUserTaskDocument flags missing required fields', () => {
  const result = validateUserTaskDocument({
    payload: {
      user_task_id: '',
      task: '',
      type: 'approval',
      name: '',
      description: '',
      user_actions: [],
      tools: [],
    },
  })

  assert.equal(result.valid, false)
  assert.ok(result.errors.some((error) => error.includes('user_task_id')))
  assert.ok(result.errors.some((error) => error.includes('task')))
})

test('validateUserTaskDocument warns about empty user_actions', () => {
  const result = validateUserTaskDocument({
    payload: {
      user_task_id: 'ut-review-docs',
      task: 'Review loan documents',
      type: 'approval',
      name: 'Document Review',
      description: '',
      user_actions: [],
      tools: ['doc-viewer'],
    },
  })

  assert.ok(result.warnings.some((warning) => warning.includes('user_actions')))
})

test('validateUserTaskDocument warns about empty tools', () => {
  const result = validateUserTaskDocument({
    payload: {
      user_task_id: 'ut-review-docs',
      task: 'Review loan documents',
      type: 'approval',
      name: 'Document Review',
      description: '',
      user_actions: ['approve', 'reject'],
      tools: [],
    },
  })

  assert.ok(result.warnings.some((warning) => warning.includes('tools')))
})

test('createDefaultUserTaskDefinition creates valid shape', () => {
  const userTask = createDefaultUserTaskDefinition()
  assert.equal(userTask.user_task_id, 'user-task-new')
  assert.equal(userTask.task, '')
  assert.equal(userTask.type, '')
  assert.equal(userTask.name, '')
  assert.equal(userTask.description, '')
  assert.deepEqual(userTask.user_actions, [])
  assert.deepEqual(userTask.tools, [])
})

test('normalizeUserTaskDefinition handles missing fields', () => {
  const definition = normalizeUserTaskDefinition({})
  assert.equal(definition.user_task_id, '')
  assert.equal(definition.task, '')
  assert.equal(definition.type, '')
  assert.equal(definition.name, '')
  assert.equal(definition.description, '')
  assert.deepEqual(definition.user_actions, [])
  assert.deepEqual(definition.tools, [])
})

test('normalizeUserTaskDefinition normalizes arrays correctly', () => {
  const definition = normalizeUserTaskDefinition({
    user_task_id: 'ut-test',
    task: 'Test task',
    user_actions: ['action1', 'action2', 'action3'],
    tools: ['tool1', 'tool2'],
  })
  assert.equal(definition.user_actions.length, 3)
  assert.equal(definition.user_actions[0], 'action1')
  assert.equal(definition.user_actions[1], 'action2')
  assert.equal(definition.user_actions[2], 'action3')
  assert.equal(definition.tools.length, 2)
  assert.equal(definition.tools[0], 'tool1')
  assert.equal(definition.tools[1], 'tool2')
})
