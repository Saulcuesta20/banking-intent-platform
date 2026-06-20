import { useEffect, useState } from 'react'
import { X } from 'lucide-react'
import type { CatalogAssetDetail, OntologySelection } from '../types'
import {
  createCatalogAssetVersion,
  deployAssetSet,
  getCatalogAsset,
  previewCatalogAssetVersion,
  transitionAssetSet,
  validateCatalogAssetDocument,
} from '../api'
import { Badge } from './ui/badge'
import { Button } from './ui/button'

// @ts-expect-error plugin JS module has no TS declarations
import { FlowCanvasView } from '../../plugins/asset-editors/src/editors/flow-editor'
// @ts-expect-error plugin JS module has no TS declarations
import { OntologyEditorView } from '../../plugins/asset-editors/src/editors/ontology-editor'
// @ts-expect-error plugin JS module has no TS declarations
import { BusinessRuleEditorView } from '../../plugins/asset-editors/src/editors/business-rule-editor'
// @ts-expect-error plugin JS module has no TS declarations
import { NavigationEditorView } from '../../plugins/asset-editors/src/editors/navigation-editor'
// @ts-expect-error plugin JS module has no TS declarations
import { MenuEditorView } from '../../plugins/asset-editors/src/editors/menu-editor'
// @ts-expect-error plugin JS module has no TS declarations
import { DomainEditorView } from '../../plugins/asset-editors/src/editors/domain-editor'
// @ts-expect-error plugin JS module has no TS declarations
import { ProcessEditorView } from '../../plugins/asset-editors/src/editors/process-editor'
// @ts-expect-error plugin JS module has no TS declarations
import { ToolEditorView } from '../../plugins/asset-editors/src/editors/tool-editor'
// @ts-expect-error plugin JS module has no TS declarations
import { QaEditorView } from '../../plugins/asset-editors/src/editors/qa-editor'
// @ts-expect-error plugin JS module has no TS declarations
import { PlanEditorView } from '../../plugins/asset-editors/src/editors/plan-editor'
// @ts-expect-error plugin JS module has no TS declarations
import { UserTaskEditorView } from '../../plugins/asset-editors/src/editors/user-task-editor'
// @ts-expect-error plugin JS module has no TS declarations
import { DocumentEditorView } from '../../plugins/asset-editors/src/editors/document-editor'
// @ts-expect-error plugin JS module has no TS declarations
import { ConfigurationEditorView } from '../../plugins/asset-editors/src/editors/configuration-editor'
// @ts-expect-error plugin JS module has no TS declarations
import { ModuleEditorView } from '../../plugins/asset-editors/src/editors/module-editor'
// @ts-expect-error plugin JS module has no TS declarations
import { FormEditorView } from '../../plugins/asset-editors/src/editors/form-editor'

type PreviewResult = {
  asset_set_id?: string
  draft_version?: string
  base_version?: string
  diff?: { summary?: string[] }
  projection_preview?: { stores?: Record<string, { status?: string; detail?: string }> }
  deployment_impact?: { message?: string }
}

type VersionCreateResult = {
  asset_set_id?: string
  version?: string
  members?: Array<{ asset_id: string; version: string }>
}

type AssetInlineEditorProps = {
  asset: CatalogAssetDetail
  onClose: () => void
  onVersionCreated?: (assetId: string, version: string) => void
  onOntologySelectionChange?: (selection: OntologySelection | null) => void
  onOntologyFormHandlerChange?: (
    handler: ((context?: { entityId?: string; entityName?: string }) => void) | null,
  ) => void
}

const colors = {
  ink: '#10213d',
  muted: '#667892',
  line: '#d7dfeb',
  panel: '#ffffff',
  canvas: '#f4f7fb',
  blue: '#1463ff',
  blueSoft: '#eaf1ff',
  green: '#147d64',
  greenSoft: '#e8f6f1',
  red: '#b42318',
  redSoft: '#fff0ee',
  amber: '#9a6700',
  amberSoft: '#fff7df',
}

const baseFont = 'Inter, ui-sans-serif, system-ui, sans-serif'

