# Memory

## Long-Term Project Memory

### Core Objective

Build INFERNAL X as a large-building emergency intelligence system that can:

- detect and reason over fire incidents
- apply targeted suppression guidance
- route every person safely and dynamically
- give clear operator and occupant instructions

### Main Brain Summary

The academic PDF positions INFERNAL X as an LLM-driven emergency platform combining:

- building layouts
- AI-CCTV analysis
- environmental sensor fusion
- occupant tracking
- dynamic suppression
- route optimization with graph algorithms
- real-time alerts and evacuation guidance

### Current Prototype Truth

What is implemented now:

- local simulation runtime
- dynamic fire and suppression state
- occupant movement and evacuation behavior
- operator dashboard with live WebSocket updates
- local Ollama reasoning using the `infernalx` model
- CrewAI multi-role orchestration
- LangGraph orchestration wrapper
- layout upload and normalization path

What is still vision or roadmap:

- real AI-CCTV ingestion
- RFID/BLE localization pipeline
- motorized hardware sprinkler control
- validated benchmark numbers from real deployment

## Session Memory

### Current Session Snapshot

Date: `2026-04-07`

Confirmed working:

- CrewAI local storage redirected into project workspace
- CrewAI telemetry disabled to avoid noisy blocked-network failures
- chat API accepts both `message` and `query`
- suppression commands like `extinguish fire in block one` work
- status commands like `what is the status of block one` work
- summary endpoint returns deterministic state-driven summaries
- one-page map-first review UI is implemented
- advanced admin/layout tools are moved into an overlay
- map hover now exposes per-person live detail and selected occupant intent/route
- frontend lint and production build pass
- deterministic assistant responses now cover review-critical questions
- explicit full-clear fire commands now work and can reduce active fire cells to zero
- routing is more stable with committed exits and deterministic idle patrol behavior
- default review map now includes extra center exits for better evacuation spread
- default crowd density is lower for a cleaner review view
- transfer-learning vision scaffold exists in `vision_training/`
- review-safe documentation exists in `docs/Transfer_Learning_Vision.md`
- side-by-side map-first desktop layout is now active (map left, support panels right)
- map auto-fit now runs on layout revision changes to prevent compressed map rendering
- `GET /api/llm_health` now exposes LLM routing and fallback metrics
- chat pipeline now validates directive format and retries with fallback model (`llama3.1`) when primary times out
- suppression command targets are validated before execution

### Current Named Models

- primary text model: `infernalx`
- fallback text model: `llama3.1`
- vision model: `llava`

### Current Important Paths

- backend: `server.py`
- agent workflow: `agents/crew.py`, `agents/langgraph_flow.py`
- UI: `ui/src/App.jsx`
- main docs: `docs/`
- academic references: `ref/`

## Presentation Memory

Use this wording when presenting:

`INFERNAL X is a local-first prototype of an LLM-driven fire detection, suppression, and evacuation assistance platform. The current build demonstrates real-time simulation, live operator control, agentic reasoning, and Ollama-based emergency response while remaining aligned with the broader academic system design.`

## Current Review Demo State

- UI story is now map-first, not tool-first
- assistant answers the main demo questions from live state instead of relying on slow free-form LLM output
- sensor fusion, blocked exits, and suppression recommendation are visible parts of the runtime story
- transfer learning is represented honestly as a scaffolded vision-training track, not a false completed model
- a hovered person now reveals immediate map-side details without leaving the main map
- a selected person now shows intent, next waypoint, and route preview
- `turn off fire completely in block two` is a valid demo command and now performs a true clear

## Mem0-Style Upgrade Path

If Mem0 or another persistent memory layer is added later, store memory in three levels:

### Episodic Memory

- previous incidents
- operator commands
- final response summaries

### Semantic Memory

- zone aliases
- building-specific rules
- recurring evacuation preferences

### Procedural Memory

- response playbooks
- suppression priority rules
- escalation order

Until then, this markdown file is the manual session memory and handoff source.

## 2026-04-07 Geometry and Model Memory Update

- operator layout now supports a strict three-rail architecture:
	- left rail: command deck (3/4) + incident feed (1/4)
	- center rail: large square map stage with minimal on-map text
	- right rail: routing log (1/4) + interactive stack (3/4)
- map readability improved by removing dense zone and exit strings from canvas rendering
- LLM prompt policy is now versioned in `model_config.py`
- backend directive validation in `server.py` now references prompt version constants
- `Modelfile` upgraded for deterministic emergency command behavior
- transfer-learning system prompt blueprint added at:
	- `vision_training/TRANSFER_LEARNING_SYSTEM_PROMPT.md`
