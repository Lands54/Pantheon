import { useEffect, useState } from 'react'
import { ackEvent, getEventCatalog, listEvents, retryEvent } from '../api/platformApi'
import { EventsAgentGrid } from '../components/EventsAgentGrid'
import { EventsTable } from '../components/EventsTable'
import { usePolling } from '../hooks/usePolling'
import { useEventsStream } from '../hooks/useEventsStream'

const INITIAL_FILTER = {
  domain: '',
  event_type: '',
  state: '',
  agent_id: '',
  limit: 50,
}

export function EventsPage({ projectId }) {
  const [filters, setFilters] = useState(INITIAL_FILTER)
  const [hideDone, setHideDone] = useState(true)
  const [hideFeedsLlmFalse, setHideFeedsLlmFalse] = useState(false)
  const [error, setError] = useState('')
  const [catalogByType, setCatalogByType] = useState({})
  const stream = useEventsStream(projectId, filters)

  const enrich = (row) => {
    const meta = catalogByType[String(row?.event_type || '')] || {}
    return {
      ...row,
      feeds_llm: meta.feeds_llm,
      description: meta.description || '',
      event_title: meta.title || '',
    }
  }

  const visibleItems = (stream.items || [])
    .map(enrich)
    .filter((x) => !(hideDone && String(x?.state || '').toLowerCase() === 'done'))
    .filter((x) => !(hideFeedsLlmFalse && x?.feeds_llm === false))

  const load = async () => {
    try {
      const data = await listEvents({ project_id: projectId, ...filters })
      stream.setItems(data.items || [])
      setError('')
    } catch (err) {
      setError(String(err.message || err))
    }
  }

  useEffect(() => {
    getEventCatalog(projectId)
      .then((res) => {
        const mp = {}
        for (const it of res.items || []) mp[String(it.event_type || '')] = it
        setCatalogByType(mp)
      })
      .catch(() => setCatalogByType({}))
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

  usePolling(async () => {
    if (!stream.connected) await load()
  }, 12000, [projectId, JSON.stringify(filters), stream.connected])

  const onRetry = async (eventId) => {
    await retryEvent(projectId, eventId)
    await load()
  }

  const onAck = async (eventId) => {
    await ackEvent(projectId, eventId)
    await load()
  }

  return (
    <div className="stack-lg">
      <div className="panel">
        <h3>Filters {stream.connected ? '(Live Stream)' : '(Polling Fallback)'}</h3>
        <div className="filter-grid">
          <input placeholder="domain" value={filters.domain} onChange={(e) => setFilters((x) => ({ ...x, domain: e.target.value }))} />
          <input placeholder="event_type" value={filters.event_type} onChange={(e) => setFilters((x) => ({ ...x, event_type: e.target.value }))} />
          <input placeholder="state" value={filters.state} onChange={(e) => setFilters((x) => ({ ...x, state: e.target.value }))} />
          <input placeholder="agent_id" value={filters.agent_id} onChange={(e) => setFilters((x) => ({ ...x, agent_id: e.target.value }))} />
          <input type="number" placeholder="limit" value={filters.limit} onChange={(e) => setFilters((x) => ({ ...x, limit: Math.max(1, Number(e.target.value) || 50) }))} />
          <button className="ghost-btn" onClick={load}>Apply</button>
        </div>
        <label className="checkbox-row top-gap">
          <input type="checkbox" checked={hideDone} onChange={(e) => setHideDone(e.target.checked)} />
          Hide done
        </label>
        <label className="checkbox-row">
          <input type="checkbox" checked={hideFeedsLlmFalse} onChange={(e) => setHideFeedsLlmFalse(e.target.checked)} />
          Hide feeds_llm=false
        </label>
      </div>

      {error && <div className="panel error-banner">{error}</div>}
      <EventsAgentGrid items={visibleItems} />
      <EventsTable items={visibleItems} onRetry={onRetry} onAck={onAck} />
    </div>
  )
}
