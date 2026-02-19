import { useEffect, useState, useMemo, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Play, Pause, Save, Trash2, X, Hexagon, Link, MousePointer
} from 'lucide-react';
import { getAgentStatus, createAgent, deleteAgent, saveConfig, getSocialGraph, updateSocialEdge } from '../api/platformApi';
import { usePolling } from '../hooks/usePolling';

// --- Utils ---
function getStatusColor(status) {
    switch (status) {
        case 'running': return '#22c55e'; // Green
        case 'stopped': return '#ef4444'; // Red
        case 'idle': return '#f59e0b'; // Amber
        case 'cooldown': return '#3b82f6'; // Blue
        default: return '#94a3b8'; // Slate
    }
}

function getInboxColor(hasInbox) {
    return hasInbox ? '#a855f7' : '#e2e8f0'; // Purple vs Slate
}

// --- Components ---

function RadialMenu({ x, y, onAction, onClose, agentId, isActive }) {
    const buttons = [
        { icon: isActive ? Pause : Play, label: isActive ? 'Pause' : 'Resume', action: 'toggle', color: isActive ? '#ef4444' : '#22c55e' },
        { icon: Link, label: 'Connect', action: 'connect', color: '#8b5cf6' },
        { icon: Save, label: 'Save Config', action: 'save', color: '#3b82f6' },
        { icon: Trash2, label: 'Delete', action: 'delete', color: '#dc2626' },
        { icon: X, label: 'Close', action: 'close', color: '#64748b' }
    ];

    return (
        <motion.div
            className="radial-menu-overlay"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            style={{
                position: 'absolute', top: 0, left: 0, width: '100%', height: '100%',
                pointerEvents: 'none', zIndex: 100
            }}
        >
            <div style={{ position: 'absolute', left: x, top: y, pointerEvents: 'auto' }}>
                {buttons.map((btn, i) => {
                    const angle = (i * (360 / buttons.length)) * (Math.PI / 180);
                    const radius = 80;
                    const bx = Math.cos(angle) * radius;
                    const by = Math.sin(angle) * radius;

                    return (
                        <motion.button
                            key={btn.label}
                            initial={{ x: 0, y: 0, scale: 0 }}
                            animate={{ x: bx, y: by, scale: 1 }}
                            exit={{ x: 0, y: 0, scale: 0 }}
                            transition={{ type: 'spring', damping: 15, stiffness: 300, delay: i * 0.05 }}
                            className="radial-btn"
                            style={{
                                position: 'absolute',
                                transform: 'translate(-50%, -50%)',
                                width: 44, height: 44, borderRadius: '50%',
                                background: btn.color, border: '2px solid white',
                                color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center',
                                boxShadow: '0 4px 12px rgba(0,0,0,0.2)', cursor: 'pointer'
                            }}
                            onClick={() => {
                                if (btn.action === 'close') onClose();
                                else onAction(btn.action, agentId);
                            }}
                            title={btn.label}
                        >
                            <btn.icon size={20} />
                        </motion.button>
                    )
                })}
            </div>
        </motion.div>
    );
}

function Satellite({ cx, cy, r, angle, index, total }) {
    const x = cx + r * Math.cos(angle);
    const y = cy + r * Math.sin(angle);

    // Determine type/color based on index (mock for now since we only have count)
    // 0: Mail (Purple), 1: Manual (Orange), 2: Cron (Blue), etc.
    const colors = ['#a855f7', '#f97316', '#3b82f6', '#10b981'];
    const color = colors[index % colors.length];

    return (
        <motion.circle
            className="satellite"
            cx={x} cy={y} r={4} fill={color}
            initial={{ scale: 0 }} animate={{ scale: 1 }}
            transition={{ delay: index * 0.05 }}
        />
    )
}

