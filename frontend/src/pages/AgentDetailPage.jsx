import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import {
  getContextPreview,
  getContextReports,
  getLatestLlmContext,
  getContextSnapshot,
  getContextSnapshotCompressions,
  getContextSnapshotDerived,
  getContextPulses,
  listEvents,
  listOutboxReceipts,
} from '../api/platformApi'

function extractXmlCandidate(text) {
  const raw = String(text || '')
  const trimmed = raw.trim()
  if (!trimmed) return ''
  const fenced = trimmed.match(/^```xml\s*([\s\S]*?)\s*```$/i)
  if (fenced && fenced[1]) return fenced[1].trim()
  return trimmed
}

function isLikelyXml(text) {
  const s = extractXmlCandidate(text)
  if (!s) return false
  if (s.startsWith('<?xml')) return true
  if (/<\s*context(\s|>)/i.test(s)) return true
  if (/<\s*pulse(\s|>)/i.test(s)) return true
  return false
}

function parseXml(xmlText) {
  const parser = new DOMParser()
  const doc = parser.parseFromString(String(xmlText || ''), 'application/xml')
  const err = doc.querySelector('parsererror')
  if (err) {
    return { ok: false, error: err.textContent || 'Invalid XML', doc: null }
  }
  return { ok: true, error: '', doc }
}

