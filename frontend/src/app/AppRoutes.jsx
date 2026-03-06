import { DashboardPage } from '../modules/overview/OverviewPage'
import { AgentGalaxyPage } from '../modules/galaxy/scene/AgentGalaxyPage'
import { ObservatoryPage } from '../modules/observatory/ObservatoryPage'
import { PolicyStudioPage } from '../modules/policy/PolicyStudioPage'
import { DebugPage } from '../modules/debug/DebugPage'

export function AppRoutes({
  activeView,
  currentProject,
  config,
  currentProjectConfig,
  isProjectRunning,
  agentRows,
  selectedAgentId,
  setSelectedAgentId,
  updateConfig,
  createAndSwitchProject,
  deleteProjectById,
  setProjectRunning,
  refreshAgents,
}) {
  const handleFocusAgent = (agentId, nextView = 'galaxy') => {
    setSelectedAgentId(agentId)
    return nextView
  }

  if (activeView === 'galaxy') {
    return (
      <AgentGalaxyPage
        projectId={currentProject}
        config={config}
        onSaveConfig={updateConfig}
        onCreateProject={createAndSwitchProject}
        onDeleteProject={deleteProjectById}
        onSetRunning={setProjectRunning}
        isRunning={isProjectRunning}
        agentRows={agentRows}
        selectedAgentId={selectedAgentId}
        onSelectAgent={setSelectedAgentId}
        onRefreshAgents={() => refreshAgents(currentProject)}
      />
    )
  }

  if (activeView === 'observatory') {
    return (
      <ObservatoryPage
        projectId={currentProject}
        agentRows={agentRows}
        agentId={selectedAgentId}
        onPickAgent={(agentId) => handleFocusAgent(agentId, 'observatory')}
      />
    )
  }

  if (activeView === 'policy') {
    return (
      <PolicyStudioPage
        projectId={currentProject}
        config={config}
        onSaveConfig={updateConfig}
      />
    )
  }

  if (activeView === 'debug') {
    return (
      <DebugPage
        config={config}
        onCreateProject={createAndSwitchProject}
        onSaveConfig={updateConfig}
      />
    )
  }

  return (
    <DashboardPage
      projectId={currentProject}
      agentRows={agentRows}
      selectedAgentId={selectedAgentId}
      onPickAgent={(agentId) => handleFocusAgent(agentId)}
      currentProjectConfig={currentProjectConfig}
      isRunning={isProjectRunning}
    />
  )
}
