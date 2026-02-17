function formatTs(ts) {
  if (!ts) return 'N/A'
  const d = new Date(ts * 1000)
  return d.toLocaleString()
}

export function AgentStatusTable({ rows = [], onPickAgent }) {
  return (
    <div className="panel">
      <h3>Agent Status</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Agent</th>
              <th>Status</th>
              <th>Last Pulse</th>
              <th>Queued</th>
              <th>Inbox Pending</th>
              <th>Error</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.agent_id} onClick={() => onPickAgent?.(row.agent_id)}>
                <td>{row.agent_id}</td>
                <td>{row.status}</td>
                <td>{formatTs(row.last_pulse_at)}</td>
                <td>{row.queued_pulse_events ?? 0}</td>
                <td>{row.has_pending_inbox ? 'Yes' : 'No'}</td>
                <td className="mono error-cell">{row.last_error || '-'}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={6}>No agent status available</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
