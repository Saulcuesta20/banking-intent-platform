export type MenuItem = {
  id: string
  label: string
  path?: string | null
  icon?: string | null
  children?: MenuItem[]
}

export type TopMenuItem = {
  id: string
  label: string
}

export type LauncherModule = {
  module_id: string
  label: string
  description: string
  icon: string
  aliases: string[]
  flow_prefixes: string[]
  menus: MenuItem[]
  top_menus?: TopMenuItem[]
  flow_count: number
  domain_id?: string
  domain_label?: string
}

export type LauncherFlowSummary = {
  module_id: string
  flow_id: string
  flow_name: string
  intent: string
  business_event: string
  source_path?: string | null
  source_type: string
  plan_steps: number
  user_tasks: string[]
  related_process_ids: string[]
  confidence: number
  explanation: string
  renderer?: 'react' | 'external'
  editor_route?: string
  module_config_id?: string
  form_id?: string
  form_version?: string
  domain_id?: string
  domain_label?: string
}

export type LauncherHomeResponse = {
  modules: LauncherModule[]
  featured_flows: LauncherFlowSummary[]
  recent_flows: LauncherFlowSummary[]
  navigation: Record<string, unknown>
}

export type ModuleRegistryDocument = {
  generatedAt: string
  domains?: LauncherDomain[]
  modules?: unknown[]
  home: LauncherHomeResponse
}

export type LauncherChatResponse = {
  message: string
  assistant_message: string
  selected_module?: LauncherModule | null
  selected_flow?: LauncherFlowSummary | null
  ask_result: Record<string, unknown>
  navigation: Record<string, unknown>
  center_panel: Record<string, unknown>
  context_panel: Record<string, unknown>
  log_events: LogEvent[]
}

export type LauncherFlowDetailResponse = {
  module?: LauncherModule | null
  flow?: LauncherFlowSummary | null
  process?: Record<string, unknown> | null
  form?: Record<string, unknown> | null
  form_version?: Record<string, unknown> | null
  renderer?: string | null
  editor_route?: string | null
}

export type ExecutionResult = {
  flow_id?: string | null
  process_id: string
  instance_id?: string | null
  status: string
  current_node_id?: string | null
  waiting_for?: string[]
  data?: Record<string, unknown>
  events?: Array<Record<string, unknown>>
  workflow_trace?: Array<Record<string, unknown>>
}

export type LogEvent = {
  level?: string
  message?: string
  timestamp?: string
  [key: string]: unknown
}

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  flow?: LauncherFlowSummary | null
  createdAt: string
}

export type LauncherDomain = {
  domainId: string
  label: string
  description: string
  order?: number
}

export type ModuleMenuItem = {
  id: string
  label: string
  path?: string
  icon?: string
  children?: ModuleMenuItem[]
}

export type ModuleProcessDefinition = {
  processId: string
  name: string
  intent: string
  businessEvent: string
  sourcePath?: string
  processIds?: string[]
  userTasks?: string[]
  editorRoute: string
  currentFormVersion: string
  formId: string
}

export type LauncherModuleManifest = {
  moduleId: string
  label: string
  description: string
  icon: string
  aliases?: string[]
  menus?: ModuleMenuItem[]
  topMenus?: TopMenuItem[]
}

export type CatalogAsset = {
  asset_id: string
  version: string
  asset_type: string
  name?: string | null
  status: string
  primary_kb?: string | null
  domain_id?: string | null
  module_id?: string | null
  tags: string[]
  stores: string[]
  payload: Record<string, unknown>
  asset_set_id?: string | null
  asset_set_version?: string | null
  active: boolean
  active_environment?: string | null
}

export type CatalogTreeNode = {
  id: string
  label: string
  kind: 'knowledge_base' | 'asset_set' | 'asset'
  count?: number
  asset_id?: string
  asset_type?: string
  version?: string
  status?: string
  tags?: string[]
  active?: boolean
  children: CatalogTreeNode[]
}

export type CatalogAssetDetail = CatalogAsset & {
  checksum?: string | null
  relationships: Array<{
    type: string
    target_asset_id: string
    metadata: Record<string, unknown>
  }>
}

export type OntologySelection = {
  entity: {
    asset_id: string
    name?: string
    layer?: string
    role?: string
    subtype?: string
    technical_type?: string
    description?: string
    aliases?: string[]
  } | null
  relations: Array<{
    id: string
    relation_type: string
    relation_family?: string
    direction?: 'incoming' | 'outgoing'
    source_entity_id?: string
    source_name?: string
    target_entity_id: string
    target_name?: string
  }>
}

export type AgentType = 'planning' | 'coordinator' | 'delegator' | 'worker' | 'monitoring'

export type SkillAsset = {
  skill_id: string
  title: string
  description: string
  scope: 'business-agents' | 'asset-behaviors' | 'launcher-behaviors'
  agent_types: AgentType[]
  allowed_tools: string[]
  status: 'draft' | 'review' | 'active'
  version: string
  markdown: string
  updated_at: string
}

export type AgentDraft = {
  agent_id: string
  name: string
  description: string
  agent_type: AgentType
  domain: 'ask' | 'ingestion' | 'asset' | 'tool' | 'system'
  skill_ids: string[]
  tool_ids: string[]
  status: 'draft' | 'review' | 'active'
}

export type AssetSetSummary = {
  asset_set_id: string
  name: string
  version: string
  status: string
  domain_id?: string | null
  module_id?: string | null
  asset_type?: string | null
  description: string
  git_commit?: string | null
  checksum: string
  metadata: Record<string, unknown>
  created_at: string
  active_environment?: string | null
}

export type AssetSetDetail = AssetSetSummary & {
  members: CatalogAsset[]
  reviews: Array<Record<string, unknown>>
  deployments: Array<Record<string, unknown>>
  lifecycle_events: Array<Record<string, unknown>>
}

export type CatalogMetadata = {
  environment: string
  asset_types: string[]
  knowledge_bases: string[]
  statuses: string[]
  tags: string[]
  domains: string[]
  modules: string[]
}
