import { CalendarRange, Inbox, Mail, Send } from 'lucide-react'
import { MetricCard } from '../../../components/ui/MetricCard'
import { SectionHeader } from '../../../components/ui/SectionHeader'
import { FeedList } from '../../../components/data-display/FeedList'
import { formatTimestamp } from '../../../utils/formatters'
import { HUMAN_IDENTITY } from '../../../types/models'

export function GalaxyActivityPanel({ recentEvents = [], timelineSummary = [], mailbox = { inbox: [], outbox: [] } }) {
  return (
    <>
      <section className="panel">
        <SectionHeader eyebrow="Recent Events" title="事件列队" actions={<span className="mono dim">{recentEvents.length} items</span>} />
        <FeedList>
          {recentEvents.slice(0, 8).map((item) => (
            <div key={item.event_id} className="feed-card-item">
              <div className="feed-card-title">{item.event_type}</div>
              <div className="feed-card-meta mono">{item.domain} · {item.state} · {(item.payload?.agent_id || item.payload?.to_id || '-')}</div>
            </div>
          ))}
          {!recentEvents.length && <div className="dim">暂无事件。</div>}
        </FeedList>
      </section>

      <section className="panel">
        <SectionHeader eyebrow="Timeline" title="项目时间线摘要" actions={<CalendarRange size={16} />} />
        <FeedList>
          {timelineSummary.slice(0, 8).map((item) => (
            <div key={`${item.id}-${item.ts}`} className="feed-card-item">
              <div className="feed-card-title">{item.title || item.summary || item.kind || item.id}</div>
              <div className="feed-card-meta mono">{formatTimestamp(item.ts)} · {item.kind || 'event'}</div>
            </div>
          ))}
          {!timelineSummary.length && <div className="dim">暂无项目时间线数据。</div>}
        </FeedList>
      </section>

      <section className="panel">
        <SectionHeader eyebrow="Human Mailbox" title={HUMAN_IDENTITY} actions={<Mail size={16} />} />
        <div className="mail-summary-grid">
          <MetricCard icon={Inbox} label="Inbox" value={mailbox.inbox.length} />
          <MetricCard icon={Send} label="Outbox" value={mailbox.outbox.length} />
        </div>
        <FeedList>
          {mailbox.inbox.slice(0, 4).map((message) => (
            <div key={`in-${message.id}`} className="feed-card-item">
              <div className="feed-card-title">{message.title}</div>
              <div className="feed-card-meta mono">from {message.from} · {message.status}</div>
            </div>
          ))}
          {!mailbox.inbox.length && <div className="dim">Human inbox 为空。</div>}
        </FeedList>
      </section>
    </>
  )
}
