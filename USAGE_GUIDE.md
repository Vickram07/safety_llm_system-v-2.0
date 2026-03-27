# 📘 AEGIS Command Continuum — Usage Guide

> Everything your team needs to know to **operate** the Safety LLM Simulation after it's installed and running.

---

## Table of Contents

- [Quick Start Checklist](#quick-start-checklist)
- [Dashboard Overview](#dashboard-overview)
- [Controls & Interaction](#controls--interaction)
- [AI Chat System](#ai-chat-system)
- [Fire & Suppression Mechanics](#fire--suppression-mechanics)
- [Scenarios](#scenarios)
- [Visual Legend](#visual-legend)
- [Standalone CLI Mode](#standalone-cli-mode)
- [Logs & Audit Trail](#logs--audit-trail)
- [Complete API Cheat Sheet](#complete-api-cheat-sheet)

---

## Quick Start Checklist

Before using, confirm all three services are running:

| # | Service | Command | Expected |
|---|---------|---------|----------|
| 1 | Ollama | Running in system tray or `ollama serve` | Ollama icon in taskbar |
| 2 | Backend | `python server.py` | `Uvicorn running on 0.0.0.0:8000` |
| 3 | Frontend | `cd ui && npm run dev` | `Local: http://localhost:5173/` |

Open **http://localhost:5173/** in your browser. You should see the full Sci-Fi dashboard with 100 people moving around.

---

## Dashboard Overview

The dashboard is a Bloomberg-style "Surveillance Command Center" with the following panels:

| Panel | What It Shows |
|-------|--------------|
| **Facility Map** | Top-down spatial view of all 13 zones with live entity positions |
| **SITREP** | AI-generated situation report (auto-updates during emergencies) |
| **Event Log** | Chronological list of AI alerts, PA announcements, and system events |
| **Chat Panel** | Send natural language commands to the InfernalX AI |
| **CCTV Feeds** | Hoverable zone camera views |
| **Stats** | Live counts — alive, escaped, trapped, panicking personnel |

---

## Controls & Interaction

### Keyboard Controls

| Key | Action |
|-----|--------|
| `Arrow Keys` | Move the currently selected character on the facility map |
| `TAB` | Cycle selection between characters (Operator → Medic → Civilians) |
| `V` | Toggle voice command mode (requires microphone) |

### Mouse Controls

| Click Target | Action |
|-------------|--------|
| `[TYPE]` button | Opens the AI chat text input |
| `[TALK]` button | Starts voice command listening |
| Facility map | Some scenarios support click-to-spawn fire |

---

## AI Chat System

The chat system connects directly to the InfernalX LLM running locally via Ollama. Type commands in natural language.

### Command Reference

| What You Type | What Happens |
|---------------|-------------|
| `"Turn on sprinklers"` | Phase 2 fire suppression activates across all fire zones |
| `"Put out the fire"` | Same as above — triggers full suppression |
| `"Status report"` | AI returns a casualty and evacuation status summary |
| `"Where is the fire?"` | AI reports which zones currently have active thermal events |
| `"Stop fire"` | Triggers suppression mode |
| `"Extinguish"` | Triggers suppression mode |
| Any question | AI responds in character as InfernalX (cold, technical, 1 sentence max) |

### Suppression Trigger Keywords

Any message containing these words auto-triggers the fire suppression system:

```
phase 2, sprinkler, water, suppress, extinguish, put out,
turn off, stop fire, disable fire, kill fire, put off
```

### AI Behavior

- **Response limit:** 15–20 words max (enforced via token cap)
- **Style:** Cold, military-robotic. No markdown, no bullets, no pleasantries.
- **Context:** The AI sees the current simulation state (alive/escaped/trapped counts, fire zones, recent incident history).
- **Fallback:** If Ollama is not running, the AI responds with `"OFFLINE."` or `"CRASH."`

---

## Fire & Suppression Mechanics

### How Fire Works

1. Fire can be spawned via:
   - Predefined scenarios (`FIRE_EMERGENCY`, `ADMIN`)
   - Manual coordinates via the API (`/api/command` with `manual_fire`)
   - Chat command interception
2. Fire **spreads** to adjacent grid cells at a 20% probability per update cycle.
3. Fire only spreads within defined building zones (it won't burn through walls).
4. Personnel in fire cells take **0.5 HP damage per tick**.

### How Suppression Works

1. **Precision targeting** — Water is deployed only on cells that are actively burning (no "flood disaster").
2. **Gradual fade** — In suppression mode, 15 fire cells are removed per frame for a realistic "fading" effect.
3. Water has a 1-cell radius spread margin around each suppressed cell.

### Evacuation AI

- When any fire exists, **all 100 agents** switch from IDLE to EVACUATING.
- Agents near fire zones enter **PANIC** mode (faster movement speed 3.5x).
- Pathfinding uses **Dijkstra's algorithm** with dynamic hazard avoidance.
- If an agent cannot find a path, they become **TRAPPED** — the AI automatically deploys targeted halon drops to clear their route.
- PA announcements are auto-generated for rerouted personnel (rate-limited to 1 every 10 seconds).

---

## Scenarios

Switch between scenarios using the API or predefined configs:

### DEFAULT / OPERATOR
- 100 personnel spawn randomly across 13 zones
- Normal peacetime operations — agents roam (Managers, Security, Cleaners patrol periodically)

### FIRE_EMERGENCY
- 100 personnel + **fires in Zone Iota (Medical) and East Corridor**
- Immediate mass evacuation triggers

### ADMIN
- 100 personnel + **fires in West Corridor and Zone Theta (Cafeteria)**
- Multi-fire chaos scenario for stress testing

### CAMERA
- Minimal scenario: 2 people only (Security Guard + Janitor)
- Good for CCTV demonstration

### Switch Scenario via API

```bash
curl -X POST http://localhost:8000/api/command \
  -H "Content-Type: application/json" \
  -d '{"action": "set_scenario", "target": "FIRE_EMERGENCY"}'
```

---

## Visual Legend

### Facility Zones (13 Zones)

| Zone | Grid Location |
|------|--------------|
| Zone Alpha (Executive) | Top-left |
| Zone Beta (Engineering) | Top-center-left |
| Zone Gamma (Datacenter) | Top-center |
| Zone Delta (Operations) | Top-center-right |
| Zone Epsilon (Logistics) | Top-right |
| West Corridor | Middle-left |
| Central Hub | Middle-center |
| East Corridor | Middle-right |
| Zone Zeta (Lobby) | Bottom-left |
| Zone Eta (R&D) | Bottom-center-left |
| Zone Theta (Cafeteria) | Bottom-center |
| Zone Iota (Medical) | Bottom-center-right |
| Zone Kappa (Security) | Bottom-right |

### Color Coding

| Element | Color | Meaning |
|---------|-------|---------|
| Fire cells | 🟥 Red / Orange | Active thermal breach — DANGER |
| Water cells | 🟦 Blue / Cyan | Active sprinklers — SAFE |
| Exit points | 🟩 Green | Evacuation exits (10 total around the perimeter) |
| Medical staff | 🟦 Cyan | Medics and medical personnel |
| Civilians | 🟪 Magenta | General workers |
| Injured | 🟨 Yellow / Orange | Personnel taking damage |

### Personnel Status States

| Status | Meaning |
|--------|---------|
| `IDLE` | Normal operations, no threat detected |
| `EVACUATING` | Facility-wide alert, orderly exit in progress |
| `PANIC` | Near fire zone, running at max speed |
| `TRAPPED` | No evacuation path found — AI deploying autonomous rescue |
| `ESCAPED` | Successfully reached an exit — removed from the map |

---

## Standalone CLI Mode

For terminal-only LLM testing (no UI needed):

```bash
python run_llm.py
```

This:
1. Builds or verifies the custom LLM model
2. Sends `scenario_input.json` sensor data to the AI
3. Streams the AI's analysis with a typewriter effect
4. Enters an interactive chat loop (`OPERATOR > ` prompt)
5. Type `exit` to quit

---

## Logs & Audit Trail

| File | What It Captures |
|------|-----------------|
| `incident_report.log` | All fire events, suppression actions, trapped personnel — permanent audit trail |
| `logs/execution_*.log` | Per-session execution logs from `run_llm.py` (timestamped) |
| `error_log.txt` | Application error log |

> Incident logs are **silently written** during runtime. Remind your audience during presentations that this creates a permanent, auditable paper trail.

---

## Complete API Cheat Sheet

### WebSocket — Real-time State

```
ws://localhost:8000/ws
```

Streams the full simulation state JSON at 30fps. Fields include:
- `people[]` — position, HP, status, path for all active agents
- `fire_cells[]` — grid coordinates of active fire
- `water_cells[]` — grid coordinates of active sprinklers
- `active_fire_zones[]` — zone names with fire
- `pa_announcements[]` — recent PA messages
- `global_events[]` — event log entries
- `sitrep` — current situation report string

### POST /api/command

```json
// Spawn fire in a zone
{"action": "spawn_fire", "target": "Zone Theta (Cafeteria)"}

// Switch scenario
{"action": "set_scenario", "target": "FIRE_EMERGENCY"}

// Spawn fire at exact coordinates
{"action": "manual_fire", "x": 500, "y": 300}
```

### POST /api/chat

```json
{"message": "What is the current threat level?"}
// Returns: {"response": "CRITICAL THERMAL BREACH IN ZONE IOTA."}
```

### POST /api/summarize

No body required. Returns an AI-generated situation summary:

```json
{"summary": "15 TRAPPED, 40 EVACUATING, 2 FIRE ZONES ACTIVE."}
```

---

## Need More Detail?

Check the `docs/` folder — it has 17 detailed architecture guides:

| Doc | Topic |
|-----|-------|
| `00_SYSTEM_OVERVIEW.md` | Full system architecture |
| `02_LLM_REASONING_ARCHITECTURE.md` | How the LLM reasons |
| `03_SENSOR_INTEGRATION_GUIDE.md` | Sensor data flow |
| `04_AI_CCTV_INTEGRATION_GUIDE.md` | Camera AI pipeline |
| `06_EVACUATION_INTELLIGENCE_GUIDE.md` | Pathfinding & evacuation |
| `15_MODEL_CREATION_AND_GGUF_GUIDE.md` | Custom model building |
| `16_BUILDING_ARCHITECTURE_MAP.md` | Physical building layout |

For LLM setup, see [**InfernalX_Setup_Guide.md**](InfernalX_Setup_Guide.md).
