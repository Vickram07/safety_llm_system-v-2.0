import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Bot,
  Cpu,
  Flame,
  LayoutTemplate,
  MapPinned,
  RefreshCcw,
  ScanSearch,
  Send,
  Shield,
  ShieldCheck,
  Siren,
  Sparkles,
  Upload,
  Users,
  Waves,
  X,
} from "lucide-react";
import "./App.css";

const getApiBase = () => {
  if (typeof window === "undefined") {
    return "";
  }
  return window.location.origin;
};

const getSocketUrl = () => {
  if (typeof window === "undefined") {
    return "ws://localhost:8000/ws";
  }
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${window.location.host}/ws`;
};

const API_BASE = getApiBase();
const SOCKET_URL = getSocketUrl();

const quickPromptCategories = {
  STATUS: [
    "Status report",
    "Which zone is most critical?",
    "How many occupants are trapped?",
  ],
  CONTROL: [
    "Should I deploy suppression now?",
    "Turn off the fire fast with low water",
  ],
  DIAGNOSTIC: [
    "Show evacuation paths",
    "Analyze exit blockages",
    "Recommend resource allocation",
  ],
};

const EMPTY_ARRAY = [];
const EMPTY_OBJECT = {};

const layoutTemplates = {
  compact_hub: {
    name: "Compact Hub",
    population: 48,
    notes: "Reference-style compact office grid.",
    zones: {
      "North Operations": { x: 120, y: 90, w: 330, h: 180 },
      "Command Center": { x: 490, y: 90, w: 250, h: 180 },
      "Research Bay": { x: 780, y: 90, w: 310, h: 180 },
      "Central Corridor": { x: 120, y: 300, w: 970, h: 110 },
      "South Logistics": { x: 120, y: 450, w: 300, h: 170 },
      "Medical Room": { x: 450, y: 450, w: 260, h: 170 },
      "Briefing Hall": { x: 740, y: 450, w: 350, h: 170 },
    },
    exits: {
      "Exit North": { x: 545, y: 30, w: 70, h: 45 },
      "Exit West": { x: 50, y: 332, w: 50, h: 50 },
      "Exit East": { x: 1110, y: 332, w: 50, h: 50 },
      "Exit South": { x: 545, y: 650, w: 70, h: 45 },
    },
  },
  split_wings: {
    name: "Split Wings",
    population: 72,
    notes: "Dual-wing response layout.",
    zones: {
      "Alpha Wing": { x: 80, y: 100, w: 280, h: 240 },
      "Beta Wing": { x: 420, y: 100, w: 280, h: 240 },
      "Control Spine": { x: 760, y: 100, w: 190, h: 430 },
      "Gamma Wing": { x: 1010, y: 100, w: 280, h: 240 },
      "Delta Wing": { x: 80, y: 390, w: 620, h: 160 },
      "Support Bay": { x: 1010, y: 390, w: 280, h: 160 },
    },
    exits: {
      "Exit A": { x: 170, y: 40, w: 60, h: 45 },
      "Exit B": { x: 540, y: 40, w: 60, h: 45 },
      "Exit C": { x: 1110, y: 40, w: 60, h: 45 },
      "Exit D": { x: 1110, y: 580, w: 60, h: 45 },
    },
  },
};

const fileToBase64 = (file) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || "");
      resolve(result.includes(",") ? result.split(",")[1] : result);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });

const formatStatusTone = (status) => {
  if (status === "PANIC") return "#ff8a66";
  if (status === "TRAPPED") return "#ffd166";
  if (status === "EVACUATING") return "#8fd3ff";
  return "#63e6be";
};

export default function App() {
  const [state, setState] = useState(null);
  const [latency, setLatency] = useState(0);
  const [selectedPersonId, setSelectedPersonId] = useState(null);
  const [hoveredPersonId, setHoveredPersonId] = useState(null);
  const [hoveredScreenPoint, setHoveredScreenPoint] = useState(null);
  const [chatInput, setChatInput] = useState("");
  const [charCount, setCharCount] = useState(0);
  const [isChatting, setIsChatting] = useState(false);
  const [chatHistory, setChatHistory] = useState([
    {
      role: "system",
      content:
        "InfernalX online. I can summarize the active fire state, recommend suppression, and help normalize a new facility design.",
    },
  ]);
  const [designText, setDesignText] = useState("");
  const [layoutJson, setLayoutJson] = useState("");
  const [uploadingLayout, setUploadingLayout] = useState(false);
  const [layoutFeedback, setLayoutFeedback] = useState("");
  const [selectedTemplate, setSelectedTemplate] = useState("compact_hub");
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [scale, setScale] = useState(1);
  const [showAdvancedTools, setShowAdvancedTools] = useState(false);
  const [autonomousMode, setAutonomousMode] = useState(false);

  const canvasRef = useRef(null);
  const socketRef = useRef(null);
  const dragStateRef = useRef({ dragging: false, moved: false, x: 0, y: 0 });
  const lastMessageAtRef = useRef(Date.now());
  const lastUiStateCommitAtRef = useRef(0);
  const latestSocketPayloadRef = useRef(null);
  const queuedSocketTimerRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const lastAutoFitRevisionRef = useRef(null);

  const people = state?.people ?? EMPTY_ARRAY;
  const hoveredPerson = people.find((person) => person.id === hoveredPersonId) || null;
  const selectedPerson =
    people.find((person) => person.id === selectedPersonId) ||
    null;
  const zones = state?.zones ?? EMPTY_OBJECT;
  const exits = state?.exits ?? EMPTY_OBJECT;
  const sensorZones = state?.sensor_pipeline?.zones ?? EMPTY_OBJECT;
  const sensorSummary = state?.sensor_pipeline?.summary ?? EMPTY_OBJECT;
  const blockedExits = state?.blocked_exits ?? EMPTY_ARRAY;

  // Sync autonomous mode state from server
  useEffect(() => {
    if (state?.autonomous_mode !== undefined) {
      setAutonomousMode(state.autonomous_mode);
    }
  }, [state?.autonomous_mode]);

  useEffect(() => {
    const connect = () => {
      const socket = new WebSocket(SOCKET_URL);
      socketRef.current = socket;

      socket.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        const now = Date.now();
        setLatency(now - lastMessageAtRef.current);
        lastMessageAtRef.current = now;

        latestSocketPayloadRef.current = payload;
        const minUiGapMs = 66;
        const elapsedSinceCommit = now - lastUiStateCommitAtRef.current;

        if (elapsedSinceCommit >= minUiGapMs) {
          setState(payload);
          lastUiStateCommitAtRef.current = now;
          return;
        }

        if (queuedSocketTimerRef.current) {
          return;
        }

        queuedSocketTimerRef.current = window.setTimeout(() => {
          queuedSocketTimerRef.current = null;
          if (latestSocketPayloadRef.current) {
            setState(latestSocketPayloadRef.current);
            lastUiStateCommitAtRef.current = Date.now();
          }
        }, Math.max(0, minUiGapMs - elapsedSinceCommit));
      };

      socket.onclose = () => {
        reconnectTimerRef.current = window.setTimeout(connect, 1500);
      };
    };

    connect();

    return () => {
      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
      }
      if (queuedSocketTimerRef.current) {
        window.clearTimeout(queuedSocketTimerRef.current);
      }
      socketRef.current?.close();
    };
  }, []);

  useEffect(() => {
    if (!selectedPerson && people.length && !selectedPersonId) {
      setSelectedPersonId(people[0].id);
    }
  }, [people, selectedPerson, selectedPersonId]);

  useEffect(() => {
    const revision = state?.layout?.revision;
    if (!state || !revision || lastAutoFitRevisionRef.current === revision) {
      return;
    }

    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }

    const zoneRects = Object.values(state?.zones ?? {});
    const exitRects = Object.values(state?.exits ?? {});
    const allRects = [...zoneRects, ...exitRects];
    if (!allRects.length) {
      return;
    }

    const minX = Math.min(...allRects.map((r) => r.x));
    const minY = Math.min(...allRects.map((r) => r.y));
    const maxX = Math.max(...allRects.map((r) => r.x + r.w));
    const maxY = Math.max(...allRects.map((r) => r.y + r.h));

    const worldWidth = Math.max(1, maxX - minX);
    const worldHeight = Math.max(1, maxY - minY);
    const padding = 15;
    const fitScale = Math.min(
      canvas.width / (worldWidth + padding * 2),
      canvas.height / (worldHeight + padding * 2),
    );
    const boundedScale = Math.max(0.1, Math.min(20.0, fitScale));

    const worldCenterX = minX + worldWidth / 2;
    const worldCenterY = minY + worldHeight / 2;

    setScale(boundedScale);
    setPan({
      x: canvas.width / 2 - worldCenterX * boundedScale,
      y: canvas.height / 2 - worldCenterY * boundedScale,
    });

    lastAutoFitRevisionRef.current = revision;
  }, [state]);

  const getNextWaypoint = (person) => {
    if (person?.next_waypoint) return person.next_waypoint;
    const path = Array.isArray(person?.path) ? person.path : [];
    if (!path.length) return "NONE";
    const current = person?.zone;
    const next = path.find((node) => node && node !== current);
    return next || path[path.length - 1] || "NONE";
  };

  const getRoutePreview = (person) => {
    if (person?.route_preview) return person.route_preview;
    const path = Array.isArray(person?.path) ? person.path : [];
    if (!path.length) return "No active route.";
    const preview = path.slice(0, 4).join(" -> ");
    return path.length > 4 ? `${preview} -> ...` : preview;
  };

  const getRouteDestination = (person) => {
    const path = Array.isArray(person?.path) ? person.path : [];
    if (!path.length) return "Awaiting route";
    return path[path.length - 1] || "Awaiting route";
  };

  const getPersonIndexLabel = (person) => {
    if (!person) return "#0";
    if (Number.isFinite(Number(person.member_index))) return `#${Number(person.member_index)}`;
    const idx = people.findIndex((p) => p.id === person.id);
    return idx >= 0 ? `#${idx + 1}` : "#0";
  };

  const getPersonNarrative = (person) => {
    if (!person) return "No occupant selected.";
    const nextWaypoint = getNextWaypoint(person);
    const destination = getRouteDestination(person);
    if (person.status === "TRAPPED") {
      return `${person.name} is isolated in ${person.zone}. The system is trying to reopen a safe path and move rescue support toward this block.`;
    }
    if (person.status === "PANIC") {
      return `${person.name} is under stress in ${person.zone} and is being rerouted toward ${destination}. Next waypoint: ${nextWaypoint}.`;
    }
    if (person.status === "EVACUATING") {
      return `${person.name} is moving out from ${person.zone} toward ${destination}. Next waypoint: ${nextWaypoint}.`;
    }
    return `${person.name} is stable in ${person.zone} and waiting for the next instruction.`;
  };

  const parseAssistantResponse = (fullMessage) => {
    const statusMatch = fullMessage.match(/STATUS:\s*(.+?)(?=MACRO-ACTION:|ACTION:|ADVISORY:|$)/is);
    const actionMatch = fullMessage.match(/(?:MACRO-ACTION|ACTION):\s*(.+?)(?=ADVISORY:|$)/is);
    const advisoryMatch = fullMessage.match(/ADVISORY:\s*(.+?)$/is);
    return {
      status: statusMatch?.[1]?.trim() || null,
      action: actionMatch?.[1]?.trim() || null,
      advisory: advisoryMatch?.[1]?.trim() || null,
      raw: fullMessage,
    };
  };

  const parseEventEntry = (entry) => {
    const eventText = String(entry || "");
    const timeMatch = eventText.match(/^\[(\d{2}:\d{2}:\d{2})\]\s*/);
    const text = eventText.replace(/^\[\d{2}:\d{2}:\d{2}\]\s*/, "");
    const upper = text.toUpperCase();
    let toneClass = "log-entry-system";
    if (/FIRE|BREACH|BURN|SMOKE/.test(upper)) {
      toneClass = "log-entry-fire";
    } else if (/EVACUATE|TRAPPED|EXIT|ROUTE/.test(upper)) {
      toneClass = "log-entry-evacuation";
    } else if (/ALERT|CRITICAL|EMERGENCY/.test(upper)) {
      toneClass = "log-entry-alert";
    }
    return {
      timeLabel: timeMatch?.[1] || "LIVE",
      text,
      toneClass,
    };
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !state) {
      return;
    }

    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    ctx.save();
    ctx.fillStyle = "#05080d";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.strokeStyle = "rgba(104, 130, 184, 0.12)";
    ctx.lineWidth = 1;
    for (let x = 0; x < canvas.width; x += 36) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, canvas.height);
      ctx.stroke();
    }
    for (let y = 0; y < canvas.height; y += 36) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(canvas.width, y);
      ctx.stroke();
    }
    ctx.restore();

    ctx.save();
    ctx.translate(pan.x, pan.y);
    ctx.scale(scale, scale);

    Object.entries(zones).forEach(([name, rect]) => {
      const isHot = state.active_fire_zones.includes(name);
      const zoneRisk = Number(sensorZones[name]?.fire_probability ?? 0);
      const riskStrength = Math.min(zoneRisk / 100, 1);
      ctx.fillStyle = isHot
        ? `rgba(201, 82, 69, ${0.18 + riskStrength * 0.2})`
        : `rgba(30, 40, 56, ${0.66 + riskStrength * 0.12})`;
      ctx.strokeStyle = isHot
        ? "rgba(255, 120, 98, 0.9)"
        : zoneRisk >= 35
          ? "rgba(255, 177, 107, 0.55)"
          : "rgba(176, 198, 255, 0.22)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.roundRect(rect.x, rect.y, rect.w, rect.h, 14);
      ctx.fill();
      ctx.stroke();

      if (isHot) {
        ctx.fillStyle = "rgba(255, 194, 168, 0.95)";
        ctx.beginPath();
        ctx.arc(rect.x + 12, rect.y + 12, 4, 0, Math.PI * 2);
        ctx.fill();
      }

      // --- NEW OFFICE ECOSYSTEM DETAILS ---
      // Distinguish Corridor/Spine/Hall vs typical functional rooms
      const isCorridor = /corridor|spine|hall/i.test(name);
      
      if (!isCorridor) {
        // Draw Desks/Benches
        ctx.fillStyle = "rgba(100, 150, 200, 0.15)";
        ctx.strokeStyle = "rgba(100, 150, 200, 0.3)";
        ctx.lineWidth = 1;
        const deskW = 34;
        const deskH = 18;
        // calculate simple grid of desks
        const cols = Math.floor((rect.w - 40) / (deskW + 20));
        const rows = Math.floor((rect.h - 70) / (deskH + 20)); // leave room for door and title
        const startX = rect.x + (rect.w - cols * (deskW + 20) + 20) / 2;
        const startY = rect.y + 45;
        
        for(let r=0; r<rows; r++) {
          for(let c=0; c<cols; c++) {
            const dx = startX + c * (deskW + 20);
            const dy = startY + r * (deskH + 20);
            ctx.beginPath();
            ctx.roundRect(dx, dy, deskW, deskH, 3);
            ctx.fill();
            ctx.stroke();
            // Draw monitors / seats
            ctx.fillStyle = "rgba(200, 200, 255, 0.2)";
            ctx.fillRect(dx + 5, dy - 4, 8, 4); // monitor
            ctx.beginPath();
            ctx.arc(dx + deskW/2, dy + deskH + 6, 4, 0, Math.PI*2); // chair
            ctx.fill();
            ctx.fillStyle = "rgba(100, 150, 200, 0.15)"; // restore
          }
        }
      }

      // Draw Door placeholder (always draw a central door edge towards a likely corridor)
      ctx.fillStyle = "#27d59b"; // Active door indication
      const doorWidth = 26;
      ctx.beginPath();
      if (rect.w > rect.h) {
         // bottom door
         ctx.fillRect(rect.x + rect.w/2 - doorWidth/2, rect.y + rect.h - 2, doorWidth, 5);
      } else {
         // right door
         ctx.fillRect(rect.x + rect.w - 2, rect.y + rect.h/2 - doorWidth/2, 5, doorWidth);
      }

      // Draw Room Name Title
      ctx.fillStyle = "rgba(255, 255, 255, 0.85)";
      ctx.font = "bold 13px 'Inter', sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.fillText(name.toUpperCase(), rect.x + rect.w / 2, rect.y + 14);
    });

    Object.entries(exits).forEach(([name, rect]) => {
      const blocked = blockedExits.includes(name);
      ctx.fillStyle = blocked ? "rgba(168, 52, 52, 0.2)" : "rgba(35, 131, 95, 0.18)";
      ctx.strokeStyle = blocked ? "rgba(255, 151, 151, 0.86)" : "rgba(117, 235, 178, 0.82)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.roundRect(rect.x, rect.y, rect.w, rect.h, 10);
      ctx.fill();
      ctx.stroke();
      if (blocked) {
        ctx.fillStyle = "rgba(255, 214, 214, 0.96)";
        ctx.beginPath();
        ctx.arc(rect.x + rect.w / 2, rect.y + rect.h / 2, 3, 0, Math.PI * 2);
        ctx.fill();
      }
    });

    const maxRenderFireCells = 1100;
    const fireStep = Math.max(1, Math.ceil(state.fire_cells.length / maxRenderFireCells));
    const visibleFireCells = state.fire_cells.filter((_, index) => index % fireStep === 0);

    ctx.save();
    if (state.fire_cells.length > 1500) {
      ctx.fillStyle = "rgba(255, 120, 74, 0.72)";
      visibleFireCells.forEach(([gx, gy]) => {
        ctx.fillRect(gx * 10, gy * 10, 10, 10);
      });
    } else {
      visibleFireCells.forEach(([gx, gy]) => {
        const x = gx * 10;
        const y = gy * 10;
        const glow = ctx.createRadialGradient(x + 5, y + 5, 0, x + 5, y + 5, 11);
        glow.addColorStop(0, "rgba(255, 228, 164, 0.95)");
        glow.addColorStop(0.45, "rgba(255, 117, 65, 0.82)");
        glow.addColorStop(1, "rgba(187, 35, 35, 0)");
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(x + 5, y + 5, 11, 0, Math.PI * 2);
        ctx.fill();
      });
    }
    ctx.restore();

    const maxRenderWaterCells = 900;
    const waterStep = Math.max(1, Math.ceil(state.water_cells.length / maxRenderWaterCells));
    const visibleWaterCells = state.water_cells.filter((_, index) => index % waterStep === 0);
    const waveTick = Date.now() / 220;
    visibleWaterCells.forEach(([gx, gy]) => {
      const baseX = gx * 10;
      const baseY = gy * 10;
      const pulse = 0.25 + Math.sin((gx + gy) * 0.35 + waveTick) * 0.1;
      const sprayHeight = 5 + Math.cos((gx * 0.4 + gy * 0.3) + waveTick * 0.8) * 2;

      const glow = ctx.createRadialGradient(baseX + 5, baseY + 5, 0, baseX + 5, baseY + 5, 11);
      glow.addColorStop(0, `rgba(168, 226, 255, ${0.42 + pulse})`);
      glow.addColorStop(1, "rgba(79, 172, 255, 0)");
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(baseX + 5, baseY + 5, 11, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = `rgba(96, 190, 255, ${0.34 + pulse})`;
      ctx.beginPath();
      ctx.roundRect(baseX, baseY, 10, 10, 4);
      ctx.fill();

      ctx.fillStyle = `rgba(190, 235, 255, ${0.16 + pulse})`;
      ctx.beginPath();
      ctx.roundRect(baseX + 3, baseY - sprayHeight, 4, sprayHeight, 2);
      ctx.fill();
    });

    people.forEach((person) => {
      const tone = formatStatusTone(person.status);

      if (person.path?.length) {
        ctx.beginPath();
        ctx.moveTo(person.x, person.y);
        person.path.forEach((nodeName) => {
          const rect = zones[nodeName] || exits[nodeName];
          if (!rect) {
            return;
          }
          ctx.lineTo(rect.x + rect.w / 2, rect.y + rect.h / 2);
        });
        ctx.strokeStyle =
          person.id === selectedPersonId
            ? "rgba(118, 186, 255, 0.9)"
            : "rgba(118, 186, 255, 0.35)";
        ctx.lineWidth = person.id === selectedPersonId ? 2.2 : 1.2;
        ctx.setLineDash([6, 5]);
        ctx.stroke();
        ctx.setLineDash([]);
      }

      ctx.beginPath();
      ctx.arc(person.x, person.y, person.id === selectedPersonId ? 6 : 4.5, 0, Math.PI * 2);
      ctx.fillStyle = tone;
      ctx.shadowColor = tone;
      ctx.shadowBlur = person.id === selectedPersonId ? 14 : 7;
      ctx.fill();
      ctx.shadowBlur = 0;

      if (person.id === selectedPersonId) {
        ctx.beginPath();
        ctx.arc(person.x, person.y, 13, 0, Math.PI * 2);
        ctx.strokeStyle = "rgba(148, 197, 255, 0.95)";
        ctx.lineWidth = 2;
        ctx.stroke();
      }
    });

    ctx.restore();
  }, [state, pan, scale, selectedPersonId, people, zones, exits, sensorZones, blockedExits]);

  const postJson = async (path, body) => {
    const response = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload?.message || `Request failed: ${response.status}`);
    }
    return payload;
  };

  const handleCommand = async (action, extra = {}) => {
    await postJson("/api/command", { action, ...extra });
  };

  const toggleAutonomousMode = async () => {
    const next = !autonomousMode;
    setAutonomousMode(next); // optimistic toggle
    try {
      await fetch(`${API_BASE}/api/autonomous-mode`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: next }),
      });
    } catch {
      setAutonomousMode(!next); // revert on error
    }
  };

  const handleCanvasPointerDown = (event) => {
    dragStateRef.current = {
      dragging: true,
      moved: false,
      x: event.clientX,
      y: event.clientY,
    };
  };

  const updateHoveredPerson = (event) => {
    const canvas = canvasRef.current;
    if (!canvas || !state) {
      return;
    }

    const bounds = canvas.getBoundingClientRect();
    const scaleX = canvas.width / bounds.width;
    const scaleY = canvas.height / bounds.height;
    const canvasX = (event.clientX - bounds.left) * scaleX;
    const canvasY = (event.clientY - bounds.top) * scaleY;
    const worldX = (canvasX - pan.x) / scale;
    const worldY = (canvasY - pan.y) / scale;

    const hovered = people.find(
      (person) => Math.hypot(person.x - worldX, person.y - worldY) <= 18 / scale,
    );
    setHoveredPersonId(hovered?.id ?? null);
    if (hovered) {
      const relX = event.clientX - bounds.left;
      const relY = event.clientY - bounds.top;
      const flipX = relX > bounds.width - 320;
      const flipY = relY > bounds.height - 220;
      setHoveredScreenPoint({
        x: Math.max(12, Math.min(bounds.width - 12, relX)),
        y: Math.max(12, Math.min(bounds.height - 12, relY)),
        flipX,
        flipY,
      });
    } else {
      setHoveredScreenPoint(null);
    }

    if (dragStateRef.current.dragging) {
      const dx = event.clientX - dragStateRef.current.x;
      const dy = event.clientY - dragStateRef.current.y;
      dragStateRef.current = {
        dragging: true,
        moved: true,
        x: event.clientX,
        y: event.clientY,
      };
      setPan((prev) => ({ x: prev.x + dx, y: prev.y + dy }));
    }
  };

  const handleCanvasPointerUp = async (event) => {
    const dragState = dragStateRef.current;
    dragStateRef.current.dragging = false;

    const canvas = canvasRef.current;
    if (!canvas || !state) {
      return;
    }

    const bounds = canvas.getBoundingClientRect();
    const scaleX = canvas.width / bounds.width;
    const scaleY = canvas.height / bounds.height;
    const canvasX = (event.clientX - bounds.left) * scaleX;
    const canvasY = (event.clientY - bounds.top) * scaleY;
    const worldX = (canvasX - pan.x) / scale;
    const worldY = (canvasY - pan.y) / scale;

    const clickedPerson = people.find(
      (person) => Math.hypot(person.x - worldX, person.y - worldY) <= 18 / scale,
    );

    if (clickedPerson) {
      setSelectedPersonId(clickedPerson.id);
      return;
    }

    if (!dragState.moved) {
      await handleCommand("manual_fire", { x: worldX, y: worldY });
    }
  };

  const handleWheel = (event) => {
    event.preventDefault();
    const nextScale = Math.max(0.55, Math.min(2.4, scale * (1 - event.deltaY * 0.001)));
    setScale(nextScale);
  };

  // Abort controller lets us cancel an in-flight chat request when user sends a new message
  const chatAbortRef = useRef(null);
  // Unique msg key for live streaming append
  const streamingIdRef = useRef(0);

  const handleChatSubmit = useCallback(async (presetMessage) => {
    const message = (presetMessage ?? chatInput).trim();
    if (!message) return;

    // Cancel any previous in-flight request immediately
    if (chatAbortRef.current) {
      chatAbortRef.current.abort();
      chatAbortRef.current = null;
    }

    const controller = new AbortController();
    chatAbortRef.current = controller;

    // Add user message + empty assistant bubble immediately
    const msgId = ++streamingIdRef.current;
    setChatHistory((prev) => [
      ...prev,
      { role: "user", content: message },
      { role: "system", content: "", streamId: msgId },
    ]);
    setChatInput("");
    setCharCount(0);
    setIsChatting(true);

    try {
      const response = await fetch(`${API_BASE}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
        signal: controller.signal,
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop();
        for (const part of parts) {
          if (!part.startsWith("data: ")) continue;
          const raw = part.slice(6).trim();
          if (raw === "[DONE]") break;
          try {
            const { token } = JSON.parse(raw);
            if (token && !controller.signal.aborted) {
              setChatHistory((prev) =>
                prev.map((m) =>
                  m.streamId === msgId ? { ...m, content: m.content + token } : m
                )
              );
            }
          } catch (_) {}
        }
      }
    } catch (error) {
      if (error?.name !== "AbortError") {
        setChatHistory((prev) =>
          prev.map((m) =>
            m.streamId === msgId
              ? { ...m, content: `Error: ${error?.message || "backend unavailable"}` }
              : m
          )
        );
      }
    } finally {
      if (!controller.signal.aborted) {
        chatAbortRef.current = null;
        setIsChatting(false);
      }
    }
  }, [chatInput]);

  const handleCancelChat = useCallback(() => {
    if (chatAbortRef.current) {
      chatAbortRef.current.abort();
      chatAbortRef.current = null;
    }
    setIsChatting(false);
  }, []);

  const applyTemplate = async () => {
    setUploadingLayout(true);
    setLayoutFeedback("");
    try {
      const data = await postJson("/api/upload_map", { layout: layoutTemplates[selectedTemplate] });
      setLayoutFeedback(`Applied template: ${data.layout.name}`);
      setPan({ x: 0, y: 0 });
      setScale(1);
    } catch {
      setLayoutFeedback("Template application failed.");
    } finally {
      setUploadingLayout(false);
    }
  };

  const submitDesignText = async () => {
    if (!designText.trim()) {
      setLayoutFeedback("Enter a design brief first.");
      return;
    }
    setUploadingLayout(true);
    setLayoutFeedback("");
    try {
      const data = await postJson("/api/upload_map", { design_text: designText });
      setLayoutFeedback(`Layout normalized: ${data.layout.name}`);
      setPan({ x: 0, y: 0 });
      setScale(1);
    } catch {
      setLayoutFeedback("Design brief normalization failed.");
    } finally {
      setUploadingLayout(false);
    }
  };

  const submitLayoutJson = async () => {
    if (!layoutJson.trim()) {
      setLayoutFeedback("Paste a structured layout JSON payload first.");
      return;
    }
    setUploadingLayout(true);
    setLayoutFeedback("");
    try {
      const parsed = JSON.parse(layoutJson);
      const data = await postJson("/api/upload_map", { layout: parsed });
      setLayoutFeedback(`Structured layout applied: ${data.layout.name}`);
      setPan({ x: 0, y: 0 });
      setScale(1);
    } catch {
      setLayoutFeedback("Structured layout JSON is invalid or could not be applied.");
    } finally {
      setUploadingLayout(false);
    }
  };

  const handleImageUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    setUploadingLayout(true);
    setLayoutFeedback("");
    try {
      const image_base64 = await fileToBase64(file);
      const data = await postJson("/api/upload_map", { image_base64 });
      if (data.status === "success") {
        setLayoutFeedback(`Image layout applied: ${data.layout.name}`);
        setPan({ x: 0, y: 0 });
        setScale(1);
      } else {
        setLayoutFeedback(data.message || "Image upload did not produce a valid layout.");
      }
    } catch {
      setLayoutFeedback("Image upload failed.");
    } finally {
      setUploadingLayout(false);
      event.target.value = "";
    }
  };

  const stats = state?.stats ?? {
    alive: 0,
    evacuated: 0,
    trapped: 0,
    casualties: 0,
    panicking: 0,
    active_fires: 0,
  };

  const activeZone =
    sensorSummary.highest_risk_zone ||
    state?.active_fire_zones?.[0] ||
    "No active fire";
  const compactMetrics = [
    { label: "Alive", value: stats.alive, tone: "text-white" },
    { label: "Evacuated", value: stats.evacuated, tone: "text-blue-200" },
    { label: "Panicking", value: stats.panicking, tone: "text-orange-200" },
    { label: "Trapped", value: stats.trapped, tone: "text-amber-200" },
  ];
  const latestAssistantMessage =
    [...chatHistory].reverse().find((entry) => entry.role === "system")?.content ??
    "Awaiting assistant directive.";
  const parsedResponse = parseAssistantResponse(latestAssistantMessage);

  return (
    <div className="app-shell px-2 py-2 lg:px-3 lg:py-3">
      <div className="mx-auto flex h-[calc(100vh-1rem)] max-w-[1880px] flex-col gap-2 overflow-hidden">
        <section className="panel top-command-bar shrink-0 rounded-[20px] px-3 py-2.5">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <div className="rounded-xl bg-blue-500/16 p-2 text-blue-200">
                <Shield className="h-4 w-4" />
              </div>
              <div>
                <div className="section-title">INFERNAL X CONTROL GRID</div>
                <h1 className="text-xl font-extrabold tracking-tight text-white">Fire Suppression + Evacuation</h1>
              </div>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {stats.active_fires > 0 ? (
                <span className="status-pill bg-red-500/14 text-red-200">
                  <Siren className="h-3.5 w-3.5" />
                  Active Incident
                </span>
              ) : (
                <span className="status-pill bg-emerald-500/14 text-emerald-200">
                  <ShieldCheck className="h-3.5 w-3.5" />
                  System Stable
                </span>
              )}
              <span className="status-pill bg-slate-700/40 text-slate-200">
                <MapPinned className="h-3.5 w-3.5" />
                {state?.layout?.name ?? "Default"}
              </span>
              <span className="status-pill bg-blue-500/12 text-blue-100 mono-ui">
                <Waves className="h-3.5 w-3.5" />
                {Math.max(latency, 0)} ms
              </span>
            </div>
          </div>
        </section>

        <div className="operations-grid min-h-0 flex-1">
          <aside className="panel-muted rail-left min-h-0 rounded-[22px] p-2.5">
            <section className="support-block rail-left-top min-h-0">
              <div className="mb-2 flex items-center justify-between gap-2">
                <div className="section-title">Command Deck</div>
                <button
                  className="button-ghost flex items-center justify-center gap-1 px-2.5 py-1.5 text-xs"
                  onClick={() => setShowAdvancedTools((prev) => !prev)}
                >
                  <LayoutTemplate className="h-3.5 w-3.5" />
                  Tools
                </button>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {compactMetrics.map((metric) => (
                  <div key={metric.label} className="metric-card compact-metric">
                    <div className="metric-label">{metric.label}</div>
                    <div className={`mt-1 text-2xl font-extrabold ${metric.tone}`}>{metric.value}</div>
                  </div>
                ))}
              </div>
              <div className="mt-2 rounded-2xl border border-white/6 bg-white/4 p-3">
                <div className="metric-label">Primary Risk Zone</div>
                <div className="mt-1 truncate text-sm font-bold text-white">{activeZone}</div>
                <div className="mt-1 text-xs uppercase tracking-[0.16em] text-slate-400">
                  {sensorSummary.highest_probability ?? 0}% fused risk
                </div>
              </div>
              {/* ---- AUTONOMOUS MODE TOGGLE ---- */}
              <button
                className="mt-2 flex w-full items-center justify-between gap-2 rounded-2xl border px-4 py-3 text-sm font-bold transition-all duration-300"
                style={{
                  borderColor: autonomousMode ? "rgba(34,197,94,0.55)" : "rgba(255,255,255,0.08)",
                  background: autonomousMode
                    ? "linear-gradient(135deg, rgba(21,128,61,0.28) 0%, rgba(5,46,22,0.4) 100%)"
                    : "rgba(255,255,255,0.04)",
                  color: autonomousMode ? "#86efac" : "#94a3b8",
                  boxShadow: autonomousMode
                    ? "0 0 18px rgba(34,197,94,0.25), 0 0 6px rgba(34,197,94,0.1)"
                    : "none",
                }}
                onClick={toggleAutonomousMode}
                title="Toggle InfernalX Autonomous Mode — AI auto-detects and suppresses fire"
              >
                <span className="flex items-center gap-2">
                  <Cpu
                    className="h-4 w-4"
                    style={{ color: autonomousMode ? "#4ade80" : "#64748b" }}
                  />
                  <span className="text-xs font-bold uppercase tracking-widest">
                    Autonomous Mode
                  </span>
                </span>
                {/* Toggle switch visual */}
                <span
                  className="relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors duration-300"
                  style={{
                    background: autonomousMode
                      ? "linear-gradient(90deg, #16a34a, #22c55e)"
                      : "rgba(71,85,105,0.6)",
                  }}
                >
                  <span
                    className="inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow-md transition-transform duration-300"
                    style={{ transform: autonomousMode ? "translateX(18px)" : "translateX(2px)" }}
                  />
                </span>
              </button>
              {/* Active indicator badge */}
              {autonomousMode && (
                <div className="mt-1.5 flex items-center gap-1.5 rounded-xl border border-emerald-500/20 bg-emerald-950/30 px-3 py-1.5">
                  <span className="relative flex h-2 w-2">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
                  </span>
                  <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-400">
                    AI Auto-suppression Active
                  </span>
                </div>
              )}
              <div className="mt-2 grid grid-cols-2 gap-2">
                <button
                  className="button-secondary flex items-center justify-center gap-1.5 px-3 py-2.5 text-xs"
                  onClick={() => handleCommand("spawn_fire", { target: "West Corridor" })}
                >
                  <Flame className="h-3.5 w-3.5" />
                  Inject Fire
                </button>
                <button
                  className="button-primary flex items-center justify-center gap-1.5 px-3 py-2.5 text-xs"
                  onClick={() => handleCommand("set_scenario", { target: "DEFAULT" })}
                >
                  <RefreshCcw className="h-3.5 w-3.5" />
                  Reset
                </button>
              </div>

            </section>

            <section className="support-block rail-left-bottom min-h-0">
              <div className="mb-2 flex items-center gap-2">
                <Activity className="h-4 w-4 text-blue-200" />
                <div className="section-title">Incident Feed</div>
              </div>
              <div className="scrollbar-thin h-full space-y-1.5 overflow-auto pr-1">
                {[...(state?.global_events ?? [])].reverse().slice(0, 16).map((entry, index) => {
                  const parsedEntry = parseEventEntry(entry);
                  return (
                    <div className={`log-entry ${parsedEntry.toneClass}`} key={`${entry}-${index}`}>
                      <div className="timeline-dot timeline-dot-enhanced" />
                      <div className="text-xs leading-5 text-slate-200">
                        <span className="mr-2 text-[10px] font-bold uppercase tracking-[0.12em] text-slate-400">
                          {parsedEntry.timeLabel}
                        </span>
                        {parsedEntry.text}
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          </aside>

          <section className="panel hero-map center-map-shell min-h-0 rounded-[24px] p-2.5">
            <div className="center-map-header mb-1.5 flex items-center justify-between gap-2 px-1">
              <div className="section-title">Center Response Map</div>
              <div className="flex items-center gap-1.5">
                <span className="status-pill bg-blue-500/12 text-blue-100 mono-ui">
                  <Users className="h-3.5 w-3.5" />
                  {people.length}
                </span>
                <span className="status-pill bg-emerald-500/12 text-emerald-100 mono-ui">
                  <MapPinned className="h-3.5 w-3.5" />
                  {Math.max(Object.keys(exits).length - blockedExits.length, 0)} open
                </span>
              </div>
            </div>

            <div className="center-map-stage min-h-0">
              <div className="canvas-frame map-square relative overflow-hidden p-1.5">
                <canvas
                  ref={canvasRef}
                  width={1600}
                  height={900}
                  className="h-full w-full cursor-crosshair rounded-[14px]"
                  onMouseDown={handleCanvasPointerDown}
                  onMouseMove={updateHoveredPerson}
                  onMouseUp={handleCanvasPointerUp}
                  onMouseLeave={() => {
                    dragStateRef.current.dragging = false;
                    setHoveredPersonId(null);
                    setHoveredScreenPoint(null);
                  }}
                  onWheel={handleWheel}
                />

                {hoveredPerson && hoveredScreenPoint ? (
                  <div
                    className="person-hover-card pointer-events-none absolute"
                    style={{
                      left: hoveredScreenPoint.x + (hoveredScreenPoint.flipX ? -14 : 14),
                      top: hoveredScreenPoint.y + (hoveredScreenPoint.flipY ? -14 : 14),
                      transform: `translate(${hoveredScreenPoint.flipX ? "-100%" : "0%"}, ${hoveredScreenPoint.flipY ? "-100%" : "0%"})`,
                    }}
                  >
                    <div className="person-hover-title">
                      <div>
                        <div className="person-hover-name">{hoveredPerson.name}</div>
                        <div className="person-hover-meta">
                          {getPersonIndexLabel(hoveredPerson)} | ID {hoveredPerson.id}
                        </div>
                      </div>
                      <div className="person-hover-role">{hoveredPerson.role}</div>
                    </div>
                    <div className="person-hover-grid">
                      <div className="person-hover-item">
                        <div className="person-hover-label">Status</div>
                        <div className="person-hover-value" style={{ color: formatStatusTone(hoveredPerson.status) }}>
                          {hoveredPerson.status}
                        </div>
                      </div>
                      <div className="person-hover-item">
                        <div className="person-hover-label">HP</div>
                        <div className="person-hover-value">{hoveredPerson.hp}%</div>
                      </div>
                      <div className="person-hover-item person-hover-span">
                        <div className="person-hover-label">Route</div>
                        <div className="person-hover-value">{getRoutePreview(hoveredPerson)}</div>
                      </div>
                    </div>
                  </div>
                ) : null}
              </div>
            </div>

            <div className="center-map-footer mt-1.5 flex items-center justify-between gap-2 px-1 text-xs text-slate-300">
              <div>zoom {scale.toFixed(2)}x</div>
              <div>{blockedExits.length ? `${blockedExits.length} exits blocked` : "all exits active"}</div>
            </div>
          </section>

          <aside className="panel-muted rail-right min-h-0 rounded-[22px] p-2.5">
            <section className="support-block rail-right-top min-h-0">
              <div className="mb-2 flex items-center gap-2">
                <Activity className="h-4 w-4 text-blue-200" />
                <div className="section-title">Routing Log</div>
              </div>
              <div className="scrollbar-thin h-full space-y-1.5 overflow-auto pr-1">
                {[...(state?.global_events ?? [])].reverse().slice(0, 10).map((entry, index) => {
                  const parsedEntry = parseEventEntry(entry);
                  return (
                    <div className={`log-entry ${parsedEntry.toneClass}`} key={`${entry}-right-${index}`}>
                      <div className="timeline-dot timeline-dot-enhanced" />
                      <div className="text-xs leading-5 text-slate-200">
                        <span className="mr-2 text-[10px] font-bold uppercase tracking-[0.12em] text-slate-400">
                          {parsedEntry.timeLabel}
                        </span>
                        {parsedEntry.text}
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>

            <section className="support-block rail-right-bottom min-h-0 flex flex-col">
              <div className="mb-2 flex items-center justify-between gap-2 shrink-0">
                <div className="flex items-center gap-2">
                  <Bot className="h-4 w-4 text-blue-200" />
                  <div className="section-title">Autonomous AI Chatbot</div>
                </div>
                <div className="status-pill bg-blue-500/12 text-blue-100">
                  <Bot className="h-3.5 w-3.5" />
                  {isChatting ? "Thinking" : "Ready"}
                </div>
              </div>

              <div className="assistant-mini-log flex-1 min-h-0 space-y-2 overflow-auto pr-2 pb-2 mt-2">
                {[...chatHistory].map((entry, idx) => {
                  const raw = String(entry.content || "");
                  // Handle legacy [INFERNALX DIRECTIVE] structured format
                  const isDirective = raw.startsWith("[INFERNALX DIRECTIVE]");
                  let displayText = raw;
                  if (isDirective) {
                    // Extract just the advisory/action line for display
                    const advisoryMatch = raw.match(/ADVISORY:\s*(.+)/is);
                    const actionMatch = raw.match(/MACRO-ACTION:\s*(.+?)(?:\n|ADVISORY:|$)/is);
                    const statusMatch = raw.match(/STATUS:\s*(.+?)(?:\n|MACRO-ACTION:|$)/is);
                    const parts = [];
                    if (statusMatch) parts.push(statusMatch[1].trim());
                    if (actionMatch) parts.push(actionMatch[1].trim());
                    if (advisoryMatch) parts.push(advisoryMatch[1].trim());
                    displayText = parts.join(" — ") || raw;
                  }
                  return (
                    <div
                      key={`${entry.role}-${idx}`}
                      className={
                        entry.role === "user"
                          ? "chat-bubble-user ml-auto max-w-[85%]"
                          : "chat-bubble-system max-w-[92%]"
                      }
                    >
                      {displayText}
                    </div>
                  );
                })}
              </div>

              <div className="shrink-0 mt-3 border-t border-white/5 pt-3">
                <div className="relative rounded-2xl border border-white/8 bg-white/3 transition-all focus-within:border-blue-400/40 focus-within:bg-white/5">
                  <textarea
                    className="assistant-input-enhanced w-full resize-none bg-transparent px-3.5 py-2.5 text-sm outline-none"
                    maxLength={320}
                    placeholder="Ask questions about operations, or trigger actions..."
                    value={chatInput}
                    onChange={(event) => {
                      setChatInput(event.target.value);
                      setCharCount(event.target.value.length);
                    }}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" && !event.shiftKey) {
                        event.preventDefault();
                        handleChatSubmit();
                      }
                    }}
                  />
                  <div className="flex items-center justify-between border-t border-white/6 px-3 py-1.5">
                    <div className="text-xs text-slate-400">{charCount}/320 characters</div>
                    <div className="flex items-center gap-1.5">
                      {isChatting && (
                        <button
                          className="button-ghost flex items-center gap-1 px-2.5 py-1.5 text-xs text-red-300 border-red-400/25"
                          onClick={handleCancelChat}
                        >
                          <X className="h-3 w-3" />
                          Cancel
                        </button>
                      )}
                      <button
                        className="button-primary flex items-center gap-1.5 px-3 py-1.5 text-xs"
                        disabled={!chatInput.trim()}
                        onClick={() => handleChatSubmit()}
                      >
                        <Send className="h-3.5 w-3.5" />
                        {isChatting ? "Interrupt" : "Send"}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </section>
          </aside>
        </div>
      </div>

      {showAdvancedTools ? (
        <div className="advanced-overlay fixed inset-0 z-50 flex items-center justify-center px-4 py-6">
          <div className="advanced-backdrop absolute inset-0 bg-slate-950/78" onClick={() => setShowAdvancedTools(false)} />
          <div className="panel advanced-modal relative z-10 max-h-[88vh] w-full max-w-[1500px] overflow-auto rounded-[28px] px-5 py-5">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <div className="section-title">Advanced Layout Tools</div>
                <div className="mt-1 text-lg font-bold text-white">Design Normalization and Layout Control</div>
              </div>
              <button className="button-ghost flex items-center gap-2 px-4 py-2" onClick={() => setShowAdvancedTools(false)}>
                <X className="h-4 w-4" />
                Close
              </button>
            </div>

            <div className="advanced-tools-grid grid gap-3 xl:grid-cols-4">
              <div className="panel-muted rounded-2xl p-4">
                <label className="metric-label block">Quick Template</label>
                <select
                  className="field mt-2"
                  value={selectedTemplate}
                  onChange={(event) => setSelectedTemplate(event.target.value)}
                >
                  <option value="compact_hub">Compact Hub</option>
                  <option value="split_wings">Split Wings</option>
                </select>
                <button className="button-ghost mt-3 w-full px-4 py-3" disabled={uploadingLayout} onClick={applyTemplate}>
                  Apply Template
                </button>
              </div>

              <div className="panel-muted rounded-2xl p-4">
                <label className="metric-label block">Design Brief</label>
                <textarea
                  className="textarea mt-2"
                  placeholder="Describe the building design in plain text."
                  value={designText}
                  onChange={(event) => setDesignText(event.target.value)}
                />
                <button className="button-ghost mt-3 w-full px-4 py-3" disabled={uploadingLayout} onClick={submitDesignText}>
                  <Sparkles className="mr-2 inline h-4 w-4" />
                  Normalize With Model
                </button>
              </div>

              <div className="panel-muted rounded-2xl p-4">
                <label className="metric-label block">Structured Layout JSON</label>
                <textarea
                  className="textarea mono-ui mt-2 min-h-[148px]"
                  placeholder='{"name":"My Layout","population":40,"zones":{"Zone A":{"x":100,"y":100,"w":280,"h":180}},"exits":{"Exit 1":{"x":180,"y":40,"w":60,"h":45}}}'
                  value={layoutJson}
                  onChange={(event) => setLayoutJson(event.target.value)}
                />
                <button className="button-ghost mt-3 w-full px-4 py-3" disabled={uploadingLayout} onClick={submitLayoutJson}>
                  <ScanSearch className="mr-2 inline h-4 w-4" />
                  Apply Structured Layout
                </button>
              </div>

              <div className="panel-muted rounded-2xl p-4">
                <label className="metric-label block">Image Layout Upload</label>
                <label className="button-ghost mt-2 flex cursor-pointer items-center justify-center gap-2 px-4 py-3 text-center">
                  <Upload className="h-4 w-4" />
                  Upload Design Image
                  <input className="hidden" type="file" accept="image/*" onChange={handleImageUpload} />
                </label>
                <div className="mt-3 rounded-2xl border border-white/6 bg-white/4 px-4 py-3 text-sm text-slate-300">
                  {layoutFeedback || "Design normalization feedback will appear here."}
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
