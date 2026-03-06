import { useMemo, useState } from 'react'

const INHERIT_STRATEGY = '__inherit__'

export function useGalaxySelection(selectedAgent, selectedConfig, defaultModel) {
  const agentId = String(selectedAgent?.agent_id || '')
  const defaults = useMemo(() => ({
    selectedModel: String(selectedConfig?.model || defaultModel),
    selectedStrategy: String(selectedConfig?.phase_strategy || '').trim() || INHERIT_STRATEGY,
    messageDraft: {
      title: 'frontend.quick_message',
      content: '',
    },
  }), [defaultModel, selectedConfig?.model, selectedConfig?.phase_strategy])
  const [draft, setDraft] = useState({
    agentId: '',
    selectedModel: defaultModel,
    selectedStrategy: INHERIT_STRATEGY,
    title: 'frontend.quick_message',
    content: '',
  })

  const selectedModel = draft.agentId === agentId ? draft.selectedModel : defaults.selectedModel
  const selectedStrategy = draft.agentId === agentId ? draft.selectedStrategy : defaults.selectedStrategy
  const messageDraft = draft.agentId === agentId
    ? { title: draft.title || 'frontend.quick_message', content: draft.content }
    : defaults.messageDraft

  const setSelectedModel = (value) => {
    setDraft((prev) => ({
      ...prev,
      agentId,
      selectedModel: typeof value === 'function' ? value(selectedModel) : value,
    }))
  }

  const setSelectedStrategy = (value) => {
    setDraft((prev) => ({
      ...prev,
      agentId,
      selectedStrategy: typeof value === 'function' ? value(selectedStrategy) : value,
    }))
  }

  const setMessageDraft = (value) => {
    setDraft((prev) => {
      const nextValue = typeof value === 'function' ? value(messageDraft) : value
      return {
        ...prev,
        agentId,
        title: nextValue?.title || 'frontend.quick_message',
        content: nextValue?.content || '',
      }
    })
  }

  return {
    selectedModel,
    setSelectedModel,
    selectedStrategy,
    setSelectedStrategy,
    messageDraft,
    setMessageDraft,
  }
}
