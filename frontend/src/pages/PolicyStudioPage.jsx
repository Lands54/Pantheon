import { useState } from 'react'
import { BookText, SlidersHorizontal, Wrench } from 'lucide-react'
import { ConfigCenterPage } from './ConfigCenterPage'
import { MemoryPolicyPage } from './MemoryPolicyPage'
import { ToolPolicyPage } from './ToolPolicyPage'

const TABS = [
  { id: 'config', label: '配置中心', icon: SlidersHorizontal },
  { id: 'tools', label: '工具策略', icon: Wrench },
  { id: 'memory', label: '记忆策略', icon: BookText },
]

export function PolicyStudioPage({ projectId, config, onSaveConfig }) {
  const [activeTab, setActiveTab] = useState('config')

  const renderContent = () => {
    if (activeTab === 'tools') {
      return <ToolPolicyPage projectId={projectId} config={config} onSaveConfig={onSaveConfig} />
    }
    if (activeTab === 'memory') {
      return <MemoryPolicyPage projectId={projectId} />
    }
    return <ConfigCenterPage projectId={projectId} config={config} onSaveConfig={onSaveConfig} />
  }

  return (
    <div className="stack-lg">
      <section className="panel workbench-intro">
        <div>
          <div className="eyebrow">Strategy Studio</div>
          <h2>策略工坊</h2>
          <p className="dim">
            把项目配置、工具白名单和记忆模板收敛到一个工作台里，避免在多个页面之间来回切换。
          </p>
        </div>
        <div className="tab-strip">
          {TABS.map((tab) => {
            const Icon = tab.icon
            return (
              <button
                key={tab.id}
                className={`tab-chip ${activeTab === tab.id ? 'active' : ''}`}
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
