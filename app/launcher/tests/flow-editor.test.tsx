import { describe, it, expect, vi } from 'vitest'
import { render } from '@testing-library/react'
import React from 'react'

describe('flow-editor helpers', () => {
  it('createDefaultFlowTask returns valid shape', async () => {
    const { createDefaultFlowTask } = await import('../plugins/asset-editors/src/editors/flow-editor/helpers.js')
    const task = createDefaultFlowTask()
    expect(task).toHaveProperty('user_task_id')
    expect(task).toHaveProperty('task')
    expect(task).toHaveProperty('type')
    expect(typeof task.user_task_id).toBe('string')
  })

  it('normalizeFlowDefinition handles empty input', async () => {
    const { normalizeFlowDefinition } = await import('../plugins/asset-editors/src/editors/flow-editor/helpers.js')
    const result = normalizeFlowDefinition({})
    expect(result).toHaveProperty('flow_id')
    expect(result).toHaveProperty('user_task_refs')
    expect(Array.isArray(result.user_task_refs)).toBe(true)
  })

  it('validateFlowDocument accepts valid flow', async () => {
    const { validateFlowDocument } = await import('../plugins/asset-editors/src/editors/flow-editor/helpers.js')
    const result = validateFlowDocument({
      payload: {
        flow_id: 'test.flow',
        flow_name: 'Test Flow',
        purpose: 'Test purpose',
        business_event: 'TestEvent',
        explanation: 'A test flow',
        user_task_refs: ['task-1'],
      },
    })
    expect(result.valid).toBe(true)
    expect(result.errors.length).toBe(0)
  })

  it('validateFlowDocument rejects missing required fields', async () => {
    const { validateFlowDocument } = await import('../plugins/asset-editors/src/editors/flow-editor/helpers.js')
    const result = validateFlowDocument({
      payload: {},
    })
    expect(result.valid).toBe(false)
    expect(result.errors.length).toBeGreaterThan(0)
  })
})

describe('flow-editor rendering', () => {
  it('renders FlowCanvasView without crashing', async () => {
    const { FlowCanvasView } = await import('../plugins/asset-editors/src/editors/flow-editor/index.js')
    const onChange = vi.fn()
    const { container } = render(
      React.createElement(FlowCanvasView, {
        value: {
          asset_id: 'flow.test',
          asset_type: 'flow',
          payload: {
            flow_id: 'test.flow',
            flow_name: 'Test Flow',
            purpose: 'Test purpose',
            business_event: 'TestEvent',
            explanation: 'A test flow',
            tasks: [],
            user_task_refs: ['task-1'],
          },
        },
        onChange,
      })
    )
    expect(container.innerHTML).toContain('Editor')
  })
})
