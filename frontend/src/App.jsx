import { useEffect, useMemo, useRef, useState } from 'react'
import { AppShell } from './components/AppShell'
import { DashboardPage } from './pages/DashboardPage'
import { EventsPage } from './pages/EventsPage'
import { MessageCenterPage } from './pages/MessageCenterPage'
import { AgentDetailPage } from './pages/AgentDetailPage'
import { ProjectControlPage } from './pages/ProjectControlPage'
import { MemoryPolicyPage } from './pages/MemoryPolicyPage'
import { ConfigCenterPage } from './pages/ConfigCenterPage'
import { ToolPolicyPage } from './pages/ToolPolicyPage'
import { AppStoreProvider, useAppStore } from './store/AppStore'
import { getAgentStatus } from './api/platformApi'
import { usePolling } from './hooks/usePolling'
import { HUMAN_IDENTITY } from './types/models'
import './App.css'

function AppInner() {
  const {
    config,
    loading,
    error,
    refreshConfig,
    switchProject,
    createAndSwitchProject,
    setProjectRunning,
    updateConfig,
  } = useAppStore()

  const [activeTab, setActiveTab] = useState('dashboard')
  const [selectedAgentId, setSelectedAgentId] = useState('')
  const [agentRows, setAgentRows] = useState([])
  const agentReqSeqRef = useRef(0)

  const currentProject = config.current_project || 'default'
  const projectIds = Object.keys(config.projects || {})
  const currentProjectConfig = (config.projects || {})[currentProject] || {}
  const isRunning = !!currentProjectConfig.simulation_enabled

  useEffect(() => {
    refreshConfig().catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const reloadAgentRows = async (projectId = currentProject) => {
    if (!projectId) return
    const reqSeq = ++agentReqSeqRef.current
    try {
      const data = await getAgentStatus(projectId)
      if (reqSeq !== agentReqSeqRef.current || projectId !== (config.current_project || 'default')) return
      setAgentRows(data.agents || [])
      if (data.agents?.length) {
        setSelectedAgentId((prev) => {
          if (prev && data.agents.some((x) => x.agent_id === prev)) return prev
          return data.agents[0].agent_id
        })
      } else {
        setSelectedAgentId('')
      }
    } catch {
      // ignore, page-level sections show their own errors
    }
  }

  useEffect(() => {
    setAgentRows([])
    setSelectedAgentId('')
    reloadAgentRows(currentProject)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentProject])

  usePolling(() => reloadAgentRows(currentProject), 10000, [currentProject])

  const content = useMemo(() => {
    switch (activeTab) {
      case 'dashboard':
        return <DashboardPage projectId={currentProject} onPickAgent={(id) => { setSelectedAgentId(id); setActiveTab('agentDetail') }} />
      case 'events':
        return <EventsPage projectId={currentProject} />
      case 'messageCenter':
        return (
          <MessageCenterPage
            projectId={currentProject}
            agents={agentRows}
            selectedAgentId={selectedAgentId}
            onPickAgent={(id) => setSelectedAgentId(id)}
          />
        )
      case 'agentDetail':
        return <AgentDetailPage projectId={currentProject} agentId={selectedAgentId} />
      case 'projectControl':
        return (
          <ProjectControlPage
            projectId={currentProject}
            isRunning={isRunning}
            onCreateProject={createAndSwitchProject}
            onSetRunning={setProjectRunning}
            config={config}
            onSaveConfig={updateConfig}
            agentRows={agentRows}
            onRefreshAgents={() => reloadAgentRows(currentProject)}
          />
        )
      case 'memoryPolicy':
        return <MemoryPolicyPage projectId={currentProject} />
      case 'configCenter':
        return <ConfigCenterPage projectId={currentProject} config={config} onSaveConfig={updateConfig} />
      case 'toolPolicy':
        return <ToolPolicyPage projectId={currentProject} config={config} onSaveConfig={updateConfig} />
      default:
        return null
    }
  }, [activeTab, currentProject, selectedAgentId, agentRows, isRunning, createAndSwitchProject, setProjectRunning, config, updateConfig])

  return (
    <AppShell
      activeTab={activeTab}
      onTabChange={setActiveTab}
      projectIds={projectIds}
      currentProject={currentProject}
      onSwitchProject={switchProject}
      onCreateProject={() => {
        const id = window.prompt('Project ID')
        if (id) createAndSwitchProject(id).catch((e) => window.alert(String(e.message || e)))
      }}
      onRefresh={() => Promise.all([refreshConfig(), reloadAgentRows()])}
      loading={loading}
      humanIdentity={HUMAN_IDENTITY}
    >
      {error && <div className="panel error-banner">{error}</div>}
      {content}
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
