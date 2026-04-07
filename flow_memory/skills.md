# Skills

## Runtime Skills Already Present

### Emergency Command Interpretation

The backend can already interpret operator phrases for:

- extinguish fire
- put off fire
- put out fire
- turn off fire
- activate sprinkler
- status of block one
- status of block two

This is handled by deterministic interception before free-form LLM output.

### Simulation Skills

- fire spawning and spread
- targeted suppression
- occupant movement updates
- evacuation routing
- zone and exit modeling
- event logging

### Agentic Skills

- CrewAI role-based reasoning
- LangGraph sequential orchestration
- LLM-backed summaries
- PA-style response generation

### Layout Skills

- structured JSON layout ingestion
- text-brief-to-layout normalization
- image-based normalization when a vision-capable Ollama model is available

## Development Skills Needed Most Often

- FastAPI backend editing
- WebSocket state debugging
- React/Vite operator UI redesign
- Ollama prompt and model routing
- CrewAI output contract hardening
- LangGraph state-machine reasoning

## Recommended Future Skills

### Retrieval Skill

- retrieve from PDF, SOPs, hardware manuals, and building-specific emergency guides

### Memory Skill

- promote repeated incidents and layout patterns into persistent memory

### Vision Skill

- validate fire, smoke, blocked exits, and people clusters from camera feeds

### Hardware Control Skill

- send verified suppression and alarm commands to real devices only after simulation and reasoning checks agree

## Skill Priority Rule

In a live emergency workflow, prefer this order:

1. simulation truth state
2. deterministic command handler
3. parsed CrewAI decision
4. free-form LLM explanation
