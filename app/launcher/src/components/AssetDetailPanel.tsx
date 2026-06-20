import {
  CheckCircle2,
  ChevronRight,
  CircleX,
  Clock3,
  Database,
  GitCommitHorizontal,
  History,
  Network,
  Pencil,
  PlayCircle,
  RotateCcw,
  ShieldCheck,
  Tags,
} from 'lucide-react'
import { useState } from 'react'
import type { AssetSetDetail, CatalogAssetDetail, OntologySelection } from '../types'
import { Button } from './ui/button'
import { StatusBadge } from './AssetExplorer'

type AssetDetailPanelProps = {
  asset?: CatalogAssetDetail | null
  assetSet?: AssetSetDetail | null
  busy: boolean
  onAction: (action: string, comment?: string) => void
  onDeploy: () => void
  onRollback: () => void
  onEdit?: () => void
  ontologySelection?: OntologySelection | null
  onOpenOntologyForm?: (context?: { entityId?: string; entityName?: string }) => void
}

export function AssetDetailPanel({
  asset,
  assetSet,
  busy,
  onAction,
  onDeploy,
  onRollback,
  onEdit,
  ontologySelection,
  onOpenOntologyForm,
}: AssetDetailPanelProps) {
  const [comment, setComment] = useState('')
  if (!asset) {
    return <p className="asset-detail-empty">Selecciona un activo del árbol para revisar sus propiedades.</p>
  }
  const status = assetSet?.status ?? asset.status
  const ontologyEntity = asset.asset_type === 'entity' ? ontologySelection?.entity : null
  const ontologyRelations = asset.asset_type === 'entity' ? ontologySelection?.relations ?? [] : []
  return (
    <div className="asset-detail-content">
      {ontologyEntity ? (
        <section className="context-section">
          <div className="context-section-title">
            <Network size={18} />
            <span>Ontology selection</span>
          </div>
          <h3>{ontologyEntity.name || ontologyEntity.asset_id}</h3>
          <p className="asset-id">
            {ontologyEntity.layer || '—'}
            {ontologyEntity.subtype ? ` / ${ontologyEntity.subtype}` : ''}
            {ontologyEntity.technical_type ? ` · técnico: ${ontologyEntity.technical_type}` : ''}
          </p>
          <p className="muted">{ontologyEntity.description || 'Sin descripción.'}</p>
          {ontologyEntity.aliases?.length ? (
            <div className="asset-tags">
              <Tags size={15} />
              {ontologyEntity.aliases.map((alias) => (
                <span key={alias}>{alias}</span>
              ))}
            </div>
          ) : null}
          {ontologyRelations.length ? (
            <ul className="ontology-relations">
              {ontologyRelations.slice(0, 6).map((relation) => (
                <li key={relation.id}>
                  {relation.direction === 'incoming' ? (
                    <>
                      {relation.source_name || relation.source_entity_id} → <strong>{relation.relation_type}</strong>
                      {relation.relation_family ? <span> · {relation.relation_family}</span> : null}
                    </>
                  ) : (
                    <>
                      <strong>{relation.relation_type}</strong>
                      {relation.relation_family ? <span> · {relation.relation_family}</span> : null}
                      {' '}→ {relation.target_name || relation.target_entity_id}
                    </>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Sin relaciones visibles.</p>
          )}
          {onOpenOntologyForm ? (
            <Button
              size="sm"
              onClick={() =>
                onOpenOntologyForm({ entityId: ontologyEntity.asset_id, entityName: ontologyEntity.name })
              }
            >
              <Pencil size={15} /> Editar en formulario
            </Button>
          ) : null}
        </section>
      ) : asset.asset_type === 'entity' ? (
        <section className="context-section">
          <div className="context-section-title">
            <Network size={18} />
            <span>Ontology selection</span>
          </div>
          <p className="muted">Selecciona un nodo en el canvas para ver sus atributos aquí.</p>
        </section>
      ) : null}

      <section className="context-section">
        <div className="context-section-title">
          <Database size={18} />
          <span>Asset Details</span>
        </div>
        <h3>{asset.name || asset.asset_id}</h3>
        <p className="asset-id">{asset.asset_id}</p>
        {onEdit ? (
          <Button size="sm" onClick={onEdit}>
            <Pencil size={15} /> Editar
          </Button>
        ) : null}
        <div className="asset-property-grid">
          <span>Asset Type</span><strong>{asset.asset_type}</strong>
          <span>Version</span><strong>{asset.version}</strong>
          <span>Domain</span><strong>{asset.domain_id || '-'}</strong>
          <span>Module</span><strong>{asset.module_id || '-'}</strong>
          <span>AssetSet</span><strong>{asset.asset_set_id || '-'}</strong>
          <span>Status</span><StatusBadge status={status} />
          <span>Active</span><strong>{asset.active ? asset.active_environment : 'No'}</strong>
          <span>Checksum</span><code>{assetSet?.checksum?.slice(0, 14) || asset.checksum?.slice(0, 14) || '-'}</code>
        </div>
        <div className="asset-tags">
          <Tags size={15} />
          {[...new Set(asset.tags)].map((tag) => <span key={tag}>{tag}</span>)}
        </div>
      </section>

      <section className="context-section">
        <div className="context-section-title">
          <GitCommitHorizontal size={18} />
          <span>Knowledge projections</span>
        </div>
        <div className="projection-list">
          {asset.stores.map((store) => (
            <div key={store}>
              <CheckCircle2 size={15} />
              <span>{store} KB</span>
              <strong>{asset.active ? 'active' : 'staging'}</strong>
            </div>
          ))}
        </div>
      </section>

      <section className="context-section">
        <div className="context-section-title">
          <ShieldCheck size={18} />
          <span>Human Review</span>
        </div>
        <textarea
          className="review-comment"
          value={comment}
          onChange={(event) => setComment(event.target.value)}
          placeholder="Comentario de revisión..."
        />
        <div className="review-actions">
          {status === 'ready_for_review' && (
            <Button size="sm" disabled={busy} onClick={() => onAction('start_review', comment)}>
              <PlayCircle size={15} /> Start Review
            </Button>
          )}
          {status === 'in_review' && (
            <>
              <Button size="sm" disabled={busy} onClick={() => onAction('validate', comment)}>
                <CheckCircle2 size={15} /> Validate
              </Button>
              <Button variant="outline" size="sm" disabled={busy || !comment.trim()} onClick={() => onAction('request_changes', comment)}>
                <RotateCcw size={15} /> Request Changes
              </Button>
              <Button variant="outline" size="sm" disabled={busy || !comment.trim()} onClick={() => onAction('reject', comment)}>
                <CircleX size={15} /> Reject
              </Button>
            </>
          )}
          {!['ready_for_review', 'in_review'].includes(status) && (
            <p className="muted">El AssetSet está en estado {status}.</p>
          )}
        </div>
      </section>

      <section className="context-section">
        <div className="context-section-title">
          <History size={18} />
          <span>Deployment</span>
        </div>
        <div className="deployment-summary">
          <span>Target</span><strong>DEV</strong>
          <span>Candidate</span><strong>{assetSet?.version || asset.asset_set_version}</strong>
          <span>Current</span><strong>{assetSet?.active_environment ? assetSet.version : 'Not active'}</strong>
        </div>
        <Button disabled={busy || status !== 'validated'} onClick={onDeploy}>
          <ChevronRight size={16} /> Deploy AssetSet
        </Button>
        <Button variant="outline" disabled={busy || !asset.active} onClick={onRollback}>
          <RotateCcw size={16} /> Rollback
        </Button>
      </section>

      <section className="context-section">
        <div className="context-section-title">
          <Clock3 size={18} />
          <span>History</span>
        </div>
        <div className="asset-history">
          {(assetSet?.lifecycle_events ?? []).slice(0, 6).map((event, index) => (
            <div key={`${String(event.event_id)}-${index}`}>
              <span>{String(event.to_status)}</span>
              <strong>{String(event.actor)}</strong>
              <time>{String(event.created_at).slice(0, 16).replace('T', ' ')}</time>
            </div>
          ))}
          {!assetSet?.lifecycle_events?.length && <p className="muted">Sin eventos registrados.</p>}
        </div>
      </section>
    </div>
  )
}
