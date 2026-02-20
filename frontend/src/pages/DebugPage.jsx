import { useMemo, useState } from 'react'
import { createAgent, deleteProject, getConfig } from '../api/platformApi'

const DEFAULT_PROJECT_ID = 'animal_world_lab'
const ANIMAL_AGENTS = ['ground', 'grass', 'sheep', 'tiger']

const AGENT_DIRECTIVES = {
  ground: '你负责系统集成与全局状态编排。',
  grass: '你负责草地生长、资源恢复、生产者侧接口。',
  sheep: '你负责羊群摄食、繁殖与种群稳定策略。',
  tiger: '你负责捕食压力、顶层捕食者行为与平衡约束。',
}

function deepClone(x) {
  return JSON.parse(JSON.stringify(x || {}))
}

export function DebugPage({ config, onCreateProject, onSaveConfig }) {
  const [projectId, setProjectId] = useState(DEFAULT_PROJECT_ID)
  const [createAgents, setCreateAgents] = useState(true)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')
  const existingProjects = useMemo(() => Object.keys(config?.projects || {}), [config])

  const handleCreateAnimalWorld = async () => {
    const pid = String(projectId || '').trim()
    if (!pid) return
    setBusy(true)
    setStatus('正在创建项目...')
    try {
      if (existingProjects.includes(pid) && pid !== 'default') {
        setStatus(`检测到已存在项目 ${pid}，正在删除旧项目...`)
        await deleteProject(pid)
      }
      await onCreateProject(pid)
      const latest = await getConfig()
      const next = deepClone(latest)
      next.current_project = pid
      next.projects = next.projects || {}
      next.projects[pid] = next.projects[pid] || {}

      const proj = next.projects[pid]
      proj.name = proj.name || 'Animal World Lab'
      proj.phase_strategy = proj.phase_strategy || 'react_graph'
      proj.context_strategy = 'sequential_v1'
      proj.simulation_enabled = false
      proj.active_agents = createAgents ? [...ANIMAL_AGENTS] : (Array.isArray(proj.active_agents) ? proj.active_agents : [])
      proj.agent_settings = proj.agent_settings && typeof proj.agent_settings === 'object' ? proj.agent_settings : {}

      for (const aid of ANIMAL_AGENTS) {
        proj.agent_settings[aid] = proj.agent_settings[aid] || {}
      }

      await onSaveConfig(next)

      if (createAgents) {
        for (const aid of ANIMAL_AGENTS) {
          try {
            await createAgent(aid, AGENT_DIRECTIVES[aid] || '')
          } catch {
            // Ignore "Agent exists" and continue for idempotent bootstrap.
          }
        }
      }
      setStatus(`已完成：${pid}（未执行任何重启）`)
    } catch (e) {
      setStatus(`失败：${String(e?.message || e)}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page-stack">
      <section className="panel">
        <h2>Debug Tools</h2>
        <p className="muted">
          该页面仅用于调试初始化。不会触发任何运行时重启流程。
        </p>
      </section>

      <section className="panel top-gap">
        <h3>Animal World Bootstrap</h3>
        <div className="form-grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
          <label>
            Project ID
            <input
              className="glass-input"
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              placeholder={DEFAULT_PROJECT_ID}
            />
          </label>
          <label>
            Create Default Agents
            <div style={{ display: 'flex', alignItems: 'center', minHeight: 42 }}>
              <input
                type="checkbox"
                checked={createAgents}
                onChange={(e) => setCreateAgents(Boolean(e.target.checked))}
              />
              <span style={{ marginLeft: 8 }} className="muted">ground / grass / sheep / tiger</span>
            </div>
          </label>
        </div>

        <div className="top-gap">
          <button className="primary-btn" onClick={handleCreateAnimalWorld} disabled={busy || !String(projectId || '').trim()}>
            {busy ? '处理中...' : '新建动物世界项目（无重启）'}
          </button>
        </div>

        {status && <div className="top-gap muted">{status}</div>}
      </section>

      <section className="panel top-gap">
        <h3>Projects</h3>
        <div className="mono" style={{ whiteSpace: 'pre-wrap' }}>
          {existingProjects.length ? existingProjects.join('\n') : '(empty)'}
        </div>
      </section>
    </div>
  )
}
