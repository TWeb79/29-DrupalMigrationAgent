import { useState, useEffect, useRef } from "react";

// Theme definitions
const THEMES = {
  dark: {
    bg: "#090b12",
    bgSecondary: "#0d1017",
    bgTertiary: "#141822",
    border: "#1e2533",
    text: "#e2e8f0",
    textSecondary: "#94a3b8",
    textMuted: "#475569",
    primary: "#6366f1",
    primaryHover: "#818cf8",
    success: "#10b981",
    warning: "#f97316",
    error: "#f87171",
    scrollTrack: "#0f1117",
    scrollThumb: "#2d3748",
  },
  light: {
    bg: "#f8fafc",
    bgSecondary: "#ffffff",
    bgTertiary: "#f1f5f9",
    border: "#e2e8f0",
    text: "#1e293b",
    textSecondary: "#64748b",
    textMuted: "#94a3b8",
    primary: "#6366f1",
    primaryHover: "#4f46e5",
    success: "#10b981",
    warning: "#f97316",
    error: "#ef4444",
    scrollTrack: "#f1f5f9",
    scrollThumb: "#cbd5e1",
  },
};

const AGENTS = {
  orchestrator: { label: "Orchestrator", color: "#6366f1", icon: "🧠" },
  analyzer:     { label: "Analyzer",     color: "#f59e0b", icon: "🔍" },
  train:        { label: "TrainAgent",   color: "#8b5cf6", icon: "📚" },
  build:        { label: "BuildAgent",   color: "#10b981", icon: "🏗️" },
  theme:        { label: "ThemeAgent",   color: "#ec4899", icon: "🎨" },
  content:      { label: "ContentAgent", color: "#14b8a6", icon: "📝" },
  test:         { label: "TestAgent",    color: "#f97316", icon: "🧪" },
  qa:           { label: "QAAgent",      color: "#06b6d4", icon: "✅" },
  memory:       { label: "MemoryAgent",  color: "#64748b", icon: "🗄️" },
};

const MOCK_LOGS = [
  { id: 1, agent: "orchestrator", msg: "Received URL: https://example-agency.com", status: "done", detail: "Parsing user intent. Mode: full migration." },
  { id: 2, agent: "orchestrator", msg: "Build plan created — 24 tasks queued", status: "done", detail: "Dispatching AnalyzerAgent as first step." },
  { id: 3, agent: "analyzer",     msg: "Scraping source site...", status: "done", detail: "Crawling 6 pages. Extracting structure." },
  { id: 4, agent: "analyzer",     msg: "Detected: Hero, Nav, Cards ×3, Footer, Blog grid", status: "done", detail: "Color palette: #1a1a2e, #e94560, #fff. Font: Playfair Display + Inter." },
  { id: 5, agent: "memory",       msg: "Site Blueprint written to memory", status: "done", detail: "Key: site_blueprint — 2.4KB" },
  { id: 6, agent: "orchestrator", msg: "Checking component knowledge gaps...", status: "done", detail: "2 unknown components: paragraph--hero-video, views--masonry-grid" },
  { id: 7, agent: "train",        msg: "Testing paragraph--hero-video...", status: "done", detail: "Created test page /train/hero-video-001. Tested 8 parameter combinations." },
  { id: 8, agent: "train",        msg: "Testing views--masonry-grid...", status: "active", detail: "Running parameter sweep... 4/12 combinations tested." },
  { id: 9, agent: "build",        msg: "Creating homepage structure...", status: "active", detail: "POST /jsonapi/node/page — placing regions" },
  { id: 10, agent: "theme",       msg: "Generating sub-theme from design tokens...", status: "active", detail: "Base: Olivero. Applying brand palette + fonts." },
  { id: 11, agent: "content",     msg: "Queued: 6 pages, 34 images, 2 menus", status: "pending", detail: "Waiting for BuildAgent page structure." },
  { id: 12, agent: "test",        msg: "Awaiting first build cycle...", status: "pending", detail: "" },
  { id: 13, agent: "qa",          msg: "Standby — will run after TestAgent approval", status: "pending", detail: "" },
];

