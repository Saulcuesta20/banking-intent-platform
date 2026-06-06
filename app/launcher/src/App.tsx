import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import './App.css'
import {
  deployAssetSet,
  getAssetSet,
  getCatalogAssets,
  getCatalogMetadata,
  getExecutions,
  getLauncherHome,
  rollbackAssetSet,
  sendChatMessage,
  transitionAssetSet,
} from './api'
import { AssetDetailPanel } from './components/AssetDetailPanel'
import { AssetExplorer } from './components/AssetExplorer'
import { Header } from './components/Header'
import { LeftNav } from './components/LeftNav'
import { RightContextPanel } from './components/RightContextPanel'
import { Workspace } from './components/Workspace'
import type {
  CatalogAssetDetail,
  ChatMessage,
  LauncherDomain,
  LauncherFlowSummary,
  LauncherHomeResponse,
  LogEvent,
  TopMenuItem,
} from './types'

const defaultTopMenus: TopMenuItem[] = [
  { id: 'queries', label: 'Consultas' },
  { id: 'operations', label: 'Operaciones' },
  { id: 'configuration', label: 'Configuracion' },
  { id: 'reports', label: 'Reportes' },
  { id: 'monitoring', label: 'Monitoreo' },
]

const assetManagementDomain: LauncherDomain = {
  domainId: 'asset-management',
  label: 'Asset Management',
  description: 'Unified Catalog, knowledge bases, AssetSets, editors, review, and deployment.',
  order: 900,
}

const assetTopMenus: TopMenuItem[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'editors', label: 'Editors' },
  { id: 'review', label: 'Review' },
  { id: 'deployments', label: 'Deployments' },
  { id: 'settings', label: 'Settings' },
]

const assetManagementModules = [
  {
    module_id: 'asset-catalog',
    label: 'Assets',
    description: 'Browse and edit Unified Catalog assets.',
    icon: 'assets',
    aliases: ['asset', 'catalog', 'kb'],
    flow_prefixes: [],
    menus: [
      { id: 'tree', label: 'Asset Tree' },
      { id: 'routes', label: 'Routes' },
      { id: 'editors', label: 'Editors' },
    ],
    top_menus: assetTopMenus,
    flow_count: 0,
    domain_id: 'asset-management',
    domain_label: 'Asset Management',
  },
  {
    module_id: 'knowledge-bases',
    label: 'Knowledge Bases',
    description: 'Graph, vector, document, repository, and relational projections.',
    icon: 'knowledge',
    aliases: ['kb', 'graph', 'vector'],
    flow_prefixes: [],
    menus: [{ id: 'projections', label: 'Projections' }],
    top_menus: assetTopMenus,
    flow_count: 0,
    domain_id: 'asset-management',
    domain_label: 'Asset Management',
  },
  {
    module_id: 'asset-sets',
    label: 'AssetSets',
    description: 'Deployment bundles, versions, lifecycle, and review.',
    icon: 'assets',
    aliases: ['bundle', 'assetset'],
    flow_prefixes: [],
    menus: [
      { id: 'versions', label: 'Versions' },
      { id: 'lifecycle', label: 'Lifecycle' },
      { id: 'deployments', label: 'Deployments' },
    ],
    top_menus: assetTopMenus,
    flow_count: 0,
    domain_id: 'asset-management',
    domain_label: 'Asset Management',
  },
  {
    module_id: 'asset-review',
    label: 'Review Queue',
    description: 'Human validation and approval queue.',
    icon: 'tasks',
    aliases: ['review', 'validate'],
    flow_prefixes: [],
    menus: [{ id: 'pending', label: 'Pending Review' }],
    top_menus: assetTopMenus,
    flow_count: 0,
    domain_id: 'asset-management',
    domain_label: 'Asset Management',
  },
]

const emptyHome: LauncherHomeResponse = {
  modules: [],
  featured_flows: [],
  recent_flows: [],
  navigation: { domains: [] },
}

function makeMessage(role: ChatMessage['role'], content: string, flow?: LauncherFlowSummary | null): ChatMessage {
  return {
    id: crypto.randomUUID(),
    role,
    content,
    flow,
    createdAt: new Date().toISOString(),
  }
}

