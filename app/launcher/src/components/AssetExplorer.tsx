import {
  ChevronLeft,
  ChevronRight,
  Boxes,
  ChevronDown,
  Code2,
  Database,
  FileBox,
  Filter,
  MoreHorizontal,
  Network,
  Pencil,
  RefreshCw,
  Route,
  Search,
  Tags,
} from 'lucide-react'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import type { CatalogAssetDetail, CatalogMetadata, CatalogTreeNode, OntologySelection } from '../types'
import { AssetInlineEditor } from './AssetInlineEditor'
import { Badge } from './ui/badge'
import { Button } from './ui/button'

const STATUS_PRIORITY: Record<string, number> = {
  ready_for_review: 0,
  in_review: 1,
  validated: 2,
  active: 3,
  draft: 4,
  approved: 5,
  rejected: 6,
  deprecated: 7,
  retired: 8,
}

type AssetExplorerProps = {
  assets: CatalogAssetDetail[]
  tree: CatalogTreeNode[]
  metadata?: CatalogMetadata
  selectedAssetId?: string | null
  selectedAsset?: CatalogAssetDetail | null
  editingAsset?: CatalogAssetDetail | null
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
  onEditAsset: (asset: CatalogAssetDetail) => void
  onCloseEditor: () => void
  onRefresh: () => void
  onOpenKnowledgeBaseEditor?: (knowledgeBase: string) => void
  onOntologySelectionChange?: (selection: OntologySelection | null) => void
  onOntologyFormHandlerChange?: (
    handler: ((context?: { entityId?: string; entityName?: string }) => void) | null,
  ) => void
}

