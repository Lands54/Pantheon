import { useEffect, useMemo, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { getProjectTimeline } from '../api/platformApi'

function pad2(n) {
  return `${n}`.padStart(2, '0')
}

function toDayKey(ts) {
  const d = new Date((Number(ts) || 0) * 1000)
  if (Number.isNaN(d.getTime())) return ''
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`
}

function normalizeMultiline(text) {
  const s = String(text ?? '')
  return s.replaceAll('\\n', '\n')
}

function PayloadView({ payload }) {
  const obj = payload && typeof payload === 'object' ? payload : {}
  const keys = Object.keys(obj)
  if (!keys.length) return <div style={{ color: '#94a3b8' }}>空 payload</div>
  return (
    <div style={{ display: 'grid', gap: 8 }}>
      {keys.map((k) => {
        const v = obj[k]
        let body = null
        if (typeof v === 'string') {
          body = (
            <pre
              style={{
                margin: 0,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                background: '#f8fafc',
                border: '1px solid #e2e8f0',
                borderRadius: 8,
                padding: 8,
                color: '#0f172a',
                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                fontSize: 12,
              }}
            >
              {normalizeMultiline(v)}
            </pre>
          )
        } else if (Array.isArray(v)) {
          body = (
            <div
              style={{
                background: '#f8fafc',
                border: '1px solid #e2e8f0',
                borderRadius: 8,
                padding: 8,
                fontSize: 12,
                color: '#0f172a',
              }}
            >
              {v.length ? v.map((x, i) => <div key={`${k}-${i}`} className="mono">- {String(x)}</div>) : <span style={{ color: '#94a3b8' }}>[empty]</span>}
            </div>
          )
        } else if (v && typeof v === 'object') {
          body = (
            <pre
              style={{
                margin: 0,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                background: '#f8fafc',
                border: '1px solid #e2e8f0',
                borderRadius: 8,
                padding: 8,
                color: '#0f172a',
                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                fontSize: 12,
              }}
            >
              {JSON.stringify(v, null, 2)}
            </pre>
          )
        } else {
          body = <div className="mono">{String(v)}</div>
        }
        return (
          <div key={k}>
            <div style={{ fontWeight: 700, marginBottom: 4 }}>{k}</div>
            {body}
          </div>
        )
      })}
    </div>
  )
}

function MonthHeatmap({ year, month, counts, onPickDay, selectedDay }) {
  const first = new Date(year, month - 1, 1)
  const firstWeekday = (first.getDay() + 6) % 7
  const days = new Date(year, month, 0).getDate()
  const blocks = []
  for (let i = 0; i < firstWeekday; i += 1) blocks.push({ empty: true, key: `e${i}` })
  for (let day = 1; day <= days; day += 1) {
    const dayKey = `${year}-${pad2(month)}-${pad2(day)}`
    const c = Number(counts[dayKey] || 0)
    blocks.push({ empty: false, day, dayKey, count: c })
  }
  const maxCount = Math.max(1, ...Object.values(counts || {}).map((x) => Number(x || 0)))
  const shade = (c) => {
    if (c <= 0) return '#f1f5f9'
    const ratio = Math.min(1, c / maxCount)
    const alpha = 0.2 + ratio * 0.75
    return `rgba(15,118,110,${alpha.toFixed(3)})`
  }
  return (
    <div style={{ border: '1px solid #e2e8f0', borderRadius: 10, padding: 10, background: '#fff' }}>
      <div style={{ fontWeight: 700, marginBottom: 8 }}>{year}-{pad2(month)}</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 4 }}>
        {['一', '二', '三', '四', '五', '六', '日'].map((w) => (
          <div key={w} style={{ fontSize: 11, color: '#64748b', textAlign: 'center' }}>{w}</div>
        ))}
        {blocks.map((b) => (
          b.empty ? (
            <div key={b.key} />
          ) : (
            <button
              key={b.dayKey}
              onClick={() => onPickDay(b.dayKey)}
              title={`${b.dayKey} (${b.count})`}
              style={{
                border: b.dayKey === selectedDay ? '2px solid #0f766e' : '1px solid #e2e8f0',
                borderRadius: 6,
                height: 24,
                fontSize: 11,
                cursor: 'pointer',
                background: shade(b.count),
                color: b.count > 0 ? '#022c22' : '#334155',
              }}
            >
              {b.day}
            </button>
          )
        ))}
      </div>
    </div>
  )
}

function ProjectSpanTimeline({ items, onPickEvent, zoom = 1, range = null, onRangeChange }) {
  if (!items.length) {
    return (
      <div className="panel" style={{ color: '#94a3b8' }}>
        暂无可展示事件
      </div>
    )
  }
  const sorted = [...items].sort((a, b) => Number(a.ts || 0) - Number(b.ts || 0))
  const minTs = Number(sorted[0]?.ts || 0)
  const maxTs = Number(sorted[sorted.length - 1]?.ts || 0)
  const hasRange = !!(range && Number(range.from_ts || 0) > 0 && Number(range.to_ts || 0) > 0)
  const rangeMin = hasRange ? Math.min(Number(range.from_ts), Number(range.to_ts)) : minTs
  const rangeMax = hasRange ? Math.max(Number(range.from_ts), Number(range.to_ts)) : maxTs
  const domainMin = Math.max(minTs, rangeMin)
  const domainMax = Math.min(maxTs, rangeMax)
  const span = Math.max(1, domainMax - domainMin)

  const priority = (row) => {
    const k = String(row.kind || '')
    if (k === 'asset_change') return 100
    if (k === 'file_write') return 90
    const p = row.payload || {}
    const title = String(row.title || '').toLowerCase()
    const msg = String(p.message || '').toLowerCase()
    if (title.includes('contract') || title.includes('契约') || msg.includes('contract') || msg.includes('契约')) return 85
    if (title.includes('error') || msg.includes('error') || msg.includes('failed') || msg.includes('失败')) return 80
    if (k === 'private_message') return 60
    return 10
  }

  const important = sorted
    .map((x) => ({ ...x, __p: priority(x) }))
    .filter((x) => {
      const ts = Number(x.ts || 0)
      return ts >= domainMin && ts <= domainMax
    })
    .sort((a, b) => b.__p - a.__p || Number(a.ts || 0) - Number(b.ts || 0))
    .slice(0, 80)
    .sort((a, b) => Number(a.ts || 0) - Number(b.ts || 0))

  const width = Math.max(1100, Math.floor(1100 * Math.max(1, Number(zoom || 1))))
  const height = 140
  const left = 24
  const right = width - 24
  const y = 72
  const xOf = (ts) => left + ((Number(ts || 0) - domainMin) / span) * (right - left)
  const tsOf = (x) => {
    const clamped = Math.max(left, Math.min(right, Number(x || left)))
    const ratio = (clamped - left) / Math.max(1, right - left)
    return domainMin + ratio * span
  }
  const fmt = (ts) => new Date(Number(ts || 0) * 1000).toLocaleString()
  const colorOf = (k) => {
    if (k === 'asset_change') return '#b91c1c'
    if (k === 'file_write') return '#0f766e'
    if (k === 'private_message') return '#1d4ed8'
    return '#475569'
  }

  const [dragging, setDragging] = useState(false)
  const [dragStartX, setDragStartX] = useState(0)
  const [dragCurrentX, setDragCurrentX] = useState(0)

  const toSvgX = (ev) => {
    const rect = ev.currentTarget.getBoundingClientRect()
    const x = ((ev.clientX - rect.left) * width) / Math.max(1, rect.width)
    return Math.max(left, Math.min(right, x))
  }

  const dragFrom = dragging ? Math.min(dragStartX, dragCurrentX) : null
  const dragTo = dragging ? Math.max(dragStartX, dragCurrentX) : null

  return (
    <div className="panel">
      <h3 style={{ marginTop: 0 }}>项目全程横轴（重要事件）</h3>
      <div style={{ overflowX: 'auto' }}>
        <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
          <line x1={left} y1={y} x2={right} y2={y} stroke="#94a3b8" strokeWidth="2" />
          <text x={left} y={y + 24} fontSize="11" fill="#64748b">{fmt(domainMin)}</text>
          <text x={right} y={y + 24} fontSize="11" fill="#64748b" textAnchor="end">{fmt(domainMax)}</text>
          {dragging && dragFrom !== null && dragTo !== null && (
            <rect
              x={dragFrom}
              y={16}
              width={Math.max(2, dragTo - dragFrom)}
              height={96}
              fill="rgba(15,118,110,0.15)"
              stroke="#0f766e"
              strokeDasharray="4 3"
            />
          )}
          {important.map((ev) => {
            const x = xOf(ev.ts)
            const r = ev.__p >= 90 ? 5 : 4
            return (
              <g key={`${ev.id}:${ev.ts}`}>
                <line x1={x} y1={y - 14} x2={x} y2={y + 14} stroke="#e2e8f0" strokeWidth="1" />
                <circle
                  cx={x}
                  cy={y}
                  r={r}
                  fill={colorOf(ev.kind)}
                  style={{ cursor: 'pointer' }}
                  onClick={() => onPickEvent(ev)}
                >
                  <title>{`${fmt(ev.ts)}\n${ev.summary || ev.title || ev.id}`}</title>
                </circle>
              </g>
            )
          })}
          <rect
            x={left}
            y={16}
            width={right - left}
            height={96}
            fill="transparent"
            style={{ cursor: 'crosshair' }}
            onMouseDown={(ev) => {
              const x = toSvgX(ev)
              setDragStartX(x)
              setDragCurrentX(x)
              setDragging(true)
            }}
            onMouseMove={(ev) => {
              if (!dragging) return
              setDragCurrentX(toSvgX(ev))
            }}
            onMouseUp={() => {
              if (!dragging) return
              const x1 = Math.min(dragStartX, dragCurrentX)
              const x2 = Math.max(dragStartX, dragCurrentX)
              setDragging(false)
              if (Math.abs(x2 - x1) < 4) return
              if (typeof onRangeChange === 'function') {
                onRangeChange({
                  from_ts: tsOf(x1),
                  to_ts: tsOf(x2),
                })
              }
            }}
            onMouseLeave={() => {
              if (!dragging) return
              setDragging(false)
            }}
          />
        </svg>
      </div>
      <div style={{ marginTop: 8, fontSize: 12, color: '#64748b' }}>
        红=资产变更 | 绿=文件写入 | 蓝=私信（重要） | 点数={important.length}{hasRange ? ' | 当前为区间视图' : ''}
      </div>
    </div>
  )
}

export function ProjectTimelinePage({ projectId }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [data, setData] = useState({ items: [], heatmap: [], stats: {} })
  const [selectedKinds, setSelectedKinds] = useState(['private_message', 'file_write', 'asset_change'])
  const [selectedDay, setSelectedDay] = useState('')
  const [selectedEvent, setSelectedEvent] = useState(null)
  const [timelineZoom, setTimelineZoom] = useState(1)
  const [selectedRange, setSelectedRange] = useState(null)

  const reload = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await getProjectTimeline(projectId, 0, 0, 20000)
      setData(res || { items: [], heatmap: [], stats: {} })
    } catch (e) {
      setError(String(e?.message || e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    reload()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

  const countsByDay = useMemo(() => {
    const map = {}
    for (const row of data.heatmap || []) {
      map[String(row.date || '')] = Number(row.count || 0)
    }
    return map
  }, [data])

  const years = useMemo(() => {
    const days = Object.keys(countsByDay)
    const y = new Set(days.map((d) => Number(String(d).slice(0, 4))).filter((x) => Number.isFinite(x) && x > 0))
    const arr = [...y].sort((a, b) => a - b)
    if (!arr.length) arr.push(new Date().getFullYear())
    return arr
  }, [countsByDay])

  const filtered = useMemo(() => {
    const set = new Set(selectedKinds)
    let rows = (data.items || []).filter((x) => set.has(String(x.kind || '')))
    if (selectedDay) rows = rows.filter((x) => toDayKey(x.ts) === selectedDay)
    if (selectedRange && Number(selectedRange.from_ts || 0) > 0 && Number(selectedRange.to_ts || 0) > 0) {
      const lo = Math.min(Number(selectedRange.from_ts), Number(selectedRange.to_ts))
      const hi = Math.max(Number(selectedRange.from_ts), Number(selectedRange.to_ts))
      rows = rows.filter((x) => {
        const ts = Number(x.ts || 0)
        return ts >= lo && ts <= hi
      })
    }
    return rows
  }, [data, selectedKinds, selectedDay, selectedRange])

  const onToggleKind = (k) => {
    setSelectedKinds((prev) => {
      const set = new Set(prev)
      if (set.has(k)) set.delete(k)
      else set.add(k)
      return [...set]
    })
  }

  return (
    <div className="panel">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>Project Timeline · <span className="mono">{projectId}</span></h2>
        <button className="ghost-btn" onClick={reload} disabled={loading}>
          <RefreshCw size={14} className={loading ? 'spin' : ''} /> Refresh
        </button>
      </div>

      {error && <div className="panel error-banner">{error}</div>}

      <div style={{ display: 'flex', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
        {['private_message', 'file_write', 'asset_change'].map((k) => (
          <button
            key={k}
            className="ghost-btn"
            onClick={() => onToggleKind(k)}
            style={{ background: selectedKinds.includes(k) ? '#dcfce7' : undefined }}
          >
            {k}
          </button>
        ))}
        {selectedDay && (
          <button className="ghost-btn" onClick={() => setSelectedDay('')}>清除日期筛选: {selectedDay}</button>
        )}
        {selectedRange && (
          <button className="ghost-btn" onClick={() => setSelectedRange(null)}>清除区间筛选</button>
        )}
      </div>

      <div className="panel" style={{ marginBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <b>时间轴缩放</b>
          <button className="ghost-btn" onClick={() => setTimelineZoom((z) => Math.max(1, Number((z - 0.5).toFixed(1))))}>-</button>
          <input
            type="range"
            min={1}
            max={8}
            step={0.5}
            value={timelineZoom}
            onChange={(e) => setTimelineZoom(Number(e.target.value))}
            style={{ width: 220 }}
          />
          <button className="ghost-btn" onClick={() => setTimelineZoom((z) => Math.min(8, Number((z + 0.5).toFixed(1))))}>+</button>
          <button className="ghost-btn" onClick={() => setTimelineZoom(1)}>重置</button>
          <span className="mono">x{timelineZoom.toFixed(1)}</span>
        </div>
      </div>

      <ProjectSpanTimeline
        items={data.items || []}
        onPickEvent={setSelectedEvent}
        zoom={timelineZoom}
        range={selectedRange}
        onRangeChange={setSelectedRange}
      />
      {selectedRange && (
        <div style={{ marginTop: 6, color: '#475569', fontSize: 12 }}>
          区间筛选: {new Date(selectedRange.from_ts * 1000).toLocaleString()} ~ {new Date(selectedRange.to_ts * 1000).toLocaleString()}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(180px,1fr))', gap: 10 }}>
        {years.map((year) => (
          Array.from({ length: 12 }).map((_, i) => (
            <MonthHeatmap
              key={`${year}-${i + 1}`}
              year={year}
              month={i + 1}
              counts={countsByDay}
              selectedDay={selectedDay}
              onPickDay={setSelectedDay}
            />
          ))
        ))}
      </div>

      <div style={{ marginTop: 14, color: '#475569', fontSize: 13 }}>
        total={Number(data.stats?.total || 0)} | message={Number(data.stats?.private_messages || 0)} | write={Number(data.stats?.file_writes || 0)} | asset={Number(data.stats?.asset_changes || 0)}
      </div>

      <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 12 }}>
        <div className="panel" style={{ maxHeight: 560, overflow: 'auto' }}>
          <h3 style={{ marginTop: 0 }}>Timeline Events ({filtered.length})</h3>
          {filtered.map((row) => {
            const ts = Number(row.ts || 0)
            const t = ts > 0 ? new Date(ts * 1000).toLocaleString() : '-'
            return (
              <button
                key={`${row.id}:${row.ts}`}
                onClick={() => setSelectedEvent(row)}
                style={{
                  display: 'block',
                  width: '100%',
                  textAlign: 'left',
                  border: '1px solid #e2e8f0',
                  borderRadius: 8,
                  background: selectedEvent?.id === row.id && selectedEvent?.ts === row.ts ? '#eef2ff' : '#fff',
                  padding: 10,
                  marginBottom: 8,
                  cursor: 'pointer',
                }}
              >
                <div style={{ fontSize: 12, color: '#64748b' }}>{t} · {row.kind}</div>
                <div style={{ fontWeight: 700, marginTop: 4 }}>{row.summary || row.title || row.id}</div>
              </button>
            )
          })}
          {!filtered.length && <div style={{ color: '#94a3b8' }}>暂无匹配事件</div>}
        </div>

        <div className="panel" style={{ maxHeight: 560, overflow: 'auto' }}>
          <h3 style={{ marginTop: 0 }}>Event Detail</h3>
          {!selectedEvent && <div style={{ color: '#94a3b8' }}>点击左侧事件查看详情</div>}
          {selectedEvent && (
            <>
              <div><b>kind:</b> <span className="mono">{selectedEvent.kind}</span></div>
              <div><b>agent:</b> <span className="mono">{selectedEvent.agent_id || '-'}</span></div>
              <div><b>target:</b> <span className="mono">{selectedEvent.target_id || '-'}</span></div>
              <div><b>title:</b> <span className="mono">{selectedEvent.title || '-'}</span></div>
              <div style={{ marginTop: 10 }}>
                <b>payload</b>
                <div style={{ marginTop: 6 }}>
                  <PayloadView payload={selectedEvent.payload || {}} />
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
