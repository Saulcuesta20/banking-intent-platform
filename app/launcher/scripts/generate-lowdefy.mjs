import { mkdir, writeFile } from 'node:fs/promises'
import { buildHomeFromModuleRegistry, ensureOutputDirs, lowdefyFile, readModuleRegistry, registryFile } from './module-utils.mjs'

const editorPages = [
  ['asset-flow-editor', 'flow'],
  ['asset-process-editor', 'process'],
  ['asset-business-rule-editor', 'business_rule'],
  ['asset-ontology-editor', 'ontology'],
  ['asset-qa-editor', 'qa'],
  ['asset-entity-editor', 'entity'],
  ['asset-tool-api-editor', 'tool_api'],
  ['asset-form-editor', 'form'],
  ['asset-module-menu-editor', 'module_menu'],
  ['asset-document-config-editor', 'document_config'],
  ['asset-code-editor', 'source'],
]

function assetEditorPage(pageId, editorType) {
  return [
    `  - id: ${pageId}`,
    '    type: Box',
    '    blocks:',
    '      - id: asset_editor_host',
    '        type: AssetEditorHost',
    '        properties:',
    '          apiBaseUrl: http://127.0.0.1:8030',
    '          environment: dev',
    '          actor: saul',
    `          editorType: ${editorType}`,
  ].join('\n')
}

function pageFragment(pageId, editorType) {
  return [
    `id: ${pageId}`,
    'type: Box',
    'blocks:',
    '  - id: asset_editor_host',
    '    type: AssetEditorHost',
    '    properties:',
    '      apiBaseUrl: http://127.0.0.1:8030',
    '      environment: dev',
    '      actor: saul',
    `      editorType: ${editorType}`,
    '',
  ].join('\n')
}

function lowdefyYamlForRegistry(registry) {
  return [
    'lowdefy: 5.3.0',
    '',
    'name: DevBank Dynamic Flow Runtime',
    '',
    'plugins:',
    '  - name: "@devbank/lowdefy-asset-editors"',
    '    version: "file:../../../lowdefy-plugins/asset-editors"',
    '',
    'connections:',
    '  - id: launcher_api',
    '    type: AxiosHttp',
    '    properties:',
    '      baseURL: http://127.0.0.1:8030',
    '',
    'theme:',
    '  antd:',
    '    token:',
    '      colorPrimary: "#1463ff"',
    '      borderRadius: 8',
    '      fontFamily: Inter, system-ui, sans-serif',
    '',
    'pages:',
    editorPages.map(([pageId, editorType]) => assetEditorPage(pageId, editorType)).join('\n'),
    '',
    '',
  ].join('\n')
}

const registryData = await readModuleRegistry()
const registry = {
  generatedAt: new Date().toISOString(),
  domains: registryData.domains,
  modules: registryData.modules,
  home: buildHomeFromModuleRegistry(registryData),
}

await ensureOutputDirs()
await mkdir(new URL('../lowdefy-runtime/pages/', import.meta.url), { recursive: true })
await writeFile(lowdefyFile, lowdefyYamlForRegistry(registryData))
await Promise.all(
  editorPages.map(([pageId, editorType]) =>
    writeFile(new URL(`../lowdefy-runtime/pages/${pageId}.yaml`, import.meta.url), pageFragment(pageId, editorType)),
  ),
)
await writeFile(registryFile, `${JSON.stringify(registry, null, 2)}\n`)

console.log(
  `Generated Lowdefy and registry from ${registryData.domains.length} domains, ${registryData.modules.length} modules, ${registry.home.featured_flows.length} processes.`,
)
