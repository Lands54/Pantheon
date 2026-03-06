import { useEffect, useMemo, useRef, useState } from 'react'
import {
  createProject,
  deleteProject,
  getAgentStatus,
  getConfig,
  getProjects,
  saveConfig,
  selectProject,
  startProject,
  stopProject,
} from '../../api/platformApi'
import { AppStoreContext } from './AppStoreContext'

const INITIAL_CONFIG = {
  openrouter_api_key: '',
  current_project: 'default',
  projects: { default: { name: 'Default World', active_agents: [], agent_settings: {} } },
  available_agents: [],
}

function pickNextAgent(rows, previousId = '') {
  const list = Array.isArray(rows) ? rows : []
  if (!list.length) return ''
  if (previousId && list.some((item) => item.agent_id === previousId)) return previousId
  const preferred = list.find((item) => item.active) || list[0]
  return String(preferred?.agent_id || '')
}

export function AppStoreProvider({ children }) {
  const [config, setConfig] = useState(INITIAL_CONFIG)
  const [loading, setLoading] = useState(false)
  const [agentLoading, setAgentLoading] = useState(false)
  const [error, setError] = useState('')
  const [agentRows, setAgentRows] = useState([])
  const [selectedAgentId, setSelectedAgentId] = useState('')
  const agentReqSeqRef = useRef(0)

  const currentProject = config.current_project || 'default'
  const projectIds = Object.keys(config.projects || {})
  const currentProjectConfig = (config.projects || {})[currentProject] || {}
  const isProjectRunning = !!currentProjectConfig.simulation_enabled

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

  const refreshAgents = async (projectId = currentProject, options = {}) => {
    if (!projectId) return []
    const { silent = false } = options
    const reqSeq = ++agentReqSeqRef.current
    setAgentLoading(true)
    if (!silent) setError('')
    try {
      const data = await getAgentStatus(projectId)
      if (reqSeq !== agentReqSeqRef.current) return []
      const rows = Array.isArray(data?.agents) ? data.agents : []
      setAgentRows(rows)
      setSelectedAgentId((prev) => pickNextAgent(rows, prev))
      return rows
    } catch (err) {
      if (!silent && reqSeq === agentReqSeqRef.current) {
        setError(String(err.message || err))
      }
      throw err
    } finally {
      if (reqSeq === agentReqSeqRef.current) {
        setAgentLoading(false)
      }
    }
  }

  useEffect(() => {
    refreshConfig().catch(() => {})
  }, [])

  useEffect(() => {
    if (!currentProject) return
    setAgentRows([])
    setSelectedAgentId('')
    refreshAgents(currentProject, { silent: true }).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentProject])

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

  const deleteProjectById = async (projectId) => {
    if (!projectId || projectId === 'null' || projectId === 'undefined') return
    await deleteProject(projectId)
    await refreshConfig()
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

  const refreshAll = async () => {
    const fresh = await refreshConfig()
    const nextProject = fresh?.current_project || currentProject
    await refreshAgents(nextProject, { silent: true })
  }

  const derived = useMemo(() => {
    const rows = Array.isArray(agentRows) ? agentRows : []
    const activeCount = rows.filter((item) => item.active).length
    const runningCount = rows.filter((item) => String(item.worker_state || '').toLowerCase() === 'running').length
    const pendingInboxCount = rows.filter((item) => item.has_pending_inbox).length
    const queuedPulseTotal = rows.reduce((sum, item) => sum + Number(item.queued_pulse_events || 0), 0)
    return {
      activeCount,
      runningCount,
      pendingInboxCount,
      queuedPulseTotal,
    }
  }, [agentRows])

  const value = {
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
    refreshConfig,
    switchProject,
    createAndSwitchProject,
    deleteProjectById,
    setProjectRunning,
    updateConfig,
    ...derived,
  }

  return <AppStoreContext.Provider value={value}>{children}</AppStoreContext.Provider>
}
