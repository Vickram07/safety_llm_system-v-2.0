import React, { useEffect, useState, useRef } from 'react';
import { Shield, Target, Zap, Clock, Cpu, Droplets, Flame, AlertOctagon, CheckCircle2, ChevronRight, ActivitySquare, ShieldCheck, Siren } from 'lucide-react';

const WEBSOCKET_URL = "ws://localhost:8000/ws";

const ZONES = {
  "Zone Alpha (Executive)": { x: 100, y: 50, w: 250, h: 200 },
  "Zone Beta (Engineering)": { x: 350, y: 50, w: 300, h: 200 },
  "Zone Gamma (Datacenter)": { x: 650, y: 50, w: 250, h: 200 },
  "Zone Delta (Operations)": { x: 900, y: 50, w: 300, h: 200 },
  "Zone Epsilon (Logistics)": { x: 1200, y: 50, w: 250, h: 200 },
  "West Corridor": { x: 100, y: 250, w: 550, h: 150 },
  "Central Hub": { x: 650, y: 250, w: 250, h: 150 },
  "East Corridor": { x: 900, y: 250, w: 550, h: 150 },
  "Zone Zeta (Lobby)": { x: 100, y: 400, w: 250, h: 200 },
  "Zone Eta (R&D)": { x: 350, y: 400, w: 300, h: 200 },
  "Zone Theta (Cafeteria)": { x: 650, y: 400, w: 250, h: 200 },
  "Zone Iota (Medical)": { x: 900, y: 400, w: 300, h: 200 },
  "Zone Kappa (Security)": { x: 1200, y: 400, w: 250, h: 200 }
};

const EXITS = {
  "Exit Alpha North": { x: 200, y: 0, w: 50, h: 50 },
  "Exit Beta North": { x: 475, y: 0, w: 50, h: 50 },
  "Exit Delta North": { x: 1025, y: 0, w: 50, h: 50 },
  "Exit Epsilon North": { x: 1300, y: 0, w: 50, h: 50 },
  "Exit Zeta South": { x: 200, y: 600, w: 50, h: 50 },
  "Exit Eta South": { x: 475, y: 600, w: 50, h: 50 },
  "Exit Iota South": { x: 1025, y: 600, w: 50, h: 50 },
  "Exit Kappa South": { x: 1300, y: 600, w: 50, h: 50 },
  "Exit West Hub": { x: 50, y: 300, w: 50, h: 50 },
  "Exit East Hub": { x: 1450, y: 300, w: 50, h: 50 }
};

