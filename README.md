# 🛡️ AEGIS Command Continuum — Safety-Bounded LLM System v2.0

> A real-time enterprise facility safety simulation powered by a locally-hosted LLM (Meta Llama 3.1 via Ollama). 100+ autonomous agents navigate fire emergencies, evacuation routes, and AI-driven suppression — all visualized on a Bloomberg-style Sci-Fi dashboard.

---

## 📑 Table of Contents

- [Architecture Overview](#architecture-overview)
- [Prerequisites](#prerequisites)
- [Installation (Step-by-Step)](#installation-step-by-step)
- [Running the Project](#running-the-project)
- [Project Structure](#project-structure)
- [Usage Guide](#usage-guide)
- [API Reference](#api-reference)
- [Troubleshooting / FAQ](#troubleshooting--faq)
- [Team Notes](#team-notes)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                     BROWSER                         │
│         React 19 + Vite + TailwindCSS 4             │
│     (Sci-Fi Dashboard with Pan/Zoom/CCTV)           │
│                  localhost:5173                      │
└──────────────────────┬──────────────────────────────┘
                       │ WebSocket + REST
┌──────────────────────▼──────────────────────────────┐
│               FastAPI Backend (server.py)            │
│    Simulation Engine: 100+ Agents, Fire/Suppression  │
│    WebSocket @30fps | REST /api/chat, /api/command   │
│                  localhost:8000                       │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP (localhost:11434)
┌──────────────────────▼──────────────────────────────┐
│             Ollama (Local LLM Runtime)               │
│        InfernalX Model (fine-tuned llama3.1)         │
│           Runs 100% offline on your machine          │
└─────────────────────────────────────────────────────┘
```

| Layer | Tech | Purpose |
|-------|------|---------|
| **Frontend** | React 19, Vite 7, TailwindCSS 4, Recharts, Lucide Icons | Real-time facility visualization |
| **Backend** | Python, FastAPI, Uvicorn, WebSockets | Simulation engine + API server |
| **LLM** | Ollama + Llama 3.1 (8B) | AI situation reports, chat, autonomous PA |
| **Extras** | Pygame, pyttsx3, SpeechRecognition | Visual simulation, TTS, voice commands |

---

## Prerequisites

Before cloning, make sure your machine has **all** of the following installed:

| Tool | Version | Download Link |
|------|---------|---------------|
| **Python** | 3.10+ | [python.org/downloads](https://www.python.org/downloads/) |
| **Node.js** | 18+ (LTS recommended) | [nodejs.org](https://nodejs.org/) |
| **npm** | Comes with Node.js | — |
| **Ollama** | Latest | [ollama.com/download](https://ollama.com/download) |
| **Git** | Latest | [git-scm.com](https://git-scm.com/) |

> [!IMPORTANT]
> **Ollama** is **mandatory**. The AI features (chat, situation reports, PA system) will not work without it. Ollama runs the LLM entirely on your local machine — no API keys, no cloud, no internet needed after initial model download.

### Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| RAM | 8 GB | 16 GB |
| Disk Space | ~6 GB (for Llama 3.1 weights) | 10 GB+ |
| GPU | Not required (CPU inference works) | NVIDIA GPU w/ CUDA for faster inference |

---

## Installation (Step-by-Step)

### Step 1 — Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/safety_llm_system.git
cd "safety_llm_system v 2.0"
```

> Replace `YOUR_USERNAME` with the actual GitHub org/user.

---

### Step 2 — Install Python Dependencies

```bash
pip install fastapi uvicorn requests pyttsx3 pygame SpeechRecognition pyaudio
```

Or use the requirements file:

```bash
pip install -r requirements.txt
pip install fastapi uvicorn
```

> [!NOTE]
> `fastapi` and `uvicorn` are used by `server.py` but are not listed in `requirements.txt` — install them manually. `pyaudio` may need additional OS-level dependencies on Linux/macOS (see [Troubleshooting](#troubleshooting--faq)).

---

### Step 3 — Install Frontend Dependencies

```bash
cd ui
npm install
cd ..
```

---

### Step 4 — Set Up the LLM (Ollama + InfernalX)

#### 4a. Pull the Base Model

```bash
ollama pull llama3.1
```

> ⏱ This downloads ~4.7 GB. Only needed **once** per machine.

#### 4b. Create the Custom InfernalX Model

Make sure your terminal is inside the project root directory (where `Modelfile` is located):

```bash
ollama create infernalx-llm -f Modelfile
```

#### 4c. Verify

```bash
ollama list
```

You should see `infernalx-llm:latest` in the output.

> [!TIP]
> The `server.py` currently uses `MODEL_NAME = "tinyllama"` by default. If you want to use the full InfernalX model, edit line 21 in `server.py` and change it to `MODEL_NAME = "infernalx-llm"`. TinyLlama is lighter and faster for quick testing.

---

## Running the Project

You need **two terminal windows** open simultaneously:

### Terminal 1 — Start the Backend Server

```bash
cd "safety_llm_system v 2.0"
python server.py
```

The FastAPI server starts on **http://localhost:8000**. You should see:

```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Terminal 2 — Start the Frontend Dashboard

```bash
cd "safety_llm_system v 2.0/ui"
npm run dev
```

The Vite dev server starts on **http://localhost:5173**. Open this URL in your browser.

> [!IMPORTANT]
> **Both servers must be running at the same time.** The frontend connects to the backend via WebSocket on port 8000.

### Quick Start Summary

```
Terminal 1:  python server.py          → Backend  @ :8000
Terminal 2:  cd ui && npm run dev      → Frontend @ :5173
Browser:     http://localhost:5173     → Open the dashboard
```

---

## Project Structure

```
safety_llm_system v 2.0/
│
├── server.py              # 🔥 Main backend — FastAPI server + simulation engine
├── run_llm.py             # CLI-mode LLM interaction (standalone testing)
├── visual_simulation.py   # Pygame-based visual simulation (standalone)
├── live_simulation.py     # Live simulation driver
├── sensor_interface.py    # Sensor data abstraction layer
├── patch.py               # Utility patches
│
├── Modelfile              # Ollama model definition for InfernalX
├── requirements.txt       # Python dependencies
├── scenario_input.json    # Sample sensor/CCTV input data
├── system_prompt.txt      # Core LLM system prompt
├── infernalx_prompt.txt   # Extended InfernalX directives
├── pa_system_prompt.txt   # PA announcement prompt template
├── live_commander_prompt.txt # Live commander prompt
│
├── incident_report.log    # Auto-generated crisis audit log
│
├── ui/                    # ⚛️ React Frontend (Vite + Tailwind)
│   ├── src/
│   │   ├── App.jsx        # Main dashboard component
│   │   ├── main.jsx       # React entry point
│   │   ├── index.css      # Global styles
│   │   └── App.css        # Component styles
│   ├── package.json       # Node.js dependencies
│   └── vite.config.js     # Vite configuration
│
├── static/                # Legacy static UI (HTML/CSS/JS)
│   ├── index.html
│   ├── app.js
│   └── styles.css
│
├── docs/                  # 📖 Architecture documentation (17 guides)
│   ├── 00_SYSTEM_OVERVIEW.md
│   ├── 01_CURRENT_IMPLEMENTATION.md
│   ├── 02_LLM_REASONING_ARCHITECTURE.md
│   ├── ...
│   └── 16_BUILDING_ARCHITECTURE_MAP.md
│
├── InfernalX_Setup_Guide.md      # LLM setup walkthrough
├── AI_Model_Retraining_Guide.md  # Model retraining reference
└── logs/                  # Execution logs directory
```

---

## Usage Guide

> For a detailed walkthrough of every feature, see [**USAGE_GUIDE.md**](USAGE_GUIDE.md).

### Simulation Controls

| Control | Action |
|---------|--------|
| **Arrow Keys** | Move the selected character |
| **TAB** | Switch between characters (Operator, Medic, Civilians) |
| **Click [TYPE]** | Open the chat box — type natural language commands to the AI |
| **Click [TALK]** or press **V** | Toggle voice command mode |

### AI Chat Commands (Examples)

| Command | What It Does |
|---------|-------------|
| `"Turn on sprinklers"` | Activates Phase 2 fire suppression system-wide |
| `"Status report"` | AI generates a casualty/evacuation status report |
| `"Where is the fire?"` | Reports active fire zone locations |
| `"Put out the fire"` | Triggers autonomous suppression + water deployment |

### Visual Indicators

| Color | Meaning |
|-------|---------|
| 🟥 Red/Orange blocks | Active fire zones (DANGER) |
| 🟦 Blue/Cyan blocks | Active water sprinklers (SAFE) |
| 🟩 Green areas | Safe exit points |
| 🟦 Cyan characters | Medical personnel |
| 🟪 Magenta characters | Civilians |
| 🟨 Yellow/Orange characters | Injured personnel |

### Scenarios

The simulation supports predefined scenarios via the API:

| Scenario | Description |
|----------|-------------|
| `DEFAULT` / `OPERATOR` | 100 personnel, normal operations |
| `FIRE_EMERGENCY` | 100 personnel + fires in Medical Zone and East Corridor |
| `ADMIN` | 100 personnel + fires in West Corridor and Cafeteria |
| `CAMERA` | Minimal 2-person CCTV surveillance scenario |

---

## API Reference

The backend exposes these endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Serves the legacy static UI |
| `WS` | `/ws` | WebSocket — streams simulation state at 30fps |
| `POST` | `/api/command` | Send commands (`spawn_fire`, `set_scenario`, `manual_fire`) |
| `POST` | `/api/chat` | Send a natural language message to InfernalX |
| `POST` | `/api/summarize` | Get an AI-generated situation summary |

### Example: Spawn a fire via API

```bash
curl -X POST http://localhost:8000/api/command \
  -H "Content-Type: application/json" \
  -d '{"action": "spawn_fire", "target": "Zone Theta (Cafeteria)"}'
```

### Example: Chat with InfernalX

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Status report"}'
```

---

## Troubleshooting / FAQ

### ❓ "Could not connect to Ollama" or LLM features not working

**Cause:** Ollama is not running in the background.

**Fix:** Open a terminal and run:

```bash
ollama serve
```

> On Windows, Ollama usually runs as a system tray application. Make sure it's started.

---

### ❓ `pyaudio` installation fails

**Windows:**
```bash
pip install pipwin
pipwin install pyaudio
```

**macOS:**
```bash
brew install portaudio
pip install pyaudio
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install portaudio19-dev
pip install pyaudio
```

---

### ❓ Frontend shows blank page / can't connect

1. Make sure `python server.py` is running in a separate terminal (port 8000).
2. Make sure `npm run dev` is running in the `ui/` directory (port 5173).
3. Check the browser console for WebSocket errors pointing to `ws://localhost:8000/ws`.

---

### ❓ "Module not found" errors in Python

Install missing packages:

```bash
pip install fastapi uvicorn requests pyttsx3 pygame SpeechRecognition pyaudio
```

---

### ❓ Node.js / npm install fails

Make sure you have Node.js 18+ installed:

```bash
node --version
npm --version
```

If `node_modules` is corrupt, delete it and reinstall:

```bash
cd ui
rm -rf node_modules package-lock.json
npm install
```

---

### ❓ How do I change which LLM model is used?

Edit `server.py` line 21:

```python
MODEL_NAME = "tinyllama"       # Fast, lightweight (default)
MODEL_NAME = "infernalx-llm"   # Full custom model (see InfernalX_Setup_Guide.md)
MODEL_NAME = "llama3.1"        # Base Llama 3.1 without custom prompt
```

---

## Team Notes

- **Everything is local.** No API keys, no cloud dependencies, no data leaves your machine.
- **Incident logs** are silently written to `incident_report.log` — a permanent audit trail of all fire events and suppression actions.
- **Execution logs** are saved in the `logs/` directory with timestamps.
- **The `docs/` folder** contains 17 detailed architecture guides covering every subsystem (sensor integration, CCTV AI, evacuation routing, blockchain audit, cybersecurity, etc.).
- For LLM-specific setup, see [**InfernalX_Setup_Guide.md**](InfernalX_Setup_Guide.md).
- For model retraining workflows, see [**AI_Model_Retraining_Guide.md**](AI_Model_Retraining_Guide.md).

---

## License

Internal project — Antigravity Team. All rights reserved.
