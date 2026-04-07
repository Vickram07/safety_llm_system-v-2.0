# InfernalX LangGraph & LangChain Architecture

## Overview
The sheer logic weight of having three distinct LLM models (FireChief, EvacuationOfficer, PA_Announcer) predicting routes in real-time threatens to completely halt graphical 60fps applications.

The **InfernalX** engine implements **LangGraph** (a state-machine wrapper over LangChain) to definitively prevent hallucination loops, ensure ordered logic flow, and execute asynchronous deliberation completely untethered from the graphical webview cycle.

---

## 🏗️ 1. Why LangChain?
LangChain provides the `AgentExecutor` environment bridging the raw `Ollama` models to contextual logic. 
- It allows custom prompts to be rigidly encoded into each model structure (so the EvacuationOfficer never hallucinates becoming a firefighter, and instead sticks strictly to routing outputs).
- The models utilize standard chains (`PromptTemplate | LLM | StrOutputParser()`) which provide cleanly filtered JSON and textual structures for the backend arrays to interpret.

## 🔄 2. Why LangGraph?
If you ask the CrewAI models to talk to each other simultaneously, they can get stuck in debate loops or talk out of order. **LangGraph** creates a directed acyclic graph (DAG) workflow:
1. `add_node("Evaluate_Fire")` -> FireChief processes.
2. `add_node("Route_Civilians")` -> EvacuationOfficer runs *only after* receiving state from the FireChief.
3. `add_node("Broadcast_Alert")` -> The PA Agent speaks *only after* routes are locked.

### The Asynchronous Loop
To ensure 0% impact on the actual A* Pathfinding Physics taking place on the frontend UI, this entire `.invoke(state)` process is launched inside a localized `asyncio` event loop running exclusively on a background thread in Python (`target=crewai_callback`).

## 🚀 The Future of the LLM Architecture
In future builds, the **LangGraph state** will dictate not only logic but raw positioning. The entire A* collision dictionary will be parsed and injected into the graph state every second. LangGraph will coordinate custom "Movement Agents" translating RAG boundaries directly into localized XY jumps for each of the 50 simulated occupants explicitly utilizing LLM predictive intelligence.
