import { useMemo, useState } from 'react'
import { GitBranch, Link2 } from 'lucide-react'
import { createAgent, deleteAgent, gatewaySendMessage, setProjectAgentActive, updateSocialEdge } from '../../../api/platformApi'
import { SuccessBanner } from '../../../components/feedback/SuccessBanner'
import { ErrorBanner } from '../../../components/feedback/ErrorBanner'
import { MetricCard } from '../../../components/ui/MetricCard'
import { SectionHeader } from '../../../components/ui/SectionHeader'
import { deepClone } from '../../../utils/deepClone'
import { selectAgentSettingsMap, selectGalaxyMetrics, selectSelectedAgent } from '../../../store/app/selectors'
import { useGalaxyGraph } from '../hooks/useGalaxyGraph'
import { useGalaxyLayout } from '../hooks/useGalaxyLayout'
import { useGalaxyMotion } from '../hooks/useGalaxyMotion'
import { useGalaxySelection } from '../hooks/useGalaxySelection'
import { ProjectCockpitPanel } from '../panels/ProjectCockpitPanel'
import { GalaxyInspectorPanel } from '../panels/GalaxyInspectorPanel'
import { GalaxyActivityPanel } from '../panels/GalaxyActivityPanel'
import { GalaxyInfrastructurePanel } from '../panels/GalaxyInfrastructurePanel'
import { GalaxyScene } from './GalaxyScene'

const MODEL_PRESETS = [
  'stepfun/step-3.5-flash:free',
  'openai/gpt-4o-mini',
  'openai/gpt-4.1-mini',
  'anthropic/claude-3.5-haiku',
]

const INHERIT_STRATEGY = '__inherit__'
const AGENT_ID_RE = /^[a-z][a-z0-9_]{0,63}$/
const HUMAN_IDENTITY = 'human.overseer'

