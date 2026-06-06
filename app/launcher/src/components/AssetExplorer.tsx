import {
  Boxes,
  ChevronDown,
  ChevronRight,
  Code2,
  Database,
  FileBox,
  Filter,
  Network,
  RefreshCw,
  Route,
  Search,
  Tags,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import type { CatalogAssetDetail, CatalogMetadata, CatalogTreeNode } from '../types'
import { Badge } from './ui/badge'
import { Button } from './ui/button'

type AssetExplorerProps = {
  assets: CatalogAssetDetail[]
  tree: CatalogTreeNode[]
  metadata?: CatalogMetadata
  selectedAssetId?: string | null
  selectedAsset?: CatalogAssetDetail | null
  loading: boolean
  filters: {
    query: string
    knowledgeBase: string
    assetType: string
    status: string
    tag: string
  }
  onFilterChange: (key: string, value: string) => void
  onSelectAsset: (asset: CatalogAssetDetail) => void
  onRefresh: () => void
}

export function AssetExplorer({
  assets,
  tree,
  metadata,
  selectedAssetId,
  selectedAsset,
  loading,
  filters,
  onFilterChange,
  onSelectAsset,
  onRefresh,
}: AssetExplorerProps) {
  const [view, setView] = useState<'tree' | 'routes'>('tree')
  const assetById = useMemo(
    () => new Map(assets.map((asset) => [`${asset.asset_id}:${asset.version}`, asset])),
    [assets],
  )

  return (
    <main className="workspace asset-workspace">
      <div className="asset-heading">
        <div>
          <div className="asset-title-line">
            <p className="eyebrow">Unified Catalog</p>
            <Badge tone="info">Launcher Embedded Editors</Badge>
          </div>
          <h1>{selectedAsset ? `Edit ${selectedAsset.name || selectedAsset.asset_id}` : 'Assets'}</h1>
          <p>{selectedAsset ? 'Edita el activo con Lowdefy dentro del launcher.' : 'Explora relaciones, versiones, proyecciones y ciclo de vida.'}</p>
        </div>
        <div className="asset-view-switch">
          <Button variant={view === 'tree' ? 'default' : 'outline'} size="sm" onClick={() => setView('tree')}>
            <Network size={16} />
            Tree
          </Button>
          <Button variant={view === 'routes' ? 'default' : 'outline'} size="sm" onClick={() => setView('routes')}>
            <Route size={16} />
            Routes
          </Button>
          <Button variant="ghost" size="icon" onClick={onRefresh} aria-label="Actualizar activos">
            <RefreshCw size={17} className={loading ? 'spin' : ''} />
          </Button>
        </div>
      </div>

      <section className="asset-filters" aria-label="Filtros de activos">
        <label className="asset-search">
          <Search size={17} />
          <input
            value={filters.query}
            onChange={(event) => onFilterChange('query', event.target.value)}
            placeholder="Buscar por nombre de activo..."
          />
        </label>
        <FilterSelect
          icon={<Database size={16} />}
          value={filters.knowledgeBase}
          emptyLabel="Knowledge Base: Todas"
          values={metadata?.knowledge_bases ?? []}
          onChange={(value) => onFilterChange('knowledgeBase', value)}
        />
        <FilterSelect
          icon={<FileBox size={16} />}
          value={filters.assetType}
          emptyLabel="Asset Type: Todos"
          values={metadata?.asset_types ?? []}
          onChange={(value) => onFilterChange('assetType', value)}
        />
        <FilterSelect
          icon={<Filter size={16} />}
          value={filters.status}
          emptyLabel="Status: Todos"
          values={metadata?.statuses ?? []}
          onChange={(value) => onFilterChange('status', value)}
        />
        <FilterSelect
          icon={<Tags size={16} />}
          value={filters.tag}
          emptyLabel="Tag: Todos"
          values={metadata?.tags ?? []}
          onChange={(value) => onFilterChange('tag', value)}
        />
      </section>

      <div className="asset-summary-row">
        <span>{assets.length} activos encontrados</span>
        <span>{tree.length} knowledge bases</span>
        <span>Environment: DEV</span>
      </div>

      <div className="asset-editor-layout">
        <section className="asset-browser-panel">
          {view === 'routes' ? (
            <RouteView assets={assets} selectedAssetId={selectedAssetId} onSelectAsset={onSelectAsset} />
          ) : (
            <section className="asset-tree-panel compact">
              {loading ? (
                <div className="asset-empty">Cargando catálogo unificado...</div>
              ) : tree.length === 0 ? (
                <div className="asset-empty">No hay activos para estos filtros.</div>
              ) : (
                tree.map((node) => (
                  <AssetTreeNode
                    key={node.id}
                    node={node}
                    depth={0}
                    assetById={assetById}
                    selectedAssetId={selectedAssetId}
                    onSelectAsset={onSelectAsset}
                  />
                ))
              )}
            </section>
          )}
        </section>
        <AssetEmbeddedEditor selectedAsset={selectedAsset} />
      </div>
    </main>
  )
}

function editorPageForAsset(asset?: CatalogAssetDetail | null) {
  const type = String(asset?.asset_type || '').toLowerCase()
  if (type === 'flow') return 'asset-flow-editor'
  if (type === 'process') return 'asset-process-editor'
  if (['business_rule', 'rule', 'ruleset'].includes(type)) return 'asset-business-rule-editor'
  if (['ontology', 'relationship'].includes(type)) return 'asset-ontology-editor'
  if (['qa', 'question_answer'].includes(type)) return 'asset-qa-editor'
  if (['entity', 'concept'].includes(type)) return 'asset-entity-editor'
  if (['tool', 'api', 'tool_api'].includes(type)) return 'asset-tool-api-editor'
  if (type === 'form') return 'asset-form-editor'
  if (['domain', 'module', 'menu', 'submenu', 'navigation'].includes(type)) return 'asset-module-menu-editor'
  if (['document', 'configuration', 'config'].includes(type)) return 'asset-document-config-editor'
  return 'asset-code-editor'
}

function AssetEmbeddedEditor({ selectedAsset }: { selectedAsset?: CatalogAssetDetail | null }) {
  const lowdefyBaseUrl = import.meta.env.VITE_LOWDEFY_RUNTIME_URL || 'http://localhost:3002'
  if (!selectedAsset) {
    return (
      <section className="asset-editor-empty">
        <Code2 size={28} />
        <h2>Selecciona un activo</h2>
        <p>El editor Lowdefy aparece aqui con el contexto del activo, version, AssetSet y tipo.</p>
      </section>
    )
  }
  const page = editorPageForAsset(selectedAsset)
  const params = new URLSearchParams({
    asset_id: selectedAsset.asset_id,
    version: selectedAsset.version,
    environment: 'dev',
  })
  return (
    <section className="asset-editor-shell">
      <div className="asset-editor-header">
        <div>
          <p className="asset-breadcrumb">
            Assets / {selectedAsset.asset_type} / {selectedAsset.asset_id}
          </p>
          <div className="asset-editor-title">
            <h2>{selectedAsset.name || selectedAsset.asset_id}</h2>
            <Badge tone="info">Lowdefy Editor</Badge>
          </div>
        </div>
        <div className="asset-editor-version">
          <span>Current</span>
          <strong>{selectedAsset.version}</strong>
          <StatusBadge status={selectedAsset.status} />
        </div>
      </div>
      <div className="asset-editor-draft-banner">
        Editing creates a new immutable AssetSet version. Current KB projections continue using the active version until deployment.
      </div>
      <div className="asset-editor-tabs">
        <span className="active">Structured Editor</span>
        <span>Relationships</span>
        <span>Raw YAML</span>
        <span>Compare Versions</span>
      </div>
      <iframe
        className="asset-editor-frame"
        src={`${lowdefyBaseUrl}/${page}?${params.toString()}`}
        title={`Lowdefy editor for ${selectedAsset.asset_id}`}
      />
    </section>
  )
}

function FilterSelect({
  icon,
  value,
  emptyLabel,
  values,
  onChange,
}: {
  icon: React.ReactNode
  value: string
  emptyLabel: string
  values: string[]
  onChange: (value: string) => void
}) {
  return (
    <label className="asset-select">
      {icon}
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">{emptyLabel}</option>
        {values.map((item) => (
          <option value={item} key={item}>
            {item}
          </option>
        ))}
      </select>
    </label>
  )
}

function AssetTreeNode({
  node,
  depth,
  assetById,
  selectedAssetId,
  onSelectAsset,
}: {
  node: CatalogTreeNode
  depth: number
  assetById: Map<string, CatalogAssetDetail>
  selectedAssetId?: string | null
  onSelectAsset: (asset: CatalogAssetDetail) => void
}) {
  const [open, setOpen] = useState(depth < 2)
  const hasChildren = node.children.length > 0
  const asset = node.asset_id ? assetById.get(`${node.asset_id}:${node.version}`) : undefined
  const Icon = node.kind === 'knowledge_base' ? Database : node.kind === 'asset_set' ? Boxes : FileBox
  return (
    <div className="asset-tree-branch">
      <button
        type="button"
        className={`asset-tree-row ${node.asset_id === selectedAssetId ? 'active' : ''}`}
        style={{ paddingLeft: `${12 + depth * 24}px` }}
        onClick={() => {
          if (asset) onSelectAsset(asset)
          else if (hasChildren) setOpen((value) => !value)
        }}
      >
        <span className="tree-chevron">
          {hasChildren ? open ? <ChevronDown size={15} /> : <ChevronRight size={15} /> : null}
        </span>
        <Icon size={17} />
        <span className="tree-label">{node.label}</span>
        {node.asset_type && <Badge>{node.asset_type}</Badge>}
        {node.version && <span className="tree-version">v{node.version}</span>}
        {node.status && <StatusBadge status={node.status} />}
        {node.count != null && <span className="tree-count">{node.count}</span>}
      </button>
      {open &&
        node.children.map((child) => (
          <AssetTreeNode
            key={child.id}
            node={child}
            depth={depth + 1}
            assetById={assetById}
            selectedAssetId={selectedAssetId}
            onSelectAsset={onSelectAsset}
          />
        ))}
    </div>
  )
}

function RouteView({
  assets,
  selectedAssetId,
  onSelectAsset,
}: {
  assets: CatalogAssetDetail[]
  selectedAssetId?: string | null
  onSelectAsset: (asset: CatalogAssetDetail) => void
}) {
  return (
    <section className="asset-route-list">
      {assets.map((asset) => (
        <button
          type="button"
          key={`${asset.asset_id}:${asset.version}`}
          className={`asset-route-row ${selectedAssetId === asset.asset_id ? 'active' : ''}`}
          onClick={() => onSelectAsset(asset)}
        >
          <span>{asset.domain_id || 'platform'}</span>
          <ChevronRight size={14} />
          <span>{asset.module_id || 'shared'}</span>
          <ChevronRight size={14} />
          <span>{asset.asset_set_id || 'unassigned'}</span>
          <ChevronRight size={14} />
          <strong>{asset.name || asset.asset_id}</strong>
          <StatusBadge status={asset.status} />
        </button>
      ))}
    </section>
  )
}

export function StatusBadge({ status }: { status: string }) {
  const tone =
    status === 'active' || status === 'validated'
      ? 'success'
      : status === 'rejected'
        ? 'danger'
        : status.includes('review')
          ? 'warning'
          : 'default'
  return <Badge tone={tone}>{status}</Badge>
}