const MOCK_TASKS = [
  { id: 1,  section: "Discovery",  task: "Scrape & analyze source",        agent: "analyzer",     status: "done" },
  { id: 2,  section: "Discovery",  task: "Extract design tokens",           agent: "analyzer",     status: "done" },
  { id: 3,  section: "Discovery",  task: "Write Site Blueprint",            agent: "memory",       status: "done" },
  { id: 4,  section: "Knowledge",  task: "Train: hero-video component",     agent: "train",        status: "done" },
  { id: 5,  section: "Knowledge",  task: "Train: masonry-grid view",        agent: "train",        status: "active" },
  { id: 6,  section: "Build",      task: "Create homepage skeleton",        agent: "build",        status: "active" },
  { id: 7,  section: "Build",      task: "Create blog listing page",        agent: "build",        status: "pending" },
  { id: 8,  section: "Build",      task: "Create contact page",             agent: "build",        status: "pending" },
  { id: 9,  section: "Theme",      task: "Generate sub-theme",              agent: "theme",        status: "active" },
  { id: 10, section: "Theme",      task: "Apply brand colors & fonts",      agent: "theme",        status: "pending" },
  { id: 11, section: "Content",    task: "Migrate hero content",            agent: "content",      status: "pending" },
  { id: 12, section: "Content",    task: "Upload 34 media assets",          agent: "content",      status: "pending" },
  { id: 13, section: "Content",    task: "Create navigation menus",         agent: "content",      status: "pending" },
  { id: 14, section: "Verify",     task: "Visual comparison test",          agent: "test",         status: "pending" },
  { id: 15, section: "Verify",     task: "Content completeness check",      agent: "test",         status: "pending" },
  { id: 16, section: "QA",         task: "Accessibility audit (WCAG 2.1)",  agent: "qa",           status: "pending" },
  { id: 17, section: "QA",         task: "Lighthouse performance scan",     agent: "qa",           status: "pending" },
  { id: 18, section: "QA",         task: "Interactive click testing",       agent: "qa",           status: "pending" },
];

const STATUS_STYLE = {
  done:    { bg: "#052e16", text: "#4ade80", label: "Done" },
  active:  { bg: "#1c1917", text: "#fb923c", label: "Running" },
  pending: { bg: "#0f172a", text: "#475569", label: "Pending" },
  failed:  { bg: "#2d0a0a", text: "#f87171", label: "Failed" },
};

function AgentBadge({ agentKey, size = "sm" }) {
  const a = AGENTS[agentKey];
  if (!a) return null;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      background: a.color + "22", border: `1px solid ${a.color}44`,
      color: a.color, borderRadius: 6,
      padding: size === "sm" ? "1px 7px" : "3px 10px",
      fontSize: size === "sm" ? 11 : 12, fontWeight: 600,
      fontFamily: "monospace", whiteSpace: "nowrap",
    }}>
      {a.icon} {a.label}
    </span>
  );
}

function PulsingDot({ color }) {
  return (
    <span style={{
      display: "inline-block", width: 8, height: 8, borderRadius: "50%",
      background: color, boxShadow: `0 0 6px ${color}`,
      animation: "pulse 1.4s ease-in-out infinite",
    }} />
  );
}

const sections = ["Discovery", "Knowledge", "Build", "Theme", "Content", "Verify", "QA"];

// LLM Provider options
const LLM_PROVIDERS = [
  { id: "anthropic", label: "Claude (Anthropic)", icon: "🧠" },
  { id: "openai", label: "GPT-4 (OpenAI)", icon: "🤖" },
  { id: "ollama", label: "Ollama (Local)", icon: "💻" },
];

