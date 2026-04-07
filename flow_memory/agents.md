# Agent Topology

## Active Agents In This Repository

### 1. Fire Safety Chief

- file: `agents/crew.py`
- responsibility: assess active fire zones and recommend targeted sprinkler deployment
- output contract: `STATUS`, `SPRINKLER_ZONES`

### 2. Evacuation Operations Officer

- file: `agents/crew.py`
- responsibility: select primary and alternate exits based on fire conditions and remaining occupants
- output contract: `PRIMARY_EXIT`, `ALTERNATE_EXIT`

### 3. Public Address System AI

- file: `agents/crew.py`
- responsibility: convert evacuation guidance into a short calm instruction
- output contract: `PA_MESSAGE`

### 4. LangGraph Orchestrator

- file: `agents/langgraph_flow.py`
- responsibility: run the CrewAI chain in the order:
  - sensor fusion
  - multi-agent deliberation
  - execution handoff

### 5. Simulation Engine

- file: `server.py`
- responsibility: maintain truth state for:
  - fire cells
  - water suppression
  - occupant movement
  - evacuation state
  - zone summaries
  - operator chat context

### 6. Operator Chat Agent

- file: `server.py`
- responsibility: accept natural-language commands and route them into:
  - deterministic suppression commands
  - area status reports
  - LLM-generated strategic replies

### 7. Layout Normalization Agent

- file: `server.py`
- responsibility: accept structured layouts, design text, or image uploads and convert them into the current simulation layout model

## Role Intent

The intended final system, aligned with the academic PDF, is:

- an AI-CCTV perception layer
- a data-fusion and localization layer
- an LLM reasoning layer
- a dynamic suppression layer
- an autonomous evacuation guidance layer

The current repository already covers the reasoning, simulation, layout, and operator-control layers. Perception and hardware control are still future-facing.

## Suggested Expansion Path

### Mem0-Ready Memory Agent

Not currently installed in this repository, but the architecture is ready for it.

Recommended role:

- store operator decisions, recurring building layouts, recurring failure patterns, and successful suppression/evacuation outcomes

Recommended storage subjects:

- building aliases like `block one` to `Zone Alpha (Executive)`
- frequently used operator commands
- known good layout templates
- incident summaries
- preferred PA announcement styles

### RAG Agent

Recommended future use:

- index the academic PDF, project docs, SOPs, building-specific safety manuals, and hardware manuals
- answer operator questions with retrieval-backed responses rather than raw prompting alone

### Vision Agent

Recommended future use:

- real CCTV smoke/fire validation
- floor-plan OCR and semantic map extraction
- blocked-exit and crowd-density estimation

## Agent Rules

- deterministic command interception takes priority over free-form LLM output
- simulation truth state is the source of truth for operator status answers
- CrewAI output should be parsed into labels before it is shown in the UI
- future persistent memory must never override the live simulation state without verification

## Active Sprint Agent Pattern

For the current runtime upgrade, orchestration must follow this manager-and-three-team structure.

### Manager Agent (Power Model)

- owns orchestration and final decision authority
- reads `flow_memory/session.md` and current code state first
- issues task order and handoff rules
- validates output contracts before merge
- records blockers and resolution notes

### Team 1: Routing Logic Team

- owns evacuation routing correctness
- owns blocked-exit handling and reroute safety
- owns per-person next-waypoint and path explainability

### Team 2: AI Edit Team

- owns directive quality and deterministic response format
- owns status clarity, person lookup responses, and path explanation output
- owns model prompt consistency across runtime and transfer files

### Team 3: AI Tech Stack + Frontend Team

- owns chat interaction UX and prompt-response usability
- owns stack integration notes (Ollama, LangChain, CrewAI, LangGraph, FastAPI, React)
- owns interactive operator flow quality in the UI panel

## Manager Execution Order (Strict)

1. Manager prepares plan and assigns scope.
2. Team 1 executes routing updates.
3. Team 2 executes AI/prompt/response updates.
4. Team 3 executes stack + frontend interaction updates.
5. Manager performs integration + verification.
6. Manager publishes final report with blocker notes.

## Blocker / Arrest Note Policy

- Blockers must be written explicitly with reason, impact, and immediate safe fallback.
- Typical blockers:
  - unresolved person lookup name
  - invalid suppression target
  - unavailable model/runtime dependency
- Every blocker entry must include one actionable next step.
