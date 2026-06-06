import {
  Activity,
  CheckCircle2,
  ChevronsLeft,
  ChevronsRight,
  Clock3,
  FileText,
  PlayCircle,
  ShieldCheck,
  Tag,
  TerminalSquare,
  Zap,
} from 'lucide-react'
import type { ChatMessage, ExecutionResult, LauncherFlowSummary, LogEvent } from '../types'
import { formatTime } from '../lib/utils'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { JsonTraceViewer } from './JsonTraceViewer'

type RightContextPanelProps = {
  collapsed: boolean
  selectedFlow?: LauncherFlowSummary | null
  messages: ChatMessage[]
  logs: LogEvent[]
  askResult?: Record<string, unknown> | null
  executions: ExecutionResult[]
  onOpenForm: () => void
  onToggle: () => void
}

export function RightContextPanel({
  collapsed,
  selectedFlow,
  messages,
  logs,
  askResult,
  executions,
  onOpenForm,
  onToggle,
}: RightContextPanelProps) {
  const operationalLogs = logs.filter((log) => !log.trace)
  const askSteps = Array.isArray(askResult?.trace_steps)
    ? (askResult.trace_steps as Array<Record<string, unknown>>)
    : []
  const latestExecution = executions.at(-1)
  const executionSteps = latestExecution?.workflow_trace ?? []

  if (collapsed) {
    return (
      <aside className="sidebar right-sidebar collapsed-sidebar">
        <Button variant="ghost" size="icon" onClick={onToggle} aria-label="Abrir detalle">
          <ChevronsLeft size={18} />
        </Button>
      </aside>
    )
  }

  return (
    <aside className="sidebar right-sidebar">
      <div className="panel-title-row">
        <div>
          <p className="eyebrow">Contexto activo</p>
          <h2>Detalle</h2>
        </div>
        <Button variant="ghost" size="icon" onClick={onToggle} aria-label="Colapsar detalle">
          <ChevronsRight size={18} />
        </Button>
      </div>

      <section className="context-section">
        <div className="context-section-title">
          <FileText size={18} />
          <span>Flow seleccionado</span>
        </div>
        {selectedFlow ? (
          <div className="context-stack">
            <h3>{selectedFlow.flow_name}</h3>
            <p>{selectedFlow.explanation || selectedFlow.intent}</p>
            <div className="meta-grid">
              <span>ID</span>
              <strong>{selectedFlow.flow_id}</strong>
              <span>Modulo</span>
              <strong>{selectedFlow.module_id}</strong>
              <span>Pasos</span>
              <strong>{selectedFlow.plan_steps || selectedFlow.user_tasks.length}</strong>
            </div>
            <Badge tone="info">{selectedFlow.source_type}</Badge>
          </div>
        ) : (
          <p className="muted">Selecciona un flow o pregunta al chat para cargar el contexto.</p>
        )}
      </section>

      <section className="context-section">
        <div className="context-section-title">
          <Zap size={18} />
          <span>Acciones</span>
        </div>
        <div className="action-list">
          <Button variant="outline" size="sm" disabled={!selectedFlow?.lowdefy_url} onClick={onOpenForm}>
            <PlayCircle size={16} />
            Iniciar
          </Button>
          <Button variant="outline" size="sm" disabled={!selectedFlow?.lowdefy_url} onClick={onOpenForm}>
            <ShieldCheck size={16} />
            Confirmar
          </Button>
          <Button variant="outline" size="sm" disabled={!selectedFlow}>
            <Tag size={16} />
            Ver metadata
          </Button>
        </div>
      </section>

      <section className="context-section">
        <div className="context-section-title">
          <TerminalSquare size={18} />
          <span>Logs</span>
        </div>
        <div className="log-list">
          {operationalLogs.length === 0 ? (
            <p className="muted">Sin eventos todavia.</p>
          ) : (
            operationalLogs.slice(-6).map((log, index) => (
              <div className="log-row" key={`${log.timestamp ?? 'log'}-${index}`}>
                <Activity size={14} />
                <div>
                  <strong>{String(log.level ?? 'info')}</strong>
                  <p>{String(log.message ?? 'Evento recibido')}</p>
                  <span>{formatTime(String(log.timestamp ?? ''))}</span>
                </div>
              </div>
            ))
          )}
        </div>
      </section>

      <section className="context-section">
        <div className="context-section-title">
          <Clock3 size={18} />
          <span>Historial chat</span>
        </div>
        <p className="muted">{messages.length} mensajes en la sesion actual.</p>
      </section>

      <section className="context-section trace-section">
        <div className="context-section-title">
          <TerminalSquare size={18} />
          <span>Trace paso a paso</span>
        </div>
        {askSteps.length === 0 ? (
          <p className="muted">Pregunta al chat para ver intent, routing y respuesta del motor.</p>
        ) : (
          <div className="trace-timeline">
            {askSteps.map((step, index) => (
              <div className="trace-step" key={`ask-${index}`}>
                <span className="trace-sequence">{String(step.sequence ?? index + 1)}</span>
                <div>
                  <strong>{String(step.title ?? traceTitle(String(step.component ?? 'ask')))}</strong>
                  <p>{String(step.summary ?? 'Paso completado')}</p>
                  {step.result ? <span className="trace-output">Resultado: {String(step.result)}</span> : null}
                </div>
                <CheckCircle2 className="trace-status" size={15} />
              </div>
            ))}
            <div className="trace-result">
              <strong>Resultado Ask</strong>
              <span>{String(askResult?.flow_id ?? 'unknown')}</span>
              <span>{String((askResult?.route as Record<string, unknown> | undefined)?.mode ?? 'unknown')}</span>
            </div>
          </div>
        )}
      </section>

      <section className="context-section trace-section">
        <div className="context-section-title">
          <PlayCircle size={18} />
          <span>Ejecucion del flow</span>
        </div>
        {!latestExecution ? (
          <p className="muted">Abre y envia el formulario para ver cada paso del orquestador.</p>
        ) : (
          <div className="trace-timeline">
            {executionSteps.map((step, index) => (
              <div className="trace-step" key={`execution-${index}`}>
                <CheckCircle2 size={16} />
                <div>
                  <strong>{traceTitle(String(step.event ?? 'execution'))}</strong>
                  <p>{executionDetail(step)}</p>
                </div>
              </div>
            ))}
            <div className="trace-result">
              <strong>Resultado</strong>
              <span>{latestExecution.status}</span>
              <span>{latestExecution.instance_id ?? 'sin instancia'}</span>
            </div>
          </div>
        )}
      </section>

      {(askResult || latestExecution) && (
        <section className="context-section trace-json-section">
          <JsonTraceViewer
            value={{
              ask: askResult,
              execution: latestExecution ?? null,
            }}
            filename={`launcher-trace-${selectedFlow?.flow_id ?? 'session'}.json`}
          />
        </section>
      )}
    </aside>
  )
}

function traceTitle(value: string) {
  return value
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function executionDetail(step: Record<string, unknown>) {
  const values = [
    step.node_id && `Nodo: ${step.node_id}`,
    step.node_type && `Tipo: ${step.node_type}`,
    step.status && `Estado: ${step.status}`,
    step.route && `Ruta: ${step.route}`,
    step.message && String(step.message),
    Array.isArray(step.waiting_for) && step.waiting_for.length
      ? `Esperando: ${step.waiting_for.join(', ')}`
      : null,
  ].filter(Boolean)
  return values.join(' | ') || 'Paso completado.'
}