export function AgentGalaxyPage({
  projectId,
  config,
  onSaveConfig,
  onCreateProject,
  onDeleteProject,
  onSetRunning,
  isRunning,
  agentRows = [],
  selectedAgentId = '',
  onSelectAgent,
  onRefreshAgents,
}) {
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [linkModeSource, setLinkModeSource] = useState('')
  const [newProjectId, setNewProjectId] = useState('')
  const [viewport, setViewport] = useState({ width: 960, height: 620 })
  const [newAgent, setNewAgent] = useState({
    id: '',
    model: MODEL_PRESETS[0],
    strategy: INHERIT_STRATEGY,
    directives: '',
  })

  const currentProjectConfig = (config?.projects || {})[projectId] || {}
  const agentSettings = selectAgentSettingsMap(config, projectId)
  const selectedAgent = selectSelectedAgent(agentRows, selectedAgentId)
  const selectedConfig = selectedAgent ? (agentSettings[selectedAgent.agent_id] || {}) : {}
  const { workspace, workspaceLoading, workspaceError, refreshWorkspace } = useGalaxyGraph(projectId, agentRows)
  const { reducedMotion } = useGalaxyMotion()
  const metrics = useMemo(
    () => workspace?.metrics || selectGalaxyMetrics(agentRows, workspace?.graph?.matrix || {}),
    [agentRows, workspace],
  )
  const { selectedModel, setSelectedModel, selectedStrategy, setSelectedStrategy, messageDraft, setMessageDraft } = useGalaxySelection(
    selectedAgent,
    selectedConfig,
    MODEL_PRESETS[0],
  )
  const positions = useGalaxyLayout(agentRows, viewport, selectedAgentId)
  const graphNodes = Array.isArray(workspace?.graph?.nodes) ? workspace.graph.nodes : []
  const connections = []
  Object.entries(workspace?.graph?.matrix || {}).forEach(([sourceId, row]) => {
    Object.entries(row || {}).forEach(([targetId, weight]) => {
      if (!positions[sourceId] || !positions[targetId] || Number(weight || 0) <= 0) return
      connections.push({
        sourceId,
        targetId,
        weight: Number(weight || 0),
        source: positions[sourceId],
        target: positions[targetId],
      })
    })
  })

  const handleCreateProject = async () => {
    const nextId = String(newProjectId || '').trim()
    if (!nextId) {
      setError('请输入新的 project id')
      return
    }
    try {
      setStatus('')
      setError('')
      await onCreateProject(nextId)
      setStatus(`已创建并切换到项目 ${nextId}`)
      setNewProjectId('')
    } catch (err) {
      setError(String(err?.message || err))
    }
  }

  const handleDeleteProject = async () => {
    if (projectId === 'default') {
      setError('默认项目不建议在前端直接删除')
      return
    }
    if (!window.confirm(`确认删除项目 ${projectId} 吗？`)) return
    try {
      setStatus('')
      setError('')
      await onDeleteProject(projectId)
      setStatus(`项目 ${projectId} 已删除`)
    } catch (err) {
      setError(String(err?.message || err))
    }
  }

  const handleToggleProject = async () => {
    try {
      setStatus('')
      setError('')
      await onSetRunning(projectId, !isRunning)
      setStatus(!isRunning ? '项目调度已启动' : '项目调度已停止')
      await onRefreshAgents?.()
    } catch (err) {
      setError(String(err?.message || err))
    }
  }

  const handleCreateAgent = async () => {
    const agentId = String(newAgent.id || '').trim()
    if (!AGENT_ID_RE.test(agentId)) {
      setError('agent_id 需为小写字母开头，可包含数字和下划线')
      return
    }
    try {
      setStatus('')
      setError('')
      await createAgent(agentId, newAgent.directives)

      const nextConfig = deepClone(config)
      nextConfig.projects = nextConfig.projects || {}
      nextConfig.projects[projectId] = nextConfig.projects[projectId] || {}
      nextConfig.projects[projectId].agent_settings = nextConfig.projects[projectId].agent_settings || {}
      nextConfig.projects[projectId].agent_settings[agentId] = {
        ...(nextConfig.projects[projectId].agent_settings[agentId] || {}),
        model: String(newAgent.model || MODEL_PRESETS[0]).trim(),
        phase_strategy: newAgent.strategy === INHERIT_STRATEGY ? null : newAgent.strategy,
      }

      await onSaveConfig(nextConfig)
      await setProjectAgentActive(projectId, agentId, true)
      await onRefreshAgents?.()
      await refreshWorkspace()
      onSelectAgent?.(agentId)
      setStatus(`Agent ${agentId} 已创建并加入当前星图`)
      setNewAgent({
        id: '',
        model: newAgent.model || MODEL_PRESETS[0],
        strategy: INHERIT_STRATEGY,
        directives: '',
      })
    } catch (err) {
      setError(String(err?.message || err))
    }
  }

  const handleSaveAgent = async () => {
    if (!selectedAgent) return
    try {
      setStatus('')
      setError('')
      const nextConfig = deepClone(config)
      nextConfig.projects = nextConfig.projects || {}
      nextConfig.projects[projectId] = nextConfig.projects[projectId] || {}
      nextConfig.projects[projectId].agent_settings = nextConfig.projects[projectId].agent_settings || {}
      nextConfig.projects[projectId].agent_settings[selectedAgent.agent_id] = {
        ...(nextConfig.projects[projectId].agent_settings[selectedAgent.agent_id] || {}),
        model: String(selectedModel || MODEL_PRESETS[0]).trim(),
        phase_strategy: selectedStrategy === INHERIT_STRATEGY ? null : selectedStrategy,
      }
      await onSaveConfig(nextConfig)
      await onRefreshAgents?.()
      setStatus(`Agent ${selectedAgent.agent_id} 配置已保存`)
    } catch (err) {
      setError(String(err?.message || err))
    }
  }

  const handleToggleAgent = async () => {
    if (!selectedAgent) return
    try {
      setStatus('')
      setError('')
      await setProjectAgentActive(projectId, selectedAgent.agent_id, !selectedAgent.active)
      await onRefreshAgents?.()
      setStatus(`${selectedAgent.agent_id} 已${selectedAgent.active ? '暂停' : '恢复'}`)
    } catch (err) {
      setError(String(err?.message || err))
    }
  }

  const handleDeleteAgent = async () => {
    if (!selectedAgent) return
    if (!window.confirm(`确认删除 agent ${selectedAgent.agent_id} 吗？`)) return
    try {
      setStatus('')
      setError('')
      await deleteAgent(selectedAgent.agent_id)
      await onRefreshAgents?.()
      await refreshWorkspace()
      setStatus(`${selectedAgent.agent_id} 已删除`)
      onSelectAgent?.('')
    } catch (err) {
      setError(String(err?.message || err))
    }
  }

  const handleSendMessage = async () => {
    if (!selectedAgent) {
      setError('请先选择一个 agent')
      return
    }
    if (!String(messageDraft.title || '').trim() || !String(messageDraft.content || '').trim()) {
      setError('消息标题和内容不能为空')
      return
    }
    try {
      setStatus('')
      setError('')
      await gatewaySendMessage(
        projectId,
        HUMAN_IDENTITY,
        selectedAgent.agent_id,
        messageDraft.title,
        messageDraft.content,
        [],
      )
      setMessageDraft((prev) => ({ ...prev, content: '' }))
      setStatus(`已向 ${selectedAgent.agent_id} 发送私信`)
      await refreshWorkspace()
    } catch (err) {
      setError(String(err?.message || err))
    }
  }

  const handleSelectNode = async (agentId) => {
    if (linkModeSource) {
      if (linkModeSource === agentId) {
        setLinkModeSource('')
        return
      }
      try {
        const weight = Number((workspace?.graph?.matrix || {})?.[linkModeSource]?.[agentId] || 0)
        await updateSocialEdge(projectId, linkModeSource, agentId, weight <= 0)
        setStatus(weight > 0 ? `已断开 ${linkModeSource} -> ${agentId}` : `已建立 ${linkModeSource} -> ${agentId}`)
        setLinkModeSource('')
        await refreshWorkspace()
      } catch (err) {
        setError(String(err?.message || err))
      }
    }
    onSelectAgent?.(agentId)
  }

  return (
    <div className="stack-lg">
      <section className="panel galaxy-hero">
        <div>
          <div className="eyebrow">Mission Control</div>
          <h2>Agent Galaxy</h2>
          <p className="dim">
            以星图为主视图，把项目控制、agent 配置、关系编辑、消息投递和运行观测收敛到同一个操作面。
          </p>
        </div>
        <div className="hero-status-grid compact">
          <MetricCard label="项目状态" value={isRunning ? '调度运行中' : '调度已停止'} className={isRunning ? 'online' : 'offline'} />
          <MetricCard label="星图节点" value={metrics.total} />
          <MetricCard label="关系边" value={metrics.edges} />
          <MetricCard label="Inbox / Queue" value={`${metrics.inbox} / ${metrics.queued}`} />
        </div>
      </section>

      <div className="galaxy-workbench layout-break-stack">
        <ProjectCockpitPanel
          title={currentProjectConfig?.name || projectId}
          workspaceLoading={workspaceLoading}
          onRefresh={() => refreshWorkspace()}
          metrics={metrics}
          currentProjectConfig={currentProjectConfig}
          newProjectId={newProjectId}
          onNewProjectIdChange={setNewProjectId}
          onCreateProject={handleCreateProject}
          isRunning={isRunning}
          onToggleProject={handleToggleProject}
          onDeleteProject={handleDeleteProject}
          newAgent={newAgent}
          onNewAgentChange={setNewAgent}
          onCreateAgent={handleCreateAgent}
          modelOptions={MODEL_PRESETS}
        />

        <section className="panel galaxy-stage-panel">
          <SectionHeader
            eyebrow="Constellation"
            title={`${projectId} 星图`}
            actions={(
              <div className="action-row wrap-row">
                <button
                  className={`ghost-btn ${linkModeSource ? 'is-linking' : ''}`}
                  onClick={() => setLinkModeSource(linkModeSource ? '' : selectedAgentId)}
                  disabled={!selectedAgentId}
                >
                  <Link2 size={14} />
                  {linkModeSource ? `选择目标: ${linkModeSource}` : '关系编辑模式'}
                </button>
                <button className="ghost-btn" onClick={() => refreshWorkspace()} disabled={workspaceLoading}>
                  <GitBranch size={14} />
                  更新拓扑
                </button>
              </div>
            )}
          />

          <GalaxyScene
            graphNodes={graphNodes}
            matrix={workspace?.graph?.matrix || {}}
            agentRows={agentRows}
            positions={positions}
            connections={connections}
            selectedAgentId={selectedAgentId}
            linkModeSource={linkModeSource}
            reducedMotion={reducedMotion}
            onViewportChange={setViewport}
            onSelectNode={handleSelectNode}
          />
        </section>

        <GalaxyInspectorPanel
          selectedAgent={selectedAgent}
          selectedModel={selectedModel}
          onSelectedModelChange={setSelectedModel}
          selectedStrategy={selectedStrategy}
          onSelectedStrategyChange={setSelectedStrategy}
          messageDraft={messageDraft}
          onMessageDraftChange={setMessageDraft}
          onSaveAgent={handleSaveAgent}
          onToggleAgent={handleToggleAgent}
          linkModeSource={linkModeSource}
          onToggleLinkMode={() => setLinkModeSource(linkModeSource ? '' : selectedAgent?.agent_id || '')}
          onDeleteAgent={handleDeleteAgent}
          onSendMessage={handleSendMessage}
        />
      </div>

      <div className="galaxy-lower-grid">
        <GalaxyActivityPanel
          recentEvents={workspace.recentEvents}
          timelineSummary={workspace.timelineSummary}
          mailbox={workspace.mailbox}
        />
        <GalaxyInfrastructurePanel infrastructure={workspace.infrastructure} council={workspace.council} />
      </div>

      <SuccessBanner message={status} />
      <ErrorBanner message={error || workspaceError} />
    </div>
  )
}
