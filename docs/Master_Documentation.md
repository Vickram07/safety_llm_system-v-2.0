# INFERNAL X Master Documentation

## Purpose

INFERNAL X is a prototype safety system for large-building fire response. The current repository focuses on a simulation-first implementation that demonstrates three core ideas:

1. fire state monitoring
2. dynamic evacuation support
3. local LLM-assisted decision output

This document keeps the scope intentionally small so it matches the current codebase.

## Current Implementation

### Backend

The backend is implemented in `server.py` using FastAPI. It provides:

- a simulation loop
- live WebSocket streaming
- command APIs
- LLM chat and summary endpoints

The simulation maintains:

- zone geometry
- exits
- occupant positions
- active fire cells
- water suppression cells
- event logs
- fused sensor state

### Frontend

The main UI is a React dashboard in `ui/`. A legacy static interface is also present in `static/` as a fallback.

The UI shows:

- facility layout
- fire zones
- occupants
- evacuation state
- logs
- PA-style notifications

### Agent Workflow

Prototype multi-agent support exists in `agents/`.

- `crew.py` defines CrewAI agents for fire review, evacuation guidance, and PA output
- `langgraph_flow.py` wraps the reasoning sequence in a LangGraph flow

In the current build, this layer is supportive. Core movement and suppression logic still rely mainly on simulation rules in `server.py`.

## Present Features

The repository currently supports these features:

- manual and zone-based fire spawning
- fire spread simulation
- targeted water suppression simulation
- evacuation route recalculation
- occupant state changes such as idle, evacuating, panic, trapped, and escaped
- local LLM chat through Ollama
- local LLM summary generation
- ordered sensor packet ingestion
- data fusion into zone-level fire probability and exit status
- structured layout upload
- design-brief normalization into a layout model

## Limited or Prototype Features

The following items are present only as early-stage or placeholder functionality:

- CrewAI and LangGraph are integrated as prototype reasoning layers
- PA announcements are simulated in the UI
- image-to-layout normalization depends on a vision-capable local model and may need refinement
- hardware adapters for MQTT, BLE, RFID, and sprinkler controllers still need real device connectors

## Not Yet Implemented as Full Systems

These ideas belong to the larger project vision but should not be treated as complete in this repository:

- live CCTV analysis
- RFID tracking
- BLE tracking
- hardware sprinkler control
- validated multi-floor deployment
- measured academic performance benchmarks

## Reference Alignment

The `ref/` folder contains the broader academic report and presentation materials for INFERNAL X. Those references are useful for:

- project context
- naming consistency
- report style
- future roadmap direction

They should not be read as a one-to-one description of the current repository state.

## Recommended Positioning

When describing this repository, use this wording:

`This repository contains the current prototype implementation of INFERNAL X, a local simulation system for LLM-assisted fire response, suppression, and evacuation support.`

## Next Documentation Rule

Until more modules are fully implemented, keep all project documentation:

- concise
- truthful
- limited to current scope
- clearly separated from future goals
