# Interaction Event Types

## Summary
Interaction domain is the unified control plane for all agent-facing interactions.
All events are submitted via `POST /events/submit` with `domain=interaction`.

## Event Types
1. `interaction.message.sent`
- Purpose: send one message from sender to target agent.
- Required payload:
  - `to_id` (or `agent_id`)
  - `sender_id`
  - `title`
  - `content`
- Optional payload:
  - `msg_type` (default `private`)
  - `trigger_pulse` (default `true`)
  - `mail_priority`

2. `interaction.message.read`
- Purpose: acknowledge handled inbox message ids.
- Required payload:
  - `agent_id`
  - `event_ids` (array)

3. `interaction.hermes.notice`
- Purpose: Hermes contract/runtime notice delivery.
- Required payload:
  - single target mode: same as `interaction.message.sent`
  - batch mode: `targets[]`, `sender_id`, `title`, `content`

4. `interaction.detach.notice`
- Purpose: detach runtime status notice to related agent.
- Required payload:
  - `agent_id`
  - `title`
  - `content`

5. `interaction.agent.trigger`
- Purpose: explicit trigger for one agent pulse.
- Required payload:
  - `agent_id`
  - `reason`

## Error Codes
1. `INTERACTION_BAD_REQUEST`
- Invalid or missing payload fields.
2. `INTERACTION_HANDLER_ERROR`
- Handler runtime failure, event requeue/dead flow applies.

