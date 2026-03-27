# System Overview: God-Level Safety-Bounded LLM

## Philosophy
This project implements a **zero-trust, safety-critical AI architecture** designed to protect human life in high-risk infrastructure environments. Unlike standard chatbots, this system acts as a **hyper-vigilant central nervous system**, aggregating sensor data, validating threats via multi-source logic, and issuing deterministic, timestamped advisory commands.

## Core Directives
1.  **Life First**: Evacuation and protection of humans supersede all asset protection.
2.  **Zero Trust**: No single sensor is trusted; multiple verifications are required.
3.  **Advisory Authority**: The AI advises human operators but prepares for future autonomous actuation (sprinklers, locks).

## Architecture at a Glance
-   **Input Layer**: MQTT/HTTP sensor aggregator (Simulated JSON for now).
-   **Cognitive Layer**: `llama3.1` with a rigid, safety-locked system prompt (Modelfile defined).
-   **Output Layer**: Structured advisory logs, ready for TTS or screen display.

## Future Scope (20-Point Roadmap)
The system is designed to scale to include:
-   RFID Identity tracking.
-   Biometric health monitoring.
-   Blockchain auditing for post-incident legal review.
-   Moral Pause Protocols for ethical dilemmas.

## Current Status
-   **Running on**: Local Laptop (Ollama).
-   **Input**: `scenario_input.json`.
-   **Logic**: `run_llm.py` + Custom Modelfile.
