import { useEffect, useMemo, useState } from 'react'
import { getConfigSchema } from '../api/platformApi'

function deepClone(v) {
  return JSON.parse(JSON.stringify(v ?? null))
}

function toLabel(k) {
  return String(k || '').replace(/_/g, ' ').replace(/\b\w/g, (m) => m.toUpperCase())
}

function castNumber(raw, type) {
  const n = type === 'integer' ? parseInt(raw, 10) : parseFloat(raw)
  return Number.isFinite(n) ? n : 0
}

function cloneDefault(v) {
  if (v === undefined) return undefined
  return deepClone(v)
}

function defaultText(v) {
  if (v === undefined) return '(registry 未提供)'
  if (v === null) return 'null'
  if (typeof v === 'string') return v
  return JSON.stringify(v)
}

function FieldEditor({ entry, value, onChange, toolOptions }) {
  const { type, nullable, enum: enumOptions } = entry

  if (nullable && value === null) {
    return (
      <div className="action-row">
        <span className="dim">null</span>
        <button className="ghost-btn" onClick={() => onChange(cloneDefault(entry.default) ?? '')}>恢复</button>
      </div>
    )
  }

  if (type === 'boolean') {
    return (
      <label className="checkbox-row inline-row">
        <input type="checkbox" checked={!!value} onChange={(e) => onChange(!!e.target.checked)} />
        <span>{value ? 'enabled' : 'disabled'}</span>
      </label>
    )
  }

  if (type === 'integer' || type === 'number') {
    return (
      <div className="action-row">
        <input
          type="number"
          value={value ?? 0}
          onChange={(e) => {
            const raw = e.target.value
            if (raw === '' && nullable) {
              onChange(null)
              return
            }
            onChange(castNumber(raw, type))
          }}
        />
        {nullable && <button className="ghost-btn" onClick={() => onChange(null)}>设为 null</button>}
      </div>
    )
  }

  if (type === 'string') {
    return (
      <div className="action-row">
        {Array.isArray(enumOptions) && enumOptions.length ? (
          <select value={value ?? ''} onChange={(e) => onChange(e.target.value)}>
            {nullable && <option value="">(null)</option>}
            {enumOptions.map((x) => <option key={x} value={x}>{x}</option>)}
          </select>
        ) : (
          <input type="text" value={value ?? ''} onChange={(e) => onChange(e.target.value)} />
        )}
        {nullable && <button className="ghost-btn" onClick={() => onChange(null)}>设为 null</button>}
      </div>
    )
  }

  if (type === 'array' && entry.key === 'disabled_tools' && Array.isArray(toolOptions) && toolOptions.length) {
    const selected = new Set(Array.isArray(value) ? value : [])
    return (
      <div className="tool-checklist">
        {toolOptions.map((name) => (
          <label key={name} className="checkbox-row inline-row">
            <input
              type="checkbox"
              checked={selected.has(name)}
              onChange={(e) => {
                const next = new Set(selected)
                if (e.target.checked) next.add(name)
                else next.delete(name)
                onChange(Array.from(next))
              }}
            />
            <span className="mono">{name}</span>
          </label>
        ))}
      </div>
    )
  }

  if (type === 'object' && entry.key === 'pulse_priority_weights') {
    const obj = value && typeof value === 'object' && !Array.isArray(value) ? value : {}
    const defaults = {
      mail_event: 100,
      manual: 80,
      system: 60,
      timer: 10,
    }
    const keys = ['mail_event', 'manual', 'system', 'timer']
    return (
      <div className="stack-sm">
        {keys.map((k) => (
          <label key={k} className="config-inline-field">
            <span className="mono">{k}</span>
            <input
              type="number"
              value={obj[k] ?? defaults[k]}
              onChange={(e) => {
                const next = parseInt(e.target.value || '0', 10)
                onChange({ ...obj, [k]: Number.isFinite(next) ? next : defaults[k] })
              }}
            />
          </label>
        ))}
      </div>
    )
  }

  return (
    <textarea
      rows={type === 'object' ? 8 : 5}
      value={JSON.stringify(value ?? (type === 'array' ? [] : {}), null, 2)}
      onChange={(e) => {
        try {
          onChange(JSON.parse(e.target.value))
        } catch {
          // ignore invalid JSON until valid
        }
      }}
    />
  )
}

