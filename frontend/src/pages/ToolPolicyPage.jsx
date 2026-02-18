import { useEffect, useMemo, useState } from 'react'
import { getConfigSchema } from '../api/platformApi'

function deepClone(v) {
  return JSON.parse(JSON.stringify(v ?? null))
}

function resolveDefaultTools(meta, strategy, phase, toolOptions) {
  const byStrategy = meta?.strategy_default_tools
  if (!byStrategy || typeof byStrategy !== 'object') return []
  const phaseMap = byStrategy[strategy]
  if (!phaseMap || typeof phaseMap !== 'object') return []
  const raw = Array.isArray(phaseMap[phase]) ? phaseMap[phase] : []
  return raw.filter((x) => typeof x === 'string' && x.trim() && toolOptions.includes(x))
}

function ensureStrategyPhaseMap(base, strategyPhases, defaultTools, toolOptions) {
  const out = { ...(base || {}) }
  for (const strategy of Object.keys(strategyPhases || {})) {
    const phases = Array.isArray(strategyPhases[strategy]) ? strategyPhases[strategy] : []
    const current = out[strategy] && typeof out[strategy] === 'object' ? { ...out[strategy] } : {}
    for (const phase of phases) {
      if (!Array.isArray(current[phase])) {
        current[phase] = resolveDefaultTools({ strategy_default_tools: defaultTools }, strategy, phase, toolOptions)
      }
    }
    out[strategy] = current
  }
  return out
}