function App() {
  const [leftCollapsed, setLeftCollapsed] = useState(false)
  const [rightCollapsed, setRightCollapsed] = useState(false)
  const [leftWidth, setLeftWidth] = useState(280)
  const [rightWidth, setRightWidth] = useState(360)
  const [activeDomainId, setActiveDomainId] = useState('all')
  const [activeModuleId, setActiveModuleId] = useState('home')
  const [activeTopMenuId, setActiveTopMenuId] = useState('operations')
  const [activeView, setActiveView] = useState<'workspace' | 'assets'>('workspace')
  const [assetFilters, setAssetFilters] = useState({
    query: '',
    knowledgeBase: '',
    assetType: '',
    status: '',
    tag: '',
  })
  const [selectedAsset, setSelectedAsset] = useState<CatalogAssetDetail | null>(null)
  const [selectedFlow, setSelectedFlow] = useState<LauncherFlowSummary | null>(null)
  const [lastAskResult, setLastAskResult] = useState<Record<string, unknown> | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [chatValue, setChatValue] = useState('')
  const [logs, setLogs] = useState<LogEvent[]>([
    { level: 'info', message: 'Launcher shell inicializado', timestamp: new Date().toISOString() },
  ])
  const [messages, setMessages] = useState<ChatMessage[]>([
    makeMessage('assistant', 'Hola, soy el launcher de DevBank. Puedo buscar flows, abrir formularios y preparar una ejecucion.'),
  ])

  const homeQuery = useQuery({
    queryKey: ['launcher-home'],
    queryFn: getLauncherHome,
    retry: 1,
  })

  const home = homeQuery.data ?? emptyHome
  const catalogMetadataQuery = useQuery({
    queryKey: ['catalog-metadata', 'dev'],
    queryFn: () => getCatalogMetadata('dev'),
    enabled: activeView === 'assets',
  })
  const catalogAssetsQuery = useQuery({
    queryKey: ['catalog-assets', assetFilters],
    queryFn: () =>
      getCatalogAssets({
        environment: 'dev',
        query: assetFilters.query || undefined,
        knowledgeBase: assetFilters.knowledgeBase || undefined,
        assetType: assetFilters.assetType || undefined,
        status: assetFilters.status || undefined,
        tag: assetFilters.tag || undefined,
      }),
    enabled: activeView === 'assets',
  })
  const assetSetQuery = useQuery({
    queryKey: ['asset-set', selectedAsset?.asset_set_id, selectedAsset?.asset_set_version],
    queryFn: () => getAssetSet(String(selectedAsset?.asset_set_id), String(selectedAsset?.asset_set_version)),
    enabled: Boolean(selectedAsset?.asset_set_id && selectedAsset?.asset_set_version),
  })
  const lifecycleMutation = useMutation({
    mutationFn: ({ action, comment }: { action: string; comment?: string }) =>
      transitionAssetSet(
        String(selectedAsset?.asset_set_id),
        String(selectedAsset?.asset_set_version),
        action,
        comment,
      ),
    onSuccess: async () => {
      await Promise.all([assetSetQuery.refetch(), catalogAssetsQuery.refetch(), homeQuery.refetch()])
    },
  })
  const deployMutation = useMutation({
    mutationFn: () =>
      deployAssetSet(
        String(selectedAsset?.asset_set_id),
        String(selectedAsset?.asset_set_version),
        'dev',
      ),
    onSuccess: async () => {
      await Promise.all([assetSetQuery.refetch(), catalogAssetsQuery.refetch(), homeQuery.refetch()])
    },
  })
  const rollbackMutation = useMutation({
    mutationFn: () =>
      rollbackAssetSet(
        String(selectedAsset?.asset_set_id),
        String(selectedAsset?.asset_set_version),
        'dev',
      ),
    onSuccess: async () => {
      await Promise.all([assetSetQuery.refetch(), catalogAssetsQuery.refetch(), homeQuery.refetch()])
    },
  })
  const apiDomains = ((home.navigation.domains as LauncherDomain[] | undefined) ?? []).sort(
    (left, right) => (left.order ?? 999) - (right.order ?? 999),
  )
  const domains = [...apiDomains.filter((domain) => domain.domainId !== assetManagementDomain.domainId), assetManagementDomain]
  const apiModules = home.modules
  const filteredModules =
    activeDomainId === 'asset-management'
      ? assetManagementModules
      : activeDomainId === 'all'
        ? apiModules
        : apiModules.filter((module) => module.domain_id === activeDomainId || module.module_id === 'home' || module.module_id === 'admin')
  const modules = filteredModules
  const activeModule = modules.find((module) => module.module_id === activeModuleId) ?? modules[0]
  const activeDomain = domains.find((domain) => domain.domainId === activeDomainId)
  const menuSourceModule =
    activeModule?.module_id && !['home', 'admin'].includes(activeModule.module_id)
      ? activeModule
      : modules.find((module) => !['home', 'admin'].includes(module.module_id))
  const topMenus =
    activeDomainId === 'asset-management'
      ? assetTopMenus
      : menuSourceModule?.top_menus?.length
        ? menuSourceModule.top_menus
        : defaultTopMenus
  const activeTopMenu = topMenus.find((menu) => menu.id === activeTopMenuId) ?? topMenus[0]
  const executionsQuery = useQuery({
    queryKey: ['orchestrator-executions', selectedFlow?.flow_id],
    queryFn: () => getExecutions(selectedFlow?.flow_id),
    enabled: Boolean(selectedFlow?.flow_id),
    refetchInterval: formOpen ? 1500 : false,
  })

  const chatMutation = useMutation({
    mutationFn: (message: string) =>
      sendChatMessage(message, {
        moduleId: activeModule?.module_id,
        domainId: activeDomainId,
        menuId: activeTopMenu?.id,
        modules,
      }),
    onSuccess: (response, message) => {
      const flow = response.selected_flow ?? null
      setSelectedFlow(flow)
      setLastAskResult(response.ask_result)
      setFormOpen(false)
      if (response.selected_module?.module_id) {
        setActiveModuleId(response.selected_module.module_id)
      } else if (flow?.module_id) {
        setActiveModuleId(flow.module_id)
      }
      setMessages((current) => [
        ...current,
        makeMessage('assistant', response.assistant_message || 'Listo. Ya prepare el contexto.', flow),
      ])
      setLogs((current) => [
        ...current,
        ...(response.log_events ?? []),
        { level: 'info', message: `Chat procesado: ${message}`, timestamp: new Date().toISOString() },
        {
          level: 'trace',
          message: `Ask trace: ${message}`,
          timestamp: new Date().toISOString(),
          trace: {
            ask_result: response.ask_result,
            selected_module: response.selected_module?.module_id ?? null,
            selected_flow: response.selected_flow?.flow_id ?? null,
            navigation: response.navigation,
            center_panel: response.center_panel,
            context_panel: response.context_panel,
          },
        },
      ])
    },
    onError: (error, message) => {
      const errorMessage = error instanceof Error ? error.message : String(error)
      setMessages((current) => [
        ...current,
        makeMessage('assistant', 'No pude completar el ciclo de pregunta en AskService. Revisa el trace para ver el detalle.'),
      ])
      setLogs((current) => [
        ...current,
        { level: 'error', message: `AskService fallo: ${errorMessage}`, timestamp: new Date().toISOString() },
        {
          level: 'trace',
          message: `Ask trace error: ${message}`,
          timestamp: new Date().toISOString(),
          trace: {
            ask_error: errorMessage,
            selected_module: null,
            selected_flow: null,
          },
        },
      ])
    },
  })

  function submitChat() {
    const message = chatValue.trim()
    if (!message || chatMutation.isPending) return
    setChatValue('')
    setMessages((current) => [...current, makeMessage('user', message)])
    chatMutation.mutate(message)
  }

  function startLeftResize(event: React.PointerEvent<HTMLDivElement>) {
    event.currentTarget.setPointerCapture(event.pointerId)
    const startX = event.clientX
    const startWidth = leftWidth

    function onMove(moveEvent: PointerEvent) {
      setLeftWidth(Math.min(380, Math.max(240, startWidth + moveEvent.clientX - startX)))
      setLeftCollapsed(false)
    }

    function onUp() {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
    }

    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
  }

  function startRightResize(event: React.PointerEvent<HTMLDivElement>) {
    event.currentTarget.setPointerCapture(event.pointerId)
    const startX = event.clientX
    const startWidth = rightWidth

    function onMove(moveEvent: PointerEvent) {
      setRightWidth(Math.min(460, Math.max(300, startWidth + startX - moveEvent.clientX)))
      setRightCollapsed(false)
    }

    function onUp() {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
    }

    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
  }

  return (
    <div className="app-shell">
      <Header
        collapsedLeft={leftCollapsed}
        collapsedRight={rightCollapsed}
        domains={domains}
        activeDomainId={activeDomainId}
        activeModule={activeModule}
        topMenus={topMenus}
        activeTopMenuId={activeTopMenu?.id ?? activeTopMenuId}
        onToggleLeft={() => setLeftCollapsed((value) => !value)}
        onToggleRight={() => setRightCollapsed((value) => !value)}
        onSelectDomain={(domainId) => {
          setActiveDomainId(domainId)
          setActiveModuleId(domainId === 'asset-management' ? 'asset-catalog' : 'home')
          setActiveView(domainId === 'asset-management' ? 'assets' : 'workspace')
          setActiveTopMenuId(domainId === 'asset-management' ? 'editors' : 'operations')
          setSelectedFlow(null)
          setLastAskResult(null)
          setFormOpen(false)
        }}
        onSelectTopMenu={setActiveTopMenuId}
      />

      <div
        className="shell-panels"
        style={{
          gridTemplateColumns: `${leftCollapsed ? 58 : leftWidth}px 6px minmax(0, 1fr) 6px ${
            rightCollapsed ? 58 : rightWidth
          }px`,
        }}
      >
        <div className="shell-panel">
          <LeftNav
            modules={modules}
            activeModuleId={activeModuleId}
            collapsed={leftCollapsed}
            activeView={activeView}
            onToggle={() => setLeftCollapsed((value) => !value)}
            onSelectModule={(module) => {
              setActiveView(module.domain_id === 'asset-management' ? 'assets' : 'workspace')
              setActiveModuleId(module.module_id)
            }}
            onSelectAssets={() => {
              setActiveView('assets')
              setActiveDomainId('asset-management')
              setActiveModuleId('asset-catalog')
              setActiveTopMenuId('editors')
              setSelectedFlow(null)
              setFormOpen(false)
            }}
          />
        </div>

        <div className="resize-handle" role="separator" aria-label="Redimensionar navegacion" onPointerDown={startLeftResize} />

        <div className="shell-panel">
          {activeView === 'assets' ? (
            <AssetExplorer
              assets={catalogAssetsQuery.data?.assets ?? []}
              tree={catalogAssetsQuery.data?.tree ?? []}
              metadata={catalogMetadataQuery.data}
              selectedAssetId={selectedAsset?.asset_id}
              selectedAsset={selectedAsset}
              loading={catalogAssetsQuery.isLoading}
              filters={assetFilters}
              onFilterChange={(key, value) =>
                setAssetFilters((current) => ({ ...current, [key]: value }))
              }
              onSelectAsset={setSelectedAsset}
              onRefresh={() => {
                void catalogMetadataQuery.refetch()
                void catalogAssetsQuery.refetch()
              }}
            />
          ) : (
            <Workspace
              activeModule={activeModule}
              activeDomainLabel={activeDomain?.label ?? 'Todos'}
              activeTopMenuLabel={activeTopMenu?.label ?? 'Operaciones'}
              selectedFlow={selectedFlow}
              messages={messages}
              chatValue={chatValue}
              chatLoading={chatMutation.isPending}
              onChatValueChange={setChatValue}
              onChatSubmit={submitChat}
              formOpen={formOpen}
              onOpenForm={() => setFormOpen(true)}
              onCloseForm={() => setFormOpen(false)}
            />
          )}
        </div>

        <div className="resize-handle" role="separator" aria-label="Redimensionar detalle" onPointerDown={startRightResize} />

        <div className="shell-panel">
          {activeView === 'assets' && !rightCollapsed ? (
            <aside className="sidebar right-sidebar">
              <div className="panel-title-row">
                <div>
                  <p className="eyebrow">Unified Catalog</p>
                  <h2>Asset Governance</h2>
                </div>
                <button className="asset-collapse-button" onClick={() => setRightCollapsed(true)} type="button">
                  &gt;&gt;
                </button>
              </div>
              <AssetDetailPanel
                asset={selectedAsset}
                assetSet={assetSetQuery.data}
                busy={lifecycleMutation.isPending || deployMutation.isPending || rollbackMutation.isPending}
                onAction={(action, comment) => lifecycleMutation.mutate({ action, comment })}
                onDeploy={() => deployMutation.mutate()}
                onRollback={() => rollbackMutation.mutate()}
              />
            </aside>
          ) : (
            <RightContextPanel
              collapsed={rightCollapsed}
              selectedFlow={selectedFlow}
              messages={messages}
              logs={logs}
              askResult={lastAskResult}
              executions={executionsQuery.data?.executions ?? []}
              onOpenForm={() => setFormOpen(true)}
              onToggle={() => setRightCollapsed((value) => !value)}
            />
          )}
        </div>
      </div>

      <footer className="statusbar">
        <span>Usuario: Saul</span>
        <span>Ambiente: DEV</span>
        <span>Region: MX</span>
        <span>Version: 1.0</span>
        <span>{homeQuery.isError ? 'Backend no disponible' : 'Catalog: Connected'}</span>
      </footer>
    </div>
  )
}

export default App