function shellCardStyle(): React.CSSProperties {
  return {
    border: `1px solid ${colors.line}`,
    borderRadius: 8,
    background: colors.panel,
    padding: 14,
  }
}

function noticeStyle(type: 'error' | 'success'): React.CSSProperties {
  return {
    border: `1px solid ${type === 'error' ? colors.red : colors.green}`,
    background: type === 'error' ? colors.redSoft : colors.greenSoft,
    color: type === 'error' ? colors.red : colors.green,
    borderRadius: 8,
    padding: '10px 12px',
    fontSize: 13,
  }
}

function sourceDocument(asset: CatalogAssetDetail) {
  const stored =
    asset?.payload && (asset.payload as Record<string, unknown>).asset_id
      ? JSON.parse(JSON.stringify(asset.payload))
      : {
          asset_id: asset.asset_id,
          asset_type: asset.asset_type,
          name: asset.name,
          version: asset.version,
          tags: asset.tags,
          relations: asset.relationships,
          payload: asset.payload,
        }
  delete (stored as Record<string, unknown>).status
  delete (stored as Record<string, unknown>).source_refs
  delete (stored as Record<string, unknown>).evidence
  if (asset.primary_kb && !(stored as Record<string, unknown>).primary_kb) {
    ;(stored as Record<string, unknown>).primary_kb = asset.primary_kb
  }
  if ((stored as { payload?: Record<string, unknown> }).payload) {
    delete (stored as { payload: Record<string, unknown> }).payload.asset_set_id
    delete (stored as { payload: Record<string, unknown> }).payload.asset_set_version
  }
  return stored as Record<string, unknown>
}

function isOntologyGraphAsset(asset: CatalogAssetDetail) {
  return asset.asset_type === 'ontology_graph'
}

function SourceEditor({
  value,
  onChange,
}: {
  value: Record<string, unknown>
  onChange: (value: Record<string, unknown>) => void
}) {
  const [text, setText] = useState(JSON.stringify(value ?? {}, null, 2))
  const [error, setError] = useState('')

  function update(nextText: string) {
    setText(nextText)
    try {
      const parsed = JSON.parse(nextText)
      if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
        throw new Error('The asset document must be an object.')
      }
      setError('')
      onChange(parsed)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason))
    }
  }

  return (
    <section style={shellCardStyle()}>
      <div style={{ color: colors.ink, fontSize: 14, fontWeight: 800, marginBottom: 12 }}>Raw Source</div>
      <textarea
        value={text}
        spellCheck={false}
        onChange={(event) => update(event.target.value)}
        style={{
          width: '100%',
          minHeight: 430,
          resize: 'vertical',
          border: `1px solid ${error ? colors.red : colors.line}`,
          borderRadius: 6,
          padding: 14,
          boxSizing: 'border-box',
          background: '#0f172a',
          color: '#dbeafe',
          font: '13px/1.55 ui-monospace, SFMono-Regular, Menlo, monospace',
          tabSize: 2,
        }}
      />
      <div
        style={{
          color: error ? colors.red : colors.green,
          background: error ? colors.redSoft : 'transparent',
          padding: error ? 10 : 0,
          marginTop: 10,
          borderRadius: 6,
          fontSize: 12,
        }}
      >
        {error || 'Syntax is valid.'}
      </div>
    </section>
  )
}

