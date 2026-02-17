/**
 * @typedef {Object} AgentStatus
 * @property {string} project_id
 * @property {string} agent_id
 * @property {string} status
 * @property {string} last_reason
 * @property {number} last_pulse_at
 * @property {number} next_eligible_at
 * @property {string} last_error
 * @property {number} queued_pulse_events
 * @property {boolean} has_pending_inbox
 */

/**
 * @typedef {Object} EventItem
 * @property {string} event_id
 * @property {string} domain
 * @property {string} event_type
 * @property {string} state
 * @property {number} priority
 * @property {Object<string, any>} payload
 * @property {number} created_at
 * @property {number} available_at
 * @property {number|null} done_at
 * @property {string} error_code
 * @property {string} error_message
 */

export const HUMAN_IDENTITY = 'human.overseer'
