import { useMutation, useQuery } from '@tanstack/react-query'
import { useCallback, useEffect, useState } from 'react'
import { Activity, Clock3, Pencil, ShieldCheck, TerminalSquare } from 'lucide-react'
import './App.css'
import {
  deployAssetSet,
  getAssetSet,
  getCatalogAsset,
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
import { SkillEditorModal } from './components/SkillEditorModal'
import { SkillAgentModal } from './components/SkillAgentModal'
import { SkillsPanel } from './components/SkillsPanel'
import { Workspace } from './components/Workspace'
import type {
  AgentDraft,
  CatalogAssetDetail,
  ChatMessage,
  LauncherDomain,
  LauncherFlowSummary,
  LauncherHomeResponse,
  LogEvent,
  OntologySelection,
  SkillAsset,
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
  { id: 'skills', label: 'Skill' },
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
    description: 'Graph, document, catalog, relational, and focused vector projections.',
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
  {
    module_id: 'skills',
    label: 'Skill',
    description: 'Skill library, markdown editor, agents, and governance.',
    icon: 'skills',
    aliases: ['skill', 'agents', 'behavior'],
    flow_prefixes: [],
    menus: [
      { id: 'library', label: 'Library' },
      { id: 'agents', label: 'Agents' },
      { id: 'governance', label: 'Governance' },
    ],
    top_menus: assetTopMenus,
    flow_count: 0,
    domain_id: 'asset-management',
    domain_label: 'Asset Management',
  },
]

const initialSkills: SkillAsset[] = [
  {
    skill_id: 'planning',
    title: 'Planning',
    description: 'Decompose business work into governed steps and recommend the next action.',
    scope: 'business-agents',
    agent_types: ['planning'],
    allowed_tools: ['Read', 'Grep'],
    status: 'active',
    version: '1.0.0',
    markdown: `---\nname: planning\ndescription: Decompose business work into governed steps and recommend the next action.\nallowed-tools:\n  - Read\n  - Grep\n---\n\nUse this skill when a user needs a decomposed plan, a route recommendation, or a controlled next step.\n\nRules:\n- Keep the plan grounded in approved assets.\n- Separate user intent, constraints, and tool-ready steps.\n- Prefer concise, auditable step lists over free-form reasoning.\n- If a policy or required tool is missing, stop and report the gap.`,
    updated_at: new Date().toISOString(),
  },
  {
    skill_id: 'delegation',
    title: 'Delegation',
    description: 'Route work to a specialist agent or approved tool-backed capability.',
    scope: 'business-agents',
    agent_types: ['delegator'],
    allowed_tools: ['Read', 'Grep'],
    status: 'active',
    version: '1.0.0',
    markdown: `---\nname: delegation\ndescription: Route work to a specialist agent or approved tool-backed capability.\nallowed-tools:\n  - Read\n  - Grep\n---\n\nUse this skill when a request should be handed off to a more specific agent or capability.\n\nRules:\n- Choose the narrowest agent that can safely handle the task.\n- Preserve traceability for every handoff.\n- Do not invent tools or capabilities outside the catalog.\n- Return the reason for delegation in one short, auditable sentence.`,
    updated_at: new Date().toISOString(),
  },
  {
    skill_id: 'loan-origination-review',
    title: 'Loan Origination Review',
    description: 'Support loan-originations with governed review, summarization, and approved tool use.',
    scope: 'business-agents',
    agent_types: ['worker', 'coordinator'],
    allowed_tools: ['Read', 'Grep'],
    status: 'review',
    version: '0.3.0',
    markdown: `---\nname: loan-origination-review\ndescription: Support loan-originations with governed review, summarization, and approved tool use.\nallowed-tools:\n  - Read\n  - Grep\n---\n\nUse this skill for loan operations review, application context, and eligibility support.\n\nRules:\n- Summarize borrower context, application state, and key policy constraints.\n- Use only approved tools referenced by the agent definition.\n- If a requested action would exceed policy, recommend escalation instead of execution.\n- Keep outputs concise enough for executive review.`,
    updated_at: new Date().toISOString(),
  },
  {
    skill_id: 'platform-governance',
    title: 'Platform Governance',
    description: 'Review catalog, deployments, lifecycle status, and platform governance state.',
    scope: 'launcher-behaviors',
    agent_types: ['monitoring', 'coordinator'],
    allowed_tools: ['Read', 'Grep'],
    status: 'draft',
    version: '0.1.0',
    markdown: `---\nname: platform-governance\ndescription: Review catalog, deployments, lifecycle status, and platform governance state.\nallowed-tools:\n  - Read\n  - Grep\n---\n\nUse this skill for platform administration, catalog review, and governance oversight.\n\nRules:\n- Favor current catalog state and lifecycle evidence.\n- Surface deployment, approval, and validation status clearly.\n- Do not change state unless the agent explicitly has permission to do so.`,
    updated_at: new Date().toISOString(),
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

function pickPreferredCatalogAsset(assets: CatalogAssetDetail[]): CatalogAssetDetail | null {
  const statuses = ['ready_for_review', 'in_review', 'validated', 'active']
  const flowAssets = assets.filter((asset) => asset.asset_type === 'flow')
  for (const status of statuses) {
    const preferredFlow = flowAssets.find((asset) => asset.status === status)
    if (preferredFlow) return preferredFlow
  }
  for (const status of statuses) {
    const preferred = assets.find((asset) => asset.status === status)
    if (preferred) return preferred
  }
  return assets[0] ?? null
}

function App() {
  const [leftCollapsed, setLeftCollapsed] = useState(false)
  const [rightCollapsed, setRightCollapsed] = useState(false)
  const [leftWidth, setLeftWidth] = useState(280)
  const [rightWidth, setRightWidth] = useState(360)
  const [activeDomainId, setActiveDomainId] = useState('all')
  const [activeModuleId, setActiveModuleId] = useState('home')
  const [activeTopMenuId, setActiveTopMenuId] = useState('operations')
  const [activeView, setActiveView] = useState<'workspace' | 'assets' | 'skills'>('workspace')
  const [assetFilters, setAssetFilters] = useState({
    query: '',
    knowledgeBase: '',
    assetType: '',
    status: '',
    tag: '',
  })
  const [selectedAsset, setSelectedAsset] = useState<CatalogAssetDetail | null>(null)
  const [editingAsset, setEditingAsset] = useState<CatalogAssetDetail | null>(null)
  const [skills, setSkills] = useState<SkillAsset[]>(initialSkills)
  const [skillEditorOpen, setSkillEditorOpen] = useState(false)
  const [skillDraft, setSkillDraft] = useState<SkillAsset | null>(null)
  const [selectedSkillId, setSelectedSkillId] = useState(initialSkills[2].skill_id)
  const [agentModalOpen, setAgentModalOpen] = useState(false)
  const [agentDraft, setAgentDraft] = useState<AgentDraft>({
    agent_id: 'agent.business.loan.review',
    name: 'Loan Review Agent',
    description: 'Support loan-originations with governed review and tool-safe summaries.',
    agent_type: 'worker',
    domain: 'ask',
    skill_ids: ['loan-origination-review'],
    tool_ids: ['Read', 'Grep'],
    status: 'draft',
  })
  const [skillActivity, setSkillActivity] = useState<string[]>(['Skill library inicializada'])
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
  const [ontologySelection, setOntologySelection] = useState<OntologySelection | null>(null)
  const [ontologyFormHandler, setOntologyFormHandler] = useState<
    ((context?: { entityId?: string; entityName?: string }) => void) | null
  >(null)

  useEffect(() => {
    if (!editingAsset || editingAsset.asset_type !== 'entity') {
      setOntologySelection(null)
      setOntologyFormHandler(null)
    }
  }, [editingAsset])

  const registerOntologyFormHandler = useCallback((
    handler: ((context?: { entityId?: string; entityName?: string }) => void) | null,
  ) => {
    setOntologyFormHandler(() => handler)
  }, [])

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
          activeOnly: false,
        }),
      enabled: activeView === 'assets',
    })

  useEffect(() => {
    if (activeView !== 'assets' || selectedAsset || editingAsset) return
    const preferredAsset = pickPreferredCatalogAsset(catalogAssetsQuery.data?.assets ?? [])
    if (preferredAsset) setSelectedAsset(preferredAsset)
  }, [activeView, catalogAssetsQuery.data?.assets, editingAsset, selectedAsset])
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
  const selectedSkill = skills.find((skill) => skill.skill_id === selectedSkillId) ?? skills[0]

  function openSkillEditor(skill: SkillAsset = selectedSkill) {
    setSkillDraft({ ...skill })
    setSkillEditorOpen(true)
  }

  function saveSkillDraft() {
    if (!skillDraft) return
    setSkills((current) => current.map((skill) => (skill.skill_id === skillDraft.skill_id ? { ...skillDraft } : skill)))
    setSelectedSkillId(skillDraft.skill_id)
    setSkillActivity((current) => [`Skill guardada: ${skillDraft.title}`, ...current].slice(0, 8))
    setSkillEditorOpen(false)
  }

  function openKnowledgeBaseEditor(knowledgeBase: string) {
    const normalized = knowledgeBase.trim().toLowerCase()
    const virtualAsset: CatalogAssetDetail = {
      asset_id: `knowledge_base.${normalized}`,
      version: 'virtual',
      asset_type: 'ontology_graph',
      name: `${knowledgeBase} ontology`,
      status: 'active',
      primary_kb: normalized,
      domain_id: null,
      module_id: null,
      tags: ['ontology', 'knowledge_base'],
      stores: ['repository', 'graph', 'vector'],
      payload: {
        asset_id: `knowledge_base.${normalized}`,
        asset_type: 'ontology_graph',
        knowledge_base: normalized,
        primary_kb: normalized,
        name: `${knowledgeBase} ontology`,
      },
      active: true,
      relationships: [],
    }
    setSelectedAsset(null)
    setEditingAsset(virtualAsset)
    setActiveView('assets')
    setActiveTopMenuId('editors')
    setLeftCollapsed(true)
    setRightCollapsed(true)
  }

  function openCatalogAssetEditor(asset: CatalogAssetDetail) {
    setEditingAsset(asset)
    if (asset.asset_type === 'entity') {
      setLeftCollapsed(true)
      setRightCollapsed(true)
    }
  }
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
      setFormOpen(Boolean(flow))
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

  async function openSelectedFlowEditor() {
    if (!selectedFlow?.flow_id) return
    setFormOpen(true)
    try {
      const asset = await getCatalogAsset(selectedFlow.flow_id)
      setSelectedAsset(asset)
      setEditingAsset(asset)
      setActiveView('assets')
      setActiveDomainId('asset-management')
      setActiveModuleId('asset-catalog')
      setActiveTopMenuId('editors')
      setRightCollapsed(false)
      setLogs((current) => [
        ...current,
        {
          level: 'info',
          message: `Flow editor opened for ${selectedFlow.flow_id}`,
          timestamp: new Date().toISOString(),
        },
      ])
    } catch (error) {
      setLogs((current) => [
        ...current,
        {
          level: 'warning',
          message: `Flow ${selectedFlow.flow_id} is not yet available in the catalog editor: ${error instanceof Error ? error.message : String(error)}`,
          timestamp: new Date().toISOString(),
        },
      ])
    }
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
          setEditingAsset(null)
          setAgentModalOpen(false)
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
              setActiveView(module.module_id === 'skills' ? 'skills' : module.domain_id === 'asset-management' ? 'assets' : 'workspace')
              setActiveModuleId(module.module_id)
              setActiveTopMenuId(module.module_id === 'skills' ? 'skills' : module.domain_id === 'asset-management' ? 'editors' : 'operations')
              setEditingAsset(null)
              setAgentModalOpen(false)
            }}
            onSelectAssets={() => {
              setActiveView('assets')
              setActiveDomainId('asset-management')
              setActiveModuleId('asset-catalog')
              setActiveTopMenuId('editors')
              setSelectedFlow(null)
              setFormOpen(false)
              setEditingAsset(null)
              setAgentModalOpen(false)
            }}
            onSelectSkills={() => {
              setActiveView('skills')
              setActiveDomainId('asset-management')
              setActiveModuleId('skills')
              setActiveTopMenuId('skills')
              setEditingAsset(null)
            }}
            onOpenAgentDraft={() => {
              setActiveView('skills')
              setActiveDomainId('asset-management')
              setActiveModuleId('skills')
              setActiveTopMenuId('skills')
              setAgentModalOpen(true)
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
              editingAsset={editingAsset}
              loading={catalogAssetsQuery.isLoading}
              filters={assetFilters}
              onFilterChange={(key, value) =>
                setAssetFilters((current) => ({ ...current, [key]: value }))
              }
              onSelectAsset={setSelectedAsset}
              onEditAsset={openCatalogAssetEditor}
              onCloseEditor={() => setEditingAsset(null)}
              onRefresh={() => {
                void catalogMetadataQuery.refetch()
                void catalogAssetsQuery.refetch()
              }}
              onOpenKnowledgeBaseEditor={openKnowledgeBaseEditor}
              onOntologySelectionChange={setOntologySelection}
              onOntologyFormHandlerChange={registerOntologyFormHandler}
            />
          ) : activeView === 'skills' ? (
            <SkillsPanel
              skills={skills}
              selectedSkill={selectedSkill}
              onSelectSkill={setSelectedSkillId}
              onCreateAgent={() => setAgentModalOpen(true)}
              onEditSkill={() => openSkillEditor(selectedSkill)}
              onValidate={() => {
                setSkillActivity((current) => [`Validación ejecutada para ${selectedSkill.skill_id}`, ...current].slice(0, 8))
              }}
              onPublish={() => {
                setSkillActivity((current) => [`Publicación preparada para ${selectedSkill.skill_id}`, ...current].slice(0, 8))
              }}
              onCompare={() => {
                setSkillActivity((current) => [`Comparación solicitada para ${selectedSkill.skill_id}`, ...current].slice(0, 8))
              }}
              draftAgent={agentDraft}
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
              onOpenForm={() => void openSelectedFlowEditor()}
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
                onEdit={selectedAsset ? () => setEditingAsset(selectedAsset) : undefined}
                ontologySelection={ontologySelection}
                onOpenOntologyForm={(context) => ontologyFormHandler?.(context)}
              />
            </aside>
          ) : activeView === 'skills' && !rightCollapsed ? (
            <aside className="sidebar right-sidebar">
              <div className="panel-title-row">
                <div>
                  <p className="eyebrow">Skills</p>
                  <h2>Skill</h2>
                </div>
                <button className="asset-collapse-button" onClick={() => setRightCollapsed(true)} type="button">
                  &gt;&gt;
                </button>
              </div>
              <section className="context-section">
                <div className="context-section-title">
                  <ShieldCheck size={18} />
                  <span>Governance</span>
                </div>
                <div className="asset-property-grid">
                  <span>Skill</span><strong>{selectedSkill.title}</strong>
                  <span>Scope</span><strong>{selectedSkill.scope}</strong>
                  <span>Version</span><strong>{selectedSkill.version}</strong>
                  <span>Status</span><strong>{selectedSkill.status}</strong>
                  <span>Agent types</span><strong>{selectedSkill.agent_types.join(', ')}</strong>
                  <span>Tools</span><strong>{selectedSkill.allowed_tools.join(', ')}</strong>
                </div>
                <div className="btn-stack">
                  <button className="button button-default button-sm" onClick={() => setAgentModalOpen(true)} type="button">
                    <Pencil size={15} /> Crear agente
                  </button>
                  <button
                    className="button button-outline button-sm"
                    onClick={() => setSkillActivity((current) => [`Skill validada: ${selectedSkill.skill_id}`, ...current].slice(0, 8))}
                    type="button"
                  >
                    <ShieldCheck size={15} /> Validar
                  </button>
                </div>
              </section>

              <section className="context-section">
                <div className="context-section-title">
                  <Activity size={18} />
                  <span>Operations</span>
                </div>
                <div className="skill-ops">
                  {skillActivity.map((entry, index) => (
                    <div key={`${entry}-${index}`} className="skill-op-row">
                      <Clock3 size={14} />
                      <span>{entry}</span>
                    </div>
                  ))}
                </div>
              </section>

              <section className="context-section">
                <div className="context-section-title">
                  <TerminalSquare size={18} />
                  <span>Agent draft</span>
                </div>
                <div className="asset-property-grid">
                  <span>Agent ID</span><strong>{agentDraft.agent_id}</strong>
                  <span>Type</span><strong>{agentDraft.agent_type}</strong>
                  <span>Domain</span><strong>{agentDraft.domain}</strong>
                  <span>Skills</span><strong>{agentDraft.skill_ids.length}</strong>
                </div>
              </section>
            </aside>
          ) : (
            <RightContextPanel
              collapsed={rightCollapsed}
              selectedFlow={selectedFlow}
              messages={messages}
              logs={logs}
              askResult={lastAskResult}
              executions={executionsQuery.data?.executions ?? []}
              onOpenForm={() => void openSelectedFlowEditor()}
              onToggle={() => setRightCollapsed((value) => !value)}
            />
          )}
        </div>
      </div>

      <SkillAgentModal
        open={agentModalOpen}
        draft={agentDraft}
        skills={skills}
        onClose={() => setAgentModalOpen(false)}
        onChange={setAgentDraft}
        onSubmit={() => {
          setSkillActivity((current) => [`Agente preparado: ${agentDraft.name} (${agentDraft.agent_type})`, ...current].slice(0, 8))
          setMessages((current) => [
            ...current,
            makeMessage('assistant', `Agente creado en modo borrador: ${agentDraft.name} con tipo ${agentDraft.agent_type}.`),
          ])
          setAgentModalOpen(false)
        }}
      />

      <SkillEditorModal
        open={skillEditorOpen}
        draft={skillDraft ?? selectedSkill}
        onClose={() => {
          setSkillEditorOpen(false)
          setSkillDraft(null)
        }}
        onChange={setSkillDraft}
        onSave={saveSkillDraft}
      />

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
