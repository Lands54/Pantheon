import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'

export function AppShell({
  activeView,
  onViewChange,
  children,
  projectIds,
  currentProject,
  onSwitchProject,
  onCreateProject,
  onRefresh,
  loading,
  humanIdentity,
  agentRows = [],
  selectedAgentId = '',
  onSelectAgent,
  projectStats = {},
  currentProjectConfig = {},
  isProjectRunning = false,
}) {
  return (
    <div className="console-root">
      <Sidebar
        activeView={activeView}
        onViewChange={onViewChange}
        projectIds={projectIds}
        currentProject={currentProject}
        onSwitchProject={onSwitchProject}
        onCreateProject={onCreateProject}
        humanIdentity={humanIdentity}
        agentRows={agentRows}
        selectedAgentId={selectedAgentId}
        onSelectAgent={onSelectAgent}
        projectStats={projectStats}
        currentProjectConfig={currentProjectConfig}
        isProjectRunning={isProjectRunning}
      />

      <main className="console-main">
        <Topbar
          activeView={activeView}
          currentProject={currentProject}
          projectStats={projectStats}
          selectedAgentId={selectedAgentId}
          onRefresh={onRefresh}
          loading={loading}
        />
        <section className="page-body">{children}</section>
      </main>
    </div>
  )
}