function AgentNode({ agent, cx, cy, onClick, isConnecting }) {
    const statusColor = getStatusColor(agent.status);
    const inboxColor = getInboxColor(agent.has_pending_inbox);
    const queueCount = agent.queued_pulse_events || 0;

    // Calculate satellites
    const satelliteRadius = 50;
    const satellites = [];
    if (queueCount > 0) {
        for (let i = 0; i < Math.min(queueCount, 20); i++) {
            const angle = (i / Math.min(queueCount, 20)) * 2 * Math.PI - Math.PI / 2;
            satellites.push({ angle, index: i });
        }
    }

    return (
        <g onClick={(e) => { e.stopPropagation(); onClick(agent, e.clientX, e.clientY); }} style={{ cursor: isConnecting ? 'crosshair' : 'pointer' }}>
            {/* Pulse Effect for Running Agents */}
            {agent.status === 'running' && (
                <motion.circle
                    cx={cx} cy={cy} r={32}
                    stroke={statusColor} strokeWidth={2} fill="none"
                    initial={{ scale: 1, opacity: 0.6 }}
                    animate={{ scale: 1.6, opacity: 0 }}
                    transition={{ duration: 2, repeat: Infinity, ease: "easeOut" }}
                />
            )}

            {/* Satellites */}
            {satellites.map(s => (
                <Satellite key={s.index} cx={cx} cy={cy} r={satelliteRadius} angle={s.angle} index={s.index} total={satellites.length} />
            ))}

            {/* Main Node */}
            <motion.circle
                cx={cx} cy={cy} r={32}
                fill={isConnecting ? '#eff6ff' : 'white'}
                stroke={isConnecting ? '#3b82f6' : inboxColor}
                strokeWidth={agent.has_pending_inbox ? 4 : 2}
                initial={{ scale: 0 }} animate={{ scale: 1 }}
                whileHover={{ scale: 1.1 }}
                style={{ filter: `drop-shadow(0 4px 12px ${statusColor}40)` }}
            />

            {/* Agent Icon/Text */}
            <text x={cx} y={cy + 5} textAnchor="middle" fill="#1e293b" fontSize={14} fontWeight="bold" style={{ pointerEvents: 'none' }}>
                {agent.agent_id.substring(0, 2).toUpperCase()}
            </text>

            <text x={cx} y={cy + 48} textAnchor="middle" fill="#64748b" fontSize={11} fontWeight="600" style={{ pointerEvents: 'none' }}>
                {agent.agent_id}
            </text>

            {/* Status Dot */}
            <circle cx={cx + 22} cy={cy - 22} r={6} fill={statusColor} stroke="white" strokeWidth={2} />
        </g>
    )
}


