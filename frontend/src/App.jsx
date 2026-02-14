import React, { useState, useEffect, useRef } from 'react';
import {
  Users, UserPlus, Trash2, Settings, MessageSquare,
  Send, Brain, Terminal, X, ChevronRight, Activity, Zap, Save, RefreshCw, Plus
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import './App.css';

const App = () => {
  const [agents, setAgents] = useState([]);
  const [activeTab, setActiveTab] = useState('debate');
  const [selectedAgentId, setSelectedAgentId] = useState(null);
  const [isConfigOpen, setIsConfigOpen] = useState(false);
  const [config, setConfig] = useState({
    openrouter_api_key: '',
    current_project: 'default',
    projects: { default: { name: 'Default World', active_agents: [], agent_settings: {} } }
  });
  const [messages, setMessages] = useState([]);
  const [privateHistory, setPrivateHistory] = useState({});
  const [isStreaming, setIsStreaming] = useState(false);
  const [inputText, setInputText] = useState('');
  const [newAgentMode, setNewAgentMode] = useState(false);
  const [newAgentData, setNewAgentData] = useState({ id: '', directives: '' });

  const [prayers, setPrayers] = useState([]);
  const [isSimulationRunning, setIsSimulationRunning] = useState(false);

  useEffect(() => {
    refreshData();
    const interval = setInterval(fetchPrayers, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchPrayers = async () => {
    try {
      const res = await fetch('/prayers/check');
      const data = await res.json();
      setPrayers(data.prayers || []);
    } catch (e) { }
  };

  const refreshData = async () => {
    try {
      const res = await fetch('/config');
      const data = await res.json();
      setConfig(data);

      const proj = (data.projects && data.projects[data.current_project]) || { active_agents: [], agent_settings: {} };
      setIsSimulationRunning(proj.simulation_enabled || false);

      const available = (data.available_agents || []).map(id => ({
        id,
        name: id.toUpperCase(),
        model: proj.agent_settings?.[id]?.model || 'google/gemini-2.0-flash-exp:free',
        isActive: proj.active_agents?.includes(id) || false
      }));
      setAgents(available);
    } catch (err) {
      console.error("Failed to load setup", err);
    }
  };

  const switchProject = async (pid) => {
    try {
      await fetch('/config/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...config, current_project: pid })
      });
      refreshData();
    } catch (e) { }
  };

  const createProject = async () => {
    const pid = prompt("Divine World Name (No spaces):");
    if (!pid) return;
    try {
      await fetch('/projects/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: pid })
      });
      await switchProject(pid);
    } catch (e) { }
  };

  const currentProj = config.projects[config.current_project] || { name: 'Default', agent_settings: {}, active_agents: [] };

  const updateCurrentProj = (updates) => {
    const newConfig = { ...config };
    newConfig.projects[config.current_project] = { ...currentProj, ...updates };
    setConfig(newConfig);
  };

  const handleUpdateConfig = async (newCfg) => {
    try {
      await fetch('/config/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newCfg)
      });
      refreshData();
      setIsConfigOpen(false);
    } catch (e) { alert("Save failed"); }
  };

  const handleCreateAgent = async () => {
    if (!newAgentData.id) return;
    try {
      await fetch('/agents/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_id: newAgentData.id, directives: newAgentData.directives })
      });
      setNewAgentMode(false);
      refreshData();
    } catch (e) { alert("Failed to create Being"); }
  };

  const handleDeleteAgent = async (id) => {
    if (!confirm(`Banish ${id} from the realm?`)) return;
    try {
      await fetch(`/agents/${id}`, { method: 'DELETE' });
      refreshData();
    } catch (e) { }
  };

  const handleBroadcast = async () => {
    if (!inputText.trim() || isStreaming) return;
    setIsStreaming(true);
    const text = inputText;
    setInputText('');
    setMessages([]);

    try {
      const response = await fetch('/broadcast', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, thread_id: 'decree_' + Date.now() })
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const data = JSON.parse(line.substring(6));
            if (data.node) {
              setMessages(prev => [...prev, data]);
            }
          } catch (e) { }
        }
      }
    } catch (err) { } finally { setIsStreaming(false); }
  };

  const handleConfession = async () => {
    if (!inputText.trim() || !selectedAgentId) return;
    const text = inputText;
    setInputText('');

    const userMsg = { speaker: 'user', content: text };
    setPrivateHistory(prev => ({
      ...prev,
      [selectedAgentId]: [...(prev[selectedAgentId] || []), userMsg]
    }));

    try {
      await fetch('/confess', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_id: selectedAgentId, message: text })
      });
    } catch (e) { alert("Confession failed"); }
  };

  const handleMainAction = () => {
    if (activeTab === 'debate') handleBroadcast();
    else handleConfession();
  };

  return (
    <div className="app-container">
      <aside className="sidebar glass">
        <div className="sidebar-header">
          <Brain className="logo-icon" />
          <h2 className="display-font">GODS TEMPLE</h2>
        </div>

        <nav className="sidebar-nav">
          <div className={`nav-item ${activeTab === 'debate' ? 'active' : ''}`} onClick={() => setActiveTab('debate')}>
            <Activity size={18} />
            <span>Sacred Chamber (Public)</span>
          </div>

          <div className={`nav-item ${activeTab === 'prayers' ? 'active' : ''}`} onClick={() => setActiveTab('prayers')}>
            <MessageSquare size={18} />
            <span>Sacred Prayers {prayers.length > 0 && <span className="badge">{prayers.length}</span>}</span>
          </div>

          <div className="nav-group-label">CURRENT WORLD</div>
          <div className="project-switcher glass-light">
            <select value={config.current_project} onChange={(e) => switchProject(e.target.value)}>
              {Object.keys(config.projects || {}).map(pid => (
                <option key={pid} value={pid}>{pid}</option>
              ))}
            </select>
            <button className="add-proj-btn" onClick={() => createProject()}><Plus size={14} /></button>
          </div>

          <div className="nav-group-label">LEGION OF AGENTS</div>
          {agents.map(agent => (
            <div
              key={agent.id}
              className={`agent-item ${selectedAgentId === agent.id && activeTab === 'private' ? 'active' : ''}`}
              onClick={() => { setSelectedAgentId(agent.id); setActiveTab('private'); }}
            >
              <div className="agent-status" style={{ background: agent.isActive ? 'var(--accent-gold)' : '#333' }} />
              <span className="agent-label">{agent.name}</span>
              <button className="del-btn" onClick={(e) => { e.stopPropagation(); handleDeleteAgent(agent.id); }}>
                <Trash2 size={12} />
              </button>
            </div>
          ))}

          <button className="create-btn" onClick={() => setNewAgentMode(true)}>
            <UserPlus size={16} />
            <span>Invoke New Being</span>
          </button>
        </nav>

        <div className="sidebar-footer">
          <div className="sim-status">
            <span className={`orb ${isSimulationRunning ? 'pulse green' : 'red'}`} />
            <span className="fade">{isSimulationRunning ? 'Simulation Pulse Active' : 'Simulation Latent'}</span>
          </div>
          <button className="console-btn" onClick={() => setIsConfigOpen(true)}>
            <Settings size={18} />
            <span>Sacred Registry</span>
          </button>
        </div>
      </aside>

      <main className="workspace">
        <header className="workspace-header">
          <div className="breadcrumb">
            <span className="fade">SYSTEM</span>
            <ChevronRight size={14} className="fade" />
            <span className="glow">{activeTab.toUpperCase()}</span>
          </div>
          <button className="refresh-btn" onClick={refreshData}><RefreshCw size={14} /></button>
        </header>

        <div className="content-area scrollbar-hide">
          {activeTab === 'debate' && (
            <div className="debate-grid">
              {agents.filter(a => a.isActive).map(agent => (
                <div key={agent.id} className="agent-chamber glass">
                  <div className="chamber-header">
                    <span className="chamber-name">{agent.name}</span>
                    <div className="chamber-stats">
                      <span className="chamber-model">{agent.model.split('/').pop()}</span>
                      <Zap size={12} className="pulse" />
                    </div>
                  </div>
                  <div className="chamber-messages">
                    {messages.filter(m => m.node === agent.id).map((m, idx) => (
                      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} key={idx} className="msg-bubble">
                        <ReactMarkdown>{m.content}</ReactMarkdown>
                      </motion.div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          {activeTab === 'prayers' && (
            <div className="prayers-view glass">
              <h3>Incoming Prayers</h3>
              <div className="prayers-list">
                {prayers.map((prayer, idx) => (
                  <div key={idx} className="prayer-item glass-light">
                    <div className="prayer-meta">
                      <span className="prayer-sender">{prayer.from}</span>
                      <span className="prayer-time">{new Date(prayer.timestamp * 1000).toLocaleTimeString()}</span>
                    </div>
                    <div className="prayer-content">{prayer.content}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'private' && (
            <div className="private-chat-view">
              <div className="chat-window glass">
                <div className="chat-log scrollbar-hide">
                  {(privateHistory[selectedAgentId] || []).map((m, idx) => (
                    <div key={idx} className={`message ${m.speaker === 'user' ? 'user' : 'agent'}`}>
                      <div className="msg-content">
                        <ReactMarkdown>{m.content}</ReactMarkdown>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {activeTab !== 'prayers' && (
          <footer className="input-section glass">
            <div className="input-wrapper">
              <input
                type="text"
                placeholder={activeTab === 'debate' ? "Submit Sacred Decree..." : `Confessional to ${selectedAgentId}...`}
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleMainAction()}
              />
              <button className="send-btn" onClick={handleMainAction} disabled={isStreaming}>
                {isStreaming ? <Activity className="spin" /> : <Send size={18} />}
              </button>
            </div>
          </footer>
        )}
      </main>

      {/* Creation Modal */}
      <AnimatePresence>
        {newAgentMode && (
          <motion.div className="modal-overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <motion.div className="modal-card glass-heavy" initial={{ y: 50 }} animate={{ y: 0 }}>
              <h3>Divine Incarnation</h3>
              <div className="form-field">
                <label>Identity Code (ID)</label>
                <input value={newAgentData.id} onChange={e => setNewAgentData({ ...newAgentData, id: e.target.value })} placeholder="e.g. archangel" />
              </div>
              <div className="form-field">
                <label>Core Directives (agent.md)</label>
                <textarea rows={6} value={newAgentData.directives} onChange={e => setNewAgentData({ ...newAgentData, directives: e.target.value })} placeholder="# YOUR MISSION..." />
              </div>
              <div className="modal-actions">
                <button onClick={() => setNewAgentMode(false)}>Cancel</button>
                <button className="primary" onClick={handleCreateAgent}>Breathe Life</button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Settings Modal */}
      <AnimatePresence>
        {isConfigOpen && (
          <motion.div className="modal-overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <motion.div className="modal-card glass-heavy large" initial={{ scale: 0.95 }}>
              <div className="modal-header">
                <h3>AETHER REGISTRY: {currentProj.name}</h3>
                <X className="close-icon" onClick={() => setIsConfigOpen(false)} />
              </div>
              <div className="modal-body">
                <div className="form-group glass-light">
                  <h4>Global Context</h4>
                  <div className="form-field">
                    <label>OpenRouter Access Key</label>
                    <input type="password" value={config.openrouter_api_key} onChange={e => setConfig({ ...config, openrouter_api_key: e.target.value })} />
                  </div>
                  <div className="config-row">
                    <span>Background Heartbeat (Simulation)</span>
                    <label className="toggle">
                      <input type="checkbox" checked={currentProj.simulation_enabled} onChange={e => updateCurrentProj({ simulation_enabled: e.target.checked })} />
                      <span className="slider"></span>
                    </label>
                  </div>
                  <div className="config-row">
                    <span>Pulse Interval (s)</span>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <input style={{ width: '40px' }} type="number" value={currentProj.simulation_interval_min} onChange={e => updateCurrentProj({ simulation_interval_min: parseInt(e.target.value) })} />
                      -
                      <input style={{ width: '40px' }} type="number" value={currentProj.simulation_interval_max} onChange={e => updateCurrentProj({ simulation_interval_max: parseInt(e.target.value) })} />
                    </div>
                  </div>
                </div>

                <div className="form-group glass-light">
                  <h4>Sacred Memory (Summarization)</h4>
                  <div className="config-row">
                    <span>Summary Threshold (Messages)</span>
                    <input style={{ width: '60px' }} type="number" value={currentProj.summarize_threshold} onChange={e => updateCurrentProj({ summarize_threshold: parseInt(e.target.value) })} />
                  </div>
                  <div className="config-row">
                    <span>Messages to Retain</span>
                    <input style={{ width: '60px' }} type="number" value={currentProj.summarize_keep_count} onChange={e => updateCurrentProj({ summarize_keep_count: parseInt(e.target.value) })} />
                  </div>
                </div>

                <div className="agents-config-list glass-light">
                  <h4>Legion Allocation & Power Restriction</h4>
                  {agents.map(a => (
                    <div key={a.id} className="agent-config-card glass-light">
                      <div className="config-row">
                        <span className="row-id">{a.id}</span>
                        <input className="row-model" value={currentProj.agent_settings?.[a.id]?.model || ''} onChange={e => {
                          const s = { ...(currentProj.agent_settings || {}) };
                          s[a.id] = { ...s[a.id], model: e.target.value };
                          updateCurrentProj({ agent_settings: s });
                        }} />
                        <label className="toggle">
                          <input type="checkbox" checked={currentProj.active_agents?.includes(a.id)} onChange={e => {
                            let active = [...(currentProj.active_agents || [])];
                            if (e.target.checked) active.push(a.id);
                            else active = active.filter(x => x !== a.id);
                            updateCurrentProj({ active_agents: active });
                          }} />
                          <span className="slider"></span>
                        </label>
                      </div>
                      <div className="tool-toggle-grid">
                        <span className="fade small">Empowered Tools:</span>
                        <div className="tools-list">
                          {config.all_tools?.map(tool => {
                            const isDisabled = currentProj.agent_settings?.[a.id]?.disabled_tools?.includes(tool);
                            return (
                              <button
                                key={tool}
                                className={`tool-tag ${isDisabled ? 'disabled' : 'enabled'}`}
                                onClick={() => {
                                  const s = { ...(currentProj.agent_settings || {}) };
                                  const agentCfg = { ...s[a.id] };
                                  let dt = [...(agentCfg.disabled_tools || [])];
                                  if (isDisabled) dt = dt.filter(t => t !== tool);
                                  else dt.push(tool);
                                  agentCfg.disabled_tools = dt;
                                  s[a.id] = agentCfg;
                                  updateCurrentProj({ agent_settings: s });
                                }}
                              >
                                {tool}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="modal-actions">
                <button className="primary" onClick={() => { handleUpdateConfig(config); }}>
                  <Save size={16} /> Enshrine Decree
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default App;
