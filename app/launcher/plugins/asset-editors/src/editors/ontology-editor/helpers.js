import { z } from 'zod'

const DEFAULT_LAYERS = [
  'party',
  'organization',
  'capability',
  'portfolio',
  'offering',
  'program',
  'channel',
  'transaction',
  'agreement',
  'event',
  'metric',
  'workforce',
  'workforce_role',
  'business_resource',
]

const DEFAULT_ROLES = ['core', 'supporting', 'risk', 'experience', 'channel', 'insight']

const DEFAULT_RELATIONS = [
  'related_to',
  'governed_by',
  'affects',
  'increases',
  'decreases',
  'represented_by',
  'represents',
  'owned_by',
  'uses',
  'supports',
  'enables',
]

const DEFAULT_TECHNICAL_TYPES = ['', 'table', 'api', 'dataset', 'service', 'system', 'document', 'tool']

const DEFAULT_SEMANTIC_SPACES = [
  'business_model',
  'operations',
  'risk',
  'compliance',
  'technology',
]

export const STRUCTURAL_LAYERS = DEFAULT_LAYERS
export const BUSINESS_LAYERS = DEFAULT_LAYERS
export const BUSINESS_ROLES = DEFAULT_ROLES
export const RELATION_TYPES = DEFAULT_RELATIONS
export const SEMANTIC_SPACES = DEFAULT_SEMANTIC_SPACES
export const TECHNICAL_TYPES = DEFAULT_TECHNICAL_TYPES

const baseString = (value, fallback = '') => (typeof value === 'string' ? value.trim() : String(value ?? fallback).trim())

function clone(value) {
  return JSON.parse(JSON.stringify(value ?? {}))
}

export const attributeZodSchema = z.object({
  id: z.string().min(1, 'attribute id is required'),
  name: z.string().min(1, 'attribute name is required'),
  type: z.string().min(1, 'attribute type is required'),
  required: z.boolean().default(false),
  description: z.string().default(''),
})

export const entityNodeZodSchema = z.object({
  id: z.string().min(1, 'entity id is required'),
  name: z.string().min(1, 'entity name is required'),
  structural_layer: z.enum(STRUCTURAL_LAYERS).default('capability'),
  layer: z.enum(STRUCTURAL_LAYERS).default('capability'),
  role: z.enum(BUSINESS_ROLES).default('core'),
  subtype: z.string().default(''),
  technical_type: z.string().default(''),
  semantic_space: z.string().default(''),
  description: z.string().default(''),
  aliases: z.array(z.string().min(1)).default([]),
  attributes: z.array(attributeZodSchema).default([]),
})

export const relationEdgeZodSchema = z.object({
  id: z.string().min(1, 'relation id is required'),
  source_entity_id: z.string().min(1, 'source entity id is required'),
  target_entity_id: z.string().min(1, 'target entity id is required'),
  relation_type: z.enum(RELATION_TYPES),
  description: z.string().default(''),
})

function normalizeRelationType(value) {
  const relationType = baseString(value)
  if (relationType === 'materializes') return 'represents'
  if (relationType === 'materialized_in' || relationType === 'materialized in') return 'represented_by'
  return RELATION_TYPES.includes(relationType) ? relationType : RELATION_TYPES[0]
}

export const layoutNodeZodSchema = z.object({
  x: z.number(),
  y: z.number(),
  collapsed: z.boolean().optional(),
})

export const layoutZodSchema = z.object({
  nodes: z.record(layoutNodeZodSchema).default({}),
})

export const businessModelZodSchema = z.object({
  entities: z.array(entityNodeZodSchema).default([]),
  relations: z.array(relationEdgeZodSchema).default([]),
  layout: layoutZodSchema.default({ nodes: {} }),
})

function uniqueId(base, used) {
  let slug = baseString(base) || 'entity'
  let candidate = slug
  let counter = 1
  while (used.has(candidate)) {
    candidate = `${slug}_${counter}`
    counter += 1
  }
  used.add(candidate)
  return candidate
}

