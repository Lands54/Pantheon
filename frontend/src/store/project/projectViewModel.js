export function buildProjectViewModel(config = {}, currentProject = '') {
  const project = (config?.projects || {})[currentProject] || {}
  return {
    projectId: currentProject,
    name: project?.name || currentProject,
    strategy: project?.phase_strategy || 'react_graph',
    contextStrategy: project?.context_strategy || 'default',
    simulationEnabled: !!project?.simulation_enabled,
    agentSettings: project?.agent_settings && typeof project.agent_settings === 'object'
      ? project.agent_settings
      : {},
  }
}
