
import { useEffect, useMemo, useState } from 'react'
// eslint-disable-next-line no-unused-vars
import { motion, AnimatePresence } from 'framer-motion'
import {
  Play, Pause, Plus, Box, Cpu, Save, Trash2,
  RefreshCw, Activity, Layers, Server,
  Inbox, X, Network, FileText, Users, Settings
} from 'lucide-react'
import { createAgent, deleteAgent, getHermesContracts, getHermesPorts, getSocialGraph } from '../api/platformApi'

function deepClone(v) {
  return JSON.parse(JSON.stringify(v))
}

const MODEL_PRESETS = [
  'stepfun/step-3.5-flash:free',
  'openai/gpt-4o-mini',
  'openai/gpt-4.1-mini',
  'anthropic/claude-3.5-haiku',
]

const STRATEGY_OPTIONS = ['react_graph', 'freeform']
const INHERIT_STRATEGY = '__inherit__'

function asList(v) {
  return Array.isArray(v) ? v : []
}

// --- Components ---

function StatusBadge({ status }) {
  const isRunning = status === 'running'
  return (
    <div className={`agent-status-badge ${isRunning ? 'status-running' : 'status-idle'}`}>
      <span className="status-point" />
      {status || 'IDLE'}
    </div>
  )
}

function AgentCard({
  agentId, status, active, model,
  inboxStatus, queueCount, busy,
  onUpdate, onDelete,
  modelDraft, setModelDraft,
  strategyDraft, setStrategyDraft,
  rawStrategy,
}) {
  const isRunning = status === 'running'

  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
      className={`agent-card ${isRunning ? 'running' : 'stopped'}`}
    >
      <div className="agent-header">
        <div className="agent-identity">
          <div className="agent-icon">
            {isRunning && <div className="agent-pulse" />}
            <Box size={20} />
          </div>
          <div className="agent-name">{agentId}</div>
        </div>
        <StatusBadge status={status} />
      </div>

      <div className="agent-body">
        <div className="info-item">
          <div className="row-between" style={{ gap: 6 }}>
            <Cpu size={14} />
            <span className="dark-label">Model</span>
          </div>
          <input
            className="glass-input"
            style={{ width: '140px', textAlign: 'right', padding: '4px 8px' }}
            value={modelDraft}
            onChange={(e) => setModelDraft(e.target.value)}
            disabled={busy}
            list="project-model-options"
          />
        </div>

        <div className="info-item">
          <div className="row-between" style={{ gap: 6 }}>
            <Layers size={14} />
            <span className="dark-label">Strategy</span>
          </div>
          <select
            className="glass-input"
            style={{ width: '140px', textAlign: 'right', padding: '4px 8px' }}
            value={strategyDraft}
            onChange={(e) => setStrategyDraft(e.target.value)}
            disabled={busy}
          >
            <option value={INHERIT_STRATEGY}>Project Default</option>
            {STRATEGY_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>

        <div className="info-item">
          <div className="row-between" style={{ gap: 6 }}>
            <Inbox size={14} />
            <span className="dark-label">Inbox</span>
          </div>
          <span className="info-val">{inboxStatus ? 'Unread' : 'Empty'}</span>
        </div>

        <div className="info-item">
          <div className="row-between" style={{ gap: 6 }}>
            <Activity size={14} />
            <span className="dark-label">Queue</span>
          </div>
          <span className="info-val">{queueCount}</span>
        </div>
      </div>

      <div className="agent-footer">
        <div className="control-group">
          {active ? (
            <button
              className="icon-btn"
              title="Pause Agent"
              disabled={busy}
              onClick={() => onUpdate(agentId, { active: false })}
            >
              <Pause size={18} />
            </button>
          ) : (
            <button
              className="icon-btn primary"
              title="Resume Agent"
              disabled={busy}
              onClick={() => onUpdate(agentId, { active: true })}
            >
              <Play size={18} />
            </button>
          )}

          <button
            className="icon-btn"
            title="Save Config"
            disabled={busy || (modelDraft === model && strategyDraft === (rawStrategy || INHERIT_STRATEGY))}
            onClick={() => {
              const patch = {}
              if (modelDraft !== model) patch.model = modelDraft
              if (strategyDraft !== (rawStrategy || INHERIT_STRATEGY)) {
                patch.phase_strategy = strategyDraft === INHERIT_STRATEGY ? null : strategyDraft
              }
              onUpdate(agentId, { agent_settings: patch })
            }}
          >
            <Save size={18} />
          </button>
        </div>

        <button
          className="icon-btn danger"
          title="Delete Agent"
          disabled={busy}
          onClick={() => onDelete(agentId)}
        >
          <Trash2 size={18} />
        </button>
      </div>
    </motion.div>
  )
}