export function AssetExplorer({
  assets,
  tree,
  metadata,
  selectedAssetId,
  selectedAsset,
  editingAsset,
  loading,
  filters,
  onFilterChange,
  onSelectAsset,
  onEditAsset,
  onCloseEditor,
  onRefresh,
  onOpenKnowledgeBaseEditor,
  onOntologySelectionChange,
  onOntologyFormHandlerChange,
}: AssetExplorerProps) {
  const [view, setView] = useState<'tree' | 'routes'>('tree')
  const [browserExpandedWhileEditing, setBrowserExpandedWhileEditing] = useState(false)
  const assetById = useMemo(
    () => new Map(assets.map((asset) => [`${asset.asset_id}:${asset.version}`, asset])),
    [assets],
  )
  const sortedAssets = useMemo(
    () =>
      [...assets].sort(
        (left, right) =>
          (STATUS_PRIORITY[left.status] ?? 999) - (STATUS_PRIORITY[right.status] ?? 999) ||
          (left.name || left.asset_id).localeCompare(right.name || right.asset_id),
      ),
    [assets],
  )
  const reviewCount = assets.filter((asset) => asset.status === 'ready_for_review' || asset.status === 'in_review').length
  const activeCount = assets.filter((asset) => asset.status === 'active').length
  const browserCollapsed = Boolean(editingAsset) && !browserExpandedWhileEditing

  function selectAsset(asset: CatalogAssetDetail) {
    onSelectAsset(asset)
    if (editingAsset && editingAsset.asset_id !== asset.asset_id) {
      handleCloseEditor()
    }
  }

  function handleEditAsset(asset: CatalogAssetDetail) {
    setBrowserExpandedWhileEditing(false)
    onEditAsset(asset)
  }

  function handleCloseEditor() {
    setBrowserExpandedWhileEditing(false)
    onCloseEditor()
  }

  return (
    <main className="workspace asset-workspace">
      <div className="asset-heading">
        <div>
          <div className="asset-title-line">
            <p className="eyebrow">Unified Catalog</p>
            <Badge tone="info">Launcher Embedded Editors</Badge>
          </div>
          <h1>{editingAsset ? `Edit ${editingAsset.name || editingAsset.asset_id}` : 'Assets'}</h1>
          <p>{editingAsset ? 'Edita el activo directamente dentro del launcher.' : 'Explora relaciones, versiones, proyecciones y ciclo de vida.'}</p>
        </div>
        <div className="asset-view-switch">
          {selectedAsset ? (
            <AssetActionMenu asset={selectedAsset} onEditAsset={handleEditAsset} />
          ) : null}
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
        <span>{reviewCount} en revisión</span>
        <span>{activeCount} activos</span>
        <span>{tree.length} catalogo{tree.length === 1 ? '' : 's'}</span>
        <span>Environment: DEV</span>
        {filters.knowledgeBase ? (
          <AssetActionMenu knowledgeBase={filters.knowledgeBase} onOpenKnowledgeBaseEditor={onOpenKnowledgeBaseEditor} />
        ) : null}
      </div>

      <div
        className={[
          'asset-editor-layout',
          editingAsset ? 'editing' : 'browsing',
          browserCollapsed ? 'browser-collapsed' : 'browser-expanded',
        ].join(' ')}
      >
        <section className={`asset-browser-panel ${browserCollapsed ? 'collapsed' : ''}`}>
          <div className="asset-browser-shell">
            <div className="asset-browser-toolbar">
              <div className={browserCollapsed ? 'asset-browser-toolbar-copy hidden' : 'asset-browser-toolbar-copy'}>
                <strong>Navegador de activos</strong>
                <span>{view === 'tree' ? 'Vista jerarquica del catalogo' : 'Vista por rutas funcionales'}</span>
              </div>
              {editingAsset ? (
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => setBrowserExpandedWhileEditing((current) => !current)}
                  aria-label={browserCollapsed ? 'Expandir navegador de activos' : 'Colapsar navegador de activos'}
                >
                  {browserCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
                </Button>
              ) : null}
            </div>
            {!browserCollapsed ? (
              view === 'routes' ? (
                <RouteView
                  assets={sortedAssets}
                  selectedAssetId={selectedAssetId}
                  onSelectAsset={selectAsset}
                  onEditAsset={handleEditAsset}
                />
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
                        onSelectAsset={selectAsset}
                        onEditAsset={handleEditAsset}
                        onOpenKnowledgeBaseEditor={onOpenKnowledgeBaseEditor}
                      />
                    ))
                  )}
                </section>
              )
            ) : (
              <button
                type="button"
                className="asset-browser-collapsed-toggle"
                onClick={() => setBrowserExpandedWhileEditing(true)}
                aria-label="Expandir navegador de activos"
              >
                <ChevronRight size={18} />
              </button>
            )}
          </div>
        </section>
        {editingAsset ? (
          <AssetEmbeddedEditor
            selectedAsset={selectedAsset}
            editingAsset={editingAsset}
            onClose={handleCloseEditor}
            onVersionCreated={() => {
              onRefresh()
            }}
            onOntologySelectionChange={onOntologySelectionChange}
            onOntologyFormHandlerChange={onOntologyFormHandlerChange}
          />
        ) : null}
      </div>
    </main>
  )
}

function AssetEmbeddedEditor({
  selectedAsset,
  editingAsset,
  onClose,
  onVersionCreated,
  onOntologySelectionChange,
  onOntologyFormHandlerChange,
}: {
  selectedAsset?: CatalogAssetDetail | null
  editingAsset?: CatalogAssetDetail | null
  onClose: () => void
  onVersionCreated: () => void
  onOntologySelectionChange?: (selection: OntologySelection | null) => void
  onOntologyFormHandlerChange?: (
    handler: ((context?: { entityId?: string; entityName?: string }) => void) | null,
  ) => void
}) {
  const activeAsset = editingAsset ?? null
  if (!selectedAsset) {
    return (
      <section className="asset-editor-empty">
        <Code2 size={28} />
        <h2>Selecciona un activo</h2>
        <p>El editor aparece aqui con el contexto del activo, version, AssetSet y tipo.</p>
      </section>
    )
  }
  if (!activeAsset) {
    return (
      <section className="asset-editor-empty">
        <Code2 size={28} />
        <h2>Activo seleccionado</h2>
        <p>Pulsa Editar para abrir el panel de edicion del tipo seleccionado.</p>
      </section>
    )
  }
  return (
    <AssetInlineEditor
      asset={activeAsset}
      onClose={onClose}
      onVersionCreated={onVersionCreated}
      onOntologySelectionChange={onOntologySelectionChange}
      onOntologyFormHandlerChange={onOntologyFormHandlerChange}
    />
  )
}