export function AssetInlineEditor({
  asset,
  onClose,
  onVersionCreated,
  onOntologySelectionChange,
  onOntologyFormHandlerChange,
}: AssetInlineEditorProps) {
  const [selected, setSelected] = useState<CatalogAssetDetail | null>(null)
  const [document, setDocument] = useState<Record<string, unknown> | null>(null)
  const [notice, setNotice] = useState<{ type: 'error' | 'success'; text: string } | null>(null)
  const [preview, setPreview] = useState<PreviewResult | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function load() {
      setBusy(true)
      setNotice(null)
      try {
        if (isOntologyGraphAsset(asset)) {
          if (cancelled) return
          setSelected(asset)
          setDocument(sourceDocument(asset))
          setPreview(null)
          return
        }
        const detail = await getCatalogAsset(asset.asset_id, asset.version)
        if (cancelled) return
        setSelected(detail)
        setDocument(sourceDocument(detail))
        setPreview(null)
      } catch (error) {
        if (!cancelled) setNotice({ type: 'error', text: error instanceof Error ? error.message : String(error) })
      } finally {
        if (!cancelled) setBusy(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [asset])

  const assetType = String(selected?.asset_type || asset.asset_type)
  const isFlowEditor = assetType === 'flow'
  const isOntologyEditor = assetType === 'entity' || assetType === 'ontology_graph'
  const isBusinessRuleEditor = assetType === 'business_rule'
  const isNavigationEditor = assetType === 'navigation'
  const isMenuEditor = assetType === 'menu'
  const isDomainEditor = assetType === 'domain'
  const isProcessEditor = assetType === 'process'
  const isToolEditor = assetType === 'tool'
  const isQaEditor = assetType === 'qa'
  const isPlanEditor = assetType === 'plan'
  const isUserTaskEditor = assetType === 'user_task'
  const isDocumentEditor = assetType === 'document'
  const isConfigurationEditor = assetType === 'configuration'
  const isModuleEditor = assetType === 'module'
  const isFormEditor = assetType === 'form'

  useEffect(() => {
    if (!isOntologyEditor) {
      onOntologySelectionChange?.(null)
      onOntologyFormHandlerChange?.(null)
    }
    return () => {
      onOntologySelectionChange?.(null)
      onOntologyFormHandlerChange?.(null)
    }
  }, [isOntologyEditor, onOntologySelectionChange, onOntologyFormHandlerChange])

  async function validate() {
    if (assetType === 'ontology_graph') {
      setNotice({ type: 'success', text: 'Ontology graph context is loaded from the active knowledge base.' })
      return
    }
    if (!selected || !document) return
    try {
      const result = await validateCatalogAssetDocument({
        document,
        expected_asset_id: selected.asset_id,
        expected_asset_type: selected.asset_type,
      })
      setNotice({
        type: 'success',
        text: `Schema valid. ${result.relation_count} relationships; stores: ${(result.stores || []).join(', ') || 'catalog'}.`,
      })
    } catch (error) {
      setNotice({ type: 'error', text: error instanceof Error ? error.message : String(error) })
    }
  }

  async function loadPreview() {
    if (assetType === 'ontology_graph') {
      setNotice({ type: 'error', text: 'El canvas de KB es una vista agregada; edita entidades individuales para versionar cambios.' })
      return null
    }
    if (!selected || !document) return null
    try {
      const result = (await previewCatalogAssetVersion(selected.asset_id, {
        base_version: selected.version,
        environment: 'dev',
        document,
      })) as PreviewResult
      setPreview(result)
      setNotice({
        type: 'success',
        text: `Preview ready. Draft ${result.draft_version} will stay inactive until review and deployment.`,
      })
      return result
    } catch (error) {
      setNotice({ type: 'error', text: error instanceof Error ? error.message : String(error) })
      return null
    }
  }

  async function reloadCurrent() {
    if (isOntologyGraphAsset(asset)) {
      setSelected(asset)
      setDocument(sourceDocument(asset))
      setPreview(null)
      setNotice(null)
      return
    }
    const detail = await getCatalogAsset(asset.asset_id, asset.version)
    setSelected(detail)
    setDocument(sourceDocument(detail))
    setPreview(null)
    setNotice(null)
  }

  async function saveNewVersion() {
    if (assetType === 'ontology_graph') {
      setNotice({ type: 'error', text: 'El canvas de KB no se versiona como un asset único. Abre una entidad para guardar una nueva versión.' })
      return
    }
    if (!selected || !document) return
    setBusy(true)
    setNotice(null)
    try {
      const resultPreview = await loadPreview()
      const confirmed =
        typeof window === 'undefined'
          ? true
          : window.confirm(
              `Create draft AssetSet version ${resultPreview?.asset_set_id}@${resultPreview?.draft_version}? Runtime and KB projections will not change until deployment.`,
            )
      if (!confirmed) {
        setNotice({ type: 'error', text: 'Save cancelled. No version was created.' })
        return
      }
      const result = (await createCatalogAssetVersion(selected.asset_id, {
        base_version: selected.version,
        actor: 'saul',
        document,
      })) as VersionCreateResult
      setNotice({
        type: 'success',
        text: `Created ${result.asset_set_id}@${result.version}. The AssetSet is ready for review.`,
      })
      const created = result.members?.find((item) => item.asset_id === selected.asset_id)
      if (created?.version) {
        const detail = await getCatalogAsset(created.asset_id, created.version)
        setSelected(detail)
        setDocument(sourceDocument(detail))
        setPreview(null)
        onVersionCreated?.(created.asset_id, created.version)
      }
    } catch (error) {
      setNotice({ type: 'error', text: error instanceof Error ? error.message : String(error) })
    } finally {
      setBusy(false)
    }
  }

  async function deployCurrentAssetSet() {
    if (assetType === 'ontology_graph') {
      setNotice({ type: 'error', text: 'El canvas de KB no tiene AssetSet propio para desplegar.' })
      return
    }
    if (!selected?.asset_set_id || !selected?.asset_set_version) return
    const confirmed =
      typeof window === 'undefined'
        ? true
        : window.confirm(
            `Deploy ${selected.asset_set_id}@${selected.asset_set_version} to DEV and update specialized KB projections?`,
          )
    if (!confirmed) return
    setBusy(true)
    setNotice(null)
    try {
      let status = selected.status
      if (status === 'ready_for_review') {
        const reviewed = await transitionAssetSet(
          selected.asset_set_id,
          selected.asset_set_version,
          'start_review',
          'Deploy requested from launcher editor.',
        )
        status = reviewed.status
      }
      if (status === 'in_review') {
        const validated = await transitionAssetSet(
          selected.asset_set_id,
          selected.asset_set_version,
          'validate',
          'Validated for deployment from launcher editor.',
        )
        status = validated.status
      }
      if (status !== 'validated' && status !== 'active') {
        throw new Error(`AssetSet must be validated before deployment. Current status: ${status}`)
      }
      await deployAssetSet(selected.asset_set_id, selected.asset_set_version, 'dev')
      const detail = await getCatalogAsset(selected.asset_id, selected.version)
      setSelected(detail)
      setDocument(sourceDocument(detail))
      setPreview(null)
      setNotice({
        type: 'success',
        text: `${selected.asset_set_id}@${selected.asset_set_version} deployed to DEV. Specialized KB projections are active.`,
      })
      onVersionCreated?.(selected.asset_id, selected.version)
    } catch (error) {
      setNotice({ type: 'error', text: error instanceof Error ? error.message : String(error) })
    } finally {
      setBusy(false)
    }
  }

  function updateDocument(nextDocument: Record<string, unknown>) {
    setDocument(nextDocument)
    setPreview(null)
  }

  function buttonStyle(primary = false): React.CSSProperties {
    return {
      border: `1px solid ${primary ? colors.blue : colors.line}`,
      background: primary ? colors.blue : colors.panel,
      color: primary ? '#fff' : colors.ink,
      borderRadius: 6,
      padding: '8px 12px',
      fontWeight: 700,
      cursor: 'pointer',
      fontFamily: baseFont,
    }
  }

  return (
    <section className="asset-editor-shell">
      <div className="asset-editor-header">
        <div>
          <p className="asset-breadcrumb">
            Assets / {asset.asset_type} / {asset.asset_id}
          </p>
          <div className="asset-editor-title">
            <h2>{asset.name || asset.asset_id}</h2>
            <Badge tone="info">Inline Editor</Badge>
          </div>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose} aria-label="Cerrar editor">
          <X size={17} />
        </Button>
      </div>

      <div className="asset-editor-body" style={{ fontFamily: baseFont, color: colors.ink, display: 'grid', gap: 14 }}>
        {notice ? <div style={noticeStyle(notice.type)}>{notice.text}</div> : null}
        {selected && document ? (
          <div style={{ display: 'grid', gap: 14 }}>
            <section style={{ ...shellCardStyle(), display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center', padding: '10px 14px' }}>
              {[
                ['Type', String(selected.asset_type || '-')],
                ['Version', String(selected.version || '-')],
                ['Status', String(selected.status || '-')],
                ['Asset Set', String(selected.asset_set_id || '-')],
              ].map(([label, value]) => (
                <span key={label} style={{ fontSize: 12, color: colors.muted }}>
                  <strong style={{ fontWeight: 700 }}>{label}:</strong> {value}
                </span>
              ))}
            </section>
            {isFlowEditor ? (
              <FlowCanvasView value={document} onChange={updateDocument} />
            ) : isOntologyEditor ? (
              <OntologyEditorView
                value={document}
                onChange={updateDocument}
                knowledgeBase={selected.primary_kb ?? (selected.payload as { owner?: string } | undefined)?.owner}
                onSelectionChange={onOntologySelectionChange}
                onRegisterFormHandler={onOntologyFormHandlerChange}
              />
            ) : isBusinessRuleEditor ? (
              <BusinessRuleEditorView value={document} onChange={updateDocument} />
            ) : isNavigationEditor ? (
              <NavigationEditorView value={document} onChange={updateDocument} />
            ) : isMenuEditor ? (
              <MenuEditorView value={document} onChange={updateDocument} />
            ) : isDomainEditor ? (
              <DomainEditorView value={document} onChange={updateDocument} />
            ) : isProcessEditor ? (
              <ProcessEditorView value={document} onChange={updateDocument} />
            ) : isToolEditor ? (
              <ToolEditorView value={document} onChange={updateDocument} />
            ) : isQaEditor ? (
              <QaEditorView value={document} onChange={updateDocument} />
            ) : isPlanEditor ? (
              <PlanEditorView value={document} onChange={updateDocument} />
            ) : isUserTaskEditor ? (
              <UserTaskEditorView value={document} onChange={updateDocument} />
            ) : isDocumentEditor ? (
              <DocumentEditorView value={document} onChange={updateDocument} />
            ) : isConfigurationEditor ? (
              <ConfigurationEditorView value={document} onChange={updateDocument} />
            ) : isModuleEditor ? (
              <ModuleEditorView value={document} onChange={updateDocument} />
            ) : isFormEditor ? (
              <FormEditorView value={document} onChange={updateDocument} />
            ) : (
              <SourceEditor key={`${selected.asset_id}:${selected.version}`} value={document} onChange={updateDocument} />
            )}
            {preview ? (
              <section style={{ ...shellCardStyle() }}>
                <div style={{ color: colors.ink, fontSize: 13, fontWeight: 800, marginBottom: 6 }}>Preview</div>
                <div style={{ fontSize: 12, color: colors.muted, lineHeight: 1.5 }}>
                  Draft: {preview.draft_version || '-'}
                </div>
                {preview.diff?.summary?.length ? (
                  <ul style={{ margin: '6px 0 0', paddingLeft: 16, fontSize: 12, color: colors.ink }}>
                    {preview.diff.summary.map((line, i) => <li key={i}>{line}</li>)}
                  </ul>
                ) : null}
              </section>
            ) : null}
            <section style={{ ...shellCardStyle(), display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center', padding: '12px 14px' }}>
              <button type="button" style={buttonStyle()} onClick={() => void validate()}>Validate</button>
              <button type="button" style={buttonStyle(true)} onClick={() => void saveNewVersion()}>Save draft</button>
              <button type="button" style={buttonStyle()} onClick={() => void loadPreview()}>View Diff</button>
              <button type="button" disabled={busy || !selected.asset_set_id} style={buttonStyle(true)} onClick={() => void deployCurrentAssetSet()}>Deploy</button>
              <button type="button" style={buttonStyle()} onClick={() => void reloadCurrent()}>Reload</button>
            </section>
          </div>
        ) : (
          <div style={{ minHeight: 520, display: 'grid', placeItems: 'center', border: `1px solid ${colors.line}`, borderRadius: 8, color: colors.muted, background: colors.canvas }}>
            {busy ? 'Loading asset editor...' : 'Select an asset in the launcher to open the editor.'}
          </div>
        )}
      </div>
    </section>
  )
}
