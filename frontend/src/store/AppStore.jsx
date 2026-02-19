import { createContext, useContext, useState } from 'react'
import { createProject, getConfig, saveConfig, startProject, stopProject } from '../api/platformApi'

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
      const data = await getConfig()
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
    const next = { ...config, current_project: projectId }
    await saveConfig(next)
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
    const res = await saveConfig(next)
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