function normalizeAttribute(attr = {}, index = 0) {
  const record = attr && typeof attr === 'object' ? attr : {}
  return {
    id: baseString(record.id, `attr_${index + 1}`) || `attr_${index + 1}`,
    name: baseString(record.name, `Attribute ${index + 1}`) || `Attribute ${index + 1}`,
    type: baseString(record.type, 'string') || 'string',
    required: Boolean(record.required),
    description: baseString(record.description),
  }
}

export function normalizeEntityNode(entity = {}, index = 0, usedIds = new Set()) {
  const record = entity && typeof entity === 'object' ? entity : {}
  const id = record.id ? baseString(record.id) : uniqueId(`entity_${index + 1}`, usedIds)
  const aliases = Array.isArray(record.aliases)
    ? record.aliases.map((item) => baseString(item)).filter(Boolean)
    : []
  const attributes = Array.isArray(record.attributes)
    ? record.attributes.map((attr, attrIndex) => normalizeAttribute(attr, attrIndex))
    : []
  const rawLayer = baseString(record.structural_layer || record.layer)
  const structuralLayer = STRUCTURAL_LAYERS.includes(rawLayer) ? rawLayer : 'capability'
  return {
    id,
    name: baseString(record.name, id) || id,
    structural_layer: structuralLayer,
    layer: structuralLayer,
    role: BUSINESS_ROLES.includes(baseString(record.role)) ? baseString(record.role) : 'core',
    subtype: baseString(record.subtype),
    technical_type: baseString(record.technical_type),
    semantic_space: baseString(record.semantic_space),
    description: baseString(record.description),
    aliases,
    attributes,
  }
}

export function normalizeRelationEdge(relation = {}, index = 0, entityIds = new Set(), usedIds = new Set()) {
  const record = relation && typeof relation === 'object' ? relation : {}
  const id = record.id ? baseString(record.id) : uniqueId(`relation_${index + 1}`, usedIds)
  return {
    id,
    source_entity_id: baseString(record.source_entity_id) || [...entityIds][0] || '',
    target_entity_id: baseString(record.target_entity_id) || [...entityIds][1] || [...entityIds][0] || '',
    relation_type: normalizeRelationType(record.relation_type || record.type),
    description: baseString(record.description),
  }
}

export function normalizeLayout(layout = {}, entityIds = []) {
  const currentNodes = layout && typeof layout === 'object' && layout.nodes && typeof layout.nodes === 'object' ? layout.nodes : {}
  const nodes = {}
  entityIds.forEach((id, index) => {
    const existing = currentNodes[id]
    if (existing && typeof existing === 'object' && Number.isFinite(existing.x) && Number.isFinite(existing.y)) {
      nodes[id] = { x: Number(existing.x), y: Number(existing.y), collapsed: Boolean(existing.collapsed) }
    } else {
      nodes[id] = computeDefaultPosition(index)
    }
  })
  return { nodes }
}

export function computeDefaultPosition(index = 0) {
  const column = index % 3
  const row = Math.floor(index / 3)
  return {
    x: 80 + column * 320,
    y: 60 + row * 220,
  }
}

export function normalizeBusinessModelPayload(payload = {}) {
  const source = payload && typeof payload === 'object' ? payload : {}
  const entityIds = new Set()
  const entities = Array.isArray(source.entities)
    ? source.entities.map((entity, index) => {
        const normalized = normalizeEntityNode(entity, index, entityIds)
        return normalized
      })
    : extractLegacyEntity(source, entityIds)

  const layout = normalizeLayout(source.layout, entities.map((entity) => entity.id))

  const relationIds = new Set()
  const relations = Array.isArray(source.relations)
    ? source.relations.map((relation, index) =>
        normalizeRelationEdge(relation, index, new Set(entities.map((entity) => entity.id)), relationIds),
      )
    : []

  return {
    entities,
    relations,
    layout,
  }
}

