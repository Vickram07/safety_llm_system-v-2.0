# InfernalX FireChief Agent

## Overview
The **FireChief Agent** is the macro-strategist of the InfernalX Multi-Agent safety swarm. Powered by CrewAI, this specific intelligence model is isolated solely to measure, evaluate, and predict the physical spread of thermal anomalies inside the Digital Twin, completely ignoring moving personnel to maintain deep focus on hazard dynamics.

## LangChain Integration
This agent utilizes the LangChain `AgentExecutor` logic wrapper to process high-dimensional spatial dictionary data (e.g., arrays of burning X/Y coordinates). It is restricted from using tools that require real-time latency (like polling every user) and instead reads the cached global variables updated by the A* simulation engine. By feeding it through an Ollama LangChain endpoint, it returns specific string classifications determining the Threat Level (`CRITICAL`, `CONTAINED`, `GROWING`).

## Future LLM Impact & RAG Transitions
Currently, the `FireChiefAgent` responds based on the visual blocks turning red inside the simulation. 

As we transition into a pure LLM-predicted engine, the `FireChief` will natively interface with RAG databases containing absolute material heat-indexes. It will know that a fire in the "Wood Shop" spreads at a completely different metric compared to the "Concrete Hallway." It will no longer rely on the static simulation loop to tell it how many grids are burning; it will *predict* them contextually and generate the fire grids itself to act as the primary physics engine.
