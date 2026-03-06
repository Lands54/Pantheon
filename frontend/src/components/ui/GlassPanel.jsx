import { Panel } from './Panel'

export function GlassPanel({ className = '', children }) {
  return <Panel className={`glass-panel ${className}`.trim()}>{children}</Panel>
}
