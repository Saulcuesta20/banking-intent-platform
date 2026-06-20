import { X } from 'lucide-react'
import type { AgentDraft, AgentType, SkillAsset } from '../types'
import { Button } from './ui/button'

type SkillAgentModalProps = {
  open: boolean
  draft: AgentDraft
  skills: SkillAsset[]
  onClose: () => void
  onChange: (next: AgentDraft) => void
  onSubmit: () => void
}

const agentTypes: AgentType[] = ['planning', 'coordinator', 'delegator', 'worker', 'monitoring']

export function SkillAgentModal({ open, draft, skills, onClose, onChange, onSubmit }: SkillAgentModalProps) {
  if (!open) return null

  function toggleSkill(skillId: string) {
    const skill_ids = draft.skill_ids.includes(skillId)
      ? draft.skill_ids.filter((item) => item !== skillId)
      : [...draft.skill_ids, skillId]
    onChange({ ...draft, skill_ids })
  }

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
        aria-label="Crear agente"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <p className="eyebrow">Agentes</p>
            <h3>Crear agente</h3>
            <p className="muted">Selecciona el tipo de agente, asocia skills y deja listo el contrato inicial.</p>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Cerrar modal">
            <X size={18} />
          </Button>
        </div>

        <div className="modal-grid">
          <label className="modal-field">
            <span>Agent ID</span>
            <input value={draft.agent_id} onChange={(event) => onChange({ ...draft, agent_id: event.target.value })} />
          </label>
          <label className="modal-field">
            <span>Nombre</span>
            <input value={draft.name} onChange={(event) => onChange({ ...draft, name: event.target.value })} />
          </label>
          <label className="modal-field full">
            <span>Descripción</span>
            <textarea value={draft.description} onChange={(event) => onChange({ ...draft, description: event.target.value })} />
          </label>
          <label className="modal-field">
            <span>Tipo de agente</span>
            <select value={draft.agent_type} onChange={(event) => onChange({ ...draft, agent_type: event.target.value as AgentType })}>
              {agentTypes.map((agentType) => (
                <option key={agentType} value={agentType}>
                  {agentType}
                </option>
              ))}
            </select>
          </label>
          <label className="modal-field">
            <span>Dominio</span>
            <select value={draft.domain} onChange={(event) => onChange({ ...draft, domain: event.target.value as AgentDraft['domain'] })}>
              <option value="ask">ask</option>
              <option value="ingestion">ingestion</option>
              <option value="asset">asset</option>
              <option value="tool">tool</option>
              <option value="system">system</option>
            </select>
          </label>
        </div>

        <div className="modal-section">
          <div className="modal-section-title">
            <strong>Skills asociados</strong>
            <span>{draft.skill_ids.length} seleccionadas</span>
          </div>
          <div className="checkbox-grid">
            {skills.map((skill) => (
              <label key={skill.skill_id} className="checkbox-card">
                <input
                  type="checkbox"
                  checked={draft.skill_ids.includes(skill.skill_id)}
                  onChange={() => toggleSkill(skill.skill_id)}
                />
                <div>
                  <strong>{skill.title}</strong>
                  <p>{skill.description}</p>
                </div>
              </label>
            ))}
          </div>
        </div>

        <div className="modal-section">
          <div className="modal-section-title">
            <strong>Tools permitidas</strong>
            <span>{draft.tool_ids.length} herramientas</span>
          </div>
          <div className="pill-row">
            {draft.tool_ids.map((tool) => (
              <span key={tool} className="pill blue">
                {tool}
              </span>
            ))}
          </div>
        </div>

        <div className="modal-footer">
          <Button variant="outline" onClick={onClose}>
            Cancelar
          </Button>
          <Button variant="outline" onClick={onSubmit}>
            Validar
          </Button>
          <Button variant="default" onClick={onSubmit}>
            Crear agente
          </Button>
        </div>
      </div>
    </div>
  )
}
