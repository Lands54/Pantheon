import { apiDelete, apiGet, apiPost, apiPut } from './client'
import { HUMAN_IDENTITY } from '../types/models'

const qp = (obj) => {
  const p = new URLSearchParams()
  Object.entries(obj || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && `${v}` !== '') p.set(k, `${v}`)
  })
  const s = p.toString()
  return s ? `?${s}` : ''
}

export function getConfig() {
  return apiGet('/config')
}

export function getConfigSchema() {
  return apiGet('/config/schema')
}

export function saveConfig(config) {
  return apiPost('/config/save', config)
}

export function createProject(id) {
  return apiPost('/projects/create', { id })
}

export function deleteProject(projectId) {
  return apiDelete(`/projects/${encodeURIComponent(projectId)}`)
}

export function startProject(projectId) {
  return apiPost(`/projects/${encodeURIComponent(projectId)}/start`, {})
}

export function stopProject(projectId) {
  return apiPost(`/projects/${encodeURIComponent(projectId)}/stop`, {})
}

export function getAgentStatus(projectId) {
  return apiGet(`/agents/status${qp({ project_id: projectId })}`)
}

export function listEvents(params) {
  return apiGet(`/events${qp(params)}`)
}

export function getEventCatalog(projectId) {
  return apiGet(`/events/catalog${qp({ project_id: projectId })}`)
}

export function retryEvent(projectId, eventId) {
  return apiPost(`/events/${encodeURIComponent(eventId)}/retry`, { project_id: projectId })
}

export function ackEvent(projectId, eventId) {
  return apiPost(`/events/${encodeURIComponent(eventId)}/ack`, { project_id: projectId })
}

export function submitInteractionMessage({
  projectId,
  toId,
  title,
  content,
  msgType = 'confession',
  triggerPulse = true,
  senderId = HUMAN_IDENTITY,
}) {
  return apiPost('/events/submit', {
    project_id: projectId,
    domain: 'interaction',
    event_type: 'interaction.message.sent',
    payload: {
      to_id: toId,
      sender_id: senderId,
      title,
      content,
      msg_type: msgType,
      trigger_pulse: triggerPulse,
    },
  })
}

export function getContextPreview(projectId, agentId) {
  return apiGet(`/projects/${encodeURIComponent(projectId)}/context/preview${qp({ agent_id: agentId })}`)
}

export function getContextReports(projectId, agentId, limit = 20) {
  return apiGet(`/projects/${encodeURIComponent(projectId)}/context/reports${qp({ agent_id: agentId, limit })}`)
}

export function getLatestLlmContext(projectId, agentId) {
  return apiGet(`/projects/${encodeURIComponent(projectId)}/context/llm-latest${qp({ agent_id: agentId })}`)
}

export function getContextSnapshot(projectId, agentId, sinceIntentSeq = 0) {
  return apiGet(
    `/projects/${encodeURIComponent(projectId)}/context/snapshot${qp({
      agent_id: agentId,
      since_intent_seq: sinceIntentSeq,
    })}`
  )
}

export function getContextSnapshotCompressions(projectId, agentId, limit = 50) {
  return apiGet(
    `/projects/${encodeURIComponent(projectId)}/context/snapshot/compressions${qp({
      agent_id: agentId,
      limit,
    })}`
  )
}

export function getContextSnapshotDerived(projectId, agentId, limit = 100) {
  return apiGet(
    `/projects/${encodeURIComponent(projectId)}/context/snapshot/derived${qp({
      agent_id: agentId,
      limit,
    })}`
  )
}

export function getContextPulses(projectId, agentId, fromSeq = 0, limit = 500) {
  return apiGet(
    `/projects/${encodeURIComponent(projectId)}/context/pulses${qp({
      agent_id: agentId,
      from_seq: fromSeq,
      limit,
    })}`
  )
}

export function listOutboxReceipts(projectId, fromAgentId, status = '', limit = 50) {
  return apiGet(`/projects/${encodeURIComponent(projectId)}/inbox/outbox${qp({ from_agent_id: fromAgentId, status, limit })}`)
}

export function getHermesProtocols(projectId) {
  return apiGet(`/hermes/list${qp({ project_id: projectId })}`)
}

export function getHermesContracts(projectId, includeDisabled = true) {
  return apiGet(`/hermes/contracts/list${qp({ project_id: projectId, include_disabled: includeDisabled })}`)
}

export function getHermesPorts(projectId) {
  return apiGet(`/hermes/ports/list${qp({ project_id: projectId })}`)
}

export function getHermesInvocations(projectId, limit = 200) {
  return apiGet(`/hermes/invocations${qp({ project_id: projectId, limit })}`)
}

export function deleteAgent(agentId) {
  return apiDelete(`/agents/${encodeURIComponent(agentId)}`)
}

export function createAgent(agentId, directives) {
  return apiPost('/agents/create', { agent_id: agentId, directives })
}

export function getMemoryTemplates(projectId) {
  return apiGet(`/mnemosyne/templates${qp({ project_id: projectId })}`)
}

export function updateMemoryTemplate(projectId, scope, key, template) {
  return apiPut(`/mnemosyne/templates/${encodeURIComponent(scope)}/${encodeURIComponent(key)}`, {
    project_id: projectId,
    template,
  })
}

export function getMemoryPolicy(projectId) {
  return apiGet(`/mnemosyne/memory-policy${qp({ project_id: projectId })}`)
}

export function updateMemoryPolicyRule(projectId, intentKey, patch) {
  return apiPut(`/mnemosyne/memory-policy/${encodeURIComponent(intentKey)}`, {
    project_id: projectId,
    ...patch,
  })
}

export function getTemplateVars(projectId, intentKey) {
  return apiGet(`/mnemosyne/template-vars${qp({ project_id: projectId, intent_key: intentKey })}`)
}

export function getSocialGraph(projectId) {
  return apiGet(`/hestia/graph${qp({ project_id: projectId })}`)
}

export function updateSocialEdge(projectId, fromId, toId, allowed) {
  return apiPost(`/hestia/edge`, {
    project_id: projectId,
    from_id: fromId,
    to_id: toId,
    allowed
  })
}

export function gatewayCheckInbox(projectId, agentId) {
  return apiPost('/tool-gateway/check_inbox', {
    project_id: projectId,
    agent_id: agentId,
  })
}

export function gatewayCheckOutbox(projectId, agentId, toId = '', status = '', limit = 50) {
  return apiPost('/tool-gateway/check_outbox', {
    project_id: projectId,
    agent_id: agentId,
    to_id: toId,
    status,
    limit,
  })
}

export function gatewaySendMessage(projectId, fromId, toId, title, message, attachments = []) {
  return apiPost('/tool-gateway/send_message', {
    project_id: projectId,
    from_id: fromId,
    to_id: toId,
    title,
    message,
    attachments,
  })
}

export function startSyncCouncil(projectId, payload) {
  return apiPost(`/projects/${encodeURIComponent(projectId)}/sync-council/start`, payload || {})
}

export function confirmSyncCouncil(projectId, agentId) {
  return apiPost(`/projects/${encodeURIComponent(projectId)}/sync-council/confirm`, { agent_id: agentId })
}

export function getSyncCouncil(projectId) {
  return apiGet(`/projects/${encodeURIComponent(projectId)}/sync-council`)
}