export function ConfigCenterPage({ projectId, config, onSaveConfig }) {
  const [schema, setSchema] = useState(null)
  const [draftProject, setDraftProject] = useState({})
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(false)
  const [showDeprecated, setShowDeprecated] = useState(false)
  const [viewMode, setViewMode] = useState('module')

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

  const projectFields = schema?.fields?.project || []
  const groups = schema?.groups?.filter((g) => g.scope === 'project') || []
  const moduleGroups = schema?.module_groups?.filter((g) => g.scope === 'project') || []
  const toolOptions = schema?.tool_options || []
  const toolManagedKeys = new Set([
    'tool_loop_max',
    'tool_policies',
    'agent_settings',
    'hermes_allow_agent_tool_provider',
    'hermes_enabled',
    'hermes_default_timeout_sec',
    'hermes_default_rate_per_minute',
    'hermes_default_max_concurrency',
  ])

  const fieldMap = useMemo(() => {
    const m = new Map()
    for (const f of projectFields) m.set(f.key, f)
    return m
  }, [projectFields])

  const groupedKeys = useMemo(() => {
    const s = new Set()
    groups.forEach((g) => (g.keys || []).forEach((k) => s.add(k)))
    moduleGroups.forEach((g) => (g.keys || []).forEach((k) => s.add(k)))
    return s
  }, [groups, moduleGroups])

  const otherFields = projectFields.filter((f) => !groupedKeys.has(f.key) && !toolManagedKeys.has(f.key))
  const agentSettings = draftProject?.agent_settings && typeof draftProject.agent_settings === 'object'
    ? draftProject.agent_settings
    : {}
  const activeAgents = Array.isArray(draftProject?.active_agents) ? draftProject.active_agents : []
  const agentIds = Array.from(new Set([...activeAgents, ...Object.keys(agentSettings)])).sort()

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
      setStatus(warnings.length ? `已保存，含 ${warnings.length} 条 warning（含 deprecated 项）` : '已保存')
    } catch (err) {
      setError(String(err.message || err))
    } finally {
      setSaving(false)
    }
  }

  const renderEntry = (entry) => {
    const deprecated = entry.status === 'deprecated'
    if (deprecated && !showDeprecated) return null
    return (
      <div key={entry.key} className="config-field">
        <div className="row-between">
          <div className="config-label">{toLabel(entry.key)}</div>
          <div className="action-row">
            {deprecated && <span className="chip off">deprecated</span>}
            <button
              className="ghost-btn"
              onClick={() => {
                const dv = cloneDefault(entry.default)
                setDraftProject((prev) => ({ ...prev, [entry.key]: dv }))
              }}
            >
              恢复默认
            </button>
          </div>
        </div>
        <div className="dim top-gap">{entry.description}</div>
        <div className="mono dim top-gap">default: {defaultText(entry.default)}</div>
        {!!entry.runtime_used_by?.length && (
          <div className="mono dim top-gap">used_by: {entry.runtime_used_by.join(', ')}</div>
        )}
        <div className="top-gap">
          <FieldEditor
            entry={entry}
            value={draftProject?.[entry.key]}
            onChange={(next) => setDraftProject((prev) => ({ ...prev, [entry.key]: next }))}
            toolOptions={toolOptions}
          />
        </div>
      </div>
    )
  }

  const renderAgentTools = () => {
    if (!toolOptions.length) return null
    return (
      <div className="panel">
        <div className="row-between">
          <h3>Tool Policies (Agent)</h3>
          <button
            className="ghost-btn"
            onClick={() => {
              const agentId = window.prompt('输入 agent_id')
              const aid = String(agentId || '').trim()
              if (!aid) return
              setDraftProject((prev) => ({
                ...prev,
                agent_settings: {
                  ...(prev.agent_settings || {}),
                  [aid]: {
                    ...(prev.agent_settings?.[aid] || {}),
                    disabled_tools: Array.isArray(prev.agent_settings?.[aid]?.disabled_tools)
                      ? prev.agent_settings[aid].disabled_tools
                      : [],
                  },
                },
              }))
            }}
          >
            新增 Agent Tool 配置
          </button>
        </div>

        {!agentIds.length && <div className="dim">当前没有 active_agents 或 agent_settings 条目。</div>}
        <div className="stack-sm">
          {agentIds.map((aid) => {
            const row = agentSettings?.[aid] || {}
            const disabled = new Set(Array.isArray(row.disabled_tools) ? row.disabled_tools : [])
            return (
              <div key={aid} className="panel map-card">
                <div className="row-between">
                  <div className="mono">{aid}</div>
                  <button
                    className="ghost-btn"
                    onClick={() => {
                      setDraftProject((prev) => {
                        const next = { ...(prev.agent_settings || {}) }
                        delete next[aid]
                        return { ...prev, agent_settings: next }
                      })
                    }}
                  >
                    删除 Agent 配置
                  </button>
                </div>

                <div className="top-gap dim">启用工具（取消勾选即禁用）</div>
                <div className="tool-checklist top-gap">
                  {toolOptions.map((name) => (
                    <label key={`${aid}-tool-${name}`} className="checkbox-row inline-row">
                      <input
                        type="checkbox"
                        checked={!disabled.has(name)}
                        onChange={(e) => {
                          setDraftProject((prev) => {
                            const all = { ...(prev.agent_settings || {}) }
                            const cur = { ...(all[aid] || {}) }
                            const d = new Set(Array.isArray(cur.disabled_tools) ? cur.disabled_tools : [])
                            if (e.target.checked) d.delete(name)
                            else d.add(name)
                            cur.disabled_tools = Array.from(d)
                            all[aid] = cur
                            return { ...prev, agent_settings: all }
                          })
                        }}
                      />
                      <span className="mono">{name}</span>
                    </label>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  return (
    <div className="stack-lg">
      <div className="panel">
        <div className="row-between">
          <h3>Config Center ({projectId})</h3>
          <div className="action-row">
            <button className="ghost-btn" onClick={() => setViewMode((v) => (v === 'module' ? 'group' : 'module'))}>
              {viewMode === 'module' ? '切换为业务分组' : '切换为模块分组'}
            </button>
            <button className="ghost-btn" onClick={() => setShowDeprecated((v) => !v)}>
              {showDeprecated ? '隐藏 Deprecated' : '显示 Deprecated'}
            </button>
            <button
              className="ghost-btn"
              onClick={() => {
                const next = deepClone(draftProject || {})
                for (const entry of projectFields) {
                  if (entry.default !== undefined) next[entry.key] = cloneDefault(entry.default)
                }
                setDraftProject(next)
              }}
            >
              全部恢复默认
            </button>
            <button className="ghost-btn" onClick={() => setDraftProject(currentProject)}>重置</button>
            <button className="primary-btn" onClick={save} disabled={saving}>{saving ? '保存中...' : '保存配置'}</button>
          </div>
        </div>
        <div className="dim">Registry schema version: {schema?.version || '-'} | zero-compat strict mode</div>
        {loading && <div className="top-gap dim">加载 schema 中...</div>}
      </div>

      {(viewMode === 'module' ? moduleGroups : groups).map((g) => {
        if (g.id === 'tools') return null
        const entries = (g.keys || [])
          .map((k) => fieldMap.get(k))
          .filter((x) => x && !toolManagedKeys.has(x.key))
        if (!entries.length) return null
        return (
          <div key={g.id} className="panel">
            <h3>{g.title}</h3>
            <div className="stack-sm">
              {entries.map((e) => renderEntry(e))}
            </div>
          </div>
        )
      })}

      {!!otherFields.length && (
        <div className="panel">
          <h3>Other</h3>
          <div className="stack-sm">
            {otherFields.map((e) => renderEntry(e))}
          </div>
        </div>
      )}

      <div className="panel">
        <h3>Raw JSON (Fallback)</h3>
        <textarea
          rows={18}
          value={JSON.stringify(draftProject || {}, null, 2)}
          onChange={(e) => {
            try {
              setDraftProject(JSON.parse(e.target.value))
            } catch {
              // ignore invalid JSON until valid
            }
          }}
        />
      </div>

      {status && <div className="panel success-banner">{status}</div>}
      {error && <div className="panel error-banner">{error}</div>}
    </div>
  )
}
