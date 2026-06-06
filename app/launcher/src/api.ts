import type {
  LauncherChatResponse,
  LauncherFlowDetailResponse,
  LauncherHomeResponse,
  LauncherModule,
  ExecutionResult,
  AssetSetDetail,
  AssetSetSummary,
  CatalogAssetDetail,
  CatalogMetadata,
  CatalogTreeNode,
} from './types'

const API_BASE_URL = import.meta.env.VITE_LAUNCHER_API_URL ?? 'http://127.0.0.1:8030'

async function request<T>(path: string, init?: RequestInit, timeoutMs?: number): Promise<T> {
  const controller = timeoutMs ? new AbortController() : null
  const timeoutId = controller ? window.setTimeout(() => controller.abort(), timeoutMs) : null

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    signal: controller?.signal ?? init?.signal,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  })

  if (timeoutId) window.clearTimeout(timeoutId)

  if (!response.ok) {
    const body = await response.text()
    throw new Error(body || `Request failed with ${response.status}`)
  }

  return response.json() as Promise<T>
}

export function getLauncherHome() {
  return request<LauncherHomeResponse>('/launcher/home')
}

export function getFlowDetail(flowId: string) {
  return request<LauncherFlowDetailResponse>(`/launcher/flows/${encodeURIComponent(flowId)}`)
}

export function getExecutions(flowId?: string | null) {
  const query = flowId ? `?flow_id=${encodeURIComponent(flowId)}` : ''
  return request<{ executions: ExecutionResult[] }>(`/orchestrator/executions${query}`)
}

export type CatalogFilters = {
  environment?: string
  query?: string
  assetType?: string
  knowledgeBase?: string
  status?: string
  tag?: string
  activeOnly?: boolean
}

export function getCatalogMetadata(environment = 'dev') {
  return request<CatalogMetadata>(`/catalog/metadata?environment=${encodeURIComponent(environment)}`)
}

export function getCatalogAssets(filters: CatalogFilters = {}) {
  const params = new URLSearchParams()
  params.set('environment', filters.environment ?? 'dev')
  if (filters.query) params.set('query', filters.query)
  if (filters.assetType) params.set('asset_type', filters.assetType)
  if (filters.knowledgeBase) params.set('knowledge_base', filters.knowledgeBase)
  if (filters.status) params.set('status', filters.status)
  if (filters.tag) params.set('tag', filters.tag)
  if (filters.activeOnly) params.set('active_only', 'true')
  return request<{ count: number; assets: CatalogAssetDetail[]; tree: CatalogTreeNode[] }>(
    `/catalog/assets?${params.toString()}`,
  )
}

export function getCatalogAsset(assetId: string, version?: string) {
  const query = version ? `?version=${encodeURIComponent(version)}` : ''
  return request<CatalogAssetDetail>(`/catalog/assets/${encodeURIComponent(assetId)}${query}`)
}

export function getAssetSets(environment = 'dev') {
  return request<{ asset_sets: AssetSetSummary[] }>(
    `/catalog/asset-sets?environment=${encodeURIComponent(environment)}&status=all`,
  )
}

export function getAssetSet(assetSetId: string, version: string) {
  return request<AssetSetDetail>(
    `/catalog/asset-sets/${encodeURIComponent(assetSetId)}/${encodeURIComponent(version)}`,
  )
}

export function transitionAssetSet(
  assetSetId: string,
  version: string,
  action: string,
  comment?: string,
) {
  return request<AssetSetDetail>(`/catalog/asset-sets/${encodeURIComponent(assetSetId)}/transition`, {
    method: 'POST',
    body: JSON.stringify({ version, action, actor: 'saul', comment }),
  })
}

export function deployAssetSet(assetSetId: string, version: string, environment = 'dev') {
  return request<Record<string, unknown>>(`/catalog/asset-sets/${encodeURIComponent(assetSetId)}/deploy`, {
    method: 'POST',
    body: JSON.stringify({ version, environment, actor: 'saul' }),
  })
}

