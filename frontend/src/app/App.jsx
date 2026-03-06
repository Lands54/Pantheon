import { useState } from 'react'
import { AppShell } from './layout/AppShell'
import { AppRoutes } from './AppRoutes'
import { AppStoreProvider } from './providers/AppStoreProvider'
import { ErrorBanner } from '../components/feedback/ErrorBanner'
import { usePolling } from '../hooks/usePolling'
import { selectProjectStats } from '../store/app/selectors'
import { useAppStore } from '../store/app/useAppStore'
import { HUMAN_IDENTITY } from '../types/models'

function AppInner() {
  const {
    config,
    loading,
    agentLoading,
    error,
    currentProject,
    projectIds,
    currentProjectConfig,
    isProjectRunning,
    agentRows,
    selectedAgentId,
    setSelectedAgentId,
    refreshAgents,
    refreshAll,
    switchProject,
    createAndSwitchProject,
    deleteProjectById,
    setProjectRunning,
    updateConfig,
  } = useAppStore()

  const [activeView, setActiveView] = useState('overview')

  usePolling(() => {
    refreshAgents(currentProject, { silent: true }).catch(() => {})
  }, 10000, [currentProject])

  const projectStats = selectProjectStats(agentRows)

  const handleCreateProject = async () => {
    const projectId = window.prompt('请输入新的 Project ID')
    if (!projectId) return
    await createAndSwitchProject(projectId)
    setActiveView('galaxy')
  }

  return (
    <AppShell
      activeView={activeView}
      onViewChange={setActiveView}
      projectIds={projectIds}
      currentProject={currentProject}
      onSwitchProject={switchProject}
      onCreateProject={() => {
        handleCreateProject().catch((err) => window.alert(String(err?.message || err)))
      }}
      onRefresh={() => refreshAll().catch(() => {})}
      loading={loading || agentLoading}
      humanIdentity={HUMAN_IDENTITY}
      agentRows={agentRows}
      selectedAgentId={selectedAgentId}
      onSelectAgent={setSelectedAgentId}
      projectStats={projectStats}
      currentProjectConfig={currentProjectConfig}
      isProjectRunning={isProjectRunning}
    >
      <ErrorBanner message={error} />
      <AppRoutes
        activeView={activeView}
        currentProject={currentProject}
        config={config}
        currentProjectConfig={currentProjectConfig}
        isProjectRunning={isProjectRunning}
        agentRows={agentRows}
        selectedAgentId={selectedAgentId}
        setSelectedAgentId={setSelectedAgentId}
        updateConfig={updateConfig}
        createAndSwitchProject={createAndSwitchProject}
        deleteProjectById={deleteProjectById}
        setProjectRunning={setProjectRunning}
        refreshAgents={refreshAgents}
      />
    </AppShell>
  )
}

export default function App() {
  return (
    <AppStoreProvider>
      <AppInner />
    </AppStoreProvider>
  )
}