export function AgentGalaxyPage({ projectId, config, onSaveConfig }) {
    const [agents, setAgents] = useState([]);
    const [selectedAgent, setSelectedAgent] = useState(null);
    const [menuPos, setMenuPos] = useState({ x: 0, y: 0 });
    const [viewerSize, setViewerSize] = useState({ w: 800, h: 600 });
    const containerRef = useRef(null);

    const [graph, setGraph] = useState({ nodes: [], matrix: {} });
    // Connect Mode State
    const [connectingSource, setConnectingSource] = useState(null);

    // Polling Logic
    const loadAgents = async () => {
        try {
            const [agentData, graphData] = await Promise.all([
                getAgentStatus(projectId),
                getSocialGraph(projectId)
            ]);
            setAgents(agentData.agents || []);
            setGraph((graphData && graphData.graph) ? graphData.graph : (graphData || { nodes: [], matrix: {} }));
        } catch (e) {
            console.error(e);
        }
    };

    useEffect(() => { loadAgents(); }, [projectId]);
    usePolling(loadAgents, 3000, [projectId]);

    useEffect(() => {
        if (containerRef.current) {
            setViewerSize({
                w: containerRef.current.clientWidth,
                h: containerRef.current.clientHeight
            });
        }
    }, []);

    const handleAction = async (action, agentId) => {
        // Implementation of actions
        if (!agentId) return;

        if (action === 'connect') {
            setConnectingSource(agentId);
            setSelectedAgent(null); // Close menu
            return;
        }

        if (action === 'toggle') {
            const agent = agents.find(a => a.agent_id === agentId);
            if (!agent) return;
            const next = JSON.parse(JSON.stringify(config));
            const proj = next.projects[projectId] || {};
            const activeSet = new Set(proj.active_agents || []);

            if (activeSet.has(agentId)) activeSet.delete(agentId);
            else activeSet.add(agentId);

            proj.active_agents = Array.from(activeSet).sort();
            await onSaveConfig(next);
            loadAgents();
            setSelectedAgent(null);
            return;
        }

        if (action === 'delete') {
            if (window.confirm(`Delete ${agentId}?`)) {
                await deleteAgent(agentId);
                loadAgents();
            }
            setSelectedAgent(null);
            return;
        }

        if (action === 'save') {
            setSelectedAgent(null);
            return;
        }

        setSelectedAgent(null);
    };

    const handleNodeClick = async (agent, x, y) => {
        if (connectingSource) {
            if (connectingSource === agent.agent_id) {
                setConnectingSource(null); // Cancel
                return;
            }

            // Toggle edge
            const matrix = graph.matrix || {};
            const currentWeight = (matrix[connectingSource] || {})[agent.agent_id] || 0;
            const newAllowed = currentWeight > 0 ? false : true; // Toggle

            try {
                await updateSocialEdge(projectId, connectingSource, agent.agent_id, newAllowed);
                loadAgents();
            } catch (e) {
                console.error(e);
                alert('Failed to update edge');
            }
            setConnectingSource(null);
            return;
        }

        // Adjust x,y to be relative to container if needed...
        const rect = containerRef.current.getBoundingClientRect();
        setMenuPos({ x: x - rect.left, y: y - rect.top });
        setSelectedAgent(agent);
    };

    // Layout Logic (Simple Grid/Force Layout Fallback)
    const getAgentPos = (index, total) => {
        // Spiral Layout
        if (total === 0) return { x: viewerSize.w / 2, y: viewerSize.h / 2 };

        const centerX = viewerSize.w / 2;
        const centerY = viewerSize.h / 2;

        if (total === 1) return { x: centerX, y: centerY };

        // Spiral
        const angle = index * 2.4; // Golden angle approx
        const r = 100 + index * 60; // Increased spacing for lines
        // Keep within bounds
        const maxR = Math.min(viewerSize.w, viewerSize.h) / 2 - 80;
        const safeR = Math.min(r, maxR);

        return {
            x: centerX + safeR * Math.cos(angle),
            y: centerY + safeR * Math.sin(angle)
        };
    };

    // Calculate positions once per render cycle for lines to use
    const agentPositions = useMemo(() => {
        const map = {};
        agents.forEach((a, i) => {
            map[a.agent_id] = getAgentPos(i, agents.length);
        });
        return map;
    }, [agents, viewerSize]);

    // Generate Lines
    const connections = useMemo(() => {
        const lines = [];
        const matrix = graph.matrix || {};
        const nodes = graph.nodes || [];

        Object.keys(matrix).forEach(srcId => {
            const row = matrix[srcId];
            if (!agentPositions[srcId]) return;

            Object.keys(row).forEach(dstId => {
                const val = row[dstId];
                if (val > 0 && agentPositions[dstId]) {
                    // Check reverse edge
                    const reverseVal = (matrix[dstId] || {})[srcId];
                    const isBiDirectional = reverseVal > 0;

                    lines.push({
                        src: srcId,
                        dst: dstId,
                        weight: val,
                        p1: agentPositions[srcId],
                        p2: agentPositions[dstId],
                        isBiDirectional
                    });
                }
            });
        });
        return lines;
    }, [graph, agentPositions]);

    return (
        <div className="galaxy-container" ref={containerRef} onClick={() => setSelectedAgent(null)}>
            <div className="galaxy-bg" />

            <h2 className="galaxy-title">
                <Hexagon size={24} style={{ color: '#3b82f6' }} />
                Agent Galaxy
                <span className="mono dim text-sm ml-4">{projectId}</span>
                {connectingSource && (
                    <div style={{ marginLeft: 20, fontSize: 14, color: '#3b82f6', display: 'flex', alignItems: 'center' }}>
                        <MousePointer size={14} style={{ marginRight: 6 }} />
                        Select target to connect from {connectingSource}...
                    </div>
                )}
            </h2>

            <svg className="galaxy-svg" width="100%" height="100%">
                <defs>
                    <filter id="glow">
                        <feGaussianBlur stdDeviation="4.5" result="coloredBlur" />
                        <feMerge><feMergeNode in="coloredBlur" /><feMergeNode in="SourceGraphic" /></feMerge>
                    </filter>
                    <marker id="line-arrow" viewBox="0 0 10 10" refX="35" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                        <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" />
                    </marker>
                </defs>

                {/* Connections */}
                {connections.map((line, i) => {
                    let d = '';
                    if (line.isBiDirectional) {
                        const dx = line.p2.x - line.p1.x;
                        const dy = line.p2.y - line.p1.y;
                        const dist = Math.sqrt(dx * dx + dy * dy);
                        if (dist === 0) return null;

                        // Offset for curvature (to the right of direction)
                        const offset = 30;
                        const mx = (line.p1.x + line.p2.x) / 2;
                        const my = (line.p1.y + line.p2.y) / 2;
                        const nx = -dy / dist; // Normal x
                        const ny = dx / dist;  // Normal y

                        const cx = mx + nx * offset;
                        const cy = my + ny * offset;

                        d = `M ${line.p1.x} ${line.p1.y} Q ${cx} ${cy} ${line.p2.x} ${line.p2.y}`;
                    } else {
                        d = `M ${line.p1.x} ${line.p1.y} L ${line.p2.x} ${line.p2.y}`;
                    }

                    return (
                        <motion.path
                            key={`${line.src}-${line.dst}`}
                            d={d}
                            fill="none"
                            stroke="#94a3b8"
                            strokeWidth={Math.min(line.weight, 3)}
                            strokeOpacity={0.6}
                            markerEnd="url(#line-arrow)"
                            initial={{ pathLength: 0, opacity: 0 }}
                            animate={{ pathLength: 1, opacity: 0.6 }}
                            transition={{ duration: 1, delay: i * 0.05 }}
                        />
                    );
                })}

                {agents.map((agent, i) => {
                    const pos = agentPositions[agent.agent_id] || { x: 0, y: 0 };
                    return (
                        <AgentNode
                            key={agent.agent_id}
                            agent={agent}
                            cx={pos.x} cy={pos.y}
                            onClick={handleNodeClick}
                        />
                    );
                })}
            </svg>

            <AnimatePresence>
                {selectedAgent && (
                    <RadialMenu
                        x={menuPos.x} y={menuPos.y}
                        agentId={selectedAgent.agent_id}
                        isActive={selectedAgent.status === 'running'}
                        onAction={handleAction}
                        onClose={() => setSelectedAgent(null)}
                    />
                )}
            </AnimatePresence>

            <div className="galaxy-legend panel">
                <div className="legend-item"><div className="dot" style={{ background: '#22c55e' }} /> Running</div>
                <div className="legend-item"><div className="dot" style={{ background: '#f59e0b' }} /> Idle</div>
                <div className="legend-item"><div className="dot" style={{ background: '#ef4444' }} /> Stopped</div>
                <div className="legend-item"><div className="dot ring" style={{ borderColor: '#a855f7' }} /> Inbox</div>
            </div>
        </div>
    );
}
