import { Activity, Bot, MessageSquare, Layers, FolderKanban, RefreshCw, BookText, SlidersHorizontal, Wrench } from 'lucide-react'

const NAV_ITEMS = [
  { id: 'dashboard', label: 'Dashboard', icon: Activity },
  { id: 'events', label: 'Events', icon: Layers },
  { id: 'agentDetail', label: 'Agent Detail', icon: Bot },
  { id: 'messageCenter', label: 'Message Center', icon: MessageSquare },
  { id: 'projectControl', label: 'Project Control', icon: FolderKanban },
  { id: 'memoryPolicy', label: 'Memory Policy', icon: BookText },
  { id: 'configCenter', label: 'Config Center', icon: SlidersHorizontal },
  { id: 'toolPolicy', label: 'Tool Policy', icon: Wrench },
]

export function AppShell({
  activeTab,
  onTabChange,
  children,
  projectIds,
  currentProject,
  onSwitchProject,
  onCreateProject,
  onRefresh,
  loading,
  humanIdentity,
}) {
  return (
    <div className="console-root">
      <aside className="console-sidebar">
        <div className="brand-block">
          <h1>Gods Console</h1>
          <p>Event-Driven Control Panel</p>
        </div>

        <div className="section-title">Project</div>
        <div className="project-row">
          <select value={currentProject} onChange={(e) => onSwitchProject(e.target.value)}>
            {projectIds.map((pid) => (
              <option key={pid} value={pid}>{pid}</option>
            ))}
          </select>
          <button className="ghost-btn" onClick={onCreateProject}>Create</button>
        </div>

        <div className="section-title">Navigation</div>
        <nav className="nav-list">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon
            return (
              <button
                key={item.id}
                className={`nav-item ${activeTab === item.id ? 'active' : ''}`}
                onClick={() => onTabChange(item.id)}
              >
                <Icon size={16} />
                <span>{item.label}</span>
              </button>
            )
          })}
        </nav>

        <div className="identity-card">
          <div className="label">Human Identity</div>
          <div className="value">{humanIdentity}</div>
        </div>
      </aside>

      <main className="console-main">
        <header className="top-bar">
          <button className="ghost-btn" onClick={onRefresh} disabled={loading}>
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
            Refresh
          </button>
        </header>
        <section className="page-body">{children}</section>
      </main>
    </div>
  )
}
