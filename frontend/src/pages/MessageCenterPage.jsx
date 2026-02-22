import { useEffect, useMemo, useState } from 'react'
import {
  gatewayCheckInbox,
  gatewayCheckOutbox,
  gatewaySendMessage,
  listEvents,
  submitInteractionMessage,
} from '../api/platformApi'
import { HUMAN_IDENTITY } from '../types/models'

export function MessageCenterPage({ projectId, agents = [], selectedAgentId, onPickAgent }) {
  const [mode, setMode] = useState('private')
  const [form, setForm] = useState({
    toId: selectedAgentId || '',
    title: 'frontend.message',
    content: '',
    msgType: 'confession',
    triggerPulse: true,
  })
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [privateInbox, setPrivateInbox] = useState([])
  const [privateOutbox, setPrivateOutbox] = useState([])
  const [loadingPrivate, setLoadingPrivate] = useState(false)
  const [matrixLoading, setMatrixLoading] = useState(false)
  const [matrixNodes, setMatrixNodes] = useState([])
  const [matrixCounts, setMatrixCounts] = useState({})

  const targetOptions = useMemo(() => agents.map((a) => a.agent_id), [agents])

  useEffect(() => {
    setForm((prev) => {
      const current = String(prev.toId || '')
      if (current && targetOptions.includes(current)) return prev
      const picked = (selectedAgentId && targetOptions.includes(selectedAgentId))
        ? selectedAgentId
        : (targetOptions[0] || '')
      return { ...prev, toId: picked }
    })
  }, [selectedAgentId, targetOptions])

  const refreshPrivateBox = async () => {
    setLoadingPrivate(true)
    setError('')
    try {
      const [inbox, outbox] = await Promise.all([
        gatewayCheckInbox(projectId, HUMAN_IDENTITY),
        gatewayCheckOutbox(projectId, HUMAN_IDENTITY, '', '', 100),
      ])
      setPrivateInbox(Array.isArray(inbox?.messages) ? inbox.messages : [])
      setPrivateOutbox(Array.isArray(outbox?.items) ? outbox.items : [])
    } catch (err) {
      setError(String(err.message || err))
    } finally {
      setLoadingPrivate(false)
    }
  }

  useEffect(() => {
    refreshPrivateBox()
    refreshMatrix()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

  const refreshMatrix = async () => {
    setMatrixLoading(true)
    setError('')
    try {
      const res = await listEvents({
        project_id: projectId,
        event_type: 'interaction.message.sent',
        limit: 2000,
      })
      const rows = Array.isArray(res?.items) ? res.items : []
      const counts = {}
      const nodeSet = new Set((agents || []).map((a) => String(a?.agent_id || '').trim()).filter(Boolean))
      nodeSet.add(HUMAN_IDENTITY)

      for (const row of rows) {
        const payload = row?.payload || {}
        const from = String(payload?.sender_id || '').trim()
        const to = String(payload?.to_id || '').trim()
        if (!from || !to) continue
        nodeSet.add(from)
        nodeSet.add(to)
        if (!counts[from]) counts[from] = {}
        counts[from][to] = (Number(counts[from][to]) || 0) + 1
      }
      setMatrixNodes(Array.from(nodeSet).sort())
      setMatrixCounts(counts)
    } catch (err) {
      setError(String(err.message || err))
    } finally {
      setMatrixLoading(false)
    }
  }

  const sendPrivate = async () => {
    setStatus('')
    setError('')
    try {
      if (!form.toId || !form.title || !form.content) {
        throw new Error('to_id, title, content are required')
      }
      await gatewaySendMessage(
        projectId,
        HUMAN_IDENTITY,
        form.toId,
        form.title,
        form.content,
        [],
      )
      setStatus('Private message sent.')
      setForm((x) => ({ ...x, content: '' }))
      onPickAgent?.(form.toId)
      await refreshPrivateBox()
    } catch (err) {
      setError(String(err.message || err))
    }
  }

  const send = async () => {
    setStatus('')
    setError('')
    try {
      if (!form.toId || !form.title || !form.content) {
        throw new Error('to_id, title, content are required')
      }
      await submitInteractionMessage({
        projectId,
        toId: form.toId,
        title: form.title,
        content: form.content,
        msgType: form.msgType,
        triggerPulse: form.triggerPulse,
        senderId: HUMAN_IDENTITY,
      })
      setStatus('Message event submitted.')
      setForm((x) => ({ ...x, content: '' }))
      onPickAgent?.(form.toId)
    } catch (err) {
      setError(String(err.message || err))
    }
  }

  return (
    <div className="stack-lg">
      <div className="panel">
        <h3>Human Private Mail</h3>
        <div className="identity-row">Identity: <span className="mono">{HUMAN_IDENTITY}</span></div>
        <div className="action-row" style={{ marginBottom: 12 }}>
          <button className={mode === 'private' ? 'primary-btn' : ''} onClick={() => setMode('private')}>Private Mail</button>
          <button className={mode === 'event' ? 'primary-btn' : ''} onClick={() => setMode('event')}>Interaction Event</button>
          <button className="ghost-btn" onClick={refreshPrivateBox} disabled={loadingPrivate}>Refresh Inbox/Outbox</button>
        </div>

        {mode === 'private' && (
          <>
            <div className="form-grid">
              <label>
                To Agent
                <select value={form.toId} onChange={(e) => setForm((x) => ({ ...x, toId: e.target.value }))}>
                  {!targetOptions.length && <option value="">(no agents)</option>}
                  {targetOptions.map((id) => <option key={id} value={id}>{id}</option>)}
                </select>
              </label>
              <label>
                Title
                <input value={form.title} onChange={(e) => setForm((x) => ({ ...x, title: e.target.value }))} />
              </label>
              <label className="full-width">
                Content
                <textarea rows={6} value={form.content} onChange={(e) => setForm((x) => ({ ...x, content: e.target.value }))} />
              </label>
            </div>
            <div className="action-row">
              <button className="primary-btn" onClick={sendPrivate}>Send Private Message</button>
            </div>
            <div className="top-gap" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="panel" style={{ margin: 0 }}>
                <h4>Inbox ({privateInbox.length})</h4>
                <div className="mono" style={{ maxHeight: 260, overflow: 'auto', whiteSpace: 'pre-wrap' }}>
                  {privateInbox.length === 0 && '(empty)'}
                  {privateInbox.map((m) => (
                    <div key={m.id} style={{ paddingBottom: 8, marginBottom: 8, borderBottom: '1px dashed #33415533' }}>
                      <div>[{m.status}] from={m.from} title={m.title}</div>
                      <div>{m.content}</div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="panel" style={{ margin: 0 }}>
                <h4>Outbox ({privateOutbox.length})</h4>
                <div className="mono" style={{ maxHeight: 260, overflow: 'auto', whiteSpace: 'pre-wrap' }}>
                  {privateOutbox.length === 0 && '(empty)'}
                  {privateOutbox.map((m) => (
                    <div key={m.id} style={{ paddingBottom: 8, marginBottom: 8, borderBottom: '1px dashed #33415533' }}>
                      <div>[{m.status}] to={m.to} title={m.title}</div>
                      <div>message_id={m.message_id}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      <div className="panel">
        <h3>Message Traffic Matrix</h3>
        <div className="muted" style={{ marginBottom: 8 }}>
          统计来源：interaction.message.sent（sender_id → to_id）
        </div>
        <div className="action-row" style={{ marginBottom: 12 }}>
          <button className="ghost-btn" onClick={refreshMatrix} disabled={matrixLoading}>
            {matrixLoading ? 'Refreshing...' : 'Refresh Matrix'}
          </button>
        </div>
        <div style={{ overflow: 'auto' }}>
          <table className="data-table" style={{ minWidth: 780 }}>
            <thead>
              <tr>
                <th>From \\ To</th>
                {matrixNodes.map((to) => (
                  <th key={`col-${to}`} className="mono">{to}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {matrixNodes.length === 0 && (
                <tr>
                  <td colSpan={2} className="muted">No message traffic yet.</td>
                </tr>
              )}
              {(() => {
                let maxCount = 0
                for (const from of matrixNodes) {
                  for (const to of matrixNodes) {
                    const v = Number(matrixCounts?.[from]?.[to] || 0)
                    if (v > maxCount) maxCount = v
                  }
                }
                return matrixNodes.map((from) => (
                  <tr key={`row-${from}`}>
                    <td className="mono">{from}</td>
                    {matrixNodes.map((to) => {
                      const value = Number(matrixCounts?.[from]?.[to] || 0)
                      const ratio = maxCount > 0 ? (value / maxCount) : 0
                      const bg = value > 0 ? `rgba(56, 189, 248, ${0.10 + ratio * 0.55})` : 'transparent'
                      return (
                        <td key={`${from}->${to}`} className="mono" style={{ background: bg }}>
                          {value}
                        </td>
                      )
                    })}
                  </tr>
                ))
              })()}
            </tbody>
          </table>
        </div>
      </div>

      {mode === 'event' && (
      <div className="panel">
        <h3>Send Message Event</h3>
        <div className="identity-row">Sender Identity: <span className="mono">{HUMAN_IDENTITY}</span></div>
        <div className="form-grid">
          <label>
            To Agent
            <select value={form.toId} onChange={(e) => setForm((x) => ({ ...x, toId: e.target.value }))}>
              {!targetOptions.length && <option value="">(no agents)</option>}
              {targetOptions.map((id) => <option key={id} value={id}>{id}</option>)}
            </select>
          </label>

          <label>
            Title
            <input value={form.title} onChange={(e) => setForm((x) => ({ ...x, title: e.target.value }))} />
          </label>

          <label>
            Message Type
            <input value={form.msgType} onChange={(e) => setForm((x) => ({ ...x, msgType: e.target.value }))} />
          </label>

          <label className="checkbox-row">
            <input type="checkbox" checked={form.triggerPulse} onChange={(e) => setForm((x) => ({ ...x, triggerPulse: e.target.checked }))} />
            Trigger Pulse
          </label>

          <label className="full-width">
            Content
            <textarea rows={8} value={form.content} onChange={(e) => setForm((x) => ({ ...x, content: e.target.value }))} />
          </label>
        </div>

        <div className="action-row">
          <button className="primary-btn" onClick={send}>Submit Interaction Event</button>
        </div>
      </div>
      )}

      {status && <div className="panel success-banner">{status}</div>}
      {error && <div className="panel error-banner">{error}</div>}
    </div>
  )
}
