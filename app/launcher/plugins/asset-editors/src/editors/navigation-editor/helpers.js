import { z } from 'zod'

export const NAVIGATION_ITEM_TYPES = ['menu', 'link', 'divider', 'header']

export const navigationItemZodSchema = z.object({
  id: z.string().min(1, 'id is required'),
  label: z.string().min(1, 'label is required'),
  type: z.enum(NAVIGATION_ITEM_TYPES),
  icon: z.string().default(''),
  route: z.string().default(''),
  children: z.array(z.object({
    id: z.string().min(1, 'id is required'),
    label: z.string().min(1, 'label is required'),
    type: z.string().default('link'),
    route: z.string().default(''),
  })).default([]),
  description: z.string().default(''),
})

export const navigationDefinitionZodSchema = z.object({
  navigation_id: z.string().min(1, 'navigation_id is required'),
  navigation_name: z.string().min(1, 'navigation_name is required'),
  description: z.string().min(1, 'description is required'),
  domain: z.string().min(1, 'domain is required'),
  module: z.string().min(1, 'module is required'),
  items: z.array(navigationItemZodSchema).default([]),
  metadata: z.object({
    version: z.string().default('1.0.0'),
    author: z.string().default(''),
  }).default({}),
})

function asString(value) {
  return String(value ?? '').trim()
}

export function normalizeArray(value) {
  return Array.isArray(value)
    ? value.map((item) => asString(item)).filter(Boolean)
    : []
}

export function normalizeNavigationItem(item, index = 0) {
  const record = item && typeof item === 'object' ? item : {}
  return {
    id: asString(record.id || `nav_${index + 1}`),
    label: asString(record.label || `Item ${index + 1}`),
    type: NAVIGATION_ITEM_TYPES.includes(asString(record.type)) ? asString(record.type) : 'menu',
    icon: asString(record.icon),
    route: asString(record.route),
    children: Array.isArray(record.children)
      ? record.children.map((child, childIndex) => ({
          id: asString(child.id || `child_${childIndex + 1}`),
          label: asString(child.label || `Child ${childIndex + 1}`),
          type: asString(child.type || 'link'),
          route: asString(child.route),
        }))
      : [],
    description: asString(record.description),
  }
}

export function normalizeNavigationDefinition(payload = {}) {
  const metadata = payload.metadata && typeof payload.metadata === 'object' ? payload.metadata : {}
  return {
    navigation_id: asString(payload.navigation_id),
    navigation_name: asString(payload.navigation_name),
    description: asString(payload.description),
    domain: asString(payload.domain),
    module: asString(payload.module),
    items: Array.isArray(payload.items)
      ? payload.items.map((item, index) => normalizeNavigationItem(item, index))
      : [],
    metadata: {
      version: asString(metadata.version || '1.0.0'),
      author: asString(metadata.author),
    },
  }
}

export function createDefaultNavigationItem(index = 0) {
  return {
    id: `nav_${index + 1}`,
    label: `Item ${index + 1}`,
    type: 'menu',
    icon: '',
    route: '',
    children: [],
    description: '',
  }
}

export function validateNavigationDocument(document = {}) {
  const payload = document.payload && typeof document.payload === 'object' ? document.payload : document
  const navigation = normalizeNavigationDefinition(payload)
  const errors = []
  const warnings = []

  const result = navigationDefinitionZodSchema.safeParse(navigation)
  if (!result.success) {
    errors.push(...result.error.issues.map((issue) => `${issue.path.join('.')} ${issue.message}`.trim()))
  }

  if (navigation.items.length === 0) {
    warnings.push('Navigation has no items defined')
  }

  navigation.items.forEach((item, index) => {
    if (!item.route && item.type === 'link') {
      warnings.push(`items[${index}] of type 'link' has no route defined`)
    }
    if (item.children.length > 0) {
      item.children.forEach((child, childIndex) => {
        if (!child.route && child.type === 'link') {
          warnings.push(`items[${index}].children[${childIndex}] of type 'link' has no route defined`)
        }
      })
    }
  })

  return {
    valid: errors.length === 0,
    navigation,
    errors,
    warnings,
  }
}
