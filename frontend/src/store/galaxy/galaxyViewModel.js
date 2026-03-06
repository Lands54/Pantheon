import {
  gatewayCheckInbox,
  gatewayCheckOutbox,
  getAthenaCouncil,
  getHermesContracts,
  getHermesPorts,
  getProjectTimeline,
  getSocialGraph,
  listEvents,
} from '../../api/platformApi'
import { HUMAN_IDENTITY } from '../../types/models'
import { selectGalaxyMetrics } from '../app/selectors'

export async function loadGalaxyViewModel(projectId, agentRows = []) {
  const results = await Promise.allSettled([
    getSocialGraph(projectId),
    listEvents({ project_id: projectId, limit: 24 }),
    getProjectTimeline(projectId, 0, 0, 48),
    gatewayCheckInbox(projectId, HUMAN_IDENTITY),
    gatewayCheckOutbox(projectId, HUMAN_IDENTITY, '', '', 20),
    getHermesContracts(projectId, true),
    getHermesPorts(projectId),
    getAthenaCouncil(projectId),
  ])

  const [graphResult, eventsResult, timelineResult, inboxResult, outboxResult, contractsResult, portsResult, councilResult] = results
  const graph = graphResult.status === 'fulfilled'
    ? (graphResult.value?.graph || graphResult.value || { nodes: [], matrix: {} })
    : { nodes: [], matrix: {} }
  const recentEvents = eventsResult.status === 'fulfilled' ? (eventsResult.value?.items || []) : []
  const timelineSummary = timelineResult.status === 'fulfilled' ? (timelineResult.value?.items || []) : []
  const mailbox = {
    inbox: inboxResult.status === 'fulfilled' ? (inboxResult.value?.messages || []) : [],
    outbox: outboxResult.status === 'fulfilled' ? (outboxResult.value?.items || []) : [],
  }
  const infrastructure = {
    contracts: contractsResult.status === 'fulfilled' ? (contractsResult.value?.contracts || []) : [],
    ports: portsResult.status === 'fulfilled' ? (portsResult.value || { leases: [] }) : { leases: [] },
  }
  const council = councilResult.status === 'fulfilled' ? (councilResult.value?.sync_council || null) : null
  const errors = results.filter((item) => item.status === 'rejected').map((item) => item.reason)

  return {
    graph,
    recentEvents,
    timelineSummary,
    mailbox,
    infrastructure,
    council,
    metrics: selectGalaxyMetrics(agentRows, graph?.matrix || {}),
    errors,
  }
}