function extractLegacyEntity(source = {}, entityIds) {
  const id = baseString(source.entity_id) || baseString(source.asset_id) || 'entity_1'
  const rawLayer = baseString(source.structural_layer || source.domain || source.layer)
  const structuralLayer = STRUCTURAL_LAYERS.includes(rawLayer) ? rawLayer : 'capability'
  const legacyEntity = {
    id,
    name: baseString(source.entity_name) || baseString(source.name) || id,
    structural_layer: structuralLayer,
    layer: structuralLayer,
    role: 'core',
    subtype: baseString(source.subtype),
    technical_type: baseString(source.technical_type),
    semantic_space: baseString(source.semantic_space),
    description: baseString(source.description) || baseString(source.definition),
    aliases: Array.isArray(source.aliases) ? source.aliases.map((alias) => baseString(alias)).filter(Boolean) : [],
    attributes: Array.isArray(source.attributes)
      ? source.attributes.map((attr, index) => normalizeAttribute(attr, index))
      : [],
  }
  entityIds.add(id)
  return [legacyEntity]
}

export function normalizeBusinessModelDocument(document = {}) {
  const base = document && typeof document === 'object' ? clone(document) : {}
  const payloadSource = base.payload && typeof base.payload === 'object' ? base.payload : base
  return {
    ...base,
    payload: normalizeBusinessModelPayload(payloadSource),
  }
}

export function createDefaultAttribute(index = 0) {
  return {
    id: `attr_${index + 1}`,
    name: `Attribute ${index + 1}`,
    type: 'string',
    required: false,
    description: '',
  }
}

export function createDefaultEntity(index = 0, existingIds = []) {
  const used = new Set(existingIds)
  const id = uniqueId(`entity_${index + 1}`, used)
  return {
    id,
    name: `Entity ${index + 1}`,
    structural_layer: 'capability',
    layer: 'capability',
    role: 'core',
    subtype: '',
    technical_type: '',
    semantic_space: '',
    description: '',
    aliases: [],
    attributes: [createDefaultAttribute(0)],
  }
}

export function createDefaultRelation(index = 0, sourceId = '', targetId = '') {
  return {
    id: `relation_${index + 1}`,
    source_entity_id: sourceId,
    target_entity_id: targetId,
    relation_type: RELATION_TYPES[0],
    description: '',
  }
}

export function validateBusinessModelDocument(document = {}) {
  const normalized = normalizeBusinessModelDocument(document)
  const payload = normalized.payload
  const errors = []
  const warnings = []

  const result = businessModelZodSchema.safeParse(payload)
  if (!result.success) {
    errors.push(...result.error.issues.map((issue) => `${issue.path.join('.')} ${issue.message}`.trim()))
  }

  const entityIdSet = new Set()
  payload.entities.forEach((entity, index) => {
    if (entityIdSet.has(entity.id)) {
      errors.push(`entities[${index}].id duplicates ${entity.id}`)
    }
    entityIdSet.add(entity.id)
  })

  payload.relations.forEach((relation, index) => {
    if (!entityIdSet.has(relation.source_entity_id)) {
      warnings.push(`relations[${index}] source ${relation.source_entity_id} missing from entities`)
    }
    if (!entityIdSet.has(relation.target_entity_id)) {
      warnings.push(`relations[${index}] target ${relation.target_entity_id} missing from entities`)
    }
    if (relation.source_entity_id === relation.target_entity_id) {
      warnings.push(`relations[${index}] connects entity ${relation.source_entity_id} to itself`)
    }
  })

  return {
    valid: errors.length === 0,
    payload,
    errors,
    warnings,
  }
}

export function knowledgeBaseFromDocument(document = {}) {
  const payload = document && typeof document === 'object' ? document.payload || document : {}
  return (
    baseString(document?.primary_kb) ||
    baseString(document?.owner) ||
    baseString(document?.knowledge_base) ||
    baseString(payload.primary_kb) ||
    baseString(payload.owner) ||
    baseString(payload.knowledge_base) ||
    'catalog'
  )
}
