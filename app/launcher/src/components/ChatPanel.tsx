import { Bot, Loader2, Mic, Paperclip, SendHorizonal, UserRound } from 'lucide-react'
import type { ChatMessage, LauncherFlowSummary } from '../types'
import { Button } from './ui/button'

type ChatPanelProps = {
  messages: ChatMessage[]
  selectedFlow?: LauncherFlowSummary | null
  value: string
  loading: boolean
  onChange: (value: string) => void
  onSubmit: () => void
}

export function ChatPanel({ messages, selectedFlow, value, loading, onChange, onSubmit }: ChatPanelProps) {
  return (
    <section className="chat-panel">
      <div className="chat-header">
        <div>
          <p className="eyebrow">Chat center</p>
          <h2>Conversacion</h2>
        </div>
        <span className="chat-flow-pill">{selectedFlow ? `Flow activo: ${selectedFlow.flow_name}` : 'Sin flow activo'}</span>
      </div>

      {selectedFlow && (
        <div className="selected-flow-banner">
          <div className="selected-flow-copy">
            <strong className="selected-flow-title">{selectedFlow.flow_name}</strong>
            <span className="selected-flow-intent">{selectedFlow.intent || selectedFlow.explanation}</span>
          </div>
          <code className="selected-flow-id">{selectedFlow.flow_id}</code>
        </div>
      )}

      <div className="chat-body">
        <div className="chat-thread">
          {messages.map((message) => (
            <div key={message.id} className={`chat-message ${message.role}`}>
              <div className="message-avatar">{message.role === 'user' ? <UserRound size={16} /> : <Bot size={16} />}</div>
              <div className="message-bubble">
                <p>{message.content}</p>
                {message.flow && <span>Flow: {message.flow.flow_name}</span>}
              </div>
            </div>
          ))}
          {loading && (
            <div className="chat-message assistant">
              <div className="message-avatar">
                <Bot size={16} />
              </div>
              <div className="message-bubble">
                <p className="loading-inline">
                  <Loader2 size={14} />
                  Analizando intent y flows disponibles...
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      <form
        className="chat-composer"
        onSubmit={(event) => {
          event.preventDefault()
          onSubmit()
        }}
      >
        <Button variant="ghost" size="icon" type="button" aria-label="Adjuntar">
          <Paperclip size={18} />
        </Button>
        <input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="Pregunta algo o escribe un comando..."
          aria-label="Mensaje"
        />
        <Button variant="ghost" size="icon" type="button" aria-label="Dictar">
          <Mic size={18} />
        </Button>
        <Button size="icon" type="submit" disabled={loading || !value.trim()} aria-label="Enviar">
          <SendHorizonal size={18} />
        </Button>
      </form>
    </section>
  )
}
