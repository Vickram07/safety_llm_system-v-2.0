# Codex Runtime Brain

## Purpose

This folder is the working flow-memory layer for the INFERNAL X project. It gives the coding agent a stable project brain that is easier to reuse across sessions than scattered notes.

Use this folder as the first reference point before changing backend logic, agent orchestration, UI flow, or documentation.

## Main Brain Sources

Primary academic reference:

- `C:\Users\Vickram\Downloads\INFERNAL_X_Final_Done.pdf`

Project-local references:

- `C:\Users\Vickram\Documents\Antigravity\safety_llm_system v 2.0\ref\INFERNAL_X_Final_1.pdf`
- `C:\Users\Vickram\Documents\Antigravity\safety_llm_system v 2.0\ref\INFERNAL_X_Final_1.docx`
- `C:\Users\Vickram\Documents\Antigravity\safety_llm_system v 2.0\docs\Master_Documentation.md`
- `C:\Users\Vickram\Documents\Antigravity\safety_llm_system v 2.0\docs\Real_Time_Implementation_Guide.md`

## Project Identity

INFERNAL X is an LLM-driven intelligent fire detection, dynamic suppression, and evacuation assistance system for large buildings.

The current repository is the working prototype implementation. It already includes:

- FastAPI backend and simulation engine
- React operator dashboard
- WebSocket live updates
- Ollama-backed command and summary generation
- CrewAI role chain
- LangGraph orchestration wrapper
- layout upload and normalization path

The broader academic report includes future-facing components like AI-CCTV, RFID/BLE localization, hardware sprinkler control, and validated benchmarks. Those remain the vision layer unless implemented directly in code.

## Current Runtime Truth

The present codebase should be treated as:

- a live simulation and operator-control prototype
- a local-first agentic emergency orchestration stack
- a presentation-ready base for a real-world fire safety platform

The present codebase should not be described as:

- a validated production deployment
- a real CCTV pipeline already connected to cameras
- a hardware sprinkler controller already integrated with building systems

## Agentic Workflow

1. `server.py` maintains the simulation state, fire spread, suppression cells, occupancy, and operator APIs.
2. `model_config.py` defines the shared local Ollama runtime.
3. `agents/crew.py` defines the Fire Chief, Evacuation Officer, and PA Announcer roles.
4. `agents/langgraph_flow.py` runs those roles in a deterministic LangGraph sequence.
5. `ui/src/App.jsx` renders the live operator UI and interactive chat workflow.

## Model Policy

Default reasoning model:

- `infernalx` via local Ollama

Optional support models:

- fallback text model: `llama3.1`
- vision normalization model: `llava`

## Memory Policy

- `memory.md` is the session handoff file
- `session.md` is the active sprint tracker and manager state
- `agents.md` defines who does what
- `skills.md` defines what the project can do
- `tools.md` defines how the system is run, observed, and extended

If a future persistent memory engine such as Mem0 is added, this folder remains the human-readable source of truth and the seed layer for ingestion.
