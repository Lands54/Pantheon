import { useEffect, useMemo, useState } from 'react'
import {
  gatewayCheckInbox,
  gatewayCheckOutbox,
  gatewaySendMessage,
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

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