function SocialGraphView({ loading, graph }) {
  if (loading) return (
    <div className="panel" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 300, color: '#64748b' }}>
      <RefreshCw className="spin" size={20} style={{ marginRight: 10 }} /> Loading Graph...
    </div>
  )

  if (!graph || !graph.nodes || graph.nodes.length === 0) return (
    <div className="panel" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 100, color: '#94a3b8', borderStyle: 'dashed' }}>
      No Social Graph Data
    </div>
  )

  const nodes = graph.nodes
  const count = nodes.length
  // Simple circular layout
  const width = 600
  const height = 400
  const radius = Math.min(width, height) / 2.8
  const cx = width / 2
  const cy = height / 2

  const coords = {}
  nodes.forEach((id, i) => {
    const angle = (2 * Math.PI * i) / count - Math.PI / 2
    coords[id] = {
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle)
    }
  })

  // Lines
  const matrix = graph.matrix || {}
  const lines = []

  nodes.forEach((src) => {
    const row = matrix[src] || {}
    Object.keys(row).forEach(dst => {
      if (row[dst] > 0 && coords[dst] && coords[src]) {
        lines.push({ src, dst, weight: row[dst] })
      }
    })
  })

  return (
    <div className="panel" style={{ display: 'flex', justifyContent: 'center', background: '#f8fafc', padding: 20, borderRadius: 16 }}>
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="28" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#cbd5e1" />
          </marker>
        </defs>

        {lines.map((l, i) => {
          const s = coords[l.src]
          const d = coords[l.dst]
          return (
            <motion.line
              key={`${l.src}-${l.dst}`}
              x1={s.x} y1={s.y} x2={d.x} y2={d.y}
              stroke="#cbd5e1"
              strokeWidth={Math.max(1, Math.min(l.weight, 4))}
              markerEnd="url(#arrow)"
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: 1 }}
              transition={{ duration: 0.8, delay: i * 0.05 }}
            />
          )
        })}

        {nodes.map((id, i) => {
          const pos = coords[id]
          return (
            <motion.g
              key={id}
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ delay: i * 0.05, type: 'spring' }}
              transform={`translate(${pos.x}, ${pos.y})`}
              style={{ cursor: 'pointer' }}
            >
              <circle r={22} fill="white" stroke="#334155" strokeWidth="2" style={{ filter: 'drop-shadow(0 4px 6px rgba(0,0,0,0.1))' }} />
              <text dy={5} textAnchor="middle" fontSize={10} fontFamily="monospace" fontWeight="bold" fill="#1e293b" style={{ pointerEvents: 'none', userSelect: 'none' }}>
                {id.substring(0, 2).toUpperCase()}
              </text>
              <text dy={38} textAnchor="middle" fontSize={11} fill="#475569" fontWeight="600" style={{ pointerEvents: 'none', userSelect: 'none' }}>
                {id}
              </text>
            </motion.g>
          )
        })}
      </svg>
    </div>
  )
}

