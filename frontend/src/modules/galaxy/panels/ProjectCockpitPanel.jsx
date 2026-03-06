import { Bot, FolderPlus, Inbox, PauseCircle, PlayCircle, RefreshCw, Rocket, Server, Trash2, Workflow } from 'lucide-react'
import { MetricCard } from '../../../components/ui/MetricCard'
import { SectionHeader } from '../../../components/ui/SectionHeader'

const STRATEGY_OPTIONS = ['react_graph', 'freeform']
const INHERIT_STRATEGY = '__inherit__'

export function ProjectCockpitPanel({
  title,
  workspaceLoading,
  onRefresh,
  metrics,
  currentProjectConfig,
  newProjectId,
  onNewProjectIdChange,
  onCreateProject,
  isRunning,
  onToggleProject,
  onDeleteProject,
  newAgent,
  onNewAgentChange,
  onCreateAgent,
  modelOptions = [],
}) {
  return (
    <section className="panel galaxy-side-panel">
      <SectionHeader
        eyebrow="Project Cockpit"
        title={title}
        actions={(
          <button className="ghost-btn" onClick={onRefresh} disabled={workspaceLoading}>
            <RefreshCw size={14} className={workspaceLoading ? 'spin' : ''} />
            刷新
          </button>
        )}
      />

      <div className="compact-metric-grid">
        <MetricCard icon={Rocket} label="运行中" value={metrics.running} />
        <MetricCard icon={Inbox} label="待处理 inbox" value={metrics.inbox} />
        <MetricCard icon={Workflow} label="策略" value={currentProjectConfig?.phase_strategy || 'react_graph'} />
        <MetricCard icon={Server} label="Context" value={currentProjectConfig?.context_strategy || 'default'} />
      </div>

      <div className="galaxy-card-group">
        <div className="subsection">
          <div className="subsection-title">
            <FolderPlus size={16} />
            项目动作
          </div>
          <div className="stack-sm">
            <input value={newProjectId} onChange={(e) => onNewProjectIdChange(e.target.value)} placeholder="new_project_id" />
            <div className="action-row wrap-row">
              <button className="primary-btn" onClick={onCreateProject}>创建并切换</button>
              <button className="ghost-btn" onClick={onToggleProject}>
                {isRunning ? <PauseCircle size={14} /> : <PlayCircle size={14} />}
                {isRunning ? '停止调度' : '启动调度'}
              </button>
              <button className="ghost-btn danger-btn" onClick={onDeleteProject}>
                <Trash2 size={14} />
                删除项目
              </button>
            </div>
          </div>
        </div>

        <div className="subsection">
          <div className="subsection-title">
            <Bot size={16} />
            新建 Agent
          </div>
          <div className="stack-sm">
            <input value={newAgent.id} onChange={(e) => onNewAgentChange({ ...newAgent, id: e.target.value })} placeholder="agent_id" />
            <input list="galaxy-model-options" value={newAgent.model} onChange={(e) => onNewAgentChange({ ...newAgent, model: e.target.value })} placeholder="llm model" />
            <select value={newAgent.strategy} onChange={(e) => onNewAgentChange({ ...newAgent, strategy: e.target.value })}>
              <option value={INHERIT_STRATEGY}>继承项目策略</option>
              {STRATEGY_OPTIONS.map((strategy) => (
                <option key={strategy} value={strategy}>{strategy}</option>
              ))}
            </select>
            <textarea rows={5} value={newAgent.directives} onChange={(e) => onNewAgentChange({ ...newAgent, directives: e.target.value })} placeholder="agent directives" />
            <button className="primary-btn" onClick={onCreateAgent}>
              <Rocket size={14} />
              创建并加入星图
            </button>
          </div>
        </div>
      </div>

      <datalist id="galaxy-model-options">
        {modelOptions.map((model) => <option key={model} value={model} />)}
      </datalist>
    </section>
  )
}
