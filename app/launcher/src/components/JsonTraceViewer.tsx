import { Braces, Check, Copy, Download, Maximize2, Minimize2, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Button } from './ui/button'

type JsonTraceViewerProps = {
  value: unknown
  filename: string
}

export function JsonTraceViewer({ value, filename }: JsonTraceViewerProps) {
  const [query, setQuery] = useState('')
  const [copied, setCopied] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const json = useMemo(() => JSON.stringify(value, null, 2), [value])
  const lines = useMemo(() => json.split('\n'), [json])
  const normalizedQuery = query.trim().toLocaleLowerCase()
  const matchCount = normalizedQuery
    ? lines.reduce(
        (count, line) => count + (line.toLocaleLowerCase().includes(normalizedQuery) ? 1 : 0),
        0,
      )
    : 0

  async function copyJson() {
    await navigator.clipboard.writeText(json)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1400)
  }

  function downloadJson() {
    const url = URL.createObjectURL(new Blob([`${json}\n`], { type: 'application/json' }))
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className={`json-viewer ${expanded ? 'json-viewer-expanded' : ''}`}>
      <div className="json-viewer-header">
        <div className="json-viewer-title">
          <Braces size={16} />
          <strong>JSON técnico</strong>
        </div>
        <div className="json-viewer-actions">
          <Button variant="ghost" size="icon" onClick={copyJson} aria-label="Copiar JSON">
            {copied ? <Check size={15} /> : <Copy size={15} />}
          </Button>
          <Button variant="ghost" size="icon" onClick={downloadJson} aria-label="Descargar JSON">
            <Download size={15} />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setExpanded((current) => !current)}
            aria-label={expanded ? 'Reducir editor JSON' : 'Ampliar editor JSON'}
          >
            {expanded ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
          </Button>
        </div>
      </div>

      <label className="json-search">
        <Search size={14} />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Buscar en el trace..."
          aria-label="Buscar en JSON"
        />
        {normalizedQuery && <span>{matchCount}</span>}
      </label>

      <div className="json-editor" role="region" aria-label="Contenido JSON">
        {lines.map((line, index) => {
          const matches = normalizedQuery && line.toLocaleLowerCase().includes(normalizedQuery)
          return (
            <div className={`json-line ${matches ? 'json-line-match' : ''}`} key={`${index}-${line}`}>
              <span className="json-line-number">{index + 1}</span>
              <code>{line || ' '}</code>
            </div>
          )
        })}
      </div>
    </div>
  )
}
