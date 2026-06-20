import test from 'node:test'
import assert from 'node:assert/strict'

import {
  createDefaultAction,
  createDefaultFlowTask,
  createDefaultTool,
  flowDefinitionZodSchema,
  normalizeFlowDefinition,
  normalizeFlowTask,
  validateTaskDraft,
  validateFlowDocument,
} from './helpers.js'

test('normalizeFlowDefinition keeps contract fields aligned', () => {
  const definition = normalizeFlowDefinition({
    flow_id: 'flow.loan.refinance',
    flow_name: 'Refinanciamiento de prestamo',
    purpose: 'Refinanciar una deuda',
    business_event: 'loan.refinance.requested',
    user_task_refs: ['task-1', 'task-2'],
    related_process_ids: ['process.loan.refinance'],
    inputs: ['customer', 'loan'],
    outputs: ['approval'],
    explanation: 'Flow explanation',
  })

  assert.equal(definition.flow_id, 'flow.loan.refinance')
  assert.deepEqual(definition.user_task_refs, ['task-1', 'task-2'])
  assert.deepEqual(definition.related_process_ids, ['process.loan.refinance'])
})

test('normalizeFlowTask fills lifecycle and tool bindings', () => {
  const task = normalizeFlowTask({
    user_task_id: 'user_task.loan.refinance.identify',
    task: 'identify eligible loan',
    type: 'user_task',
    name: 'Identify eligible loan',
    description: 'Capture information',
    user_actions: [
      {
        action_id: 'action_1',
        type: 'back',
        implementation_type: 'tool_call',
        tool_ids: ['tool.loan.search'],
      },
    ],
    tools: [
      {
        tool_id: 'tool.loan.search',
        tool_type: 'backend_tool',
        operation: 'search',
        resource: 'loan',
      },
    ],
  })

  assert.equal(task.actions[0].lifecycle_state, 'not_started')
  assert.deepEqual(task.actions[0].tool_ids, ['tool.loan.search'])
  assert.equal(task.tools[0].tool_id, 'tool.loan.search')
})

test('validateFlowDocument accepts a valid task binding', () => {
  const task = createDefaultFlowTask('flow.loan.refinance', 0)
  task.description = 'Show the refinance options and compare outcomes.'
  task.user_actions[0].description = 'Open the refinance proposal panel.'
  task.tools.push({
    tool_id: 'tool.loan.conditions.calculate',
    tool_type: 'backend_tool',
    operation: 'calculate_conditions',
    resource: 'loan',
  })
  task.user_actions[0].type = 'back'
  task.user_actions[0].implementation_type = 'tool_call'
  task.user_actions[0].tool_ids = ['tool.loan.conditions.calculate']
  task.user_actions[0].tool_id = 'tool.loan.conditions.calculate'

  const result = validateFlowDocument({
    payload: {
      flow_id: 'flow.loan.refinance',
      flow_name: 'Refinanciamiento de prestamo',
      purpose: 'Refinanciar una deuda',
      business_event: 'loan.refinance.requested',
      user_task_refs: ['user_task.loan.refinance.identify'],
      explanation: 'Flow explanation',
      user_tasks: [task],
    },
  })

  assert.equal(result.valid, true)
  assert.equal(result.errors.length, 0)
})

test('validateFlowDocument flags broken action bindings', () => {
  const task = createDefaultFlowTask('flow.loan.refinance', 0)
  task.description = 'Show the refinance options and compare outcomes.'
  task.user_actions[0].description = 'Open the refinance proposal panel.'
  task.user_actions[0].type = 'back'
  task.user_actions[0].implementation_type = 'tool_call'
  task.user_actions[0].tool_ids = ['tool.missing']
  task.user_actions[0].tool_id = 'tool.missing'

  const result = validateFlowDocument({
    payload: {
      flow_id: 'flow.loan.refinance',
      flow_name: 'Refinanciamiento de prestamo',
      purpose: 'Refinanciar una deuda',
      business_event: 'loan.refinance.requested',
      user_task_refs: ['user_task.loan.refinance.identify'],
      explanation: 'Flow explanation',
      user_tasks: [task],
    },
  })

  assert.equal(result.valid, true)
  assert.ok(result.warnings.some((warning) => warning.includes('tool.missing')))
})

test('default helpers create compatible action and tool shapes', () => {
  const action = createDefaultAction(1, 'back')
  const tool = createDefaultTool('user_task.loan.refinance.identify', 0)

  assert.equal(action.lifecycle_state, 'not_started')
  assert.equal(action.implementation_type, 'tool_call')
  assert.equal(tool.tool_type, 'backend_tool')
})

test('zod schema rejects empty required flow fields', () => {
  const result = flowDefinitionZodSchema.safeParse({
    flow_id: '',
    flow_name: '',
    purpose: '',
    business_event: '',
    user_task_refs: [],
    related_process_ids: [],
    inputs: [],
    outputs: [],
    explanation: '',
  })

  assert.equal(result.success, false)
})

test('validateTaskDraft rejects null-like values', () => {
  const result = validateTaskDraft({
    user_task_id: '',
    task: '',
    type: 'user_task',
    name: '',
    description: '',
    user_actions: [],
    tools: [],
  })

  assert.equal(result.valid, false)
  assert.ok(result.errors.some((message) => message.includes('description')))
})