export function ToolPolicyPage({ projectId, config, onSaveConfig }) {
  const [schema, setSchema] = useState(null)
  const [draftProject, setDraftProject] = useState({})
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [selectedStrategy, setSelectedStrategy] = useState('react_graph')

  const currentProject = useMemo(() => deepClone((config?.projects || {})[projectId] || {}), [config, projectId])

  useEffect(() => {
    setDraftProject(currentProject)
  }, [currentProject])

  useEffect(() => {
    let active = true
    setLoading(true)
    getConfigSchema()
      .then((res) => {
        if (!active) return
        setSchema(res)
      })
      .catch((err) => {
        if (!active) return
        setError(String(err.message || err))
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  const toolOptions = schema?.tool_options || []
  const projectFieldMap = new Map((schema?.fields?.project || []).map((x) => [x.key, x]))
  const agentFieldMap = new Map((schema?.fields?.agent || []).map((x) => [x.key, x]))
  const projectPolicyEntry = projectFieldMap.get('tool_policies')
  const agentPolicyEntry = agentFieldMap.get('tool_policies')

  const strategyPhases = projectPolicyEntry?.ui?.strategy_phases || { react_graph: ['global'], freeform: ['global'] }
  const strategyDefaultTools = projectPolicyEntry?.ui?.strategy_default_tools || {}
  const strategies = Object.keys(strategyPhases)

  useEffect(() => {
    if (!strategies.includes(selectedStrategy) && strategies.length) {
      setSelectedStrategy(strategies[0])
    }
  }, [selectedStrategy, strategies])

  const activeAgents = Array.isArray(draftProject?.active_agents) ? draftProject.active_agents : []
  const agentSettings = draftProject?.agent_settings && typeof draftProject.agent_settings === 'object' ? draftProject.agent_settings : {}
  const agentIds = Array.from(new Set([...activeAgents, ...Object.keys(agentSettings)])).sort()

  const projectToolPolicies = ensureStrategyPhaseMap(
    draftProject?.tool_policies && typeof draftProject.tool_policies === 'object' ? draftProject.tool_policies : {},
    strategyPhases,
    strategyDefaultTools,
    toolOptions,
  )

  const save = async () => {
    setSaving(true)
    setStatus('')
    setError('')
    try {
      const next = deepClone(config)
      next.projects = next.projects || {}
      next.projects[projectId] = deepClone(draftProject)
      const res = await onSaveConfig(next)
      const warnings = Array.isArray(res?.warnings) ? res.warnings : []
      setStatus(warnings.length ? `已保存，含 ${warnings.length} 条 warning` : '已保存')
    } catch (err) {
      setError(String(err.message || err))
    } finally {
      setSaving(false)
    }
  }

  const setProjectPhaseTools = (strategy, phase, updater) => {
    setDraftProject((prev) => {
      const tp = ensureStrategyPhaseMap(prev.tool_policies || {}, strategyPhases, strategyDefaultTools, toolOptions)
      const s = { ...(tp[strategy] || {}) }
      s[phase] = updater(Array.isArray(s[phase]) ? s[phase] : [])
      tp[strategy] = s
      return { ...prev, tool_policies: tp }
    })
  }

  return (
    <div className="stack-lg">
      <div className="panel">
        <div className="row-between">
          <h3>Tool Policy ({projectId})</h3>
          <div className="action-row">
            <button
              className="ghost-btn"
              onClick={() => {
                setDraftProject((prev) => ({
                  ...prev,
                  tool_policies: ensureStrategyPhaseMap({}, strategyPhases, strategyDefaultTools, toolOptions),
                }))
              }}
            >
              恢复默认策略工具
            </button>
            <button className="ghost-btn" onClick={() => setDraftProject(currentProject)}>重置</button>
            <button className="primary-btn" onClick={save} disabled={saving}>{saving ? '保存中...' : '保存配置'}</button>
          </div>
        </div>
        <div className="dim">配置路径：tool_policies.&lt;strategy&gt;.&lt;phase&gt;（global 也是 phase）</div>
        {loading && <div className="dim top-gap">加载 schema 中...</div>}
      </div>

      <div className="panel">
        <div className="row-between">
          <h3>Project Strategy Tool Policies</h3>
          <select value={selectedStrategy} onChange={(e) => setSelectedStrategy(e.target.value)}>
            {strategies.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div className="stack-sm top-gap">
          {(strategyPhases[selectedStrategy] || []).map((phase) => {
            const selected = new Set(Array.isArray(projectToolPolicies?.[selectedStrategy]?.[phase]) ? projectToolPolicies[selectedStrategy][phase] : [])
            return (
              <div key={`${selectedStrategy}-${phase}`} className="panel map-card">
                <div className="mono">{phase}</div>
                <div className="tool-checklist top-gap">
                  {toolOptions.map((tool) => (
                    <label key={`${selectedStrategy}-${phase}-${tool}`} className="checkbox-row inline-row">
                      <input
                        type="checkbox"
                        checked={selected.has(tool)}
                        onChange={(e) => {
                          setProjectPhaseTools(selectedStrategy, phase, (current) => {
                            const set = new Set(Array.isArray(current) ? current : [])
                            if (e.target.checked) set.add(tool)
                            else set.delete(tool)
                            return Array.from(set)
                          })
                        }}
                      />
                      <span className="mono">{tool}</span>
                    </label>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <div className="panel">
        <h3>Agent Strategy Tool Policies (override)</h3>
        {!agentIds.length && <div className="dim">当前无 agent（可先在项目中激活 agent）</div>}
        <div className="stack-sm">
          {agentIds.map((aid) => {
            const row = agentSettings[aid] || {}
            const disabled = new Set(Array.isArray(row.disabled_tools) ? row.disabled_tools : [])
            const basePolicies = row.tool_policies && typeof row.tool_policies === 'object' ? row.tool_policies : {}
            const policies = ensureStrategyPhaseMap(
              basePolicies,
              agentPolicyEntry?.ui?.strategy_phases || strategyPhases,
              agentPolicyEntry?.ui?.strategy_default_tools || strategyDefaultTools,
              toolOptions,
            )
            return (
              <div key={aid} className="panel map-card">
                <div className="mono">{aid}</div>
                <div className="top-gap dim">工具启用（勾选=启用）</div>
                <div className="tool-checklist top-gap">
                  {toolOptions.map((tool) => (
                    <label key={`${aid}-enabled-${tool}`} className="checkbox-row inline-row">
                      <input
                        type="checkbox"
                        checked={!disabled.has(tool)}
                        onChange={(e) => {
                          setDraftProject((prev) => {
                            const aset = { ...(prev.agent_settings || {}) }
                            const cur = { ...(aset[aid] || {}) }
                            const set = new Set(Array.isArray(cur.disabled_tools) ? cur.disabled_tools : [])
                            if (e.target.checked) set.delete(tool)
                            else set.add(tool)
                            cur.disabled_tools = Array.from(set)
                            aset[aid] = cur
                            return { ...prev, agent_settings: aset }
                          })
                        }}
                      />
                      <span className="mono">{tool}</span>
                    </label>
                  ))}
                </div>

                <div className="top-gap dim">策略阶段白名单（当前: {selectedStrategy}）</div>
                <div className="stack-sm top-gap">
                  {(strategyPhases[selectedStrategy] || []).map((phase) => {
                    const selected = new Set(Array.isArray(policies?.[selectedStrategy]?.[phase]) ? policies[selectedStrategy][phase] : [])
                    return (
                      <div key={`${aid}-${selectedStrategy}-${phase}`} className="panel map-card">
                        <div className="mono">{phase}</div>
                        <div className="tool-checklist top-gap">
                          {toolOptions.map((tool) => (
                            <label key={`${aid}-${selectedStrategy}-${phase}-${tool}`} className="checkbox-row inline-row">
                              <input
                                type="checkbox"
                                checked={selected.has(tool)}
                                onChange={(e) => {
                                  setDraftProject((prev) => {
                                    const aset = { ...(prev.agent_settings || {}) }
                                    const cur = { ...(aset[aid] || {}) }
                                    const tp = ensureStrategyPhaseMap(cur.tool_policies || {}, strategyPhases, strategyDefaultTools, toolOptions)
                                    const s = { ...(tp[selectedStrategy] || {}) }
                                    const set = new Set(Array.isArray(s[phase]) ? s[phase] : [])
                                    if (e.target.checked) set.add(tool)
                                    else set.delete(tool)
                                    s[phase] = Array.from(set)
                                    tp[selectedStrategy] = s
                                    cur.tool_policies = tp
                                    aset[aid] = cur
                                    return { ...prev, agent_settings: aset }
                                  })
                                }}
                              />
                              <span className="mono">{tool}</span>
                            </label>
                          ))}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {status && <div className="panel success-banner">{status}</div>}
      {error && <div className="panel error-banner">{error}</div>}
    </div>
  )
}