export default function App() {
  const [state, setState] = useState(null);
  const [hoveredPerson, setHoveredPerson] = useState(null);
  const [latency, setLatency] = useState(0);

  // Chat State
  const [chatHistory, setChatHistory] = useState([
    { role: 'system', content: 'Connection Established. InfernalX Online and monitoring facility wide thermal integrity. How can I assist you?' }
  ]);
  const [isChatting, setIsChatting] = useState(false);

  // Camera Pan & Zoom state
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [scale, setScale] = useState(1);
  const isDragging = useRef(false);
  const hasDragged = useRef(false);
  const lastMousePos = useRef({ x: 0, y: 0 });

  const canvasRef = useRef(null);
  const lastUpdate = useRef(Date.now());
  const socketRef = useRef(null);

  useEffect(() => {
    socketRef.current = new WebSocket(WEBSOCKET_URL);
    socketRef.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data && data.people) {
        setState(data);
        const now = Date.now();
        setLatency(now - lastUpdate.current);
        lastUpdate.current = now;
      }
    };
    return () => socketRef.current?.close();
  }, []);

  const handleTriggerFire = () => {
    fetch('http://localhost:8000/api/command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'spawn_fire', target: 'West Corridor' })
    });
  };
  
  const handleReset = () => {
    fetch('http://localhost:8000/api/command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'set_scenario', target: 'DEFAULT' })
    });
  };

  const handleWheel = (e) => {
    e.preventDefault();
    const zoomFactor = -e.deltaY * 0.001;
    let newScale = scale * (1 + zoomFactor);
    newScale = Math.max(0.5, Math.min(newScale, 3));
    setScale(newScale);
  };

  const handleMouseDown = (e) => {
    isDragging.current = true;
    hasDragged.current = false;
    lastMousePos.current = { x: e.clientX, y: e.clientY };
  };

  const handleCanvasClick = (e) => {
    if (hasDragged.current) return;
    if (!state || !canvasRef.current) return;

    const rect = canvasRef.current.getBoundingClientRect();
    const scaleX = canvasRef.current.width / rect.width;
    const scaleY = canvasRef.current.height / rect.height;

    const canvasX = (e.clientX - rect.left) * scaleX;
    const canvasY = (e.clientY - rect.top) * scaleY;

    const worldX = (canvasX - pan.x) / scale;
    const worldY = (canvasY - pan.y) / scale;

    fetch('http://localhost:8000/api/command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'manual_fire', x: worldX, y: worldY })
    });
  };

  const handleChatSend = (msg) => {
    if (!msg.trim() || isChatting) return;

    const newHistory = [...chatHistory, { role: 'user', content: msg }];
    setChatHistory(newHistory);
    setIsChatting(true);

    fetch('http://localhost:8000/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: msg })
    })
      .then(res => res.json())
      .then(data => {
        setChatHistory([...newHistory, { role: 'system', content: data.response }]);
        setIsChatting(false);
      })
      .catch(() => {
        setChatHistory([...newHistory, { role: 'system', content: 'Connection to InfernalX framework failed. Ensure server.py is running.' }]);
        setIsChatting(false);
      });
  };

  const handleMouseUpOrLeave = () => {
    isDragging.current = false;
  };

  const handleMouseMove = (e) => {
    if (isDragging.current) {
      hasDragged.current = true;
      const dx = e.clientX - lastMousePos.current.x;
      const dy = e.clientY - lastMousePos.current.y;
      setPan((prev) => ({ x: prev.x + dx, y: prev.y + dy }));
      lastMousePos.current = { x: e.clientX, y: e.clientY };
      return;
    }

    if (!state || !canvasRef.current) return;

    const rect = canvasRef.current.getBoundingClientRect();
    const scaleX = canvasRef.current.width / rect.width;
    const scaleY = canvasRef.current.height / rect.height;

    const canvasX = (e.clientX - rect.left) * scaleX;
    const canvasY = (e.clientY - rect.top) * scaleY;

    const worldX = (canvasX - pan.x) / scale;
    const worldY = (canvasY - pan.y) / scale;

    let found = null;
    for (const p of state.people) {
      // Don't interact with escaped people (even though backend filters them now, it's good safety)
      if (p.status === 'ESCAPED') continue;
      
      if (Math.hypot(p.x - worldX, p.y - worldY) < (20 / scale)) {
        found = p;
        break;
      }
    }
    setHoveredPerson(found);
  };

  useEffect(() => {
    if (!state || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');

    // Clean, modern dark mode background 
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    // Draw base aesthetic layout
    const gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
    gradient.addColorStop(0, '#09090b'); // zinc-950
    gradient.addColorStop(1, '#18181b'); // zinc-900
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    // Draw subtle dot grid for modern tech feel
    ctx.fillStyle = 'rgba(255, 255, 255, 0.02)';
    for(let x = 0; x < canvas.width; x += 30) {
      for(let y = 0; y < canvas.height; y += 30) {
        ctx.beginPath();
        ctx.arc(x, y, 1, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    ctx.restore();

    ctx.save();
    ctx.translate(pan.x, pan.y);
    ctx.scale(scale, scale);

    // Draw Zones - sleek minimal borders with soft glow
    Object.entries(ZONES).forEach(([name, z]) => {
      const isFire = state.active_fire_zones.includes(name);
      ctx.strokeStyle = isFire ? 'rgba(239, 68, 68, 0.4)' : 'rgba(148, 163, 184, 0.15)'; // slate-400
      ctx.lineWidth = 1;
      ctx.fillStyle = isFire ? 'rgba(239, 68, 68, 0.03)' : 'rgba(148, 163, 184, 0.02)';
      
      ctx.beginPath();
      ctx.roundRect(z.x, z.y, z.w, z.h, 12);
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = isFire ? 'rgba(239, 68, 68, 0.8)' : 'rgba(148, 163, 184, 0.6)';
      ctx.font = '500 12px "Inter", sans-serif';
      ctx.fillText(name, z.x + 12, z.y + 24);
    });

    // Draw Exits
    Object.entries(EXITS).forEach(([name, z]) => {
      ctx.strokeStyle = 'rgba(34, 197, 94, 0.3)';
      ctx.fillStyle = 'rgba(34, 197, 94, 0.05)';
      ctx.beginPath();
      ctx.roundRect(z.x, z.y, z.w, z.h, 8);
      ctx.fill();
      ctx.stroke();
      
      ctx.fillStyle = 'rgba(34, 197, 94, 0.8)';
      ctx.font = '600 10px "Inter", sans-serif';
      ctx.fillText("EXIT", z.x + 12, z.y + 28);
    });

    // Draw Fire with glowing effect
    ctx.save();
    ctx.shadowBlur = 15;
    ctx.shadowColor = 'rgba(239, 68, 68, 0.6)';
    ctx.fillStyle = 'rgba(239, 68, 68, 0.85)';
    state.fire_cells.forEach(([gx, gy]) => {
      ctx.beginPath();
      ctx.roundRect(gx * 10, gy * 10, 10, 10, 3);
      ctx.fill();
    });
    ctx.restore();

    // Draw Water/Suppression
    ctx.fillStyle = 'rgba(14, 165, 233, 0.6)'; // sky-500
    state.water_cells.forEach(([gx, gy]) => {
      ctx.beginPath();
      ctx.roundRect(gx * 10, gy * 10, 10, 10, 3);
      ctx.fill();
    });

    // Draw People - cleaner dots
    state.people.forEach(p => {
      // Skip escaped people from drawing logic entirely
      if (p.status === 'ESCAPED') return;

      ctx.beginPath();
      ctx.arc(p.x, p.y, 4, 0, Math.PI * 2);
      ctx.fillStyle = p.status === 'PANIC' ? '#ef4444' : p.status === 'TRAPPED' ? '#f59e0b' : '#10b981'; // red, amber, emerald
      ctx.fill();

      // Soft glow for people
      ctx.shadowBlur = p.status === 'PANIC' ? 8 : 4;
      ctx.shadowColor = ctx.fillStyle;
      ctx.fill();
      ctx.shadowBlur = 0;

      if (hoveredPerson?.id === p.id && p.path && p.path.length > 0) {
        ctx.beginPath();
        ctx.moveTo(p.x, p.y);
        p.path.forEach(nodeName => {
          let r = ZONES[nodeName] || EXITS[nodeName];
          if (r) ctx.lineTo(r.x + r.w / 2, r.y + r.h / 2);
        });
        ctx.strokeStyle = 'rgba(14, 165, 233, 0.8)'; // sky-500
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 4]);
        ctx.stroke();
        ctx.setLineDash([]);
      }
    });

    // Draw Highlight ring for selection
    if (hoveredPerson) {
      ctx.beginPath();
      ctx.arc(hoveredPerson.x, hoveredPerson.y, 14, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(14, 165, 233, 1)'; // sky-500
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    ctx.restore();

  }, [state, hoveredPerson, pan, scale]);

  return (
    <div className="flex flex-col h-screen bg-[#050508] text-slate-200 font-sans selection:bg-indigo-500/30 overflow-hidden relative">
      <div className="absolute inset-0 flex justify-center z-0 pointer-events-none">
         <div className="w-[1000px] h-[500px] bg-indigo-500/20 blur-[150px] rounded-full opacity-30 -translate-y-1/2"></div>
      </div>
      
      {/* HEADER / TOP NAVBAR */}
      <header className="flex justify-between items-center px-8 py-5 bg-[#050508]/60 backdrop-blur-2xl border-b border-indigo-500/10 z-20 shadow-[0_8px_30px_rgb(0,0,0,0.5)] relative">
        <div className="flex items-center gap-5">
          <div className="relative">
             <div className="absolute inset-0 bg-indigo-500 blur-lg opacity-40 mix-blend-screen"></div>
             <div className="relative p-3 bg-gradient-to-b from-indigo-500 to-indigo-700 rounded-xl shadow-xl shadow-indigo-500/30 border border-white/20 ring-1 ring-indigo-400/50">
               <Shield className="text-white w-6 h-6" />
             </div>
          </div>
          <div>
            <h1 className="text-2xl font-black text-white tracking-tighter bg-clip-text text-transparent bg-gradient-to-b from-white via-indigo-50 to-slate-400 drop-shadow-sm">AEGIS <span className="font-light text-indigo-400">COMMAND</span> V5</h1>
            <p className="text-[10px] text-indigo-300 font-bold tracking-[0.25em] uppercase mt-0.5 opacity-80">Enterprise Safety Intelligence</p>
          </div>
        </div>
        
        <div className="flex items-center gap-6">
          <div className="flex flex-col text-right mr-4">
            <span className="text-[9px] text-slate-500 font-bold tracking-widest uppercase mb-1.5 align-middle">Live Status Overview</span>
            {state?.active_fire_zones?.length > 0 ? (
              <span className="text-red-400 text-xs font-bold uppercase tracking-wider animate-pulse flex items-center gap-2 bg-red-500/10 px-4 py-1.5 rounded-full border border-red-500/20 shadow-[0_0_15px_rgba(239,68,68,0.2)]">
                <Siren className="w-4 h-4" /> Thermal Breach active
              </span>
            ) : (
              <span className="text-emerald-400 text-xs font-bold uppercase tracking-wider flex items-center gap-2 bg-emerald-500/10 px-4 py-1.5 rounded-full border border-emerald-500/20 shadow-[0_0_15px_rgba(16,185,129,0.1)]">
                <ShieldCheck className="w-4 h-4" /> Systems Nominal
              </span>
            )}
          </div>
          <button 
            onClick={handleTriggerFire} 
            className="px-6 py-2.5 bg-gradient-to-b from-red-500 to-red-600 hover:from-red-400 hover:to-red-500 text-white rounded-xl text-xs font-bold uppercase tracking-wider transition-all duration-300 shadow-lg shadow-red-500/20 flex items-center gap-2 ring-1 ring-red-400/50 hover:shadow-red-500/40 hover:-translate-y-0.5"
          >
            <AlertOctagon className="w-4 h-4" /> Inject Event
          </button>
          <button 
            onClick={handleReset} 
            className="px-6 py-2.5 bg-black/40 hover:bg-black/60 text-slate-300 border border-white/10 rounded-xl text-xs font-bold uppercase tracking-wider transition-all duration-300 backdrop-blur-xl hover:border-white/20 hover:text-white"
          >
            Reset Matrix
          </button>
        </div>
      </header>

      {/* MAIN BODY */}
      <div className="flex flex-1 overflow-hidden relative">
        
        {/* LEFT PANEL: VITALS & LOGS */}
        <div className="w-[360px] shrink-0 bg-[#050508]/80 backdrop-blur-2xl border-r border-indigo-500/10 flex flex-col z-10 shadow-[20px_0_40px_rgba(0,0,0,0.5)] relative">
          
          <div className="p-7">
            <h2 className="text-[10px] font-black text-indigo-400/80 uppercase tracking-[0.2em] mb-5 flex items-center gap-2">
               <ActivitySquare className="w-4 h-4 text-indigo-400" /> Executive Dashboard
            </h2>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-[#0f111a]/60 backdrop-blur-xl border border-white/5 p-5 rounded-2xl flex flex-col hover:bg-[#151824] transition-all duration-300 relative overflow-hidden group shadow-lg hover:shadow-indigo-500/5 hover:-translate-y-0.5">
                <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
                <div className="absolute top-0 right-0 w-24 h-24 bg-emerald-500/10 blur-2xl rounded-full translate-x-8 -translate-y-8 group-hover:bg-emerald-500/20 transition-colors duration-500"></div>
                <span className="text-[9px] text-slate-400 font-bold mb-1 uppercase tracking-[0.15em] z-10 flex items-center gap-1.5">Alive</span>
                <span className="text-4xl font-black text-transparent bg-clip-text bg-gradient-to-b from-white to-slate-400 z-10 tracking-tight">{state ? state.people.filter(p => p.hp > 0 && p.status !== 'ESCAPED').length : 0}</span>
                <span className="text-[9px] text-emerald-400 mt-3 font-bold z-10 border border-emerald-500/20 bg-emerald-500/10 w-max px-2.5 py-1 rounded shadow-inner flex items-center gap-1.5 uppercase tracking-widest"><CheckCircle2 className="w-3 h-3"/> Active</span>
              </div>
              
              <div className="bg-[#0f111a]/60 backdrop-blur-xl border border-white/5 p-5 rounded-2xl flex flex-col hover:bg-[#151824] transition-all duration-300 relative overflow-hidden group shadow-lg hover:shadow-indigo-500/5 hover:-translate-y-0.5">
                 <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
                 <div className="absolute top-0 right-0 w-24 h-24 bg-indigo-500/10 blur-2xl rounded-full translate-x-8 -translate-y-8 group-hover:bg-indigo-500/20 transition-colors duration-500"></div>
                <span className="text-[9px] text-slate-400 font-bold mb-1 uppercase tracking-[0.15em] z-10 flex items-center gap-1.5">Evacuated</span>
                <span className="text-4xl font-black text-transparent bg-clip-text bg-gradient-to-b from-white to-slate-400 z-10 tracking-tight">{state ? state.people.filter(p => p.status === 'ESCAPED').length : 0}</span>
                <span className="text-[9px] text-indigo-400 mt-3 font-bold z-10 border border-indigo-500/20 bg-indigo-500/10 w-max px-2.5 py-1 rounded shadow-inner flex items-center gap-1.5 uppercase tracking-widest">Safe Zone</span>
              </div>
              
              <div className="bg-[#0f111a]/60 backdrop-blur-xl border border-white/5 p-5 rounded-2xl flex flex-col hover:bg-[#151824] transition-all duration-300 relative overflow-hidden group shadow-lg hover:shadow-indigo-500/5 hover:-translate-y-0.5">
                 <div className="absolute inset-0 bg-gradient-to-br from-amber-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
                 <div className="absolute top-0 right-0 w-24 h-24 bg-amber-500/10 blur-2xl rounded-full translate-x-8 -translate-y-8 group-hover:bg-amber-500/20 transition-colors duration-500"></div>
                <span className="text-[9px] text-slate-400 font-bold mb-1 uppercase tracking-[0.15em] z-10 flex items-center gap-1.5">Trapped</span>
                <span className="text-4xl font-black text-transparent bg-clip-text bg-gradient-to-b from-white to-slate-400 z-10 tracking-tight">{state ? state.people.filter(p => p.status === 'TRAPPED').length : 0}</span>
                <span className="text-[9px] text-amber-500 mt-3 font-bold z-10 border border-amber-500/20 bg-amber-500/10 w-max px-2.5 py-1 rounded shadow-inner flex items-center gap-1.5 uppercase tracking-widest">Needs Assist</span>
              </div>

              <div className="bg-[#0f111a]/60 backdrop-blur-xl border border-white/5 p-5 rounded-2xl flex flex-col hover:bg-[#151824] transition-all duration-300 relative overflow-hidden group shadow-lg hover:shadow-indigo-500/5 hover:-translate-y-0.5">
                 <div className="absolute inset-0 bg-gradient-to-br from-red-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
                 <div className="absolute top-0 right-0 w-24 h-24 bg-red-500/10 blur-2xl rounded-full translate-x-8 -translate-y-8 group-hover:bg-red-500/20 transition-colors duration-500"></div>
                <span className="text-[9px] text-slate-400 font-bold mb-1 uppercase tracking-[0.15em] z-10 flex items-center gap-1.5">Casualties</span>
                <span className="text-4xl font-black text-transparent bg-clip-text bg-gradient-to-b from-white to-slate-400 z-10 tracking-tight">{state ? state.people.filter(p => p.hp <= 0).length : 0}</span>
                <span className="text-[9px] text-red-500 mt-3 font-bold z-10 border border-red-500/20 bg-red-500/10 w-max px-2.5 py-1 rounded shadow-inner flex items-center gap-1.5 uppercase tracking-widest">Critical</span>
              </div>
            </div>
          </div>

          <div className="flex-1 flex flex-col min-h-0 relative">
            <div className="px-7 py-4 border-t border-b border-indigo-500/10 flex items-center justify-between bg-black/40 backdrop-blur-xl shadow-inner">
              <h2 className="text-[10px] font-black text-indigo-400/80 uppercase tracking-[0.2em] flex items-center gap-2">
                <Clock className="w-4 h-4 text-indigo-400" /> Operational Log
              </h2>
              <span className="text-[9px] font-bold tracking-widest bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 px-2 py-0.5 rounded shadow shadow-indigo-500/20">SYNCED</span>
            </div>
            
            <div className="flex-1 overflow-y-auto p-6 flex flex-col-reverse gap-4 bg-black/20">
              {[...(state?.global_events || [])].reverse().map((log, i) => {
                const parts = log.split("] ");
                const time = parts[0] ? parts[0].replace('[', '') : "";
                const content = parts.slice(1).join("] ") || log;
                
                // Regex checks for color coding
                const isCritical = log.includes("CRITICAL") || log.includes("EMERGENCY") || log.includes("BREACH");
                const isSystem = log.includes("UPDATE") || log.includes("COMMAND RECEIVED") || log.includes("ONLINE");
                
                return (
                  <div key={i} className="flex gap-4 group">
                    <div className="flex flex-col items-center">
                      <div className={`w-2.5 h-2.5 rounded-full mt-1 shrink-0 ${isCritical ? 'bg-red-500 shadow-[0_0_12px_rgba(239,68,68,0.9)] border border-red-300' : isSystem ? 'bg-indigo-500 shadow-[0_0_12px_rgba(99,102,241,0.9)] border border-indigo-300' : 'bg-slate-600 border border-slate-400'}`}></div>
                      <div className="w-[1px] h-full bg-gradient-to-b from-indigo-500/30 to-transparent mt-2 group-last:hidden"></div>
                    </div>
                    <div className="pb-5">
                      <span className="text-[10px] text-slate-500 font-mono font-bold tracking-widest">{time}</span>
                      <p className={`text-[13px] leading-relaxed mt-1 font-medium ${isCritical ? 'text-red-300' : isSystem ? 'text-indigo-200' : 'text-slate-400'}`}>
                        {content}
                      </p>
                    </div>
                  </div>
                );
              })}
              
              {(!state?.global_events || state.global_events.length === 0) && (
                <div className="h-full flex flex-col items-center justify-center text-slate-600">
                  <ActivitySquare className="w-8 h-8 opacity-20 mb-3" />
                  <span className="text-[11px] font-bold tracking-widest uppercase">Awaiting Matrix Events...</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* CENTER CANVASES */}
        <div className="flex-1 relative bg-[#09090b] flex items-center justify-center overflow-hidden h-full z-0 p-8">
          
          <canvas
            ref={canvasRef}
            width={1400}
            height={600}
            onWheel={handleWheel}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUpOrLeave}
            onMouseLeave={handleMouseUpOrLeave}
            onClick={handleCanvasClick}
            className={`border border-white/10 rounded-[2rem] shadow-2xl overflow-hidden backdrop-blur-md max-w-full h-auto transform-gpu ${hoveredPerson ? 'cursor-crosshair' : 'cursor-grab active:cursor-grabbing'}`}
            style={{ boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(255,255,255,0.05)' }}
          />

          {/* Floating PA Annoucements */}
          <div className="absolute top-12 left-1/2 transform -translate-x-1/2 flex flex-col items-center gap-3 z-50 pointer-events-none">
             {state?.pa_announcements?.map(pa => (
                <div key={pa.id} style={{animation: 'slideDown 0.3s ease-out forwards'}} className="flex items-center gap-3 bg-gradient-to-r from-sky-900/90 to-indigo-900/90 border border-sky-400/30 px-6 py-3.5 rounded-2xl shadow-2xl backdrop-blur-xl">
                  <div className="w-8 h-8 rounded-full bg-sky-500/20 flex items-center justify-center shrink-0">
                    <Zap className="w-4 h-4 text-sky-400" />
                  </div>
                  <div>
                    <span className="text-[10px] font-bold text-sky-400 uppercase tracking-widest block mb-0.5">PA Announcement Active</span>
                    <span className="text-sm font-medium text-white">{pa.text}</span>
                  </div>
                </div>
              ))}
          </div>

        </div>

        {/* RIGHT PANEL: INTEL & CHAT */}
        <div className="w-[400px] shrink-0 bg-[#050508]/80 backdrop-blur-2xl border-l border-indigo-500/10 flex flex-col z-10 shadow-[-20px_0_40px_rgba(0,0,0,0.5)] relative">
          
          {/* INTEL PANEL */}
          <div className="shrink-0 min-h-[160px] border-b border-indigo-500/10 flex flex-col bg-black/40 pb-6 relative overflow-hidden">
             
             <div className="px-7 py-4 flex items-center justify-between border-b border-indigo-500/10 bg-indigo-500/5">
              <h2 className="text-[10px] font-black text-indigo-400/80 uppercase tracking-[0.2em] flex items-center gap-2">
                <Target className="w-4 h-4 text-emerald-400" /> Telemetry Focus
              </h2>
              {hoveredPerson && <span className="text-[9px] bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-2 py-0.5 rounded uppercase font-bold tracking-[0.2em] shadow-[0_0_10px_rgba(16,185,129,0.2)]">Target Acquired</span>}
            </div>
            
            <div className="flex-1 p-7 flex flex-col justify-center relative z-10">
              {hoveredPerson ? (
                <div className="flex flex-col gap-6 animate-in fade-in duration-300">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="text-[9px] font-black text-slate-500 tracking-[0.2em] uppercase mb-1.5">Selected Asset</div>
                      <div className="text-2xl font-black text-white tracking-tighter shadow-black/50 drop-shadow-md">{hoveredPerson.name}</div>
                      <div className="text-[11px] font-bold text-indigo-300/80 mt-1.5 flex items-center gap-2 tracking-wide uppercase">
                        {hoveredPerson.role} <span className="w-1.5 h-1.5 rounded-full bg-indigo-500"></span> UID: {hoveredPerson.id.substr(0,6)}
                      </div>
                    </div>
                    {hoveredPerson.status === 'PANIC' && <div className="p-3 bg-gradient-to-br from-red-500/20 to-red-600/10 rounded-2xl border border-red-500/30 shadow-[0_0_15px_rgba(239,68,68,0.2)]"><Siren className="w-5 h-5 text-red-500 animate-pulse"/></div>}
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-[#0f111a]/80 backdrop-blur-md p-4 rounded-2xl border border-white/5 shadow-inner relative overflow-hidden">
                      <div className={`absolute top-0 right-0 w-12 h-12 blur-xl rounded-full translate-x-4 -translate-y-4 ${hoveredPerson.status === 'PANIC' ? 'bg-red-500/20' : hoveredPerson.status === 'TRAPPED' ? 'bg-amber-500/20' : 'bg-emerald-500/20'}`}></div>
                      <div className="text-[9px] text-slate-500 mb-1.5 font-bold tracking-[0.2em] uppercase">Status</div>
                      <div className={`text-sm font-black tracking-wider uppercase ${hoveredPerson.status === 'PANIC' ? 'text-red-400 drop-shadow-[0_0_8px_rgba(239,68,68,0.5)]' : hoveredPerson.status === 'TRAPPED' ? 'text-amber-400 drop-shadow-[0_0_8px_rgba(245,158,11,0.5)]' : 'text-emerald-400 drop-shadow-[0_0_8px_rgba(16,185,129,0.5)]'}`}>
                        {hoveredPerson.status}
                      </div>
                    </div>
                    <div className="bg-[#0f111a]/80 backdrop-blur-md p-4 rounded-2xl border border-white/5 shadow-inner relative overflow-hidden">
                       <div className="absolute top-0 right-0 w-12 h-12 blur-xl rounded-full translate-x-4 -translate-y-4 bg-indigo-500/20"></div>
                      <div className="text-[9px] text-slate-500 mb-1.5 font-bold tracking-[0.2em] uppercase">Vitals</div>
                      <div className="text-sm font-black text-white flex items-center justify-between tracking-wider">
                        {hoveredPerson.hp.toFixed(0)}%
                        <div className="w-14 h-2 bg-black/60 rounded-full overflow-hidden border border-white/5 shadow-inner">
                           <div className="h-full bg-gradient-to-r from-emerald-600 to-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.5)]" style={{width: `${hoveredPerson.hp}%`}}></div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center text-indigo-500/30">
                   <Target className="w-12 h-12 mb-4 stroke-1" />
                   <p className="text-[10px] font-bold tracking-[0.15em] uppercase text-center max-w-[200px] leading-relaxed">Engage telemetry lock by selecting an asset on the matrix.</p>
                </div>
              )}
            </div>
          </div>

          {/* AI ASSISTANT PANEL */}
          <div className="flex-1 flex flex-col min-h-0 relative bg-black/40">
            <div className="px-7 py-5 border-b border-indigo-500/10 flex flex-col gap-2 bg-indigo-500/5 shadow-inner">
              <div className="flex items-center justify-between">
                 <h2 className="text-[10px] font-black text-indigo-400/80 tracking-[0.2em] uppercase flex items-center gap-2">
                   <Cpu className="w-4 h-4 text-indigo-400" /> Overseer Core
                 </h2>
                 <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-[9px] font-bold uppercase tracking-[0.2em] shadow-sm ${isChatting ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30' : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 shadow-[0_0_10px_rgba(16,185,129,0.1)]'}`}>
                   <div className={`w-1.5 h-1.5 rounded-full ${isChatting ? 'bg-indigo-300 animate-pulse blur-[1px]' : 'bg-emerald-400 shadow-[0_0_5px_#34d399]'}`}></div>
                   {isChatting ? 'PROCESSING' : 'LINK ESTABLISHED'}
                 </div>
              </div>
              <p className="text-[10px] text-slate-500 leading-relaxed mt-1 font-medium tracking-wide">Natural language deployment active. Awaiting override vectors.</p>
            </div>
            
            <div className="flex-1 p-7 overflow-y-auto flex flex-col gap-6 text-sm scrolling-chat custom-scrollbar bg-black/20">
              {chatHistory.map((msg, idx) => (
                <div key={idx} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                  {msg.role === 'system' && <span className="text-[9px] text-indigo-400 mb-2 font-black ml-1 uppercase tracking-[0.2em]">InfernalX</span>}
                  <div className={`shadow-lg px-5 py-4 max-w-[90%] text-[13px] leading-relaxed relative border font-medium tracking-wide ${msg.role === 'user' ? 'bg-gradient-to-br from-indigo-600 to-indigo-700 border-indigo-500 shadow-indigo-500/20 text-white rounded-2xl rounded-tr-sm' : 'bg-gradient-to-br from-[#12141c] to-[#0f111a] border-white/5 shadow-black/50 text-indigo-100 rounded-2xl rounded-tl-sm'}`}>
                    {msg.content}
                  </div>
                </div>
              ))}
              
              {isChatting && (
                <div className="flex flex-col items-start">
                   <span className="text-[9px] text-indigo-400 mb-2 font-black ml-1 uppercase tracking-[0.2em]">InfernalX</span>
                   <div className="bg-gradient-to-br from-[#12141c] to-[#0f111a] border border-white/5 shadow-black/50 text-slate-400 rounded-2xl rounded-tl-sm px-6 py-5">
                     <div className="flex gap-2 items-center">
                       <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce shadow-[0_0_8px_#6366f1]"></span>
                       <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce shadow-[0_0_8px_#6366f1]" style={{ animationDelay: '0.15s' }}></span>
                       <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce shadow-[0_0_8px_#6366f1]" style={{ animationDelay: '0.3s' }}></span>
                     </div>
                   </div>
                </div>
              )}
            </div>
            
            <div className="p-6 bg-black/40 border-t border-indigo-500/10 backdrop-blur-3xl relative">
              <div className="absolute inset-0 bg-gradient-to-t from-indigo-500/5 to-transparent pointer-events-none"></div>
              <div className="relative group shadow-2xl">
                <input
                  type="text"
                  className="w-full bg-[#0a0b10]/80 border border-white/10 rounded-xl pl-5 pr-14 py-4 text-[13px] text-white placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 transition-all font-medium tracking-wide shadow-inner backdrop-blur-xl"
                  placeholder="Initiate terminal sequence..."
                  onKeyDown={e => {
                    if (e.key === 'Enter' && e.target.value) {
                      handleChatSend(e.target.value);
                      e.target.value = '';
                    }
                  }}
                  disabled={isChatting}
                />
                <button className="absolute right-2.5 top-1/2 -translate-y-1/2 p-2.5 bg-indigo-500 text-white hover:bg-indigo-400 rounded-lg transition-all shadow-[0_0_15px_rgba(99,102,241,0.4)] disabled:opacity-50"
                  onClick={(e) => {
                    const input = e.currentTarget.previousElementSibling;
                    if (input.value) {
                      handleChatSend(input.value);
                      input.value = '';
                    }
                  }}
                >
                  <ChevronRight className="w-4 h-4 stroke-[3]" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes slideDown {
          0% { transform: translateY(-20px); opacity: 0; }
          100% { transform: translateY(0); opacity: 1; }
        }
        .custom-scrollbar::-webkit-scrollbar {
          width: 6px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background-color: rgba(255, 255, 255, 0.1);
          border-radius: 10px;
        }
      `}} />
    </div>
  );
}
