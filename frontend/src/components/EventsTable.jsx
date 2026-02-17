function fmt(ts) {
  if (!ts) return 'N/A'
  return new Date(ts * 1000).toLocaleString()
}

export function EventsTable({ items = [], onRetry, onAck }) {
  return (
    <div className="panel">
      <h3>Events</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Domain</th>
              <th>Type</th>
              <th>State</th>
              <th>feeds_llm</th>
              <th>Agent</th>
              <th>Created</th>
              <th>Description</th>
              <th>Error</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const agent = item?.payload?.agent_id || item?.payload?.to_id || '-'
              const retryable = item.state === 'failed' || item.state === 'dead'
              return (
                <tr key={item.event_id}>
                  <td className="mono">{item.event_id.slice(0, 10)}...</td>
                  <td>{item.domain}</td>
                  <td>{item.event_type}</td>
                  <td>{item.state}</td>
                  <td>
                    {item.feeds_llm === true ? 'yes' : item.feeds_llm === false ? 'no' : '-'}
                  </td>
                  <td>{agent}</td>
                  <td>{fmt(item.created_at)}</td>
                  <td>{item.description || '-'}</td>
                  <td className="mono error-cell">{item.error_message || '-'}</td>
                  <td>
                    <div className="action-row">
                      <button className="ghost-btn" disabled={!retryable} onClick={() => onRetry?.(item.event_id)}>
                        Retry
                      </button>
                      <button className="ghost-btn" onClick={() => onAck?.(item.event_id)}>
                        Ack
                      </button>
                    </div>
                  </td>
                </tr>
              )
            })}
            {items.length === 0 && (
              <tr>
                <td colSpan={10}>No events</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
