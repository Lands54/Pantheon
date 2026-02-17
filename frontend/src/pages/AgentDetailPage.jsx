import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { getContextPreview, getContextReports, getLatestLlmContext, listEvents, listOutboxReceipts } from '../api/platformApi'

export function AgentDetailPage({ projectId, agentId }) {
  const [preview, setPreview] = useState(null)
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
      const [p, r, e, out, llm] = await Promise.all([
        getContextPreview(projectId, agentId),
        getContextReports(projectId, agentId, 20),
        listEvents({ project_id: projectId, agent_id: agentId, limit: 50 }),
        listOutboxReceipts(projectId, agentId, receiptStatus, 50),
        getLatestLlmContext(projectId, agentId),
      ])
      setPreview(p.preview || p)
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

  if (!agentId) {
    return <div className="panel">Pick an agent from Dashboard/Message Center first.</div>
  }

  return (
    <div className="stack-lg">
      {error && <div className="panel error-banner">{error}</div>}

      <div className="panel">
        <div className="row-between">
          <h3>Live Context - {agentId}</h3>
          <button className="ghost-btn" onClick={load}>Reload</button>
        </div>
        <pre className="json-block">{JSON.stringify(preview || {}, null, 2)}</pre>
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
