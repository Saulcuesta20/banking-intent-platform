import { access, mkdir, readdir, readFile } from 'node:fs/promises'
import { join } from 'node:path'

export const root = new URL('..', import.meta.url).pathname
export const modulesDir = join(root, 'modules')
export const publicDir = join(root, 'public')
export const registryFile = join(publicDir, 'module-registry.json')

export async function ensureOutputDirs() {
  await mkdir(publicDir, { recursive: true })
}

async function exists(path) {
  try {
    await access(path)
    return true
  } catch {
    return false
  }
}

async function readJson(path) {
  return JSON.parse(await readFile(path, 'utf8'))
}

function assertString(value, path) {
  if (typeof value !== 'string' || value.trim() === '') {
    throw new Error(`Invalid module manifest: "${path}" must be a non-empty string.`)
  }
}

function assertArray(value, path) {
  if (!Array.isArray(value)) {
    throw new Error(`Invalid module manifest: "${path}" must be an array.`)
  }
}

function validateField(field, path) {
  assertString(field.id, `${path}.id`)
  assertString(field.label, `${path}.label`)
  assertString(field.type, `${path}.type`)
}

function validateForm(form, path) {
  assertString(form.formId, `${path}.formId`)
  assertString(form.version, `${path}.version`)
  assertString(form.pageId, `${path}.pageId`)
  assertString(form.title, `${path}.title`)
  assertString(form.submitTitle, `${path}.submitTitle`)
  assertArray(form.fields, `${path}.fields`)
  form.fields.forEach((field, index) => validateField(field, `${path}.fields[${index}]`))
}

function validateProcess(process, path) {
  assertString(process.processId, `${path}.processId`)
  assertString(process.name, `${path}.name`)
  assertString(process.intent, `${path}.intent`)
  assertString(process.businessEvent, `${path}.businessEvent`)
  assertString(process.editorRoute, `${path}.editorRoute`)
  assertString(process.currentFormVersion, `${path}.currentFormVersion`)
  assertString(process.formId, `${path}.formId`)
}

function validateModule(module, path) {
  assertString(module.moduleId, `${path}.moduleId`)
  assertString(module.label, `${path}.label`)
  assertString(module.description, `${path}.description`)
  assertString(module.icon, `${path}.icon`)
  if (module.menus != null) assertArray(module.menus, `${path}.menus`)
}

export async function readDomains() {
  const domainsPath = join(modulesDir, 'domains.json')
  const domains = await readJson(domainsPath)
  assertArray(domains, 'modules/domains.json')

  for (const domain of domains) {
    assertString(domain.domainId, 'modules/domains.json[].domainId')
    assertString(domain.label, 'modules/domains.json[].label')
    assertString(domain.description, 'modules/domains.json[].description')
  }

  return domains.sort((left, right) => (left.order ?? 999) - (right.order ?? 999))
}

async function readProcess(domainId, moduleId, processEntry) {
  const processRoot = join(modulesDir, domainId, moduleId, 'processes', processEntry.name)
  const processPath = join(processRoot, 'process.json')
  const process = await readJson(processPath)
  validateProcess(process, `modules/${domainId}/${moduleId}/processes/${processEntry.name}/process.json`)

  const formsRoot = join(modulesDir, domainId, moduleId, 'forms', process.formId, 'versions')
  const formVersionPath = join(formsRoot, process.currentFormVersion, 'form.json')
  const form = await readJson(formVersionPath)
  validateForm(form, `modules/${domainId}/${moduleId}/forms/${process.formId}/versions/${process.currentFormVersion}/form.json`)

  return {
    ...process,
    processFolder: processEntry.name,
    form,
    formVersions: [form.version],
  }
}

async function readModule(domain, moduleEntry) {
  const moduleRoot = join(modulesDir, domain.domainId, moduleEntry.name)
  const modulePath = join(moduleRoot, 'module.json')
  const module = await readJson(modulePath)
  validateModule(module, `modules/${domain.domainId}/${moduleEntry.name}/module.json`)

  const processesRoot = join(moduleRoot, 'processes')
  const processEntries = (await exists(processesRoot))
    ? (await readdir(processesRoot, { withFileTypes: true })).filter((entry) => entry.isDirectory())
    : []
  const processes = []

  for (const processEntry of processEntries) {
    processes.push(await readProcess(domain.domainId, module.moduleId, processEntry))
  }

  return {
    ...module,
    domainId: domain.domainId,
    domainLabel: domain.label,
    moduleFolder: moduleEntry.name,
    processes: processes.sort((left, right) => left.name.localeCompare(right.name)),
  }
}

export async function readModuleRegistry() {
  const domains = await readDomains()
  const modules = []

  for (const domain of domains) {
    const domainRoot = join(modulesDir, domain.domainId)
    const moduleEntries = (await exists(domainRoot))
      ? (await readdir(domainRoot, { withFileTypes: true })).filter((entry) => entry.isDirectory())
      : []

    for (const moduleEntry of moduleEntries) {
      const modulePath = join(domainRoot, moduleEntry.name, 'module.json')
      if (!(await exists(modulePath))) continue
      modules.push(await readModule(domain, moduleEntry))
    }
  }

  return { domains, modules }
}

export function buildHomeFromModuleRegistry(registry) {
  const modules = registry.modules.map((module) => ({
    module_id: module.moduleId,
    label: module.label,
    description: module.description,
    icon: module.icon,
    aliases: module.aliases ?? [],
    flow_prefixes: [module.moduleId],
    menus: module.menus ?? [],
    top_menus: module.topMenus ?? [],
    flow_count: module.processes.length,
    domain_id: module.domainId,
    domain_label: module.domainLabel,
  }))

  const featured_flows = registry.modules.flatMap((module) =>
    module.processes.map((process) => ({
      module_id: module.moduleId,
      flow_id: process.processId,
      flow_name: process.name,
      intent: process.intent,
      business_event: process.businessEvent,
      source_path: process.sourcePath,
      source_type: 'module',
      plan_steps: process.userTasks?.length ?? 0,
      user_tasks: process.userTasks ?? [],
      related_process_ids: process.processIds ?? [],
      confidence: 1,
      explanation: process.intent,
      renderer: 'react',
      editor_route: process.editorRoute,
      module_config_id: module.moduleId,
      form_id: process.form.formId,
      form_version: process.form.version,
      domain_id: module.domainId,
      domain_label: module.domainLabel,
    })),
  )

  return {
    modules: [
      {
        module_id: 'home',
        label: 'Home',
        description: 'Workspace principal del launcher.',
        icon: 'home',
        aliases: ['inicio'],
        flow_prefixes: [],
        menus: [],
        flow_count: 0,
        domain_id: 'all',
        domain_label: 'Todos',
      },
      ...modules,
      {
        module_id: 'admin',
        label: 'Admin',
        description: 'Registro de modulos, permisos y configuracion.',
        icon: 'settings',
        aliases: ['administracion'],
        flow_prefixes: [],
        menus: [],
        flow_count: 0,
        domain_id: 'all',
        domain_label: 'Todos',
      },
    ],
    featured_flows,
    recent_flows: [],
    navigation: {
      source: 'module-registry',
      domains: registry.domains,
      module_count: registry.modules.length,
    },
  }
}
