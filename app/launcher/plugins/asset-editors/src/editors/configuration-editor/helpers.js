import { z } from 'zod'

export const configurationDefinitionZodSchema = z.object({
  config_id: z.string().min(1, 'config_id is required'),
  scope: z.string().optional(),
  settings: z.record(z.unknown()).optional(),
  environment: z.string().optional(),
  owner: z.string().optional(),
})

function asString(value) {
  return String(value ?? '').trim()
}

export function normalizeConfigurationDefinition(payload = {}) {
  return {
    config_id: asString(payload.config_id),
    scope: asString(payload.scope),
    settings: payload.settings && typeof payload.settings === 'object' ? payload.settings : {},
    environment: asString(payload.environment),
    owner: asString(payload.owner),
  }
}

export function createDefaultConfiguration() {
  return {
    config_id: 'config-new',
    scope: '',
    settings: {},
    environment: '',
    owner: '',
  }
}

export function validateConfigurationDocument(document = {}) {
  const payload = document.payload && typeof document.payload === 'object' ? document.payload : document
  const configuration = normalizeConfigurationDefinition(payload)
  const errors = []
  const warnings = []

  const result = configurationDefinitionZodSchema.safeParse(configuration)
  if (!result.success) {
    errors.push(...result.error.issues.map((issue) => `${issue.path.join('.')} ${issue.message}`.trim()))
  }

  if (!configuration.config_id.includes('.')) {
    warnings.push('config_id may be missing a dot-separated prefix (e.g. config.lending.rate)')
  }

  if (!configuration.environment) {
    warnings.push('environment is not set')
  }

  if (!configuration.owner) {
    warnings.push('owner is not set')
  }

  return {
    valid: errors.length === 0,
    configuration,
    errors,
    warnings,
  }
}