function escapeXmlText(s) {
  return String(s || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&apos;')
}

function formatXmlNode(node, indent = '') {
  if (!node) return ''
  if (node.nodeType === Node.TEXT_NODE) {
    const txt = (node.nodeValue || '').trim()
    if (!txt) return ''
    return `${indent}${escapeXmlText(txt)}\n`
  }
  if (node.nodeType !== Node.ELEMENT_NODE) return ''

  const tag = node.tagName
  const attrs = Array.from(node.attributes || [])
    .map((a) => `${a.name}="${escapeXmlText(a.value)}"`)
    .join(' ')
  const head = attrs ? `<${tag} ${attrs}>` : `<${tag}>`
  const children = Array.from(node.childNodes || [])
  const hasElementChild = children.some((c) => c.nodeType === Node.ELEMENT_NODE)
  const textOnly = children.every((c) => c.nodeType === Node.TEXT_NODE) && children.length > 0

  if (!children.length) {
    return `${indent}${head}</${tag}>\n`
  }
  if (textOnly) {
    const txt = children.map((c) => (c.nodeValue || '').trim()).join('').trim()
    return `${indent}${head}${escapeXmlText(txt)}</${tag}>\n`
  }
  let out = `${indent}${head}\n`
  for (const child of children) {
    out += formatXmlNode(child, `${indent}  `)
  }
  out += `${indent}</${tag}>\n`
  if (!hasElementChild) return out
  return out
}

function formatXml(xmlText) {
  const parsed = parseXml(xmlText)
  if (!parsed.ok || !parsed.doc?.documentElement) {
    return { ok: false, text: String(xmlText || ''), error: parsed.error || 'Invalid XML', doc: null }
  }
  const header = "<?xml version='1.0' encoding='utf-8'?>\n"
  const body = formatXmlNode(parsed.doc.documentElement, '')
  return { ok: true, text: `${header}${body}`.trimEnd(), error: '', doc: parsed.doc }
}

function XmlTreeNode({ node }) {
  if (!node || node.nodeType !== Node.ELEMENT_NODE) return null
  const attrs = Array.from(node.attributes || [])
  const children = Array.from(node.children || [])
  const text = (node.textContent || '').trim()
  const hasChildren = children.length > 0

  return (
    <details className="xml-tree-node" open>
      <summary className="xml-tree-summary">
        <span className="mono">&lt;{node.tagName}&gt;</span>
        {!!attrs.length && (
          <span className="mono dim xml-attrs">
            {' '}
            {attrs.map((a) => `${a.name}="${a.value}"`).join(' ')}
          </span>
        )}
      </summary>
      {!hasChildren && !!text && <pre className="xml-tree-text mono">{text}</pre>}
      {!!hasChildren && (
        <div className="xml-tree-children">
          {children.map((c, i) => (
            <XmlTreeNode key={`${c.tagName}-${i}`} node={c} />
          ))}
        </div>
      )}
    </details>
  )
}

function XmlContextViewer({ xmlText }) {
  const rawXml = extractXmlCandidate(xmlText)
  const formatted = formatXml(rawXml)
  return (
    <div className="stack-sm">
      {!formatted.ok && <div className="warn">XML parse failed: {formatted.error}</div>}
      <div className="row-between">
        <div className="mono dim">XML Context</div>
        <button
          className="ghost-btn"
          onClick={() => navigator.clipboard?.writeText(String(rawXml || ''))}
          title="Copy raw XML"
        >
          Copy Raw
        </button>
      </div>
      <pre className="xml-block mono">{formatted.text}</pre>
      {formatted.ok && formatted.doc?.documentElement && (
        <details className="xml-tree-wrap">
          <summary>Tree View</summary>
          <div className="top-gap">
            <XmlTreeNode node={formatted.doc.documentElement} />
          </div>
        </details>
      )}
    </div>
  )
}

export function AgentDetailPage({ projectId, agentId }) {
  const [preview, setPreview] = useState(null)
  const [snapshotMeta, setSnapshotMeta] = useState({ available: false, base_intent_seq: 0, token_estimate: 0, snapshot_id: '' })
  const [snapshotCards, setSnapshotCards] = useState([])
  const [snapshotCursor, setSnapshotCursor] = useState(0)
  const [snapshotCompressLogs, setSnapshotCompressLogs] = useState([])
  const [snapshotDerivedLogs, setSnapshotDerivedLogs] = useState([])
  const [pulseRows, setPulseRows] = useState([])
  const [pulseErrors, setPulseErrors] = useState([])
  const [intentRows, setIntentRows] = useState([])
  const [selectedPulseId, setSelectedPulseId] = useState('')
  const [reports, setReports] = useState([])
  const [events, setEvents] = useState([])
  const [receipts, setReceipts] = useState([])
  const [llmTrace, setLlmTrace] = useState(null)
  const [receiptStatus, setReceiptStatus] = useState('')
  const [eventDomain, setEventDomain] = useState('')
  const [eventType, setEventType] = useState('')
  const [eventState, setEventState] = useState('')
  const [eventLimit, setEventLimit] = useState(100)
  const [error, setError] = useState('')
  const [forceXmlView, setForceXmlView] = useState(false)

  const renderMessageContent = (msg) => {
    const raw = msg?.content
    if (raw === null || raw === undefined) return ''
    if (typeof raw === 'string') return raw
    if (Array.isArray(raw)) {
      return raw
        .map((x) => {
          if (typeof x === 'string') return x
          if (x && typeof x === 'object') {
            if (typeof x.text === 'string') return x.text
            if (typeof x.content === 'string') return x.content
            return JSON.stringify(x, null, 2)
          }
          return String(x)
        })
        .join('\n')
    }
    if (typeof raw === 'object') return JSON.stringify(raw, null, 2)
    return String(raw)
  }

  const load = async () => {
    if (!agentId) return
    try {
      const [p, r, e, out, llm, snap, comp, derived, pulses] = await Promise.all([
        getContextPreview(projectId, agentId),
        getContextReports(projectId, agentId, 20),
        listEvents({
          project_id: projectId,
          agent_id: agentId,
          domain: eventDomain,
          event_type: eventType,
          state: eventState,
          limit: Number(eventLimit || 100),
        }),
        listOutboxReceipts(projectId, agentId, receiptStatus, 50),
        getLatestLlmContext(projectId, agentId),
        getContextSnapshot(projectId, agentId, 0),
        getContextSnapshotCompressions(projectId, agentId, 20),
        getContextSnapshotDerived(projectId, agentId, 50),
        getContextPulses(projectId, agentId, 0, 500),
      ])
      setPreview(p.preview || p)
      setSnapshotMeta({
        available: !!snap.available,
        base_intent_seq: Number(snap.base_intent_seq || 0),
        token_estimate: Number(snap.token_estimate || 0),
        snapshot_id: snap.snapshot_id || '',
      })
      setSnapshotCards(Array.isArray(snap.upsert_cards) ? snap.upsert_cards : [])
      setSnapshotCursor(Number(snap.base_intent_seq || 0))
      setSnapshotCompressLogs(Array.isArray(comp.items) ? comp.items : [])
      setSnapshotDerivedLogs(Array.isArray(derived.items) ? derived.items : [])
      setPulseRows(Array.isArray(pulses.pulses) ? pulses.pulses : [])
      setPulseErrors(Array.isArray(pulses.errors) ? pulses.errors : [])
      setIntentRows(Array.isArray(pulses.intents) ? pulses.intents : [])
      setReports(r.reports || [])
      setEvents(e.items || [])
      setReceipts(out.items || [])
      setLlmTrace(llm.trace || null)
      setError('')
    } catch (err) {
      setError(String(err.message || err))
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, agentId, receiptStatus, eventDomain, eventType, eventState, eventLimit])

  useEffect(() => {
    if (!projectId || !agentId) return undefined
    const timer = setInterval(async () => {
      try {
        const delta = await getContextSnapshot(projectId, agentId, snapshotCursor)
        if (!delta || !delta.available) return
        const upserts = Array.isArray(delta.upsert_cards) ? delta.upsert_cards : []
        const removes = new Set(Array.isArray(delta.remove_card_ids) ? delta.remove_card_ids.map((x) => `${x}`) : [])
        setSnapshotCards((prev) => {
          const map = new Map()
          ;(Array.isArray(prev) ? prev : []).forEach((c) => {
            const id = `${c?.card_id || ''}`
            if (!id || removes.has(id)) return
            map.set(id, c)
          })
          upserts.forEach((c) => {
            const id = `${c?.card_id || ''}`
            if (!id) return
            map.set(id, c)
          })
          return Array.from(map.values()).sort((a, b) => {
            const pa = Number(a?.priority || 0)
            const pb = Number(b?.priority || 0)
            if (pa !== pb) return pb - pa
            const sa = Number(a?.source_intent_seq_max || 0)
            const sb = Number(b?.source_intent_seq_max || 0)
            return sb - sa
          })
        })
        const nextSeq = Number(delta.base_intent_seq || 0)
        if (nextSeq > snapshotCursor) setSnapshotCursor(nextSeq)
        setSnapshotMeta({
          available: !!delta.available,
          base_intent_seq: Number(delta.base_intent_seq || 0),
          token_estimate: Number(delta.token_estimate || 0),
          snapshot_id: delta.snapshot_id || '',
        })
        const comp = await getContextSnapshotCompressions(projectId, agentId, 20)
        setSnapshotCompressLogs(Array.isArray(comp.items) ? comp.items : [])
        const derived = await getContextSnapshotDerived(projectId, agentId, 50)
        setSnapshotDerivedLogs(Array.isArray(derived.items) ? derived.items : [])
        // Keep pulse ledger view stable: always refresh from dedicated pulse API
        // instead of replacing with snapshot delta window.
        const pulsesLive = await getContextPulses(projectId, agentId, 0, 500)
        setPulseRows(Array.isArray(pulsesLive.pulses) ? pulsesLive.pulses : [])
        setPulseErrors(Array.isArray(pulsesLive.errors) ? pulsesLive.errors : [])
        setIntentRows(Array.isArray(pulsesLive.intents) ? pulsesLive.intents : [])
      } catch (e) {
        // ignore polling errors; full reload path still available
      }
    }, 2000)
    return () => clearInterval(timer)
  }, [projectId, agentId, snapshotCursor])

  if (!agentId) {
    return <div className="panel">Pick an agent from Dashboard/Message Center first.</div>
  }

  return (
    <div className="stack-lg">
      {error && <div className="panel error-banner">{error}</div>}

      <div className="panel">
        <div className="row-between">
          <h3>Card Context Feed - {agentId}</h3>
          <button className="ghost-btn" onClick={load}>Reload</button>
        </div>
        <pre className="json-block">{JSON.stringify(preview || {}, null, 2)}</pre>
      </div>

      <div className="panel">
        <div className="row-between">
          <h3>Pulse + Intent 联动视图</h3>
          <div className="mono dim">
            base_seq={snapshotMeta.base_intent_seq} | pulses={pulseRows.length} | intents={intentRows.length}
          </div>
        </div>
        {!!pulseErrors.length && (
          <div className="warn">
            {pulseErrors.map((x, i) => <div key={`pe-${i}`} className="mono">{String(x)}</div>)}
          </div>
        )}
        <div className="action-row top-gap">
          <div className="mono dim">Pulse 过滤:</div>
          <select value={selectedPulseId} onChange={(e) => setSelectedPulseId(e.target.value)}>
            <option value="">(全部)</option>
            {pulseRows.map((p) => (
              <option key={`pf-${p.pulse_id}`} value={p.pulse_id}>{p.pulse_id}</option>
            ))}
          </select>
          <button className="ghost-btn" onClick={() => setSelectedPulseId('')}>清除过滤</button>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }} className="top-gap">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>pulse_id</th>
                  <th>trigger</th>
                  <th>llm</th>
                  <th>tools</th>
                  <th>finish</th>
                </tr>
              </thead>
              <tbody>
                {pulseRows.map((p) => {
                  const active = selectedPulseId && selectedPulseId === p.pulse_id
                  return (
                    <tr
                      key={p.pulse_id}
                      style={{ background: active ? 'rgba(80,120,240,0.08)' : 'transparent', cursor: 'pointer' }}
                      onClick={() => setSelectedPulseId((x) => (x === p.pulse_id ? '' : p.pulse_id))}
                    >
                      <td className="mono">{p.pulse_id}</td>
                      <td className="mono">{(p.triggers || []).length}</td>
                      <td className="mono">{(p.llm || []).length}</td>
                      <td className="mono">{(p.tools || []).length}</td>
                      <td className="mono">{p.finish ? 'yes' : 'no'}</td>
                    </tr>
                  )
                })}
                {!pulseRows.length && (
                  <tr><td colSpan={5}>No pulse records</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>intent_seq</th>
                  <th>pulse_id</th>
                  <th>intent_key</th>
                  <th>fallback_text</th>
                </tr>
              </thead>
              <tbody>
                {(intentRows || [])
                  .filter((x) => !selectedPulseId || String(x?.pulse_id || '') === selectedPulseId)
                  .slice()
                  .sort((a, b) => Number(a?.intent_seq || 0) - Number(b?.intent_seq || 0))
                  .map((x) => (
                    <tr key={`i-${x.intent_seq}-${x.intent_id || ''}`}>
                      <td className="mono">{x.intent_seq}</td>
                      <td className="mono">{x.pulse_id || '-'}</td>
                      <td className="mono">{x.intent_key || '-'}</td>
                      <td>{x.fallback_text || '-'}</td>
                    </tr>
                  ))}
                {!intentRows.length && (
                  <tr><td colSpan={4}>No intent records</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="panel">
        <h3>Janus Compression Records</h3>
        {!snapshotCompressLogs.length && <div className="dim">No compression records yet.</div>}
        {!!snapshotCompressLogs.length && (
          <div className="log-list">
            {snapshotCompressLogs.slice().reverse().map((r, idx) => (
              <div key={`cmp-${idx}`} className="log-row">
                <span className="mono">{new Date((r.timestamp || 0) * 1000).toLocaleString()}</span>
                <span>snapshot={r.snapshot_id || '-'}</span>
                <span className="mono">tokens {r.before_tokens || 0} {"->"} {r.after_tokens || 0}</span>
                <span>derived={r.derived_count || 0}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Janus Derived Card Ledger</h3>
        {!snapshotDerivedLogs.length && <div className="dim">No derived card records yet.</div>}
        {!!snapshotDerivedLogs.length && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>time</th>
                  <th>snapshot</th>
                  <th>derived_card</th>
                  <th>from</th>
                  <th>supersedes</th>
                </tr>
              </thead>
              <tbody>
                {snapshotDerivedLogs.slice().reverse().map((r, idx) => {
                  const d = r.derived_card || {}
                  return (
                    <tr key={`d-${idx}`}>
                      <td className="mono">{new Date((r.timestamp || 0) * 1000).toLocaleString()}</td>
                      <td className="mono">{r.snapshot_id || '-'}</td>
                      <td className="mono">{d.card_id || '-'}</td>
                      <td className="mono">{Array.isArray(d.derived_from_card_ids) ? d.derived_from_card_ids.length : 0}</td>
                      <td className="mono">{Array.isArray(d.supersedes_card_ids) ? d.supersedes_card_ids.length : 0}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Latest LLM Full Context (Markdown)</h3>
        {!llmTrace && <div className="dim">No LLM trace yet (ensure debug.llm_trace=true and run at least one LLM call).</div>}
        {!!llmTrace && (
          <div className="stack-md">
            <div className="mono dim">ts: {new Date((llmTrace.ts || 0) * 1000).toLocaleString()} | mode: {llmTrace.mode || '-'} | model: {llmTrace.model || '-'}</div>
            <label className="inline-row mono dim">
              <input type="checkbox" checked={forceXmlView} onChange={(e) => setForceXmlView(!!e.target.checked)} />
              Force XML Viewer
            </label>
            {(llmTrace.request_messages || []).map((msg, idx) => (
              <div key={`llm-msg-${idx}`} className="panel">
                <div className="mono dim">[{idx + 1}] {msg?.type || 'Message'} {msg?.name ? `(${msg.name})` : ''}</div>
                {(forceXmlView || isLikelyXml(renderMessageContent(msg))) ? (
                  <XmlContextViewer xmlText={renderMessageContent(msg)} />
                ) : (
                  <ReactMarkdown>{renderMessageContent(msg)}</ReactMarkdown>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Context Reports</h3>
        <div className="log-list">
          {reports.map((item, idx) => (
            <div key={idx} className="log-row">
              <span className="mono">{new Date((item.timestamp || 0) * 1000).toLocaleString()}</span>
              <span>{item.strategy_used || item.mode || 'report'}</span>
              <span className="mono dim">{JSON.stringify(item.preview || {}).slice(0, 160)}</span>
            </div>
          ))}
          {!reports.length && <div className="dim">No reports yet</div>}
        </div>
      </div>

      <div className="panel">
        <div className="row-between">
          <h3>Inbox/Outbox Receipts</h3>
          <div className="action-row">
            <input placeholder="status filter" value={receiptStatus} onChange={(e) => setReceiptStatus(e.target.value)} />
            <button className="ghost-btn" onClick={load}>Apply</button>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>To</th>
                <th>Status</th>
                <th>Title</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {receipts.map((row) => (
                <tr key={row.receipt_id}>
                  <td>{row.to_agent_id}</td>
                  <td>{row.status}</td>
                  <td>{row.title || '-'}</td>
                  <td>{new Date((row.updated_at || row.created_at || 0) * 1000).toLocaleString()}</td>
                </tr>
              ))}
              {!receipts.length && (
                <tr><td colSpan={4}>No receipts</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel">
        <div className="row-between">
          <h3>Recent Events (Agent)</h3>
          <div className="action-row">
            <input
              placeholder="domain (e.g. iris/interaction)"
              value={eventDomain}
              onChange={(e) => setEventDomain(e.target.value)}
            />
            <input
              placeholder="event_type (e.g. mail_event)"
              value={eventType}
              onChange={(e) => setEventType(e.target.value)}
            />
            <input
              placeholder="state (queued/done/dead)"
              value={eventState}
              onChange={(e) => setEventState(e.target.value)}
            />
            <input
              type="number"
              min="1"
              max="1000"
              value={eventLimit}
              onChange={(e) => setEventLimit(Math.max(1, Math.min(1000, Number(e.target.value || 100))))}
              style={{ width: 96 }}
            />
            <button
              className="ghost-btn"
              onClick={() => {
                setEventDomain('iris')
                setEventType('mail_event')
                setEventState('')
              }}
            >
              Only Mail
            </button>
            <button
              className="ghost-btn"
              onClick={() => {
                setEventDomain('')
                setEventType('')
                setEventState('')
                setEventLimit(100)
              }}
            >
              Reset
            </button>
            <button className="ghost-btn" onClick={load}>Apply</button>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Domain</th>
                <th>Type</th>
                <th>State</th>
                <th>Created</th>
                <th>Error</th>
              </tr>
            </thead>
            <tbody>
              {events.map((row) => (
                <tr key={row.event_id}>
                  <td>{row.domain || '-'}</td>
                  <td>{row.event_type}</td>
                  <td>{row.state}</td>
                  <td>{new Date((row.created_at || 0) * 1000).toLocaleString()}</td>
                  <td className="mono error-cell">{row.error_message || '-'}</td>
                </tr>
              ))}
              {!events.length && <tr><td colSpan={5}>No events</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
