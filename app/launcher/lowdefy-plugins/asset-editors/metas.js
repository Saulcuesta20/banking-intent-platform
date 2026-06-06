const inputMeta = (description) => ({
  category: 'input',
  icons: [],
  valueType: 'object',
  cssKeys: { element: description },
  events: {
    onChange: {
      description: 'Triggered when the asset definition changes.',
      event: { value: 'The edited asset document.' },
    },
    onValidate: {
      description: 'Triggered when the editor validates the asset.',
      event: { valid: 'Whether the asset is valid.', errors: 'Validation errors.' },
    },
  },
  properties: {
    type: 'object',
    additionalProperties: true,
    properties: {
      title: { type: 'string' },
      readOnly: { type: 'boolean', default: false },
      height: { type: 'number', default: 520 },
      apiBaseUrl: { type: 'string' },
      environment: { type: 'string', default: 'dev' },
    },
  },
})

export const AssetCodeEditor = inputMeta('JSON and YAML asset code editor.')
export const ProcessCanvas = inputMeta('Visual process and flow editor.')
export const OntologyGraph = inputMeta('Ontology node and relationship editor.')
export const RuleBuilder = inputMeta('Business rule condition builder.')
export const FormDesigner = inputMeta('Declarative form designer.')
export const NavigationTree = inputMeta('Domain, module, menu, and submenu tree editor.')
export const FlowEditor = inputMeta('Flow definition editor.')
export const ProcessEditor = inputMeta('Process definition editor.')
export const BusinessRuleEditor = inputMeta('Business rule editor.')
export const OntologyEditor = inputMeta('Ontology graph editor.')
export const QaEditor = inputMeta('Question and answer asset editor.')
export const EntityEditor = inputMeta('Entity and concept editor.')
export const ToolApiEditor = inputMeta('Tool and API asset editor.')
export const FormAssetEditor = inputMeta('Form asset designer.')
export const ModuleMenuEditor = inputMeta('Module, menu, and submenu editor.')
export const DocumentConfigEditor = inputMeta('Document and configuration asset editor.')

export const AssetStudio = {
  category: 'display',
  icons: [],
  valueType: null,
  cssKeys: { element: 'Unified Catalog asset studio.' },
  events: {},
  properties: {
    type: 'object',
    additionalProperties: false,
    properties: {
      apiBaseUrl: { type: 'string', default: 'http://127.0.0.1:8030' },
      environment: { type: 'string', default: 'dev' },
      actor: { type: 'string', default: 'saul' },
    },
  },
}

export const AssetEditorHost = {
  category: 'display',
  icons: [],
  valueType: null,
  cssKeys: { element: 'Launcher-embedded asset editor host.' },
  events: {},
  properties: {
    type: 'object',
    additionalProperties: false,
    properties: {
      apiBaseUrl: { type: 'string', default: 'http://127.0.0.1:8030' },
      environment: { type: 'string', default: 'dev' },
      actor: { type: 'string', default: 'saul' },
      assetId: { type: 'string' },
      version: { type: 'string' },
      editorType: { type: 'string' },
    },
  },
}
