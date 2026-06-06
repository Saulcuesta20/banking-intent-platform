import React, { useEffect, useMemo, useState } from 'react'
import { withBlockDefaults } from '@lowdefy/block-utils'
import {
  AssetCodeEditorView,
  baseFont,
  buttonStyle,
  colors,
  editorFor,
  sourceDocument,
} from '../shared/editor-components.js'

const h = React.createElement

function readQuery() {
  if (typeof window === 'undefined') return new URLSearchParams()
  return new URLSearchParams(window.location.search)
}

function normalizeEditorType(type) {
  const value = String(type || '').toLowerCase()
  if (value.includes('process')) return 'process'
  if (value.includes('rule')) return 'business_rule'
  if (value.includes('ontology')) return 'ontology'
  if (value.includes('entity')) return 'entity'
  if (value.includes('qa')) return 'qa'
  if (value.includes('tool')) return 'tool'
  if (value.includes('form')) return 'form'
  if (value.includes('menu') || value.includes('module')) return 'module'
  if (value.includes('document') || value.includes('config')) return 'configuration'
  if (value.includes('flow')) return 'flow'
  return ''
}

function noticeStyle(type) {
  return {
    border: `1px solid ${type === 'error' ? colors.red : colors.green}`,
    background: type === 'error' ? colors.redSoft : colors.greenSoft,
    color: type === 'error' ? colors.red : colors.green,
    borderRadius: 8,
    padding: '10px 12px',
    marginBottom: 12,
    fontSize: 13,
  }
}

function AssetEditorHostBlock({ blockId, classNames = {}, properties = {}, styles = {} }) {
  const query = useMemo(() => readQuery(), [])
  const api = properties.apiBaseUrl || 'http://127.0.0.1:8030'
  const actor = properties.actor || query.get('actor') || 'saul'
  const environment = properties.environment || query.get('environment') || 'dev'
  const assetId = properties.assetId || query.get('asset_id')
  const version = properties.version || query.get('version')
  const forcedType = normalizeEditorType(properties.editorType || query.get('editor_type'))
  const [selected, setSelected] = useState(null)
  const [document, setDocument] = useState(null)
  const [mode, setMode] = useState('visual')
  const [notice, setNotice] = useState(null)
  const [busy, setBusy] = useState(false)

  async function request(path, options) {
    const response = await fetch(`${api}${path}`, {
      headers: { 'Content-Type': 'application/json', ...(options?.headers || {}) },
      ...options,
    })
    const body = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(body.detail || `${response.status} ${response.statusText}`)
    return body
  }

  async function loadAsset() {
    if (!assetId) {
      setNotice({ type: 'error', text: 'No asset_id was provided to the Lowdefy editor.' })
      return
    }
    setBusy(true)
    setNotice(null)
    try {
      const versionParam = version ? `?version=${encodeURIComponent(version)}` : ''
      const detail = await request(`/catalog/assets/${encodeURIComponent(assetId)}${versionParam}`)
      setSelected(detail)
      setDocument(sourceDocument(detail))
      setMode('visual')
    } catch (error) {
      setNotice({ type: 'error', text: error instanceof Error ? error.message : String(error) })
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    void loadAsset()
  }, [api, assetId, version])

  async function validate() {
    if (!selected || !document) return null
    const result = await request('/catalog/assets/validate', {
      method: 'POST',
      body: JSON.stringify({
        document,
        expected_asset_id: selected.asset_id,
        expected_asset_type: selected.asset_type,
      }),
    })
    setNotice({
      type: 'success',
      text: `Schema valid. ${result.relation_count} relationships; stores: ${(result.stores || []).join(', ') || 'repository'}.`,
    })
    return result
  }

  async function saveNewVersion() {
    if (!selected || !document) return
    setBusy(true)
    setNotice(null)
    try {
      await validate()
      const result = await request(`/catalog/assets/${encodeURIComponent(selected.asset_id)}/versions`, {
        method: 'POST',
        body: JSON.stringify({ base_version: selected.version, actor, document }),
      })
      setNotice({
        type: 'success',
        text: `Created ${result.asset_set_id}@${result.version}. The AssetSet is ready for review.`,
      })
      const created = (result.members || []).find((item) => item.asset_id === selected.asset_id)
      if (created?.version) {
        const detail = await request(`/catalog/assets/${encodeURIComponent(created.asset_id)}?version=${encodeURIComponent(created.version)}`)
        setSelected(detail)
        setDocument(sourceDocument(detail))
      }
    } catch (error) {
      setNotice({ type: 'error', text: error instanceof Error ? error.message : String(error) })
    } finally {
      setBusy(false)
    }
  }

  const editorDocument = forcedType && document ? { ...document, asset_type: forcedType } : document
  const Editor = editorFor(editorDocument)

  return h(
    'div',
    {
      id: blockId,
      className: classNames.element,
      style: {
        ...styles.element,
        minHeight: 560,
        fontFamily: baseFont,
        color: colors.ink,
        background: '#fff',
        boxSizing: 'border-box',
      },
    },
    h('style', null, `
      #${blockId} button:disabled { opacity: .55; cursor: not-allowed; }
      #${blockId} .asset-host-toolbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        flex-wrap: wrap;
        padding-bottom: 12px;
      }
      #${blockId} .asset-host-actions {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
      }
    `),
    notice ? h('div', { style: noticeStyle(notice.type) }, notice.text) : null,
    selected && document
      ? h(
          React.Fragment,
          null,
          h(
            'div',
            { className: 'asset-host-toolbar' },
            h(
              'div',
              null,
              h('div', { style: { color: colors.muted, fontSize: 11, fontWeight: 800, textTransform: 'uppercase' } }, 'Lowdefy Dynamic Editor'),
              h('strong', { style: { fontSize: 14 } }, `${selected.asset_type} · ${selected.asset_id}`),
            ),
            h(
              'div',
              { className: 'asset-host-actions' },
              h('button', { type: 'button', style: buttonStyle(mode === 'visual'), onClick: () => setMode('visual') }, 'Structured Editor'),
              h('button', { type: 'button', style: buttonStyle(mode === 'source'), onClick: () => setMode('source') }, 'Raw YAML'),
              h('button', { type: 'button', disabled: busy, style: buttonStyle(), onClick: validate }, 'Validate'),
              h('button', { type: 'button', disabled: busy, style: buttonStyle(true), onClick: saveNewVersion }, busy ? 'Working...' : 'Save new version'),
            ),
          ),
          mode === 'source'
            ? h(AssetCodeEditorView, { value: document, onChange: setDocument })
            : h(Editor, { value: editorDocument, onChange: setDocument }),
        )
      : h(
          'div',
          {
            style: {
              minHeight: 520,
              display: 'grid',
              placeItems: 'center',
              border: `1px solid ${colors.line}`,
              borderRadius: 8,
              color: colors.muted,
              background: colors.canvas,
            },
          },
          busy ? 'Loading asset editor...' : 'Select an asset in the launcher to open the editor.',
        ),
  )
}

export default withBlockDefaults(AssetEditorHostBlock)
