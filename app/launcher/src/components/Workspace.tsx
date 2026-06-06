import type { LauncherFlowSummary, LauncherModule } from '../types'
import { ExternalLink, X } from 'lucide-react'
import { ChatPanel } from './ChatPanel'
import { Button } from './ui/button'

type WorkspaceProps = {
  activeModule?: LauncherModule
  activeDomainLabel: string
  activeTopMenuLabel: string
  selectedFlow?: LauncherFlowSummary | null
  messages: Parameters<typeof ChatPanel>[0]['messages']
  chatValue: string
  chatLoading: boolean
  onChatValueChange: (value: string) => void
  onChatSubmit: () => void
  formOpen: boolean
  onOpenForm: () => void
  onCloseForm: () => void
}

export function Workspace({
  activeModule,
  activeDomainLabel,
  activeTopMenuLabel,
  selectedFlow,
  messages,
  chatValue,
  chatLoading,
  onChatValueChange,
  onChatSubmit,
  formOpen,
  onOpenForm,
  onCloseForm,
}: WorkspaceProps) {
  return (
    <main className="workspace">
      <div className="welcome-row">
        <div>
          <p className="eyebrow">Main workspace</p>
          <h1>Bienvenido, Saul</h1>
          <p>Selecciona una opcion o pregunta al chat para iniciar un flow.</p>
        </div>
        <div className="workspace-meta">
          <span>{activeDomainLabel} / {activeTopMenuLabel}</span>
          <strong>{activeModule?.label ?? 'Home'}</strong>
        </div>
      </div>

      <div className="workspace-stack">
        <ChatPanel
          messages={messages}
          selectedFlow={selectedFlow}
          value={chatValue}
          loading={chatLoading}
          onChange={onChatValueChange}
          onSubmit={onChatSubmit}
        />
        {selectedFlow?.lowdefy_url && (
          <section className="flow-runtime">
            <div className="flow-runtime-header">
              <div>
                <p className="eyebrow">Activo dinamico</p>
                <h2>{selectedFlow.flow_name}</h2>
                <span>{selectedFlow.form_id} / {selectedFlow.form_version} / mapping provisional</span>
              </div>
              {formOpen ? (
                <Button variant="ghost" size="icon" onClick={onCloseForm} aria-label="Cerrar formulario">
                  <X size={18} />
                </Button>
              ) : (
                <Button onClick={onOpenForm}>
                  <ExternalLink size={16} />
                  Confirmar y abrir formulario
                </Button>
              )}
            </div>
            {formOpen && (
              <iframe
                className="lowdefy-frame"
                src={selectedFlow.lowdefy_url}
                title={`Formulario ${selectedFlow.flow_name}`}
              />
            )}
          </section>
        )}
      </div>
    </main>
  )
}
