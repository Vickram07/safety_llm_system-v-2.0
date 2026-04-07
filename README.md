# INFERNAL X

LLM-driven fire detection, suppression, and evacuation assistance prototype for large buildings.

This repository currently contains a local simulation build of the INFERNAL X project. It demonstrates the project direction shown in the reference documents, but with a deliberately limited implementation scope.

## Current Scope

- Real-time building safety simulation served with FastAPI
- Live dashboard UI with WebSocket state updates
- Fire spawning, spread, and water suppression simulation
- Occupant movement with dynamic evacuation routing
- Local LLM-backed chat and situation summary endpoints
- CrewAI and LangGraph prototype integration for high-level emergency reasoning
- Ordered sensor ingestion and fusion pipeline for real-time deployment bridging

## What This Build Is

This build should be treated as a working prototype, not the full final system described in the reference report.

Implemented now:

- Local simulation environment
- Zone and exit model
- Evacuation path computation
- Simulated suppression behavior
- LLM-assisted text output

Not fully implemented yet:

- Real CCTV ingestion
- Real RFID or BLE occupant tracking
- Real motorized sprinkler hardware control
- Validated dataset pipeline
- Measured academic performance claims

## Project Structure

- `server.py` - FastAPI backend, simulation engine, REST and WebSocket endpoints
- `model_config.py` - shared Ollama model configuration
- `sensor_pipeline.py` - ordered sensor collection and fusion pipeline
- `sensor_interface.py` - simulated and adapter-based sensor providers
- `sensor_demo_packet.json` - presentation-ready demo packet for the sensor pipeline
- `scenario_input.json` - example structured fire scenario input
- `ui/` - React dashboard
- `static/` - legacy static dashboard fallback
- `agents/` - CrewAI and LangGraph prototype workflow
- `docs/` - concise project documentation
- `flow_memory/` - project brain for Codex-style agent memory, workflow, skills, and tools
- `ref/` - academic reference materials for project direction and report style

## Run

1. Install Python dependencies:

```bash
pip install -r requirements.txt
```

2. Make sure Ollama is running locally.

The default project model is the existing local custom model `infernalx`.

3. Start the backend:

```bash
python server.py
```

4. Open:

```text
http://localhost:8000
```

If the React build is not present, the server falls back to the legacy static UI.

## Main Endpoints

- `GET /` - serve UI
- `WS /ws` - live simulation state
- `POST /api/command` - fire spawn and scenario control
- `POST /api/chat` - LLM chat
- `POST /api/summarize` - LLM situation summary
- `POST /api/upload_map` - prototype layout remap endpoint
- `GET /api/sensor_snapshot` - latest fused sensor state
- `POST /api/sensor_ingest` - ingest real or staged sensor packets
- `POST /api/sensor_demo` - load the demo fire packet into the pipeline

## Documentation Note

The `ref` folder represents the broader academic project vision. The repository documentation is intentionally kept more limited and accurate to the current codebase.
