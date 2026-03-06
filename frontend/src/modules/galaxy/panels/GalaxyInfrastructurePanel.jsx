import { GitBranch, Server, Workflow } from 'lucide-react'
import { MetricCard } from '../../../components/ui/MetricCard'
import { SectionHeader } from '../../../components/ui/SectionHeader'

export function GalaxyInfrastructurePanel({ infrastructure = { contracts: [], ports: { leases: [] } }, council = null }) {
  const contracts = infrastructure?.contracts || []
  const ports = infrastructure?.ports || { leases: [] }
  return (
    <section className="panel">
      <SectionHeader eyebrow="Infrastructure" title="部署与商议" actions={<Server size={16} />} />
      <div className="compact-metric-grid">
        <MetricCard icon={Workflow} label="Contracts" value={contracts.length} />
        <MetricCard icon={Server} label="Ports" value={Array.isArray(ports?.leases) ? ports.leases.length : 0} />
        <MetricCard icon={GitBranch} label="Council" value={council?.status || 'idle'} />
      </div>
      <div className="stack-sm mono dim">
        <div>contracts={contracts.slice(0, 3).map((item) => item.name).join(', ') || 'none'}</div>
        <div>ports={Array.isArray(ports?.leases) ? ports.leases.slice(0, 3).map((item) => item.port).join(', ') : 'none'}</div>
        <div>council_title={council?.title || 'none'}</div>
      </div>
    </section>
  )
}
