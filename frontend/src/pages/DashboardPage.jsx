import { Activity, Inbox, Orbit, RadioTower, Sparkles } from 'lucide-react'
import { AgentStatusTable } from '../components/AgentStatusTable'
import { useEventsStream } from '../hooks/useEventsStream'
import { useHermesStream } from '../hooks/useHermesStream'

function formatTs(ts) {
  if (!ts) return '暂无'
  return new Date(Number(ts || 0) * 1000).toLocaleString()
}

export function DashboardPage({
  projectId,
  agentRows = [],
  selectedAgentId = '',
  onPickAgent,
  currentProjectConfig = {},
  isRunning = false,
}) {
  const hermes = useHermesStream(projectId)
  const events = useEventsStream(projectId, { limit: 18 })
  const selectedAgent = agentRows.find((item) => item.agent_id === selectedAgentId) || agentRows[0] || null
  const activeCount = agentRows.filter((item) => item.active).length
  const pendingInbox = agentRows.filter((item) => item.has_pending_inbox).length
  const queued = agentRows.reduce((sum, item) => sum + Number(item.queued_pulse_events || 0), 0)
  const runningCount = agentRows.filter((item) => String(item.worker_state || '').toLowerCase() === 'running').length
  const nodes = Object.keys(hermes.nodes || {}).length
  const edges = Object.keys(hermes.edges || {}).length

  return (
    <div className="stack-lg">
      <section className="panel overview-hero">
        <div>
          <div className="eyebrow">Overview</div>
          <h2>{currentProjectConfig?.name || projectId}</h2>
          <p className="dim">
            当前项目采用
            <span className="mono"> {currentProjectConfig?.phase_strategy || 'react_graph'} </span>
            策略，context 为
            <span className="mono"> {currentProjectConfig?.context_strategy || 'default'} </span>
            。
          </p>
        </div>
        <div className="hero-status-grid">
          <div className={`hero-status-card ${isRunning ? 'online' : 'offline'}`}>
            <span>调度状态</span>
            <strong>{isRunning ? '运行中' : '已停止'}</strong>
          </div>
          <div className="hero-status-card">
            <span>活跃 Agent</span>
            <strong>{activeCount}/{agentRows.length}</strong>
          </div>
          <div className="hero-status-card">
            <span>Pending Inbox</span>
            <strong>{pendingInbox}</strong>
          </div>
          <div className="hero-status-card">
            <span>Pulse Queue</span>
            <strong>{queued}</strong>
          </div>
        </div>
      </section>

      <div className="overview-grid">
        <section className="panel">
          <div className="section-header">
            <div>
              <div className="eyebrow">Focus Agent</div>
              <h3>{selectedAgent?.agent_id || '暂无 agent'}</h3>
            </div>
            {selectedAgent && (
              <button className="ghost-btn" onClick={() => onPickAgent?.(selectedAgent.agent_id)}>
                打开 Agent
              </button>
            )}
          </div>
          {!selectedAgent && <div className="dim">当前项目还没有可观察的 agent。</div>}
          {selectedAgent && (
            <div className="focus-agent-card">
              <div className="focus-agent-head">
                <div>
                  <div className="focus-title">{selectedAgent.agent_id}</div>
                  <div className="mono dim">{selectedAgent.worker_state || 'idle'} / {selectedAgent.llm_state || 'none'}</div>
                </div>
                <div className={`project-state-chip compact ${selectedAgent.active ? 'online' : 'offline'}`}>
                  <span className="state-dot" />
                  {selectedAgent.active ? 'active' : 'inactive'}
                </div>
              </div>
              <div className="focus-agent-grid">
                <div>
                  <span>最后脉冲</span>
                  <strong>{formatTs(selectedAgent.last_pulse_at)}</strong>
                </div>
                <div>
                  <span>等待队列</span>
                  <strong>{selectedAgent.queued_pulse_events || 0}</strong>
                </div>
                <div>
                  <span>Inbox</span>
                  <strong>{selectedAgent.has_pending_inbox ? '有未读' : '清空'}</strong>
                </div>
                <div>
                  <span>最近原因</span>
                  <strong>{selectedAgent.last_reason || 'n/a'}</strong>
                </div>
              </div>
              {selectedAgent.last_error && (
                <div className="warn top-gap">
                  最近错误：<span className="mono">{selectedAgent.last_error}</span>
                </div>
              )}
            </div>
          )}
        </section>

        <section className="panel">
          <div className="section-header">
            <div>
              <div className="eyebrow">Live Bus</div>
              <h3>系统脉动</h3>
            </div>
            <div className="stream-chip-row">
              <span className={`stream-chip ${hermes.connected ? 'online' : 'offline'}`}>
                <RadioTower size={14} />
                Hermes {hermes.connected ? 'SSE' : 'fallback'}
              </span>
              <span className={`stream-chip ${events.connected ? 'online' : 'offline'}`}>
                <Activity size={14} />
                Events {events.connected ? 'SSE' : 'fallback'}
              </span>
            </div>
          </div>
          <div className="overview-mini-grid">
            <div className="summary-tile">
              <Orbit size={16} />
              <div>
                <span>拓扑节点</span>
                <strong>{nodes}</strong>
              </div>
            </div>
            <div className="summary-tile">
              <Sparkles size={16} />
              <div>
                <span>协议边</span>
                <strong>{edges}</strong>
              </div>
            </div>
            <div className="summary-tile">
              <Activity size={16} />
              <div>
                <span>运行中 agent</span>
                <strong>{runningCount}</strong>
              </div>
            </div>
            <div className="summary-tile">
              <Inbox size={16} />
              <div>
                <span>最近事件</span>
                <strong>{events.items?.length || 0}</strong>
              </div>
            </div>
          </div>
          <div className="feed-card-list">
            {(events.items || []).slice(0, 8).map((item) => (
              <div key={item.event_id} className="feed-card-item">
                <div className="feed-card-title">{item.event_type}</div>
                <div className="feed-card-meta mono">
                  {item.domain} · {item.state} · {(item.payload?.agent_id || item.payload?.to_id || '-')}
                </div>
              </div>
            ))}
            {!events.items?.length && <div className="dim">暂无实时事件。</div>}
          </div>
        </section>
      </div>

      <AgentStatusTable rows={agentRows} onPickAgent={onPickAgent} />
    </div>
  )
}
