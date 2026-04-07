# InfernalX Evacuation Officer Agent

## Overview
The **Evacuation Officer Agent** is the tactical micro-router of the InfernalX Swarm. Where the FireChief cares only about the flames, the Evacuation Officer exclusively processes the exact position, health, and psychological status (e.g., `PANIC`, `IDLE`) of the 50 occupants scattered throughout the environment.

## LangChain Context Interpretation
It relies on the execution pipeline of LangGraph to never execute *before* the FireChief. The LangGraph cyclic state ensures that the `Evacuation Officer` only receives prompt context containing the FireChief's latest thermal classification. Using that, it mathematically infers the safest directional exit without suffering hallucinations. 

## Future LLM Impact & Psychological RAG
In the near future, the rigid A* pathfinding algorithms governing the occupants will be removed entirely. 

The Evacuation Officer will be equipped with **Agentic RAG Personas**. Every spawned occupant will possess a virtual token identity. The Evacuation Officer will query contextual instructions differently for a 65-year-old manager experiencing panic compared to a 20-year-old security guard. It will assign routes based on *human capacity and capability* rather than raw proximity logic—evolving from a simple router into an intelligent emergency triage commander.
