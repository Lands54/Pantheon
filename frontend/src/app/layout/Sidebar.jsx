import {
  Activity,
  AlertCircle,
  Bot,
  Hexagon,
  Microscope,
  Settings2,
  Sparkles,
  TerminalSquare,
} from 'lucide-react'

const NAV_ITEMS = [
  { id: 'overview', label: '总览', description: '实时概览与运行健康', icon: Activity },
  { id: 'galaxy', label: 'Agent Galaxy', description: '以星图为核心的总控台', icon: Hexagon },
  { id: 'observatory', label: '观测站', description: '事件、时间线与上下文深挖', icon: Microscope },
  { id: 'policy', label: '策略工坊', description: '配置、工具与记忆策略', icon: Settings2 },
  { id: 'debug', label: '调试', description: '初始化与实验入口', icon: TerminalSquare },
]

function statusTone(workerState) {
  const state = String(workerState || 'idle').toLowerCase()
  if (state === 'running') return 'running'
  if (state === 'failed' || state === 'dead') return 'error'
  if (state === 'cooldown' || state === 'queued') return 'queued'
  return 'idle'
}

export function Sidebar({
  activeView,
  onViewChange,
  projectIds,
  currentProject,
  onSwitchProject,
  onCreateProject,
  humanIdentity,
  agentRows = [],
  selectedAgentId = '',
  onSelectAgent,
  projectStats = {},
  currentProjectConfig = {},
  isProjectRunning = false,
}) {
  const activeAgents = Array.isArray(agentRows) ? agentRows : []
  const projectName = currentProjectConfig?.name || currentProject
  const strategy = String(currentProjectConfig?.phase_strategy || 'react_graph')

  return (
    <aside className="console-sidebar">
      <div className="brand-block brand-hero">
        <div className="brand-icon">
          <Sparkles size={18} />
        </div>
        <div>
          <h1>Gods Console</h1>
          <p>让 Agent Galaxy 成为统一工具，而不是零散页面集合</p>
        </div>
      </div>

      <div className="sidebar-metrics">
        <div className="sidebar-metric-card">
          <div className="metric-kicker">当前项目</div>
          <div className="metric-main">{projectName}</div>
          <div className="metric-sub mono">{currentProject}</div>
        </div>
        <div className="sidebar-metric-grid">
          <div className="mini-metric">
            <span>Agents</span>
            <strong>{projectStats.total || 0}</strong>
          </div>
          <div className="mini-metric">
            <span>运行中</span>
            <strong>{projectStats.running || 0}</strong>
          </div>
          <div className="mini-metric">
            <span>Inbox</span>
            <strong>{projectStats.pendingInbox || 0}</strong>
          </div>
          <div className="mini-metric">
            <span>Queue</span>
            <strong>{projectStats.queued || 0}</strong>
          </div>
        </div>
        <div className={`project-state-chip ${isProjectRunning ? 'online' : 'offline'}`}>
          <span className="state-dot" />
          {isProjectRunning ? '调度已启动' : '调度未启动'}
          <span className="mono dim">strategy={strategy}</span>
        </div>
      </div>

      <div className="section-title">Project</div>
      <div className="project-row">
        <select value={currentProject} onChange={(e) => onSwitchProject(e.target.value)}>
          {projectIds.map((pid) => (
            <option key={pid} value={pid}>{pid}</option>
          ))}
        </select>
        <button className="ghost-btn" onClick={onCreateProject}>新建</button>
      </div>

      <div className="section-title">Workspace</div>
      <nav className="nav-list">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon
          return (
            <button
              key={item.id}
              className={`nav-item nav-rich ${activeView === item.id ? 'active' : ''}`}
              onClick={() => onViewChange(item.id)}
            >
              <Icon size={16} />
              <div className="nav-copy">
                <span>{item.label}</span>
                <small>{item.description}</small>
              </div>
            </button>
          )
        })}
      </nav>

      <div className="section-title">Fleet</div>
      <div className="agent-quick-list">
        {!activeAgents.length && (
          <div className="agent-quick-empty">
            <AlertCircle size={14} />
            当前项目还没有 agent
          </div>
        )}
        {activeAgents.map((agent) => (
          <button
            key={agent.agent_id}
            className={`agent-quick-item ${selectedAgentId === agent.agent_id ? 'active' : ''}`}
            onClick={() => {
              onSelectAgent?.(agent.agent_id)
              onViewChange('galaxy')
            }}
          >
            <div className={`quick-state ${statusTone(agent.worker_state)}`} />
            <div className="agent-quick-copy">
              <span>{agent.agent_id}</span>
              <small>{agent.worker_state || 'idle'} / queue {agent.queued_pulse_events || 0}</small>
            </div>
            {agent.has_pending_inbox && <Bot size={14} className="quick-inbox" />}
          </button>
        ))}
      </div>

      <div className="identity-card">
        <div className="label">Human Identity</div>
        <div className="value">{humanIdentity}</div>
      </div>
    </aside>
  )
}
