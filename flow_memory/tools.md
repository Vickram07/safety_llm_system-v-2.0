# Tools

## Core Runtime Files

- `server.py` - backend, simulation engine, WebSocket server, chat APIs, layout ingestion
- `model_config.py` - shared Ollama model names and base URL
- `sensor_pipeline.py` - ordered sensor fusion and fire-state pipeline
- `sensor_interface.py` - simulated and adapter-based device collectors
- `run_llm.py` - local model helper and runner
- `agents/crew.py` - CrewAI role definitions and parsing
- `agents/langgraph_flow.py` - LangGraph execution chain
- `agents/layout_manager.py` - layout graph support
- `ui/src/App.jsx` - main React operator interface

## Local Model Tools

Expected local service:

- Ollama running at `http://127.0.0.1:11434`

Expected models:

- `infernalx`
- `llava` if image normalization is used

Useful local checks:

```powershell
ollama list
ollama show infernalx
ollama run infernalx "status of block one"
```

## App Endpoints

- `GET /` - serve UI
- `WS /ws` - live state stream
- `POST /api/command` - scenario and simulation control
- `POST /api/chat` - operator chat and commands
- `POST /api/summarize` - situation summary
- `POST /api/upload_map` - layout remap and normalization
- `GET /api/sensor_snapshot` - latest fused sensor state
- `POST /api/sensor_ingest` - sensor ingestion endpoint
- `POST /api/sensor_demo` - load the demo fire packet

## Verification Tools

Backend syntax:

```powershell
python -m py_compile server.py agents\crew.py agents\langgraph_flow.py
```

Frontend verification:

```powershell
npm.cmd run lint
npm.cmd run build
```

## Memory and Logging Tools

- `incident_report.log` - operator and incident trail
- `logs/` - execution and response traces
- `.crewai_local/` - local CrewAI storage redirected into workspace

## MCP / Plugin / Automation Readiness

This repository is currently strongest in local-first execution. If external MCPs, plugins, or automation tools are added later, use them for:

- PDF and document retrieval
- persistent memory indexing
- building-specific SOP retrieval
- recurring reporting or health checks

Do not make them the single source of truth for fire state. The simulation backend must stay authoritative.
