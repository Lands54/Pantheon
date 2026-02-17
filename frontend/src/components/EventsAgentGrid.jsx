function eventAgent(item) {
  return item?.payload?.agent_id || item?.payload?.to_id || item?.agent_id || 'unknown'
}

function eventTitle(item) {
  const raw = item?.payload?.title || item?.payload?.reason || item?.event_type || 'event'
  return String(raw)
}

function eventTooltip(item) {
  const lines = [
    `id: ${item?.event_id || '-'}`,
    `domain: ${item?.domain || '-'}`,
    `type: ${item?.event_type || '-'}`,
    `state: ${item?.state || '-'}`,
    `agent: ${eventAgent(item)}`,
    `created: ${item?.created_at ? new Date(item.created_at * 1000).toLocaleString() : 'N/A'}`,
    `feeds_llm: ${item?.feeds_llm === true ? 'yes' : item?.feeds_llm === false ? 'no' : '-'}`,
  ]
  if (item?.description) lines.push(`desc: ${item.description}`)
  if (item?.error_message) lines.push(`error: ${item.error_message}`)
  return lines.join('\n')
}

export function EventsAgentGrid({ items = [] }) {
  const groups = {}
  for (const item of items) {
    const aid = eventAgent(item)
    if (!groups[aid]) groups[aid] = []
    groups[aid].push(item)
  }
  const agentIds = Object.keys(groups).sort()

  return (
    <div className="panel">
      <h3>Events by Agent</h3>
      <div className="agent-event-grid-wrap">
        {agentIds.length === 0 && <div className="dim">No events</div>}
        {agentIds.map((aid) => (
          <div className="agent-event-row" key={aid}>
            <div className="agent-event-label mono">{aid}</div>
            <div className="agent-event-cells">
              {groups[aid].map((ev) => (
                <div
                  key={ev.event_id}
                  className={`event-cell state-${String(ev.state || '').toLowerCase()}`}
                  title={eventTooltip(ev)}
                >
                  <div className="event-cell-title">{eventTitle(ev)}</div>
                  <div className="event-cell-meta mono">{ev.state || '-'}</div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
