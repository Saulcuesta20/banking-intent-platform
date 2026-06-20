import { writeFile } from 'node:fs/promises'
import { buildHomeFromModuleRegistry, ensureOutputDirs, readModuleRegistry, registryFile } from './module-utils.mjs'

const registryData = await readModuleRegistry()
const registry = {
  generatedAt: new Date().toISOString(),
  domains: registryData.domains,
  modules: registryData.modules,
  home: buildHomeFromModuleRegistry(registryData),
}

await ensureOutputDirs()
await writeFile(registryFile, `${JSON.stringify(registry, null, 2)}\n`)

console.log(
  `Generated module registry from ${registryData.domains.length} domains, ${registryData.modules.length} modules, ${registry.home.featured_flows.length} processes.`,
)
