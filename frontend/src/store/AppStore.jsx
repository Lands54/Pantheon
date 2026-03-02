import { createContext, useContext, useState } from 'react'
import { createProject, getConfig, getProjects, saveConfig, selectProject, startProject, stopProject } from '../api/platformApi'

const AppStoreContext = createContext(null)

export function AppStoreProvider({ children }) {
  const [config, setConfig] = useState({
    openrouter_api_key: '',
    current_project: 'default',
    projects: { default: { name: 'Default World', active_agents: [], agent_settings: {} } },
    available_agents: [],
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const refreshConfig = async () => {
    setLoading(true)
    setError('')
    try {
      const [cfg, projectsState] = await Promise.all([getConfig(), getProjects()])
      const data = {
        ...(cfg || {}),
        current_project: projectsState?.current || cfg?.current_project || 'default',
        projects: projectsState?.projects || cfg?.projects || {},
      }
      setConfig(data)
      return data
    } catch (err) {
      setError(String(err.message || err))
      throw err
    } finally {
      setLoading(false)
    }
  }

  const switchProject = async (projectId) => {
    if (!projectId || projectId === 'null' || projectId === 'undefined') return
    await selectProject(projectId)
    await refreshConfig()
  }

  const createAndSwitchProject = async (projectId) => {
    if (!projectId || projectId === 'null' || projectId === 'undefined') return
    await createProject(projectId)
    await switchProject(projectId)
  }

  const setProjectRunning = async (projectId, running) => {
    if (!projectId || projectId === 'null' || projectId === 'undefined') return
    if (running) await startProject(projectId)
    else await stopProject(projectId)
    await refreshConfig()
  }

  const updateConfig = async (next) => {
    const payload = JSON.parse(JSON.stringify(next || {}))
    delete payload.current_project
    const projects = payload.projects && typeof payload.projects === 'object' ? payload.projects : {}
    for (const pid of Object.keys(projects)) {
      const proj = projects[pid]
      if (proj && typeof proj === 'object') {
        delete proj.active_agents
      }
    }
    const res = await saveConfig(payload)
    const fresh = await refreshConfig()
    return { ...(fresh || {}), warnings: res?.warnings || [] }
  }

  const value = {
    config,
    loading,
    error,
    refreshConfig,
    switchProject,
    createAndSwitchProject,
    setProjectRunning,
    updateConfig,
  }

  return <AppStoreContext.Provider value={value}>{children}</AppStoreContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAppStore() {
  const ctx = useContext(AppStoreContext)
  if (!ctx) throw new Error('useAppStore must be used inside AppStoreProvider')
  return ctx
}
