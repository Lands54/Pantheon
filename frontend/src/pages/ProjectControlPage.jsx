import { useEffect, useMemo, useState } from 'react'
import { createAgent, deleteAgent, getHermesContracts, getHermesPorts } from '../api/platformApi'

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

function obligationSummary(ob) {
  const id = String(ob?.id || '-')
  const summary = String(ob?.summary || '')
  const provider = ob?.provider && typeof ob.provider === 'object' ? ob.provider : {}
  const runtime = ob?.runtime && typeof ob.runtime === 'object' ? ob.runtime : {}
  const providerType = String(provider?.type || '-')
  const endpoint = String(provider?.url || provider?.tool_name || provider?.agent_id || '-')
  const mode = String(runtime?.mode || '-')
  const timeout = String(runtime?.timeout_sec ?? '-')
  return { id, summary, providerType, endpoint, mode, timeout }
}

function flattenAgentObligations(obligationsMap) {
  const out = []
  if (!obligationsMap || typeof obligationsMap !== 'object') return out
  for (const [owner, clauses] of Object.entries(obligationsMap)) {
    if (!Array.isArray(clauses)) continue
    for (const clause of clauses) {
      out.push({ owner: String(owner || '-'), ...obligationSummary(clause) })
    }
  }
  return out
}

function fmtTs(ts) {
  const n = Number(ts || 0)
  if (!n) return '-'
  return new Date(n * 1000).toLocaleString()
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
  const [newAgentActive, setNewAgentActive] = useState(true)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [savingAgentId, setSavingAgentId] = useState('')
  const [deletingAgentId, setDeletingAgentId] = useState('')
  const [modelDrafts, setModelDrafts] = useState({})
  const [agentStrategyDrafts, setAgentStrategyDrafts] = useState({})
  const [projectStrategyDraft, setProjectStrategyDraft] = useState(STRATEGY_OPTIONS[0])
  const [contracts, setContracts] = useState([])
  const [contractsLoading, setContractsLoading] = useState(false)
  const [contractsError, setContractsError] = useState('')
  const [includeDisabledContracts, setIncludeDisabledContracts] = useState(true)
  const [selectedContract, setSelectedContract] = useState(null)
  const [portsState, setPortsState] = useState({ project_id: projectId, leases: [] })
  const [portsLoading, setPortsLoading] = useState(false)
  const [portsError, setPortsError] = useState('')

  const currentProject = useMemo(() => (config?.projects || {})[projectId] || {}, [config, projectId])
  const projectStrategy = String(currentProject?.phase_strategy || STRATEGY_OPTIONS[0])
  const activeAgents = Array.isArray(currentProject?.active_agents) ? currentProject.active_agents : []
  const agentSettings = currentProject?.agent_settings && typeof currentProject.agent_settings === 'object'
    ? currentProject.agent_settings
    : {}

  const statusMap = useMemo(() => {
    const m = new Map()
    for (const row of agentRows || []) m.set(row.agent_id, row)
    return m
  }, [agentRows])

  const allAgentIds = useMemo(() => {
    const ids = new Set([...activeAgents, ...Object.keys(agentSettings || {}), ...Array.from(statusMap.keys())])
    return Array.from(ids).sort()
  }, [activeAgents, agentSettings, statusMap])

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

  const portLeases = useMemo(() => asList(portsState?.leases), [portsState])
  const ownerPortSummary = useMemo(() => {
    const m = new Map()
    for (const row of portLeases) {
      const owner = String(row?.owner_id || '-')
      const count = Number(m.get(owner) || 0)
      m.set(owner, count + 1)
    }
    return Array.from(m.entries()).sort((a, b) => b[1] - a[1])
  }, [portLeases])

  const loadContracts = async (pid = projectId, includeDisabled = includeDisabledContracts) => {
    setContractsLoading(true)
    setContractsError('')
    try {
      const data = await getHermesContracts(pid, includeDisabled)
      setContracts(Array.isArray(data?.contracts) ? data.contracts : [])
    } catch (err) {
      setContracts([])
      setContractsError(String(err.message || err))
    } finally {
      setContractsLoading(false)
    }
  }

  useEffect(() => {
    loadContracts(projectId, includeDisabledContracts)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, includeDisabledContracts])

  const loadPorts = async (pid = projectId) => {
    setPortsLoading(true)
    setPortsError('')
    try {
      const data = await getHermesPorts(pid)
      setPortsState(data && typeof data === 'object' ? data : { project_id: pid, leases: [] })
    } catch (err) {
      setPortsState({ project_id: pid, leases: [] })
      setPortsError(String(err.message || err))
    } finally {
      setPortsLoading(false)
    }
  }

  useEffect(() => {
    loadPorts(projectId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

  const saveProjectStrategy = async () => {
    setStatus('')
    setError('')
    setSavingAgentId('__project__')
    try {
      const next = deepClone(config || {})
      next.projects = next.projects || {}
      next.projects[projectId] = next.projects[projectId] || {}
      next.projects[projectId].phase_strategy = projectStrategyDraft
      const saved = await onSaveConfig(next)
      const warnings = Array.isArray(saved?.warnings) ? saved.warnings : []
      setStatus(`已更新项目策略为 ${projectStrategyDraft}${warnings.length ? `（含 ${warnings.length} 条 warning）` : ''}`)
      await onRefreshAgents?.()
    } catch (err) {
      setError(String(err.message || err))
    } finally {
      setSavingAgentId('')
    }
  }

  const create = async () => {
    setStatus('')
    setError('')
    try {
      const id = newProjectId.trim()
      if (!id) throw new Error('project id is required')
      await onCreateProject(id)
      setStatus(`Created project: ${id}`)
      setNewProjectId('')
    } catch (err) {
      setError(String(err.message || err))
    }
  }

  const setRunning = async (running) => {
    setStatus('')
    setError('')
    try {
      await onSetRunning(projectId, running)
      setStatus(running ? 'Project started' : 'Project stopped')
    } catch (err) {
      setError(String(err.message || err))
    }
  }

  const updateAgentConfig = async (agentId, patch = {}) => {
    setStatus('')
    setError('')
    setSavingAgentId(agentId)
    try {
      const next = deepClone(config || {})
      next.projects = next.projects || {}
      next.projects[projectId] = next.projects[projectId] || {}
      const proj = next.projects[projectId]
      proj.active_agents = Array.isArray(proj.active_agents) ? proj.active_agents : []
      proj.agent_settings = proj.agent_settings && typeof proj.agent_settings === 'object' ? proj.agent_settings : {}
      const row = proj.agent_settings[agentId] && typeof proj.agent_settings[agentId] === 'object'
        ? proj.agent_settings[agentId]
        : {}
      proj.agent_settings[agentId] = { ...row, ...(patch.agent_settings || {}) }
      if (typeof patch.active === 'boolean') {
        const set = new Set(proj.active_agents)
        if (patch.active) set.add(agentId)
        else set.delete(agentId)
        proj.active_agents = Array.from(set).sort()
      }
      const saved = await onSaveConfig(next)
      const warnings = Array.isArray(saved?.warnings) ? saved.warnings : []
      setStatus(`已更新 Agent ${agentId}${warnings.length ? `（含 ${warnings.length} 条 warning）` : ''}`)
      await onRefreshAgents?.()
    } catch (err) {
      setError(String(err.message || err))
    } finally {
      setSavingAgentId('')
    }
  }

  const createNewAgent = async () => {
    setStatus('')
    setError('')
    const aid = String(newAgentId || '').trim()
    if (!aid) {
      setError('agent_id is required')
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
      proj.agent_settings = proj.agent_settings && typeof proj.agent_settings === 'object' ? proj.agent_settings : {}
      const old = proj.agent_settings[aid] && typeof proj.agent_settings[aid] === 'object' ? proj.agent_settings[aid] : {}
      proj.agent_settings[aid] = {
        ...old,
        model: String(newAgentModel || MODEL_PRESETS[0]).trim() || MODEL_PRESETS[0],
        phase_strategy: newAgentStrategy === INHERIT_STRATEGY ? null : newAgentStrategy,
      }
      const set = new Set(proj.active_agents)
      if (newAgentActive) set.add(aid)
      proj.active_agents = Array.from(set).sort()
      await onSaveConfig(next)
      setStatus(`已创建 Agent ${aid}`)
      setNewAgentId('')
      setNewAgentDirectives('')
      setNewAgentStrategy(INHERIT_STRATEGY)
      await onRefreshAgents?.()
    } catch (err) {
      setError(String(err.message || err))
    } finally {
      setSavingAgentId('')
    }
  }

  const removeAgent = async (agentId) => {
    if (!window.confirm(`确认删除 agent ${agentId}？`)) return
    setStatus('')
    setError('')
    setDeletingAgentId(agentId)
    try {
      await deleteAgent(agentId)
      setStatus(`已删除 Agent ${agentId}`)
      await onRefreshAgents?.()
    } catch (err) {
      setError(String(err.message || err))
    } finally {
      setDeletingAgentId('')
    }
  }

  return (
    <div className="stack-lg">
      <div className="panel">
        <h3>Project Lifecycle</h3>
        <div className="row-between">
          <div>Current Project: <span className="mono">{projectId}</span></div>
          <div>Status: <span className={`chip ${isRunning ? 'ok' : 'off'}`}>{isRunning ? 'Running' : 'Stopped'}</span></div>
        </div>
        <div className="action-row top-gap">
          <button className="primary-btn" onClick={() => setRunning(true)}>Start</button>
          <button className="ghost-btn" onClick={() => setRunning(false)}>Stop</button>
        </div>
      </div>

      <div className="panel">
        <h3>Project Strategy</h3>
        <div className="form-grid">
          <label>
            phase_strategy
            <select value={projectStrategyDraft} onChange={(e) => setProjectStrategyDraft(e.target.value)}>
              {STRATEGY_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
        </div>
        <div className="action-row top-gap">
          <button
            className="primary-btn"
            disabled={savingAgentId === '__project__' || projectStrategyDraft === projectStrategy}
            onClick={saveProjectStrategy}
          >
            {savingAgentId === '__project__' ? 'Saving...' : 'Save Project Strategy'}
          </button>
        </div>
      </div>

      <div className="panel">
        <h3>Hermes Contracts</h3>
        <div className="action-row">
          <label className="identity-row">
            <input
              type="checkbox"
              checked={includeDisabledContracts}
              onChange={(e) => setIncludeDisabledContracts(e.target.checked)}
            />
            Include disabled
          </label>
          <button
            className="ghost-btn"
            disabled={contractsLoading}
            onClick={() => loadContracts(projectId, includeDisabledContracts)}
          >
            {contractsLoading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
        {contractsError && <div className="warn">{contractsError}</div>}
        {!contractsError && !contracts.length && !contractsLoading && (
          <div className="dim top-gap">当前项目没有 Hermes 契约。</div>
        )}
        {!!contracts.length && (
          <div className="table-wrap top-gap">
            <table>
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Version</th>
                  <th>Status</th>
                  <th>Committers</th>
                  <th>Missing</th>
                  <th>Obligations</th>
                  <th>Description</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {contracts.map((row, idx) => {
                  const title = String(row?.title || '-')
                  const version = String(row?.version || '-')
                  const statusVal = String(row?.status || 'active')
                  const committers = Array.isArray(row?.committers) ? row.committers : []
                  const missing = Array.isArray(row?.missing_committers) ? row.missing_committers : []
                  const obligations = Array.isArray(row?.default_obligations) ? row.default_obligations.length : 0
                  const description = String(row?.description || '')
                  return (
                    <tr key={`${title}:${version}:${idx}`}>
                      <td className="mono">{title}</td>
                      <td className="mono">{version}</td>
                      <td>
                        <span className={`chip ${statusVal === 'active' ? 'ok' : 'off'}`}>{statusVal}</span>
                      </td>
                      <td>{committers.join(', ') || '-'}</td>
                      <td>{missing.join(', ') || '-'}</td>
                      <td>{obligations}</td>
                      <td>{description || '-'}</td>
                      <td>
                        <button className="ghost-btn" onClick={() => setSelectedContract(row)}>
                          查看
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Hermes Ports State</h3>
        <div className="action-row">
          <button className="ghost-btn" disabled={portsLoading} onClick={() => loadPorts(projectId)}>
            {portsLoading ? 'Refreshing...' : 'Refresh'}
          </button>
          {portsError && <span className="warn">{portsError}</span>}
        </div>
        <div className="top-gap stack-sm">
          <div><span className="mono">project:</span> {String(portsState?.project_id || projectId)}</div>
          <div><span className="mono">total leases:</span> {portLeases.length}</div>
        </div>
        <div className="top-gap">
          <h4>Owner Summary</h4>
          {!ownerPortSummary.length && <div className="dim">无端口租约</div>}
          {!!ownerPortSummary.length && (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Owner</th>
                    <th>Lease Count</th>
                  </tr>
                </thead>
                <tbody>
                  {ownerPortSummary.map(([owner, count]) => (
                    <tr key={owner}>
                      <td className="mono">{owner}</td>
                      <td>{count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        <div className="top-gap">
          <h4>Port Leases</h4>
          {!portLeases.length && <div className="dim">无端口租约</div>}
          {!!portLeases.length && (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Port</th>
                    <th>Owner</th>
                    <th>Note</th>
                    <th>Created</th>
                    <th>Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {portLeases
                    .slice()
                    .sort((a, b) => Number(a?.port || 0) - Number(b?.port || 0))
                    .map((row, i) => (
                      <tr key={`${row?.owner_id || '-'}:${row?.port || 0}:${i}`}>
                        <td className="mono">{String(row?.port ?? '-')}</td>
                        <td className="mono">{String(row?.owner_id || '-')}</td>
                        <td>{String(row?.note || '-')}</td>
                        <td>{fmtTs(row?.created_at)}</td>
                        <td>{fmtTs(row?.updated_at)}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        <details className="top-gap">
          <summary className="mono">Raw JSON</summary>
          <pre className="json-block top-gap">{JSON.stringify(portsState, null, 2)}</pre>
        </details>
      </div>

      <div className="panel">
        <h3>Create Project</h3>
        <div className="action-row">
          <input value={newProjectId} onChange={(e) => setNewProjectId(e.target.value)} placeholder="new_project_id" />
          <button className="primary-btn" onClick={create}>Create & Switch</button>
        </div>
      </div>

      <div className="panel">
        <h3>Create Agent</h3>
        <div className="form-grid">
          <label>
            agent_id
            <input value={newAgentId} onChange={(e) => setNewAgentId(e.target.value)} placeholder="new_agent_id" />
          </label>
          <label>
            model
            <input
              list="project-model-options"
              value={newAgentModel}
              onChange={(e) => setNewAgentModel(e.target.value)}
              placeholder="model id"
            />
          </label>
          <label>
            phase_strategy
            <select value={newAgentStrategy} onChange={(e) => setNewAgentStrategy(e.target.value)}>
              <option value={INHERIT_STRATEGY}>与项目相同</option>
              {STRATEGY_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          <label className="full-width">
            directives (profile seed)
            <textarea
              rows={4}
              value={newAgentDirectives}
              onChange={(e) => setNewAgentDirectives(e.target.value)}
              placeholder="输入新 agent 的 directives"
            />
          </label>
        </div>
        <div className="action-row top-gap">
          <label className="identity-row">
            <input type="checkbox" checked={newAgentActive} onChange={(e) => setNewAgentActive(e.target.checked)} />
            Create as active agent
          </label>
          <button className="primary-btn" onClick={createNewAgent} disabled={!!savingAgentId}>
            {savingAgentId && savingAgentId === newAgentId.trim() ? 'Creating...' : 'Create Agent'}
          </button>
        </div>
      </div>

      <div className="panel">
        <h3>Agent Control ({projectId})</h3>
        {!allAgentIds.length && <div className="dim">当前项目没有 agent。</div>}
        {!!allAgentIds.length && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Agent</th>
                  <th>State</th>
                  <th>Active</th>
                  <th>Model</th>
                  <th>Strategy</th>
                  <th>Inbox</th>
                  <th>Queue</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {allAgentIds.map((aid) => {
                  const srow = statusMap.get(aid) || {}
                  const cfg = agentSettings?.[aid] || {}
                  const model = String(cfg?.model || MODEL_PRESETS[0])
                  const modelDraft = String(modelDrafts?.[aid] || model)
                  const rawStrategy = String(cfg?.phase_strategy || '').trim()
                  const strategyDraft = String(agentStrategyDrafts?.[aid] || (rawStrategy || INHERIT_STRATEGY))
                  const strategyLabel = rawStrategy || `与项目相同 (${projectStrategy})`
                  const active = activeAgents.includes(aid)
                  const busy = savingAgentId === aid || deletingAgentId === aid
                  return (
                    <tr key={aid}>
                      <td className="mono">{aid}</td>
                      <td>
                        <span className={`chip ${String(srow?.status || 'idle') === 'running' ? 'ok' : 'off'}`}>
                          {srow?.status || 'idle'}
                        </span>
                      </td>
                      <td>
                        <input
                          type="checkbox"
                          checked={active}
                          disabled={busy}
                          onChange={(e) => updateAgentConfig(aid, { active: e.target.checked })}
                        />
                      </td>
                      <td>
                        <input
                          list="project-model-options"
                          value={modelDraft}
                          disabled={busy}
                          onChange={(e) => setModelDrafts((prev) => ({ ...prev, [aid]: e.target.value }))}
                        />
                      </td>
                      <td>
                        <div className="stack-sm">
                          <select
                            value={strategyDraft}
                            disabled={busy}
                            onChange={(e) => setAgentStrategyDrafts((prev) => ({ ...prev, [aid]: e.target.value }))}
                          >
                            <option value={INHERIT_STRATEGY}>与项目相同</option>
                            {STRATEGY_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
                          </select>
                          <div className="dim">{strategyLabel}</div>
                        </div>
                      </td>
                      <td>{srow?.has_pending_inbox ? 'Yes' : 'No'}</td>
                      <td>{Number(srow?.queued_pulse_events || 0)}</td>
                      <td>
                        <div className="action-row wrap-row">
                          <button
                            className="ghost-btn"
                            disabled={busy || active}
                            onClick={() => updateAgentConfig(aid, { active: true })}
                          >
                            Resume
                          </button>
                          <button
                            className="ghost-btn"
                            disabled={busy || !active}
                            onClick={() => updateAgentConfig(aid, { active: false })}
                          >
                            Pause
                          </button>
                          <button
                            className="ghost-btn"
                            disabled={busy || modelDraft === model}
                            onClick={() => updateAgentConfig(aid, { agent_settings: { model: modelDraft } })}
                          >
                            Save Model
                          </button>
                          <button
                            className="ghost-btn"
                            disabled={busy || strategyDraft === (rawStrategy || INHERIT_STRATEGY)}
                            onClick={() => updateAgentConfig(aid, { agent_settings: { phase_strategy: strategyDraft === INHERIT_STRATEGY ? null : strategyDraft } })}
                          >
                            Save Strategy
                          </button>
                          <button
                            className="ghost-btn"
                            disabled={busy}
                            onClick={() => removeAgent(aid)}
                          >
                            {deletingAgentId === aid ? 'Deleting...' : 'Delete'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {status && <div className="panel success-banner">{status}</div>}
      {error && <div className="panel error-banner">{error}</div>}
      {selectedContract && (
        <div className="modal-overlay" onClick={() => setSelectedContract(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="row-between">
              <h3>Hermes Contract Detail</h3>
              <button className="ghost-btn" onClick={() => setSelectedContract(null)}>关闭</button>
            </div>
            <div className="stack-sm">
              <div><span className="mono">title:</span> {String(selectedContract?.title || '-')}</div>
              <div><span className="mono">version:</span> {String(selectedContract?.version || '-')}</div>
              <div><span className="mono">status:</span> {String(selectedContract?.status || '-')}</div>
              <div><span className="mono">description:</span> {String(selectedContract?.description || '-')}</div>
              <div>
                <span className="mono">committers:</span> {asList(selectedContract?.committers).join(', ') || '-'}
              </div>
              <div>
                <span className="mono">required:</span> {asList(selectedContract?.required_committers).join(', ') || '-'}
              </div>
              <div>
                <span className="mono">missing:</span> {asList(selectedContract?.missing_committers).join(', ') || '-'}
              </div>
            </div>
            <div className="top-gap">
              <h4>Default Obligations</h4>
              {!asList(selectedContract?.default_obligations).length && <div className="dim">无</div>}
              {!!asList(selectedContract?.default_obligations).length && (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Summary</th>
                        <th>Provider</th>
                        <th>Endpoint/Tool</th>
                        <th>Mode</th>
                        <th>Timeout(s)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {asList(selectedContract?.default_obligations).map((ob, i) => {
                        const it = obligationSummary(ob)
                        return (
                          <tr key={`${it.id}:${i}`}>
                            <td className="mono">{it.id}</td>
                            <td>{it.summary || '-'}</td>
                            <td>{it.providerType}</td>
                            <td className="mono">{it.endpoint}</td>
                            <td>{it.mode}</td>
                            <td>{it.timeout}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
            <div className="top-gap">
              <h4>Agent-specific Obligations</h4>
              {(() => {
                const rows = flattenAgentObligations(selectedContract?.obligations)
                if (!rows.length) return <div className="dim">无</div>
                return (
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Owner Agent</th>
                          <th>ID</th>
                          <th>Summary</th>
                          <th>Provider</th>
                          <th>Endpoint/Tool</th>
                          <th>Mode</th>
                          <th>Timeout(s)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rows.map((it, i) => (
                          <tr key={`${it.owner}:${it.id}:${i}`}>
                            <td className="mono">{it.owner}</td>
                            <td className="mono">{it.id}</td>
                            <td>{it.summary || '-'}</td>
                            <td>{it.providerType}</td>
                            <td className="mono">{it.endpoint}</td>
                            <td>{it.mode}</td>
                            <td>{it.timeout}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )
              })()}
            </div>
            <details className="top-gap">
              <summary className="mono">Raw JSON</summary>
              <pre className="json-block top-gap">{JSON.stringify(selectedContract, null, 2)}</pre>
            </details>
          </div>
        </div>
      )}
      <datalist id="project-model-options">
        {availableModels.map((m) => <option key={m} value={m} />)}
      </datalist>
    </div>
  )
}
