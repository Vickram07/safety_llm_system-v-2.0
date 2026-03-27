# Current Implementation

## Overview
This defines the V1.0 "Laptop Simulation" state of the project.

## Components
1.  **Ollama Runtime**: Hosting the LLM locally for privacy and offline capability.
2.  **Modelfile**: Custom parameter definitions (temp=0.0) to enforce determinism.
3.  **Python Controller (`run_llm.py`)**:
    -   Validates environment.
    -   Injects `system_prompt.txt`.
    -   Parses `scenario_input.json`.
    -   Logs all decisions to `logs/`.

## Data Flow
`JSON Sensor Data` -> `Python Script` -> `Ollama API (Safety Model)` -> `Structured Decision` -> `Log File`

## Constraints
-   No live hardware connection.
-   No real-time video feed (simulated via JSON text descriptions).
-   Single-turn reasoning (no conversation memory in current script, designed for immediate state analysis).