export function rollbackAssetSet(assetSetId: string, version: string, environment = 'dev') {
  return request<Record<string, unknown>>(`/catalog/asset-sets/${encodeURIComponent(assetSetId)}/rollback`, {
    method: 'POST',
    body: JSON.stringify({ version, environment, actor: 'saul' }),
  })
}

type AskResponse = {
  can_resolve?: boolean
  flow_id?: string
  flow_name?: string
  intent?: string
  confidence?: number
  business_event?: string
  explanation?: string
  plan?: string[]
  tasks?: unknown[]
  [key: string]: unknown
}

type ChatContext = {
  moduleId?: string | null
  domainId?: string | null
  menuId?: string | null
  modules: LauncherModule[]
}

export async function sendChatMessage(message: string, context: ChatContext): Promise<LauncherChatResponse> {
  let askResult: AskResponse
  let askError: string | null = null

  try {
    askResult = await request<AskResponse>(
      '/ask',
      {
        method: 'POST',
        body: JSON.stringify({
          question: message,
        }),
      },
    )
  } catch (error) {
    askError = error instanceof Error ? error.message : String(error)
    askResult = {
      can_resolve: false,
      flow_id: 'unknown',
      flow_name: 'Unknown flow',
      intent: 'unknown',
      confidence: 0,
      business_event: 'unknown',
      explanation: 'AskService no respondio correctamente. Revisa el trace para ver el error del ciclo de pregunta.',
    }
  }

  let selectedFlow: LauncherChatResponse['selected_flow'] = buildSelectedFlowFromAsk(askResult)
  if (selectedFlow) {
    try {
      const context = await getFlowDetail(selectedFlow.flow_id)
      selectedFlow = {
        ...selectedFlow,
        ...(context.flow ?? {}),
        lowdefy_url: context.lowdefy_url ?? undefined,
      }
    } catch {
      // Ask remains authoritative even if optional launcher context is unavailable.
    }
  }
  const selectedModule =
    context.modules.find((module) => selectedFlow?.module_id && module.module_id === selectedFlow.module_id) ??
    context.modules.find((module) => module.module_id === context.moduleId) ??
    null

  return {
    message,
    assistant_message:
      askResult.explanation ??
      (selectedFlow ? `Ask selecciono el flow "${selectedFlow.flow_name}".` : 'Ask proceso la pregunta, pero no selecciono un flow activo.'),
    selected_module: selectedModule,
    selected_flow: selectedFlow,
    ask_result: {
      ...askResult,
      ask_error: askError,
      launcher_context: {
        module_id: context.moduleId,
        domain_id: context.domainId,
        menu_id: context.menuId,
      },
    },
    navigation: {},
    center_panel: {},
    context_panel: {},
    log_events: [
      {
        level: askError ? 'warning' : askResult.can_resolve ? 'success' : 'warning',
        message: askError
          ? 'AskService error'
          : `AskService flow_id=${askResult.flow_id ?? 'unknown'} confidence=${askResult.confidence ?? 0}`,
        timestamp: new Date().toISOString(),
      },
    ],
  }
}

function buildSelectedFlowFromAsk(askResult: AskResponse) {
  const flowId = String(askResult.flow_id ?? '')
  const canResolve = askResult.can_resolve === true && flowId !== '' && flowId !== 'unknown' && flowId !== 'qa.answer'
  if (!canResolve) return null

  const moduleId = flowId.split('.')[0] || 'unknown'
  const tasks = Array.isArray(askResult.tasks) ? askResult.tasks : []

  return {
    module_id: moduleId,
    flow_id: flowId,
    flow_name: String(askResult.flow_name ?? flowId),
    intent: String(askResult.intent ?? ''),
    business_event: String(askResult.business_event ?? ''),
    source_type: 'ask',
    plan_steps: Array.isArray(askResult.plan) ? askResult.plan.length : tasks.length,
    user_tasks: tasks.map(taskToLabel),
    related_process_ids: [],
    confidence: Number(askResult.confidence ?? 0),
    explanation: String(askResult.explanation ?? ''),
    renderer: 'external' as const,
  }
}

function taskToLabel(task: unknown) {
  if (typeof task === 'string') return task
  if (task && typeof task === 'object' && 'task' in task) return String(task.task)
  return String(task)
}
