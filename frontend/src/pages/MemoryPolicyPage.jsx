import { useEffect, useMemo, useState } from 'react'
import {
  getMemoryPolicy,
  getMemoryTemplates,
  getTemplateVars,
  updateMemoryPolicyRule,
  updateMemoryTemplate,
} from '../api/platformApi'

export function MemoryPolicyPage({ projectId }) {
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')

  const [templates, setTemplates] = useState({ runtime_log: {}, chronicle: {} })
  const [policy, setPolicy] = useState({})
  const [selectedIntentKey, setSelectedIntentKey] = useState('')
  const [selectedScope, setSelectedScope] = useState('runtime_log')
  const [selectedTemplateKey, setSelectedTemplateKey] = useState('')
  const [templateBody, setTemplateBody] = useState('')
  const [varsInfo, setVarsInfo] = useState({ guaranteed_vars: [], optional_vars: [], observed_vars: [] })
  const [ruleDraft, setRuleDraft] = useState({
    to_chronicle: false,
    to_runtime_log: true,
    chronicle_template_key: '',
    runtime_log_template_key: '',
  })

  const loadAll = async () => {
    const [tpl, pol] = await Promise.all([getMemoryTemplates(projectId), getMemoryPolicy(projectId)])
    const nextTemplates = { runtime_log: tpl.runtime_log || {}, chronicle: tpl.chronicle || {} }
    const nextPolicy = pol.items || {}
    setTemplates(nextTemplates)
    setPolicy(nextPolicy)
    const intentKeys = Object.keys(nextPolicy).sort()
    const intent = intentKeys.includes(selectedIntentKey) ? selectedIntentKey : (intentKeys[0] || '')
    setSelectedIntentKey(intent)
  }

  useEffect(() => {
    loadAll().catch((err) => setError(String(err.message || err)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

  useEffect(() => {
    const rule = policy[selectedIntentKey] || {}
    const nextDraft = {
      to_chronicle: !!rule.to_chronicle,
      to_runtime_log: !!rule.to_runtime_log,
      chronicle_template_key: String(rule.chronicle_template_key || ''),
      runtime_log_template_key: String(rule.runtime_log_template_key || ''),
    }
    setRuleDraft(nextDraft)
    if (!selectedIntentKey || !projectId) {
      setVarsInfo({ guaranteed_vars: [], optional_vars: [], observed_vars: [] })
      return
    }
    getTemplateVars(projectId, selectedIntentKey || '').then((d) => {
      setVarsInfo({
        guaranteed_vars: d.guaranteed_vars || [],
        optional_vars: d.optional_vars || [],
        observed_vars: d.observed_vars || [],
      })
    }).catch(() => {
      setVarsInfo({ guaranteed_vars: [], optional_vars: [], observed_vars: [] })
    })
  }, [policy, projectId, selectedIntentKey])

  const intentKeys = useMemo(() => Object.keys(policy || {}).sort(), [policy])
  const templateKeys = useMemo(() => Object.keys((templates || {})[selectedScope] || {}).sort(), [selectedScope, templates])

  useEffect(() => {
    const viaRule = selectedScope === 'chronicle'
      ? ruleDraft.chronicle_template_key
      : ruleDraft.runtime_log_template_key
    const key = (viaRule && templateKeys.includes(viaRule)) ? viaRule : (templateKeys[0] || '')
    setSelectedTemplateKey(key)
    setTemplateBody(key ? String((templates[selectedScope] || {})[key] || '') : '')
  }, [ruleDraft, selectedScope, templateKeys, templates])

  const savePolicy = async () => {
    setStatus('')
    setError('')
    try {
      if (!selectedIntentKey) throw new Error('intent_key is required')
      await updateMemoryPolicyRule(projectId, selectedIntentKey, ruleDraft)
      setStatus(`Policy updated: ${selectedIntentKey}`)
      await loadAll()
    } catch (err) {
      setError(String(err.message || err))
    }
  }

  const quickUpdatePolicy = async (intentKey, patch) => {
    setStatus('')
    setError('')
    try {
      await updateMemoryPolicyRule(projectId, intentKey, patch)
      setStatus(`Policy updated: ${intentKey}`)
      await loadAll()
    } catch (err) {
      setError(String(err.message || err))
    }
  }

  const saveTemplate = async () => {
    setStatus('')
    setError('')
    try {
      const key = selectedTemplateKey.trim()
      if (!key) throw new Error('template key is required')
      await updateMemoryTemplate(projectId, selectedScope, key, templateBody)
      setStatus(`Template saved: ${selectedScope}/${key}`)
      await loadAll()
    } catch (err) {
      setError(String(err.message || err))
    }
  }

  const insertVar = (name) => {
    setTemplateBody((prev) => `${prev}$${name}`)
  }

  const onTemplateKeySelect = (key) => {
    const k = String(key || '')
    setSelectedTemplateKey(k)
    setTemplateBody(k ? String((templates[selectedScope] || {})[k] || '') : '')
  }

  return (
    <div className="stack-lg">
      <div className="panel">
        <div className="row-between">
          <h3>Memory Template Studio</h3>
          <button className="ghost-btn" onClick={() => loadAll().catch((err) => setError(String(err.message || err)))}>Reload</button>
        </div>
        <div className="form-grid top-gap">
          <label>
            Intent Key
            <select value={selectedIntentKey} onChange={(e) => setSelectedIntentKey(e.target.value)}>
              {!intentKeys.length && <option value="">(no intent keys)</option>}
              {intentKeys.map((k) => <option key={k} value={k}>{k}</option>)}
            </select>
          </label>
          <label>
            Scope
            <select value={selectedScope} onChange={(e) => setSelectedScope(e.target.value)}>
              <option value="runtime_log">runtime_log_templates.json</option>
              <option value="chronicle">chronicle_templates.json</option>
            </select>
          </label>
          <label>
            to_runtime_log
            <select value={ruleDraft.to_runtime_log ? 'true' : 'false'} onChange={(e) => setRuleDraft((x) => ({ ...x, to_runtime_log: e.target.value === 'true' }))}>
              <option value="true">true</option>
              <option value="false">false</option>
            </select>
          </label>
          <label>
            to_chronicle
            <select value={ruleDraft.to_chronicle ? 'true' : 'false'} onChange={(e) => setRuleDraft((x) => ({ ...x, to_chronicle: e.target.value === 'true' }))}>
              <option value="true">true</option>
              <option value="false">false</option>
            </select>
          </label>
          <label>
            runtime_log_template_key
            <input value={ruleDraft.runtime_log_template_key} onChange={(e) => setRuleDraft((x) => ({ ...x, runtime_log_template_key: e.target.value }))} />
          </label>
          <label>
            chronicle_template_key
            <input value={ruleDraft.chronicle_template_key} onChange={(e) => setRuleDraft((x) => ({ ...x, chronicle_template_key: e.target.value }))} />
          </label>
        </div>
        <div className="action-row top-gap">
          <button className="primary-btn" onClick={savePolicy}>Save Binding</button>
        </div>
        <div className="action-row top-gap">
          <label className="stack-sm">
            Scope
            <select value={selectedScope} onChange={(e) => setSelectedScope(e.target.value)}>
              <option value="runtime_log">runtime_log_templates.json</option>
              <option value="chronicle">chronicle_templates.json</option>
            </select>
          </label>
          <label className="stack-sm grow">
            Template Key
            <select value={selectedTemplateKey} onChange={(e) => onTemplateKeySelect(e.target.value)}>
              {!templateKeys.length && <option value="">(no templates)</option>}
              {templateKeys.map((k) => <option key={k} value={k}>{k}</option>)}
            </select>
          </label>
          <label className="stack-sm grow">
            Or New Key
            <input value={selectedTemplateKey} onChange={(e) => setSelectedTemplateKey(e.target.value)} placeholder="memory_custom_key" />
          </label>
        </div>
        <textarea
          className="top-gap"
          style={{ width: '100%', minHeight: 180 }}
          value={templateBody}
          onChange={(e) => setTemplateBody(e.target.value)}
          placeholder="Template body, supports $placeholder variables"
        />
        <div className="action-row top-gap">
          <button className="primary-btn" onClick={saveTemplate}>Save Template</button>
          {selectedIntentKey && (
            <button
              className="ghost-btn"
              onClick={() => {
                if (selectedScope === 'runtime_log') {
                  setRuleDraft((x) => ({ ...x, runtime_log_template_key: selectedTemplateKey }))
                } else {
                  setRuleDraft((x) => ({ ...x, chronicle_template_key: selectedTemplateKey }))
                }
              }}
            >
              Use As Selected Intent Template
            </button>
          )}
        </div>
        <div className="top-gap">
          <div className="dim">可用变量（点击插入）</div>
          <div className="action-row top-gap" style={{ flexWrap: 'wrap' }}>
            {varsInfo.guaranteed_vars.map((v) => <button key={`g-${v}`} className="ghost-btn" onClick={() => insertVar(v)}>${v}</button>)}
            {varsInfo.optional_vars.map((v) => <button key={`o-${v}`} className="ghost-btn" onClick={() => insertVar(v)}>${v}</button>)}
            {varsInfo.observed_vars.map((v) => <button key={`x-${v}`} className="ghost-btn" onClick={() => insertVar(v)}>${v}</button>)}
          </div>
        </div>
      </div>

      <div className="panel">
        <h3>Memory Policy Matrix</h3>
        <div className="dim">可直接开关“是否写入日志/记忆”，并修改模板 key</div>
        <div className="table-wrap top-gap">
          <table>
            <thead>
              <tr>
                <th>intent_key</th>
                <th>to_runtime_log</th>
                <th>to_chronicle</th>
                <th>runtime_log_template_key</th>
                <th>chronicle_template_key</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {intentKeys.map((key) => {
                const row = policy[key] || {}
                const toRuntime = !!row.to_runtime_log
                const toChronicle = !!row.to_chronicle
                const runtimeKey = String(row.runtime_log_template_key || '')
                const chronicleKey = String(row.chronicle_template_key || '')
                return (
                  <tr key={key}>
                    <td className="mono">{key}</td>
                    <td><input type="checkbox" checked={toRuntime} onChange={(e) => quickUpdatePolicy(key, { to_runtime_log: e.target.checked })} /></td>
                    <td><input type="checkbox" checked={toChronicle} onChange={(e) => quickUpdatePolicy(key, { to_chronicle: e.target.checked })} /></td>
                    <td className="mono">{runtimeKey || '-'}</td>
                    <td className="mono">{chronicleKey || '-'}</td>
                    <td>
                      <button
                        className="ghost-btn"
                        onClick={() => {
                          setSelectedIntentKey(key)
                          setRuleDraft({
                            to_runtime_log: toRuntime,
                            to_chronicle: toChronicle,
                            runtime_log_template_key: runtimeKey,
                            chronicle_template_key: chronicleKey,
                          })
                        }}
                      >
                        编辑
                      </button>
                    </td>
                  </tr>
                )
              })}
              {!intentKeys.length && <tr><td colSpan={6}>No policy rules</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      {status && <div className="panel success-banner">{status}</div>}
      {error && <div className="panel error-banner">{error}</div>}
    </div>
  )
}