export function ProjectControlPage({
  projectId,
  onCreateProject,
  onSetRunning,
  isRunning,
  config,
  onSaveConfig,
  agentRows = [],
  onRefreshAgents,
}) {
  const [newProjectId, setNewProjectId] = useState('')
  const [newAgentId, setNewAgentId] = useState('')
  const [newAgentModel, setNewAgentModel] = useState(MODEL_PRESETS[0])
  const [newAgentStrategy, setNewAgentStrategy] = useState(INHERIT_STRATEGY)
  const [newAgentDirectives, setNewAgentDirectives] = useState('')
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [savingAgentId, setSavingAgentId] = useState('')
  const [deletingAgentId, setDeletingAgentId] = useState('')
  // Local drafts for each agent card
  const [modelDrafts, setModelDrafts] = useState({})
  const [agentStrategyDrafts, setAgentStrategyDrafts] = useState({})

  const [projectStrategyDraft, setProjectStrategyDraft] = useState(STRATEGY_OPTIONS[0])

  // Deployment Info
  const [contracts, setContracts] = useState([])
  const [contractsLoading, setContractsLoading] = useState(false)
  const [portsState, setPortsState] = useState({ project_id: projectId, leases: [] })
  const [portsLoading, setPortsLoading] = useState(false)
  const [showDeployment, setShowDeployment] = useState(false)

  // Social Graph
  const [showSocial, setShowSocial] = useState(false)
  const [socialLoading, setSocialLoading] = useState(false)
  const [socialData, setSocialData] = useState(null)
  const [projectToggleBusy, setProjectToggleBusy] = useState(false)

  // Derived State
  const currentProject = useMemo(() => (config?.projects || {})[projectId] || {}, [config, projectId])

  const projectStrategy = String(currentProject?.phase_strategy || STRATEGY_OPTIONS[0])

  const activeAgents = useMemo(() =>
    Array.isArray(currentProject?.active_agents) ? currentProject.active_agents : []
    , [currentProject])

  const agentSettings = useMemo(() =>
    currentProject?.agent_settings && typeof currentProject.agent_settings === 'object'
      ? currentProject.agent_settings
      : {}
    , [currentProject])

  const statusMap = useMemo(() => {
    const m = new Map()
    for (const row of agentRows || []) m.set(row.agent_id, row)
    return m
  }, [agentRows])

  const allAgentIds = useMemo(() => {
    const ids = new Set([...activeAgents, ...Object.keys(agentSettings || {}), ...Array.from(statusMap.keys())])
    return Array.from(ids).sort()
  }, [activeAgents, agentSettings, statusMap])

  // Sync Drafts
  useEffect(() => {
    setProjectStrategyDraft(projectStrategy)
    const modelNext = {}
    const strategyNext = {}
    for (const aid of Object.keys(agentSettings || {})) {
      modelNext[aid] = String(agentSettings?.[aid]?.model || MODEL_PRESETS[0])
      const sv = String(agentSettings?.[aid]?.phase_strategy || '').trim()
      strategyNext[aid] = sv || INHERIT_STRATEGY
    }
    setModelDrafts(modelNext)
    setAgentStrategyDrafts(strategyNext)
  }, [agentSettings, projectStrategy])

  const availableModels = useMemo(() => {
    const s = new Set(MODEL_PRESETS)
    for (const aid of Object.keys(agentSettings || {})) {
      const mv = String(agentSettings?.[aid]?.model || '').trim()
      if (mv) s.add(mv)
    }
    return Array.from(s)
  }, [agentSettings])

  // Actions
  const handleSaveProjectStrategy = async () => {
    setStatus('')
    setError('')
    setSavingAgentId('__project__')
    try {
      const next = deepClone(config || {})
      next.projects = next.projects || {}
      next.projects[projectId] = next.projects[projectId] || {}
      next.projects[projectId].phase_strategy = projectStrategyDraft
      await onSaveConfig(next)
      setStatus(`Project Config Saved`)
      await onRefreshAgents?.()
    } catch (err) {
      setError(String(err.message || err))
    } finally {
      setSavingAgentId('')
    }
  }

  const handleCreateAgent = async () => {
    setStatus('')
    setError('')
    const aid = String(newAgentId || '').trim()
    if (!aid) {
      setError('Agent ID is required')
      return
    }
    try {
      setSavingAgentId(aid)
      await createAgent(aid, newAgentDirectives)
      const next = deepClone(config || {})
      next.projects = next.projects || {}
      next.projects[projectId] = next.projects[projectId] || {}
      const proj = next.projects[projectId]
      proj.active_agents = Array.isArray(proj.active_agents) ? proj.active_agents : []
      proj.agent_settings = proj.agent_settings || {}

      proj.agent_settings[aid] = {
        ...(proj.agent_settings[aid] || {}),
        model: String(newAgentModel || MODEL_PRESETS[0]).trim(),
        phase_strategy: newAgentStrategy === INHERIT_STRATEGY ? null : newAgentStrategy,
      }

      const set = new Set(proj.active_agents)
      set.add(aid)
      proj.active_agents = Array.from(set).sort()

      await onSaveConfig(next)
      setStatus(`Agent ${aid} created`)
      setNewAgentId('')
      setNewAgentDirectives('')
      await onRefreshAgents?.()
    } catch (err) {
      setError(String(err.message || err))
    } finally {
      setSavingAgentId('')
    }
  }

  const handleUpdateAgent = async (agentId, patch = {}) => {
    setStatus('')
    setError('')
    setSavingAgentId(agentId)
    try {
      const next = deepClone(config || {})
      next.projects = next.projects || {}
      next.projects[projectId] = next.projects[projectId] || {}
      const proj = next.projects[projectId]

      // Update settings
      if (patch.agent_settings) {
        proj.agent_settings = proj.agent_settings || {}
        proj.agent_settings[agentId] = {
          ...(proj.agent_settings[agentId] || {}),
          ...patch.agent_settings
        }
      }

      // Update active state
      if (typeof patch.active === 'boolean') {
        const set = new Set(proj.active_agents || [])
        if (patch.active) set.add(agentId)
        else set.delete(agentId)
        proj.active_agents = Array.from(set).sort()
      }

      await onSaveConfig(next)
      setStatus(`Agent ${agentId} updated`)
      await onRefreshAgents?.()
    } catch (err) {
      setError(String(err.message || err))
    } finally {
      setSavingAgentId('')
    }
  }

  const handleDeleteAgent = async (agentId) => {
    if (!window.confirm(`Delete agent ${agentId}? This cannot be undone.`)) return
    setStatus('')
    setError('')
    setDeletingAgentId(agentId)
    try {
      await deleteAgent(agentId)
      setStatus(`Agent ${agentId} deleted`)
      await onRefreshAgents?.()
    } catch (err) {
      setError(String(err.message || err))
    } finally {
      setDeletingAgentId('')
    }
  }

  const handleToggleProjectRunning = async (running) => {
    setStatus('')
    setError('')
    setProjectToggleBusy(true)
    try {
      await onSetRunning(projectId, running)
      setStatus(running ? 'Project started' : 'Project stopped')
      await onRefreshAgents?.()
    } catch (err) {
      setError(String(err?.message || err))
    } finally {
      setProjectToggleBusy(false)
    }
  }

  // Load deployment info on demand
  useEffect(() => {
    if (showDeployment) {
      setContractsLoading(true)
      getHermesContracts(projectId, true).then(d => {
        setContracts(d?.contracts || [])
        setContractsLoading(false)
      }).catch(() => setContractsLoading(false))

      setPortsLoading(true)
      getHermesPorts(projectId).then(d => {
        setPortsState(d || { project_id: projectId, leases: [] })
        setPortsLoading(false)
      }).catch(() => setPortsLoading(false))
    }
  }, [showDeployment, projectId])

  // Load social graph on demand
  useEffect(() => {
    if (showSocial) {
      setSocialLoading(true)
      getSocialGraph(projectId).then(d => {
        setSocialData((d && d.graph) ? d.graph : d)
        setSocialLoading(false)
      }).catch(() => setSocialLoading(false))
    }
  }, [showSocial, projectId])

  return (
    <div className="stack-lg page-body">

      <div className="dashboard-header">
        <div className="dash-title">
          <h2>Project Control &bull; <span className="mono">{projectId}</span></h2>
          <div className="sub">
            Global Strategy: <span className="mono">{projectStrategy}</span>
          </div>
        </div>
        <div className="row-between">
          <div className={`chip ${isRunning ? 'ok' : 'off'}`} style={{ marginRight: 12 }}>
            {isRunning ? 'SYSTEM RUNNING' : 'SYSTEM HALTED'}
          </div>
          {isRunning ? (
            <button
              className="primary-btn"
              onClick={() => handleToggleProjectRunning(false)}
              style={{ background: '#ef4444' }}
              disabled={projectToggleBusy}
            >
              SHUTDOWN
            </button>
          ) : (
            <button
              className="primary-btn"
              onClick={() => handleToggleProjectRunning(true)}
              disabled={projectToggleBusy}
            >
              BOOT SYSTEM
            </button>
          )}
        </div>
      </div>

      {status && (
        <motion.div
          initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
          className="panel success-banner row-between"
        >
          <span>{status}</span>
          <button className="ghost-btn" onClick={() => setStatus('')}><X size={14} /></button>
        </motion.div>
      )}
      {error && (
        <motion.div
          initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
          className="panel error-banner row-between"
        >
          <span>{error}</span>
          <button className="ghost-btn" onClick={() => setError('')}><X size={14} /></button>
        </motion.div>
      )}

      <div>
        <div className="section-title row-between">
          <span>Active Agents ({allAgentIds.length})</span>
          <button className="ghost-btn" onClick={onRefreshAgents}>
            <RefreshCw size={14} /> Refresh Status
          </button>
        </div>

        <div className="agent-grid">
          <AnimatePresence>
            {allAgentIds.map(aid => {
              const srow = statusMap.get(aid) || {}
              const cfg = agentSettings?.[aid] || {}
              const model = String(cfg?.model || MODEL_PRESETS[0])
              const rawStrategy = String(cfg?.phase_strategy || '').trim()
              const active = activeAgents.includes(aid)

              return (
                <AgentCard
                  key={aid}
                  agentId={aid}
                  status={srow?.status || 'idle'}
                  active={active}
                  model={model}
                  // Draft state management
                  modelDraft={modelDrafts[aid] || model}
                  setModelDraft={(v) => setModelDrafts(prev => ({ ...prev, [aid]: v }))}
                  strategyDraft={agentStrategyDrafts[aid] || (rawStrategy || INHERIT_STRATEGY)}
                  setStrategyDraft={(v) => setAgentStrategyDrafts(prev => ({ ...prev, [aid]: v }))}
                  projectStrategy={projectStrategy}
                  rawStrategy={rawStrategy}

                  inboxStatus={srow?.has_pending_inbox}
                  queueCount={Number(srow?.queued_pulse_events || 0)}
                  busy={savingAgentId === aid || deletingAgentId === aid}
                  onUpdate={handleUpdateAgent}
                  onDelete={handleDeleteAgent}
                />
              )
            })}
          </AnimatePresence>

          {/* Create New Agent Card */}
          <motion.div
            className="agent-card"
            style={{ borderStyle: 'dashed', background: 'rgba(255,255,255,0.4)', justifyContent: 'center' }}
          >
            <div className="agent-header">
              <div className="agent-identity">
                <div className="agent-icon" style={{ background: 'transparent', border: '1px dashed #cbd5e1' }}>
                  <Plus size={20} />
                </div>
                <div className="agent-name dim">New Agent</div>
              </div>
            </div>
            <div className="agent-body">
              <input
                className="glass-input"
                placeholder="Agent ID (e.g. 'architect')"
                value={newAgentId}
                onChange={e => setNewAgentId(e.target.value)}
              />
              <input
                className="glass-input"
                placeholder="Model ID"
                list="project-model-options"
                value={newAgentModel}
                onChange={e => setNewAgentModel(e.target.value)}
              />
              <select
                className="glass-input"
                value={newAgentStrategy}
                onChange={e => setNewAgentStrategy(e.target.value)}
              >
                <option value={INHERIT_STRATEGY}>Inherit Strategy</option>
                {STRATEGY_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
              <textarea
                className="glass-input"
                rows={2}
                placeholder="Directives (optional)..."
                value={newAgentDirectives}
                onChange={e => setNewAgentDirectives(e.target.value)}
              />
            </div>
            <div className="agent-footer">
              <div />
              <button
                className="primary-btn"
                disabled={!newAgentId || !!savingAgentId}
                onClick={handleCreateAgent}
              >
                Create & Activate
              </button>
            </div>
          </motion.div>
        </div>
      </div>

      <div className="top-gap">
        <button
          className="ghost-btn row-between"
          style={{ width: '100%', justifyContent: 'center' }}
          onClick={() => setShowDeployment(!showDeployment)}
        >
          {showDeployment ? 'Hide Deployment Details' : 'Show Deployment Details (Contracts & Ports)'}
          <Server size={14} style={{ marginLeft: 8 }} />
        </button>

        {showDeployment && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            className="deployment-panel top-gap"
          >
            <div className="infra-grid">
              <div className="infra-section">
                <h3><Settings size={18} /> System Configuration</h3>
                <div className="form-grid" style={{ gridTemplateColumns: '1fr' }}>
                  <label>
                    Global Strategy
                    <select
                      className="glass-input"
                      value={projectStrategyDraft}
                      onChange={e => setProjectStrategyDraft(e.target.value)}
                    >
                      {STRATEGY_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </label>
                  <button
                    className="primary-btn"
                    disabled={projectStrategyDraft === projectStrategy || savingAgentId === '__project__'}
                    onClick={handleSaveProjectStrategy}
                  >
                    Update Global Strategy
                  </button>

                  <div className="top-gap"></div>
                  <label>
                    Create / Switch Project
                    <div className="action-row">
                      <input className="glass-input" value={newProjectId} onChange={e => setNewProjectId(e.target.value)} placeholder="new_project_id" />
                      <button className="ghost-btn" onClick={async () => {
                        if (!newProjectId) return
                        await onCreateProject(newProjectId)
                        setNewProjectId('')
                      }}>Switch</button>
                    </div>
                  </label>
                </div>
              </div>

              <div className="infra-section">
                <div className="row-between" style={{ marginBottom: 16 }}>
                  <h3><FileText size={18} /> Contracts ({contracts.length})</h3>
                  {contractsLoading && <RefreshCw className="spin" size={14} />}
                </div>

                {contracts.length === 0 ? (
                  <div className="empty-state-box">No Active Contracts</div>
                ) : (
                  <div className="infra-card-grid">
                    {contracts.map((c, i) => (
                      <div key={i} className="contract-card">
                        <div className="contract-header">
                          <div className="contract-title">{c.title}</div>
                          <div className="contract-ver">v{c.version}</div>
                        </div>
                        <div className="contract-meta">
                          Status: <span className={`chip ${c.status === 'active' ? 'ok' : 'off'}`}>{c.status}</span>
                        </div>
                        <div className="contract-meta" style={{ marginTop: 'auto' }}>
                          <Users size={12} />
                          <span style={{ marginLeft: 4 }}>
                            {asList(c.committers).join(', ') || 'System'}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                <div className="row-between" style={{ marginBottom: 16, marginTop: 40 }}>
                  <h3><Network size={18} /> Active Ports ({portsState?.leases?.length || 0})</h3>
                  {portsLoading && <RefreshCw className="spin" size={14} />}
                </div>

                {(portsState?.leases?.length || 0) === 0 ? (
                  <div className="empty-state-box">No Active Ports</div>
                ) : (
                  <div className="port-grid">
                    {portsState.leases.map((lease, i) => (
                      <div key={i} className={`port-card ${lease.active ? 'active' : ''}`}>
                        <div className="port-status-dot" />
                        <div className="port-label">{lease.protocol || 'TCP'}</div>
                        <div className="port-number">{lease.port}</div>
                        <div className="port-label" style={{ opacity: 0.7 }}>
                          {lease.allocated_to || 'System'}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </div>

      <div className="top-gap">
        <button
          className="ghost-btn row-between"
          style={{ width: '100%', justifyContent: 'center' }}
          onClick={() => setShowSocial(!showSocial)}
        >
          {showSocial ? 'Hide Social Graph' : 'Show Social Graph (Hestia)'}
          <Network size={14} style={{ marginLeft: 8 }} />
        </button>

        <AnimatePresence>
          {showSocial && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="top-gap"
            >
              <SocialGraphView loading={socialLoading} graph={socialData} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>


      <datalist id="project-model-options">
        {availableModels.map((m) => <option key={m} value={m} />)}
      </datalist>
    </div>
  )
}
