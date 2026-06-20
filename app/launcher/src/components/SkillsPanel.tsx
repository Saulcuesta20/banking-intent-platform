import { Plus, RefreshCw, ShieldCheck, Sparkles } from 'lucide-react'
import type { AgentDraft, SkillAsset } from '../types'
import { Badge } from './ui/badge'
import { Button } from './ui/button'

type SkillsPanelProps = {
  skills: SkillAsset[]
  selectedSkill: SkillAsset
  onSelectSkill: (skillId: string) => void
  onCreateAgent: () => void
  onEditSkill: () => void
  onValidate: () => void
  onPublish: () => void
  onCompare: () => void
  draftAgent?: AgentDraft | null
}

export function SkillsPanel({
  skills,
  selectedSkill,
  onSelectSkill,
  onCreateAgent,
  onEditSkill,
  onValidate,
  onPublish,
  onCompare,
  draftAgent,
}: SkillsPanelProps) {
  return (
    <main className="workspace asset-workspace">
      <div className="asset-heading">
        <div>
          <div className="asset-title-line">
            <p className="eyebrow">Unified Catalog</p>
            <Badge tone="info">Launcher Embedded Editors</Badge>
          </div>
          <h1>Skill</h1>
          <p>Administra skills en Markdown y prepara la creación de agentes con tipo seleccionado.</p>
        </div>
        <div className="asset-view-switch">
          <Button variant="outline" size="sm" onClick={onEditSkill}>
            <Sparkles size={16} />
            Editor
          </Button>
          <Button variant="outline" size="sm" onClick={onCreateAgent}>
            <Plus size={16} />
            Nuevo agente
          </Button>
          <Button variant="outline" size="sm" onClick={onValidate}>
            <ShieldCheck size={16} />
            Validar
          </Button>
          <Button variant="ghost" size="icon" onClick={onCompare} aria-label="Comparar">
            <RefreshCw size={17} />
          </Button>
        </div>
      </div>

      <div className="skill-workspace">
        <section className="skill-browser">
          <div className="skill-browser-header">
            <div>
              <strong>Skill library</strong>
              <span>{skills.length} skills</span>
            </div>
          </div>
          <div className="skill-list">
            {skills.map((skill) => (
              <button
                key={skill.skill_id}
                type="button"
                className={skill.skill_id === selectedSkill.skill_id ? 'skill-item active' : 'skill-item'}
                onClick={() => onSelectSkill(skill.skill_id)}
              >
                <strong>{skill.title}</strong>
                <p>{skill.description}</p>
                <div className="skill-meta">
                  <span>{skill.scope}</span>
                  <span>{skill.status}</span>
                </div>
              </button>
            ))}
          </div>
        </section>

        <section className="skill-editor-card">
          <div className="skill-editor-header">
            <div>
              <strong>{selectedSkill.title}</strong>
              <span>{selectedSkill.skill_id}</span>
            </div>
            <Badge tone="success">{selectedSkill.status}</Badge>
          </div>
          <div className="skill-editor-tabs">
            <button type="button" className="active" onClick={onEditSkill}>
              Editor
            </button>
            <button type="button">Preview</button>
          </div>
          <div className="skill-markdown">
            <pre>{selectedSkill.markdown}</pre>
          </div>
        </section>
      </div>

      {draftAgent ? (
        <div className="skill-roadmap">
          <div className="mini">
            <h4>Agent draft</h4>
            <div className="future">
              <div className="item">{draftAgent.name}</div>
              <div className="item">{draftAgent.agent_type}</div>
              <div className="item">{draftAgent.skill_ids.join(', ') || 'No skills selected'}</div>
            </div>
          </div>
        </div>
      ) : null}

      <div className="skill-actions">
        <Button variant="outline" onClick={onValidate}>Validar skill</Button>
        <Button variant="outline" onClick={onPublish}>Publicar skill</Button>
        <Button variant="default" onClick={onCreateAgent}>Crear agente</Button>
      </div>
    </main>
  )
}