function FilterSelect({
  icon,
  value,
  emptyLabel,
  values,
  onChange,
}: {
  icon: ReactNode
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
            {item === 'repository' ? 'catalog' : item}
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
  onEditAsset,
  onOpenKnowledgeBaseEditor,
}: {
  node: CatalogTreeNode
  depth: number
  assetById: Map<string, CatalogAssetDetail>
  selectedAssetId?: string | null
  onSelectAsset: (asset: CatalogAssetDetail) => void
  onEditAsset: (asset: CatalogAssetDetail) => void
  onOpenKnowledgeBaseEditor?: (knowledgeBase: string) => void
}) {
  const [open, setOpen] = useState(depth < 2)
  const hasChildren = node.children.length > 0
  const asset = node.asset_id ? assetById.get(`${node.asset_id}:${node.version}`) : undefined
  const Icon = node.kind === 'knowledge_base' ? Database : node.kind === 'asset_set' ? Boxes : FileBox
  return (
    <div className="asset-tree-branch">
      <div className={`asset-tree-row-wrap ${node.asset_id === selectedAssetId ? 'active' : ''}`}>
        <button
          type="button"
          className="asset-tree-row"
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
        {asset || node.kind === 'knowledge_base' ? (
          <AssetActionMenu
            asset={asset}
            knowledgeBase={node.kind === 'knowledge_base' ? node.label : undefined}
            onEditAsset={onEditAsset}
            onOpenKnowledgeBaseEditor={onOpenKnowledgeBaseEditor}
          />
        ) : null}
      </div>
      {open &&
        node.children.map((child) => (
          <AssetTreeNode
            key={child.id}
            node={child}
            depth={depth + 1}
            assetById={assetById}
            selectedAssetId={selectedAssetId}
            onSelectAsset={onSelectAsset}
            onEditAsset={onEditAsset}
            onOpenKnowledgeBaseEditor={onOpenKnowledgeBaseEditor}
          />
        ))}
    </div>
  )
}

function RouteView({
  assets,
  selectedAssetId,
  onSelectAsset,
  onEditAsset,
}: {
  assets: CatalogAssetDetail[]
  selectedAssetId?: string | null
  onSelectAsset: (asset: CatalogAssetDetail) => void
  onEditAsset?: (asset: CatalogAssetDetail) => void
}) {
  return (
    <section className="asset-route-list">
      {assets.map((asset) => (
        <div
          key={`${asset.asset_id}:${asset.version}`}
          className={`asset-route-row-wrap ${selectedAssetId === asset.asset_id ? 'active' : ''}`}
        >
          <button
            type="button"
            className="asset-route-row"
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
          {onEditAsset ? <AssetActionMenu asset={asset} onEditAsset={onEditAsset} /> : null}
        </div>
      ))}
    </section>
  )
}

function AssetActionMenu({
  asset,
  knowledgeBase,
  onEditAsset,
  onOpenKnowledgeBaseEditor,
}: {
  asset?: CatalogAssetDetail
  knowledgeBase?: string
  onEditAsset?: (asset: CatalogAssetDetail) => void
  onOpenKnowledgeBaseEditor?: (knowledgeBase: string) => void
}) {
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="asset-row-menu-button"
          aria-label={knowledgeBase ? `Acciones de ${knowledgeBase}` : `Acciones de ${asset?.name || asset?.asset_id || 'activo'}`}
          onClick={(event) => event.stopPropagation()}
        >
          <MoreHorizontal size={17} />
        </Button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content className="dropdown-content" align="end" sideOffset={6}>
          {asset && onEditAsset ? (
            <DropdownMenu.Item
              className="dropdown-item"
              onSelect={() => onEditAsset(asset)}
            >
              <Pencil size={15} /> Editar activo
            </DropdownMenu.Item>
          ) : null}
          {knowledgeBase && onOpenKnowledgeBaseEditor ? (
            <DropdownMenu.Item
              className="dropdown-item"
              onSelect={() => onOpenKnowledgeBaseEditor(knowledgeBase)}
            >
              <Network size={15} /> Canvas de ontología
            </DropdownMenu.Item>
          ) : null}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
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