export default function DrupalMind() {
  const [url, setUrl] = useState("https://example-agency.com");
  const [mode, setMode] = useState("migrate");
  const [started, setStarted] = useState(false);
  const [expandedLog, setExpandedLog] = useState(null);
  const [activeSection, setActiveSection] = useState("Build");
  const [llmProvider, setLlmProvider] = useState("anthropic");
  const [theme, setTheme] = useState("dark");
  
  // Real-time log state
  const [logs, setLogs] = useState([]);
  const [jobId, setJobId] = useState(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [buildStatus, setBuildStatus] = useState("idle");
  const wsRef = useRef(null);
  const logRef = useRef(null);

  const t = THEMES[theme];
  const doneTasks = MOCK_TASKS.filter(task => task.status === "done").length;
  const progress = Math.round((doneTasks / MOCK_TASKS.length) * 100);

  // Connect to WebSocket when jobId is set
  useEffect(() => {
    if (!jobId) return;
    
    // Use relative WebSocket URL (proxied through nginx)
    const wsUrl = `ws://${window.location.host}/ws/${jobId}`;
    
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    
    ws.onopen = () => {
      setWsConnected(true);
      console.log('[WS] Connected to job:', jobId);
    };
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('[WS] Received:', data);
        
        if (data.type === 'log') {
          setLogs(prev => [...prev, { 
            id: Date.now(), 
            agent: data.agent, 
            msg: data.message, 
            status: data.status || 'active', 
            detail: data.detail || '',
            event_data: data.event_data || data.data || null,
            data_type: data.data?.data_type || null
          }]);
        } else if (data.type === 'image') {
          // Image events from agents (e.g. VisualDiffAgent.log_image)
          // Treat them as log entries so they show up in the Live Agent Log
          const label = data.data?.label || 'Screenshot';
          setLogs(prev => [...prev, {
            id: Date.now(),
            agent: data.agent || 'visualdiff',
            msg: label,
            status: data.status || 'done',
            // Non-empty detail so the row is expandable and can render the image
            detail: label,
            event_data: data.data || null,
            data_type: 'image',
          }]);
        } else if (data.type === 'started') {
          setBuildStatus('running');
        } else if (data.type === 'completed' || data.type === 'done') {
          setBuildStatus('done');
          setStarted(false);
        } else if (data.type === 'error') {
          setBuildStatus('error');
        }
      } catch (e) {
        console.error('[WS] Parse error:', e);
      }
    };
    
    ws.onerror = (error) => {
      console.error('[WS] Error:', error);
    };
    
    ws.onclose = () => {
      setWsConnected(false);
      console.log('[WS] Disconnected');
    };
    
    return () => {
      ws.close();
    };
  }, [jobId]);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [logs]);

  // Start a build job via REST API
  const startBuild = async () => {
    try {
      setStarted(true);
      setBuildStatus('starting');
      setLogs([]);
      
      // Use relative API URL (proxied through nginx)
      const response = await fetch('/api/build', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source: url, mode: mode })
      });
      
      if (!response.ok) {
        throw new Error(`Server error: ${response.status} ${response.statusText}`);
      }
      
      const data = await response.json();
      console.log('[API] Build started:', data);
      setJobId(data.job_id);
      setBuildStatus('running');
    } catch (error) {
      console.error('[API] Error starting build:', error);
      setBuildStatus('error');
      setStarted(false);
      // Show user-friendly error message
      const errorMsg = error.message || 'Failed to connect to server';
      alert(`Failed to start build: ${errorMsg}\n\nMake sure Docker containers are running:\ndocker-compose up -d`);
    }
  };

  return (
    <div style={{
      minHeight: "100vh", background: t.bg, color: t.text,
      fontFamily: "'DM Sans', system-ui, sans-serif",
      display: "flex", flexDirection: "column",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: ${t.scrollTrack}; }
        ::-webkit-scrollbar-thumb { background: ${t.scrollThumb}; border-radius: 4px; }
        @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:.3; } }
        @keyframes slideIn { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:none; } }
        .log-row:hover { background: ${theme === 'dark' ? '#ffffff08' : '#00000008'} !important; }
        .task-row:hover { background: ${theme === 'dark' ? '#ffffff06' : '#00000006'} !important; }
        .agent-node:hover { transform: scale(1.05); }
      `}</style>

      {/* Header */}
      <div style={{
        borderBottom: `1px solid ${t.border}`,
        padding: "0 24px",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        height: 52, background: t.bgSecondary,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 28, height: 28, borderRadius: 8,
            background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 14,
          }}>🧠</div>
          <span style={{ fontWeight: 700, fontSize: 16, letterSpacing: "-0.3px" }}>DrupalMind</span>
          <span style={{
            fontSize: 10, background: t.primary + "22", color: t.primary,
            border: `1px solid ${t.primary}33`, borderRadius: 4, padding: "1px 6px",
            fontFamily: "monospace", fontWeight: 600,
          }}>v0.1 BETA</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          {/* Theme Toggle */}
          <button
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            style={{
              background: t.bgTertiary,
              border: `1px solid ${t.border}`,
              borderRadius: 6,
              padding: "6px 12px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 6,
              color: t.text,
              fontSize: 14,
            }}
          >
            {theme === "dark" ? "🌙" : "☀️"}
          </button>
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: t.textSecondary }}>
            <PulsingDot color={wsConnected ? t.success : t.textMuted} />
            <span>{wsConnected ? `Connected (Job: ${jobId || '-'})` : "Disconnected"}</span>
          </div>
          <div style={{
            background: t.primary + "22", color: t.primary, border: `1px solid ${t.primary}33`,
            borderRadius: 6, padding: "4px 12px", fontSize: 12, fontWeight: 600, cursor: "pointer",
          }}>Drupal: localhost:5500 ↗</div>
        </div>
      </div>

      <div style={{ display: "flex", flex: 1, overflow: "hidden", height: "calc(100vh - 52px)" }}>

        {/* LEFT PANEL — Input + Agent Map */}
        <div style={{
          width: 280, borderRight: `1px solid ${t.border}`,
          display: "flex", flexDirection: "column", background: t.bgSecondary, flexShrink: 0,
        }}>
          {/* Input */}
          <div style={{ padding: 16, borderBottom: `1px solid ${t.border}` }}>
            <div style={{ fontSize: 10, color: t.textMuted, fontWeight: 600, letterSpacing: 1, marginBottom: 8, textTransform: "uppercase" }}>
              Migration Target
            </div>
            <div style={{
              display: "flex", gap: 4, marginBottom: 10,
            }}>
              {["migrate", "describe"].map(m => (
                <button key={m} onClick={() => setMode(m)} style={{
                  flex: 1, padding: "5px 0", borderRadius: 6, border: "none", cursor: "pointer",
                  fontSize: 11, fontWeight: 600,
                  background: mode === m ? t.primary : t.bgTertiary,
                  color: mode === m ? "#fff" : t.textSecondary,
                  transition: "all 0.15s",
                }}>
                  {m === "migrate" ? "🔗 URL" : "✏️ Describe"}
                </button>
              ))}
            </div>
            {mode === "migrate" ? (
              <input
                value={url}
                onChange={e => setUrl(e.target.value)}
                placeholder="https://source-site.com"
                style={{
                  width: "100%", background: t.bgTertiary, border: `1px solid ${t.border}`,
                  borderRadius: 8, padding: "8px 10px", color: t.text,
                  fontSize: 12, fontFamily: "DM Mono, monospace", outline: "none",
                }}
              />
            ) : (
              <textarea
                placeholder="Describe the website you want to build..."
                rows={3}
                style={{
                  width: "100%", background: t.bgTertiary, border: `1px solid ${t.border}`,
                  borderRadius: 8, padding: "8px 10px", color: t.text,
                  fontSize: 12, outline: "none", resize: "none", fontFamily: "DM Sans, sans-serif",
                }}
              />
            )}
            <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 4 }}>
              {[["Full site migration", true], ["Structure only", false], ["Content only", false]].map(([label, checked]) => (
                <label key={label} style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 11, color: t.textSecondary, cursor: "pointer" }}>
                  <div style={{
                    width: 14, height: 14, borderRadius: 4, border: `1px solid ${t.border}`,
                    background: checked ? t.primary : "transparent",
                    display: "flex", alignItems: "center", justifyContent: "center", fontSize: 9, color: "#fff",
                  }}>{checked ? "✓" : ""}</div>
                  {label}
                </label>
              ))}
            </div>
            
            {/* LLM Provider Selection */}
            <div style={{ marginTop: 12, paddingTop: 12, borderTop: `1px solid ${t.border}` }}>
              <div style={{ fontSize: 10, color: t.textMuted, fontWeight: 600, letterSpacing: 1, marginBottom: 8, textTransform: "uppercase" }}>
                AI Model
              </div>
              <div style={{ display: "flex", gap: 4 }}>
                {LLM_PROVIDERS.map(provider => (
                  <button
                    key={provider.id}
                    onClick={() => setLlmProvider(provider.id)}
                    style={{
                      flex: 1,
                      padding: "6px 4px",
                      borderRadius: 6,
                      border: "none",
                      cursor: "pointer",
                      fontSize: 10,
                      fontWeight: 600,
                      background: llmProvider === provider.id ? t.primary : t.bgTertiary,
                      color: llmProvider === provider.id ? "#fff" : t.textSecondary,
                      transition: "all 0.15s",
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      gap: 2,
                    }}
                  >
                    <span style={{ fontSize: 14 }}>{provider.icon}</span>
                    <span>{provider.label.split(" (")[0]}</span>
                  </button>
                ))}
              </div>
            </div>
            
            <button
              onClick={startBuild}
              disabled={started}
              style={{
                width: "100%", marginTop: 12, padding: "9px 0",
                background: started ? t.bgTertiary : "linear-gradient(135deg, #6366f1, #8b5cf6)",
                color: started ? t.textMuted : "#fff",
                border: "none", borderRadius: 8, fontSize: 13, fontWeight: 600,
                cursor: started ? "default" : "pointer",
                transition: "all 0.2s",
              }}
            >
              {started ? "⏳ Build in progress..." : "🚀 Start Build"}
            </button>
          </div>

          {/* Progress */}
          <div style={{ padding: "12px 16px", borderBottom: `1px solid ${t.border}` }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <span style={{ fontSize: 11, color: t.textSecondary }}>Overall Progress</span>
              <span style={{ fontSize: 12, fontWeight: 700, color: t.primary, fontFamily: "monospace" }}>{progress}%</span>
            </div>
            <div style={{ height: 4, background: t.bgTertiary, borderRadius: 4, overflow: "hidden" }}>
              <div style={{
                height: "100%", width: `${progress}%`,
                background: "linear-gradient(90deg, #6366f1, #8b5cf6)",
                borderRadius: 4, transition: "width 0.5s ease",
              }} />
            </div>
            <div style={{ marginTop: 8, fontSize: 11, color: t.textMuted }}>
              {doneTasks} / {MOCK_TASKS.length} tasks complete
            </div>
          </div>

          {/* Agent Status */}
          <div style={{ padding: "12px 16px", flex: 1, overflow: "auto" }}>
            <div style={{ fontSize: 10, color: t.textMuted, fontWeight: 600, letterSpacing: 1, marginBottom: 10, textTransform: "uppercase" }}>
              Agent Status
            </div>
            {Object.entries(AGENTS).map(([key, agent]) => {
              const isActive = ["train", "build", "theme"].includes(key);
              const isDone = ["orchestrator", "analyzer", "memory"].includes(key);
              const status = isDone ? "done" : isActive ? "active" : "pending";
              const s = STATUS_STYLE[status];
              return (
                <div key={key} className="agent-node" style={{
                  display: "flex", alignItems: "center", justifyContent: "space-between",
                  padding: "6px 10px", borderRadius: 8, marginBottom: 4,
                  background: t.bgTertiary, border: `1px solid ${t.border}`,
                  cursor: "pointer", transition: "transform 0.15s",
                }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                    <span style={{ fontSize: 14 }}>{agent.icon}</span>
                    <span style={{ fontSize: 12, fontWeight: 500, color: t.text }}>{agent.label}</span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                    {status === "active" && <PulsingDot color={agent.color} />}
                    <span style={{
                      fontSize: 10, padding: "1px 6px", borderRadius: 4,
                      background: s.bg, color: s.text, fontWeight: 600,
                    }}>{s.label}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* CENTER — Log + Task Board */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>

          {/* Live Log */}
          <div style={{ flex: 1, borderBottom: `1px solid ${t.border}`, overflow: "auto", padding: "0" }} ref={logRef}>
            <div style={{
              position: "sticky", top: 0, background: t.bg,
              padding: "10px 20px", borderBottom: `1px solid ${t.border}`,
              display: "flex", alignItems: "center", justifyContent: "space-between", zIndex: 2,
            }}>
              <span style={{ fontSize: 11, fontWeight: 600, color: t.textMuted, letterSpacing: 1, textTransform: "uppercase" }}>
                Live Agent Log
              </span>
              <span style={{ fontSize: 11, color: t.textMuted }}>
                {wsConnected ? "🟢" : "🔴"} {logs.length} entries
              </span>
            </div>
            {logs.length === 0 ? (
              <div style={{ padding: 40, textAlign: "center", color: t.textMuted }}>
                <div style={{ fontSize: 24, marginBottom: 8 }}>📋</div>
                <div style={{ fontSize: 12 }}>
                  {started ? "Waiting for agent logs..." : "Click 'Start Build' to begin"}
                </div>
              </div>
            ) : (
              logs.map((log, i) => {
                const agent = AGENTS[log.agent];
                const isExpanded = expandedLog === log.id;
                const isActive = log.status === "active";
                return (
                  <div
                    key={log.id}
                    className="log-row"
                    onClick={() => setExpandedLog(isExpanded ? null : log.id)}
                    style={{
                      padding: "8px 20px", cursor: "pointer",
                      borderBottom: `1px solid ${t.border}`,
                      animation: `slideIn 0.2s ease ${i * 0.03}s both`,
                      background: isExpanded ? "#ffffff06" : "transparent",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span style={{ fontSize: 10, color: "#334155", fontFamily: "monospace", minWidth: 50 }}>
                        {new Date(log.id).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                      </span>
                      <AgentBadge agentKey={log.agent} />
                      <span style={{ fontSize: 12, color: isActive ? t.text : t.textSecondary, flex: 1 }}>
                        {isActive && <><PulsingDot color={agent?.color || t.text} /> </>}
                        {log.msg}
                      </span>
                      {log.detail && (
                        <span style={{ fontSize: 10, color: "#334155" }}>{isExpanded ? "▲" : "▼"}</span>
                      )}
                    </div>
                    {isExpanded && log.detail && (
                      <div style={{
                      marginTop: 6, marginLeft: 60, padding: "8px 12px",
                      background: t.bgSecondary, borderRadius: 6, borderLeft: `2px solid ${agent?.color}44`,
                      fontSize: 11, color: t.textSecondary, fontFamily: "DM Mono, monospace",
                    }}>
                      {log.detail}
                      {/* Render images if present in event data */}
                      {log.event_data && log.event_data.image_url && (
                        <div style={{ marginTop: 8 }}>
                          {log.event_data.label && (
                            <div style={{ marginBottom: 4, fontSize: 10, color: t.textMuted }}>
                              {log.event_data.label}
                            </div>
                          )}
                          <img 
                            src={log.event_data.image_url} 
                            alt={log.event_data.label || "Screenshot"}
                            style={{ 
                              width: log.event_data.preview_width || 100, 
                              cursor: 'pointer',
                              borderRadius: 4,
                              border: `1px solid ${t.border}`,
                            }}
                            onClick={(e) => {
                              e.stopPropagation();
                              window.open(log.event_data.image_url, '_blank');
                            }}
                            title="Click to open in new window"
                          />
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            ))}
          </div>

          {/* Task Board */}
          <div style={{ height: 220, overflow: "auto", background: "#0d1017" }}>
            <div style={{
              position: "sticky", top: 0, background: t.bgSecondary,
              padding: "8px 20px", borderBottom: `1px solid ${t.border}`,
              display: "flex", alignItems: "center", gap: 12, zIndex: 2,
              overflowX: "auto",
            }}>
              <span style={{ fontSize: 11, fontWeight: 600, color: "#475569", letterSpacing: 1, textTransform: "uppercase", whiteSpace: "nowrap" }}>
                Build Plan
              </span>
              {sections.map(s => (
                <button key={s} onClick={() => setActiveSection(s)} style={{
                  padding: "3px 10px", borderRadius: 6, border: "none", cursor: "pointer",
                  fontSize: 11, fontWeight: 600, whiteSpace: "nowrap",
                  background: activeSection === s ? t.primary + "22" : "transparent",
                  color: activeSection === s ? t.primaryHover : t.textMuted,
                  transition: "all 0.15s",
                }}>
                  {s}
                </button>
              ))}
            </div>
            <div style={{ padding: "8px 20px" }}>
              {MOCK_TASKS.filter(t => t.section === activeSection).map(task => {
                const s = STATUS_STYLE[task.status];
                const agent = AGENTS[task.agent];
                return (
                  <div key={task.id} className="task-row" style={{
                    display: "flex", alignItems: "center", gap: 10,
                    padding: "6px 8px", borderRadius: 6, marginBottom: 2,
                    cursor: "pointer", transition: "background 0.1s",
                  }}>
                    <div style={{
                      width: 16, height: 16, borderRadius: 4,
                      background: task.status === "done" ? t.success : task.status === "active" ? t.warning : t.bgTertiary,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: 9, color: "#fff", flexShrink: 0,
                    }}>
                      {task.status === "done" ? "✓" : task.status === "active" ? "⟳" : ""}
                    </div>
                    <span style={{ fontSize: 12, color: task.status === "pending" ? t.textMuted : t.text, flex: 1 }}>
                      {task.task}
                    </span>
                    <AgentBadge agentKey={task.agent} />
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* RIGHT — Preview */}
        <div style={{
          width: 320, borderLeft: "1px solid #1e2533",
          display: "flex", flexDirection: "column", background: "#0d1017", flexShrink: 0,
        }}>
          <div style={{
            padding: "10px 16px", borderBottom: "1px solid #1e2533",
            fontSize: 11, fontWeight: 600, color: "#475569", letterSpacing: 1, textTransform: "uppercase",
            display: "flex", justifyContent: "space-between", alignItems: "center",
          }}>
            Preview
            <span style={{ fontSize: 10, color: "#334155", fontFamily: "monospace" }}>Last updated: 09:43</span>
          </div>

          <div style={{ padding: 12, flex: 1, overflow: "auto" }}>
            {/* Source */}
            <div style={{ marginBottom: 10 }}>
              <div style={{ fontSize: 10, color: "#f59e0b", fontWeight: 600, marginBottom: 6, display: "flex", alignItems: "center", gap: 5 }}>
                🔍 SOURCE
              </div>
              <div style={{
                height: 160, borderRadius: 8, overflow: "hidden",
                background: "#141822", border: "1px solid #1e2533",
                display: "flex", flexDirection: "column",
              }}>
                {/* Mock browser chrome */}
                <div style={{ background: "#1e2533", padding: "5px 8px", display: "flex", alignItems: "center", gap: 5 }}>
                  {["#f87171","#fbbf24","#4ade80"].map(c => (
                    <div key={c} style={{ width: 8, height: 8, borderRadius: "50%", background: c }} />
                  ))}
                  <div style={{ flex: 1, background: t.bgSecondary, borderRadius: 4, padding: "2px 8px", marginLeft: 4, fontSize: 9, color: t.textMuted, fontFamily: "monospace" }}>
                    example-agency.com
                  </div>
                </div>
                {/* Mock page */}
                <div style={{ flex: 1, padding: 8, display: "flex", flexDirection: "column", gap: 4 }}>
                  <div style={{ height: 40, background: "#1a1a2e", borderRadius: 4, display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <div style={{ width: 60, height: 8, background: "#e94560", borderRadius: 3 }} />
                  </div>
                  <div style={{ display: "flex", gap: 4, flex: 1 }}>
                    {[1,2,3].map(n => (
                      <div key={n} style={{ flex: 1, background: t.bgSecondary, borderRadius: 4 }} />
                    ))}
                  </div>
                  <div style={{ height: 20, background: "#1a1a2e", borderRadius: 4 }} />
                </div>
              </div>
            </div>

            {/* Built */}
            <div style={{ marginBottom: 10 }}>
              <div style={{ fontSize: 10, color: "#10b981", fontWeight: 600, marginBottom: 6, display: "flex", alignItems: "center", gap: 5 }}>
                🏗️ BUILD IN PROGRESS
              </div>
              <div style={{
                height: 160, borderRadius: 8, overflow: "hidden",
                background: t.bgTertiary, border: `1px solid ${t.success}55`,
                display: "flex", flexDirection: "column",
              }}>
                <div style={{ background: t.bgSecondary, padding: "5px 8px", display: "flex", alignItems: "center", gap: 5 }}>
                  {["#f87171","#fbbf24","#4ade80"].map(c => (
                    <div key={c} style={{ width: 8, height: 8, borderRadius: "50%", background: c }} />
                  ))}
                  <div style={{ flex: 1, background: t.bg, borderRadius: 4, padding: "2px 8px", marginLeft: 4, fontSize: 9, color: t.textMuted, fontFamily: "monospace" }}>
                    localhost:5500
                  </div>
                </div>
                <div style={{ flex: 1, padding: 8, display: "flex", flexDirection: "column", gap: 4, position: "relative" }}>
                  <div style={{ height: 40, background: "#1a1a2e", borderRadius: 4, display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <div style={{ width: 50, height: 8, background: "#4b4b6e", borderRadius: 3 }} />
                  </div>
                  <div style={{ display: "flex", gap: 4, flex: 1 }}>
                    {[1,2].map(n => (
                      <div key={n} style={{ flex: 1, background: t.bgSecondary, borderRadius: 4 }} />
                    ))}
                    <div style={{ flex: 1, background: "#1e233388", borderRadius: 4, border: "1px dashed #334155" }} />
                  </div>
                  {/* In-progress overlay */}
                  <div style={{
                    position: "absolute", bottom: 8, right: 8,
                    background: "#10b98122", border: "1px solid #10b98144",
                    borderRadius: 4, padding: "2px 6px", fontSize: 9, color: "#4ade80", fontFamily: "monospace",
                  }}>
                    building...
                  </div>
                </div>
              </div>
            </div>

            {/* Match score */}
            <div style={{
              background: t.bgTertiary, border: `1px solid ${t.border}`,
              borderRadius: 8, padding: 10,
            }}>
              <div style={{ fontSize: 10, color: t.textMuted, fontWeight: 600, marginBottom: 8, letterSpacing: 1, textTransform: "uppercase" }}>
                Match Score
              </div>
              {[
                { label: "Structure", score: 80, color: "#10b981" },
                { label: "Content",   score: 0,  color: "#6366f1" },
                { label: "Visuals",   score: 30, color: "#f59e0b" },
                { label: "Links",     score: 0,  color: "#ec4899" },
              ].map(({ label, score, color }) => (
                <div key={label} style={{ marginBottom: 6 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                    <span style={{ fontSize: 11, color: t.textSecondary }}>{label}</span>
                    <span style={{ fontSize: 11, fontFamily: "monospace", color: score > 50 ? color : t.textMuted }}>
                      {score > 0 ? `${score}%` : "—"}
                    </span>
                  </div>
                  <div style={{ height: 3, background: t.bgSecondary, borderRadius: 3 }}>
                    <div style={{
                      height: "100%", width: `${score}%`,
                      background: color, borderRadius: 3,
                      transition: "width 0.5s ease",
                    }} />
                  </div>
                </div>
              ))}
            </div>

            <button style={{
              width: "100%", marginTop: 10, padding: "8px 0",
              background: t.bgTertiary, color: t.textSecondary,
              border: `1px solid ${t.border}`, borderRadius: 8,
              fontSize: 12, cursor: "pointer", fontWeight: 500,
            }}>
              Open in Drupal ↗
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
