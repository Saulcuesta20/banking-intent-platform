import { X } from 'lucide-react'
import type { SkillAsset } from '../types'
import { Button } from './ui/button'

type SkillEditorModalProps = {
  open: boolean
  draft: SkillAsset
  onClose: () => void
  onChange: (next: SkillAsset) => void
  onSave: () => void
}

export function SkillEditorModal({ open, draft, onClose, onChange, onSave }: SkillEditorModalProps) {
  if (!open) return null

  return (
    <div
      className="modal-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div
        className="modal-card skill-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Editar skill"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <p className="eyebrow">Skill editor</p>
            <h3>Editar Markdown</h3>
            <p className="muted">Edita el contrato del skill y guarda o cancela sin salir del launcher.</p>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Cerrar modal">
            <X size={18} />
          </Button>
        </div>

        <div className="modal-grid">
          <label className="modal-field">
            <span>Skill ID</span>
            <input value={draft.skill_id} readOnly />
          </label>
          <label className="modal-field">
            <span>Título</span>
            <input value={draft.title} onChange={(event) => onChange({ ...draft, title: event.target.value })} />
          </label>
          <label className="modal-field">
            <span>Descripción</span>
            <textarea
              className="skill-description-input"
              value={draft.description}
              onChange={(event) => onChange({ ...draft, description: event.target.value })}
            />
          </label>
          <label className="modal-field">
            <span>Estado</span>
            <select value={draft.status} onChange={(event) => onChange({ ...draft, status: event.target.value as SkillAsset['status'] })}>
              <option value="draft">draft</option>
              <option value="review">review</option>
              <option value="active">active</option>
            </select>
          </label>
        </div>

        <div className="modal-section">
          <div className="modal-section-title">
            <strong>Markdown</strong>
            <span>{draft.markdown.length} chars</span>
          </div>
          <textarea
            className="skill-markdown-editor"
            value={draft.markdown}
            onChange={(event) => onChange({ ...draft, markdown: event.target.value })}
          />
        </div>

        <div className="modal-footer">
          <Button variant="outline" onClick={onClose}>
            Cancelar
          </Button>
          <Button variant="default" onClick={onSave}>
            Guardar
          </Button>
        </div>
      </div>
    </div>
  )
}
