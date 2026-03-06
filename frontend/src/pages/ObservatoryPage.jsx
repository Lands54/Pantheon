import { useState } from 'react'
import { Activity, Bot, CalendarRange, MessageSquare } from 'lucide-react'
import { AgentDetailPage } from './AgentDetailPage'
import { EventsPage } from './EventsPage'
import { MessageCenterPage } from './MessageCenterPage'
import { ProjectTimelinePage } from './ProjectTimelinePage'

const TABS = [
  { id: 'events', label: '事件流', icon: Activity },
  { id: 'timeline', label: '项目时间线', icon: CalendarRange },
  { id: 'messages', label: '通信矩阵', icon: MessageSquare },
  { id: 'agent', label: 'Agent 深度视图', icon: Bot },
]

export function ObservatoryPage({ projectId, agentRows = [], agentId = '', onPickAgent }) {
  const [activeTab, setActiveTab] = useState(agentId ? 'agent' : 'events')
  const resolvedTab = !agentId && activeTab === 'agent' ? 'events' : activeTab

  const renderContent = () => {
    if (resolvedTab === 'timeline') {
      return <ProjectTimelinePage projectId={projectId} />
    }
    if (resolvedTab === 'messages') {
      return (
        <MessageCenterPage
          projectId={projectId}
          agents={agentRows}
          selectedAgentId={agentId}
          onPickAgent={onPickAgent}
        />
      )
    }
    if (resolvedTab === 'agent') {
      return <AgentDetailPage projectId={projectId} agentId={agentId} />
    }
    return <EventsPage projectId={projectId} />
  }

  return (
    <div className="stack-lg">
      <section className="panel workbench-intro">
        <div>
          <div className="eyebrow">Observatory</div>
          <h2>观测站</h2>
          <p className="dim">
            保留深度观察能力，但把入口压缩成一个工作台。当前聚焦：
            <span className="mono"> {agentId || '(未选中)'}</span>
          </p>
        </div>
        <div className="tab-strip">
          {TABS.map((tab) => {
            const Icon = tab.icon
            return (
              <button
                key={tab.id}
                className={`tab-chip ${resolvedTab === tab.id ? 'active' : ''}`}
                onClick={() => setActiveTab(tab.id)}
              >
                <Icon size={14} />
                {tab.label}
              </button>
            )
          })}
        </div>
      </section>
      {renderContent()}
    </div>
  )
}
