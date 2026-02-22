import { useMemo, useState } from 'react'
import { createAgent, deleteProject, getConfig, startProject } from '../api/platformApi'

const DEFAULT_PROJECT_ID = 'animal_world_lab'
const ANIMAL_AGENTS = [
  'ground',
  'grass',
  'sheep',
  'tiger',
  'river',
  'rain',
  'sun',
  'wind',
  'tree',
  'flowers',
  'bees',
  'wolves',
  'rabbits',
  'owls',
  'fungi',
  'bacteria',
]

const AGENT_DIRECTIVES = {
  ground: '你负责系统集成与全局状态编排。',
  grass: '你负责草地生长、资源恢复、生产者侧接口。',
  sheep: '你负责羊群摄食、繁殖与种群稳定策略。',
  tiger: '你负责捕食压力、顶层捕食者行为与平衡约束。',
  river: '你负责水循环与河道供水，维持生态水资源稳定。',
  rain: '你负责降水节律与旱涝平衡，为生态提供水分输入。',
  sun: '你负责光照与能量输入，影响生长、行为和昼夜节律。',
  wind: '你负责空气流动、传播与扰动影响，调节局部环境。',
  tree: '你负责树木生长、碳汇与栖息地结构维护。',
  flowers: '你负责开花、授粉依赖关系与季节性资源供给。',
  bees: '你负责授粉网络、采集行为与群体健康。',
  wolves: '你负责中高阶捕食压力，与虎群形成竞争与分工关系。',
  rabbits: '你负责草食小型种群动态，连接底层生产者与捕食者。',
  owls: '你负责夜行捕食与夜间生态观测，补充昼夜行为链路。',
  fungi: '你负责分解循环与土壤养分回补，处理枯落物与残骸。',
  bacteria: '你负责微生物代谢、土壤活性与基础生态化学过程。',
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
      proj.simulation_enabled = true
      proj.simulation_interval_min = 8
      proj.simulation_interval_max = 12
      // 16-agent debug world: raise project LLM lane to avoid apparent stall.
      proj.llm_control_enabled = true
      proj.llm_project_max_concurrency = 8
      proj.llm_project_rate_per_minute = 240
      proj.llm_acquire_timeout_sec = 60
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
      await startProject(pid)
      setStatus(`已完成：${pid}（已启动调度，无需重启）`)
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
              <span style={{ marginLeft: 8 }} className="muted">{ANIMAL_AGENTS.join(' / ')}</span>
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
