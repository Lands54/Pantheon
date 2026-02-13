import React, { useState, useEffect, useRef } from 'react';
import {
  Users, UserPlus, Trash2, Settings, MessageSquare,
  Send, Brain, Terminal, X, ChevronRight, Activity, Zap, Save, RefreshCw
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import './App.css';

const App = () => {
  const [agents, setAgents] = useState([]);
  const [activeTab, setActiveTab] = useState('debate');
  const [selectedAgentId, setSelectedAgentId] = useState(null);
  const [isConfigOpen, setIsConfigOpen] = useState(false);
  const [config, setConfig] = useState({ openrouter_api_key: '', agent_settings: {}, active_agents: [] });
  const [messages, setMessages] = useState([]);
  const [privateHistory, setPrivateHistory] = useState({});
  const [isStreaming, setIsStreaming] = useState(false);
  const [inputText, setInputText] = useState('');
  const [newAgentMode, setNewAgentMode] = useState(false);
  const [newAgentData, setNewAgentData] = useState({ id: '', directives: '' });

  const scrollRef = useRef({});

  useEffect(() => {
    refreshData();
  }, []);

  const refreshData = async () => {
    try {
      const res = await fetch('/config');
      const data = await res.json();
      setConfig(data);
      const available = data.available_agents.map(id => ({
        id,
        name: id.toUpperCase(),
        model: data.agent_settings[id]?.model || 'google/gemini-2.0-flash-exp:free',
        isActive: data.active_agents.includes(id)
      }));
      setAgents(available);
    } catch (err) {
      console.error("Failed to load setup", err);
    }
  };

  const handleUpdateConfig = async (newCfg) => {
    try {
      await fetch('/config/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newCfg)
      });
      refreshData();
    } catch (e) { alert("Save failed"); }
  };

  const handleCreateAgent = async () => {
    if (!newAgentData.id) return;
    try {
      await fetch('/agents/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newAgentData)
      });
      setNewAgentMode(false);
      setNewAgentData({ id: '', directives: '' });
      refreshData();
    } catch (e) { alert("Creation failed"); }
  };

  const handleDeleteAgent = async (id) => {
    if (!window.confirm(`Delete agent ${id}?`)) return;
    try {
      await fetch(`/agents/${id}`, { method: 'DELETE' });
      refreshData();
    } catch (e) { alert("Delete failed"); }
  };

  const handleMainAction = () => {
    if (activeTab === 'debate') handleStartDebate();
    else handlePrivateChatAction();
  };

  const handleStartDebate = async () => {
    if (!inputText.trim() || isStreaming) return;
    setIsStreaming(true);
    setMessages([]);

    try {
      const response = await fetch('/oracle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task: inputText, thread_id: 'debate_' + Date.now() })
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
              setMessages(prev => {
                const lastIdx = prev.length - 1;
                // Since our backend emits step-by-step, we might want to append or update
                // For simplified debate view, we append unique messages per node/step
                return [...prev, data];
              });
            }
          } catch (e) { }
        }
      }
    } catch (err) { } finally { setIsStreaming(false); setInputText(''); }
  };

  const handlePrivateChatAction = async () => {
    if (!inputText.trim() || isStreaming || !selectedAgentId) return;
    const text = inputText;
    setInputText('');
    setIsStreaming(true);

    const userMsg = { speaker: 'user', content: text };
    setPrivateHistory(prev => ({
      ...prev,
      [selectedAgentId]: [...(prev[selectedAgentId] || []), userMsg]
    }));

    try {
      const response = await fetch('/chat/private', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent_id: selectedAgentId,
          message: text,
          thread_id: 'private_' + selectedAgentId
        })
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
          const data = JSON.parse(line.substring(6));
          setPrivateHistory(prev => {
            const current = prev[selectedAgentId] || [];
            // If it's intermediate, update last; if result, append
            return { ...prev, [selectedAgentId]: [...current, data] };
          });
        }
      }
    } catch (e) { } finally { setIsStreaming(false); }
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
            <span>Resonance Mode</span>
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
            <span>New Creation</span>
          </button>
        </nav>

        <div className="sidebar-footer">
          <button className="console-btn" onClick={() => setIsConfigOpen(true)}>
            <Settings size={18} />
            <span>Master Registry</span>
          </button>
        </div>
      </aside>

      <main className="workspace">
        <header className="workspace-header">
          <div className="breadcrumb">
            <span className="fade">{activeTab.toUpperCase()}</span>
            <ChevronRight size={14} className="fade" />
            <span className="glow">{activeTab === 'debate' ? 'GLOBAL ORACLE' : selectedAgentId}</span>
          </div>
          {activeTab === 'debate' && <button className="refresh-btn" onClick={refreshData}><RefreshCw size={14} /></button>}
        </header>

        <div className="content-area scrollbar-hide">
          {activeTab === 'debate' ? (
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
          ) : (
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

        <footer className="input-section glass">
          <div className="input-wrapper">
            <input
              type="text"
              placeholder={activeTab === 'debate' ? "Submit Divine Inquiry..." : `Direct Command to ${selectedAgentId}...`}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleMainAction()}
            />
            <button className="send-btn" onClick={handleMainAction} disabled={isStreaming}>
              {isStreaming ? <Activity className="spin" /> : <Send size={18} />}
            </button>
          </div>
        </footer>
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
                <h3>AETHER REGISTRY</h3>
                <X className="close-icon" onClick={() => setIsConfigOpen(false)} />
              </div>
              <div className="modal-body">
                <div className="form-field">
                  <label>OpenRouter Access Key</label>
                  <input type="password" value={config.openrouter_api_key} onChange={e => setConfig({ ...config, openrouter_api_key: e.target.value })} />
                </div>
                <div className="agents-config-list">
                  <label>Agent Configuration</label>
                  {agents.map(a => (
                    <div key={a.id} className="config-row">
                      <span className="row-id">{a.id}</span>
                      <input className="row-model" value={config.agent_settings[a.id]?.model || ''} onChange={e => {
                        const s = { ...config.agent_settings };
                        s[a.id] = { model: e.target.value };
                        setConfig({ ...config, agent_settings: s });
                      }} />
                      <label className="toggle">
                        <input type="checkbox" checked={config.active_agents.includes(a.id)} onChange={e => {
                          let active = [...config.active_agents];
                          if (e.target.checked) active.push(a.id);
                          else active = active.filter(x => x !== a.id);
                          setConfig({ ...config, active_agents: active });
                        }} />
                        <span className="slider"></span>
                      </label>
                    </div>
                  ))}
                </div>
              </div>
              <div className="modal-actions">
                <button className="primary" onClick={() => { handleUpdateConfig(config); setIsConfigOpen(false); }}>
                  <Save size={16} /> Commit to Aether
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
