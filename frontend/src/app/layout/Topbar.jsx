import { RefreshCw } from 'lucide-react'

const VIEW_LABELS = {
  overview: '总览',
  galaxy: 'Agent Galaxy',
  observatory: '观测站',
  policy: '策略工坊',
  debug: '调试',
}

export function Topbar({
  activeView,
  currentProject,
  projectStats = {},
  selectedAgentId = '',
  onRefresh,
  loading,
}) {
  return (
    <header className="top-bar top-bar-rich">
      <div>
        <div className="top-kicker">Workspace</div>
        <div className="top-heading">{VIEW_LABELS[activeView] || '控制台'}</div>
        <div className="top-subtitle">
          <span className="mono">{currentProject}</span>
          <span>·</span>
          <span>{projectStats.total || 0} agents</span>
          <span>·</span>
          <span>{selectedAgentId ? `聚焦 ${selectedAgentId}` : '未选中 agent'}</span>
        </div>
      </div>
      <button className="ghost-btn" onClick={onRefresh} disabled={loading}>
        <RefreshCw size={14} className={loading ? 'spin' : ''} />
        刷新工作台
      </button>
    </header>
  )
}
