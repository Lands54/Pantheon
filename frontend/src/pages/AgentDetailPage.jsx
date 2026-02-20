import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import {
  getContextPreview,
  getContextReports,
  getLatestLlmContext,
  getContextSnapshot,
  getContextSnapshotCompressions,
  getContextSnapshotDerived,
  listEvents,
  listOutboxReceipts,
} from '../api/platformApi'

export function AgentDetailPage({ projectId, agentId }) {
  const [preview, setPreview] = useState(null)
  const [snapshotMeta, setSnapshotMeta] = useState({ available: false, base_intent_seq: 0, token_estimate: 0, snapshot_id: '' })
  const [snapshotCards, setSnapshotCards] = useState([])
  const [snapshotCursor, setSnapshotCursor] = useState(0)
  const [snapshotCompressLogs, setSnapshotCompressLogs] = useState([])
  const [snapshotDerivedLogs, setSnapshotDerivedLogs] = useState([])
  const [reports, setReports] = useState([])
  const [events, setEvents] = useState([])
  const [receipts, setReceipts] = useState([])
  const [llmTrace, setLlmTrace] = useState(null)
  const [receiptStatus, setReceiptStatus] = useState('')
  const [error, setError] = useState('')

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
      const [p, r, e, out, llm, snap, comp, derived] = await Promise.all([
        getContextPreview(projectId, agentId),
        getContextReports(projectId, agentId, 20),
        listEvents({ project_id: projectId, agent_id: agentId, limit: 50 }),
        listOutboxReceipts(projectId, agentId, receiptStatus, 50),
        getLatestLlmContext(projectId, agentId),
        getContextSnapshot(projectId, agentId, 0),
        getContextSnapshotCompressions(projectId, agentId, 20),
        getContextSnapshotDerived(projectId, agentId, 50),
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
  }, [projectId, agentId, receiptStatus])

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
          <h3>Janus Snapshot (Incremental)</h3>
          <div className="mono dim">
            base_intent_seq={snapshotMeta.base_intent_seq} | cards={snapshotCards.length} | tokens~{snapshotMeta.token_estimate}
          </div>
        </div>
        {!snapshotMeta.available && <div className="dim">No snapshot yet. Trigger at least one LLM pulse.</div>}
        {!!snapshotMeta.available && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>card_id</th>
                  <th>kind</th>
                  <th>priority</th>
                  <th>source_seq</th>
                  <th>text</th>
                </tr>
              </thead>
              <tbody>
                {snapshotCards.map((c) => (
                  <tr key={c.card_id}>
                    <td className="mono">{c.card_id}</td>
                    <td>{c.kind}</td>
                    <td>{c.priority}</td>
                    <td>{c.source_intent_seq_max}</td>
                    <td className="mono">{String(c.text || '')}</td>
                  </tr>
                ))}
                {!snapshotCards.length && (
                  <tr><td colSpan={5}>No cards</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
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
            {(llmTrace.request_messages || []).map((msg, idx) => (
              <div key={`llm-msg-${idx}`} className="panel">
                <div className="mono dim">[{idx + 1}] {msg?.type || 'Message'} {msg?.name ? `(${msg.name})` : ''}</div>
                <ReactMarkdown>{renderMessageContent(msg)}</ReactMarkdown>
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
        <h3>Recent Events (Agent)</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Type</th>
                <th>State</th>
                <th>Created</th>
                <th>Error</th>
              </tr>
            </thead>
            <tbody>
              {events.map((row) => (
                <tr key={row.event_id}>
                  <td>{row.event_type}</td>
                  <td>{row.state}</td>
                  <td>{new Date((row.created_at || 0) * 1000).toLocaleString()}</td>
                  <td className="mono error-cell">{row.error_message || '-'}</td>
                </tr>
              ))}
              {!events.length && <tr><td colSpan={4}>No events</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
