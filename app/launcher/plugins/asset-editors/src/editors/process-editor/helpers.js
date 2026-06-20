import { z } from 'zod'

export const processDefinitionZodSchema = z.object({
  process_id: z.string().min(1, 'process_id is required'),
  description: z.string().optional().default(''),
  nodes: z.array(z.object({
    node_id: z.string(),
    name: z.string(),
    type: z.string(),
  })).optional().default([]),
  edges: z.array(z.object({
    from_node: z.string(),
    to_node: z.string(),
  })).optional().default([]),
  decisions: z.array(z.object({}).passthrough()).optional().default([]),
  systems: z.array(z.string()).optional().default([]),
  exceptions: z.array(z.object({}).passthrough()).optional().default([]),
})

function asString(value) {
  return String(value ?? '').trim()
}

function asArray(value) {
  return Array.isArray(value) ? value : []
}

export function normalizeProcessDefinition(payload = {}) {
  return {
    process_id: asString(payload.process_id),
    description: asString(payload.description),
    nodes: asArray(payload.nodes).map((n) => ({
      node_id: asString(n.node_id),
      name: asString(n.name),
      type: asString(n.type),
    })),
    edges: asArray(payload.edges).map((e) => ({
      from_node: asString(e.from_node),
      to_node: asString(e.to_node),
    })),
    decisions: asArray(payload.decisions),
    systems: asArray(payload.systems),
    exceptions: asArray(payload.exceptions),
  }
}

export function createDefaultProcessDefinition() {
  return {
    process_id: 'process-new',
    description: '',
    nodes: [],
    edges: [],
    decisions: [],
    systems: [],
    exceptions: [],
  }
}

export function validateProcessDocument(document = {}) {
  const payload = document.payload && typeof document.payload === 'object' ? document.payload : document
  const process = normalizeProcessDefinition(payload)
  const errors = []
  const warnings = []

  const result = processDefinitionZodSchema.safeParse(process)
  if (!result.success) {
    errors.push(...result.error.issues.map((issue) => `${issue.path.join('.')} ${issue.message}`.trim()))
  }

  if (process.process_id && !process.process_id.includes('.')) {
    warnings.push('process_id may be missing a dot-separated prefix (e.g. process.loan.apply)')
  }

  if (process.nodes.length === 0) {
    warnings.push('No execution nodes defined')
  }

  if (process.edges.length === 0 && process.nodes.length > 1) {
    warnings.push('Multiple nodes defined but no transitions (edges) between them')
  }

  return {
    valid: errors.length === 0,
    process,
    errors,
    warnings,
  }
}
