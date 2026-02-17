import { useEffect, useMemo, useState } from 'react'
import { submitInteractionMessage } from '../api/platformApi'
import { HUMAN_IDENTITY } from '../types/models'

export function MessageCenterPage({ projectId, agents = [], selectedAgentId, onPickAgent }) {
  const [form, setForm] = useState({
    toId: selectedAgentId || '',
    title: 'frontend.message',
    content: '',
    msgType: 'confession',
    triggerPulse: true,
  })
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')

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

      {status && <div className="panel success-banner">{status}</div>}
      {error && <div className="panel error-banner">{error}</div>}
    </div>
  )
}
