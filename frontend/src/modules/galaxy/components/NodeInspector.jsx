import { Activity, Bot, Cpu, Inbox, Link2, Mail, MessageSquare, PauseCircle, PlayCircle, Save, Send, Trash2 } from 'lucide-react'
import { MetricCard } from '../../../components/ui/MetricCard'
import { SectionHeader } from '../../../components/ui/SectionHeader'
import { StatusPill } from '../../../components/ui/StatusPill'
import { formatTimestamp } from '../../../utils/formatters'

const STRATEGY_OPTIONS = ['react_graph', 'freeform']
const INHERIT_STRATEGY = '__inherit__'

export function NodeInspector({
  selectedAgent,
  selectedModel,
  onSelectedModelChange,
  selectedStrategy,
  onSelectedStrategyChange,
  messageDraft,
  onMessageDraftChange,
  onSaveAgent,
  onToggleAgent,
  linkModeSource,
  onToggleLinkMode,
  onDeleteAgent,
  onSendMessage,
}) {
  return (
    <div className="stack-lg">
      <SectionHeader
        eyebrow="Inspector"
        title={selectedAgent?.agent_id || '选择一个节点'}
        actions={selectedAgent ? <StatusPill online={selectedAgent.active} compact>{selectedAgent.active ? 'active' : 'inactive'}</StatusPill> : null}
      />

      {!selectedAgent && (
        <div className="dim">
          从星图或左侧 fleet 列表中点选 agent，右侧会自动切换成配置、消息和关系操作面板。
        </div>
      )}

      {selectedAgent && (
        <div className="stack-lg">
          <div className="compact-metric-grid">
            <MetricCard icon={Activity} label="Worker" value={selectedAgent.worker_state || 'idle'} />
            <MetricCard icon={Cpu} label="LLM" value={selectedAgent.llm_state || 'none'} />
            <MetricCard icon={Inbox} label="Inbox" value={selectedAgent.has_pending_inbox ? 'pending' : 'clear'} />
            <MetricCard icon={Mail} label="Last Pulse" value={formatTimestamp(selectedAgent.last_pulse_at)} />
          </div>

          <div className="subsection">
            <div className="subsection-title">
              <Cpu size={16} />
              配置
            </div>
            <div className="stack-sm">
              <input value={selectedModel} onChange={(e) => onSelectedModelChange(e.target.value)} placeholder="llm model" />
              <select value={selectedStrategy} onChange={(e) => onSelectedStrategyChange(e.target.value)}>
                <option value={INHERIT_STRATEGY}>继承项目策略</option>
                {STRATEGY_OPTIONS.map((strategy) => (
                  <option key={strategy} value={strategy}>{strategy}</option>
                ))}
              </select>
              <div className="action-row wrap-row">
                <button className="primary-btn" onClick={onSaveAgent}>
                  <Save size={14} />
                  保存配置
                </button>
                <button className="ghost-btn" onClick={onToggleAgent}>
                  {selectedAgent.active ? <PauseCircle size={14} /> : <PlayCircle size={14} />}
                  {selectedAgent.active ? '暂停 Agent' : '恢复 Agent'}
                </button>
                <button className={`ghost-btn ${linkModeSource ? 'is-linking' : ''}`} onClick={onToggleLinkMode}>
                  <Link2 size={14} />
                  {linkModeSource === selectedAgent.agent_id ? '取消连线' : '从此节点连线'}
                </button>
                <button className="ghost-btn danger-btn" onClick={onDeleteAgent}>
                  <Trash2 size={14} />
                  删除
                </button>
              </div>
            </div>
          </div>

          <div className="subsection">
            <div className="subsection-title">
              <MessageSquare size={16} />
              人类私信
            </div>
            <div className="stack-sm">
              <input value={messageDraft.title} onChange={(e) => onMessageDraftChange({ ...messageDraft, title: e.target.value })} placeholder="message title" />
              <textarea
                rows={6}
                value={messageDraft.content}
                onChange={(e) => onMessageDraftChange({ ...messageDraft, content: e.target.value })}
                placeholder={`发给 ${selectedAgent.agent_id} 的私信内容`}
              />
              <button className="primary-btn" onClick={onSendMessage}>
                <Send size={14} />
                立即发送
              </button>
            </div>
          </div>

          <div className="subsection">
            <div className="subsection-title">
              <Bot size={16} />
              运行摘要
            </div>
            <div className="stack-sm mono dim">
              <div>queued={selectedAgent.queued_pulse_events || 0}</div>
              <div>next_eligible={formatTimestamp(selectedAgent.next_eligible_at)}</div>
              <div>last_reason={selectedAgent.last_reason || 'n/a'}</div>
              {selectedAgent.last_error && <div className="error-cell">last_error={selectedAgent.last_error}</div>}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
