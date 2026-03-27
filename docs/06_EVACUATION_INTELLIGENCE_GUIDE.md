# Evacuation Intelligence Guide

## The "Life-First" Loop
This module is the calculate core of evacuation routing.

## Current State
The LLM suggests a generic "Evacuate via Stairwell B" based on the static prompt.

## Future Implementation (NOT IMPLEMENTED NOW)
1.  **Graph Mapping**: Represent the building as a NetworkX graph (Nodes = Rooms, Edges = Doors).
2.  **Dynamic Weighting**:
    -   Normal Edge Weight: 1.0
    -   Fire Edge Weight: 1000.0 (Impassable)
    -   Smoke Edge Weight: 50.0 (Avoid)
3.  **Conflict-Free Routing**:
    -   If 50 people are in Zone A, and 10 in Zone B, do not route them to collide in a narrow Hallway C.
    -   LLM acts as a "Traffic Controller", distributing load across available exits.

## Panic Prediction
-   Use agent-based simulation (e.g., tiny simulated agents) to predict bottlenecks before they happen, and route real humans away from them.
