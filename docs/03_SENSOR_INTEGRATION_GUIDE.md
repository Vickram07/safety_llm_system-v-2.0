# Sensor Integration Guide

## Current State
Sensors are simulated via `scenario_input.json`.

## Future Implementation (NOT IMPLEMENTED NOW)
To connect real sensors:
1.  **Hardware Layer**: deploy ESP32 or PLC modules for Smoke, Heat, CO2.
2.  **Transport Layer**: Use MQTT (e.g., Mosquitto Broker) to publish readings to `building/sensors/#`.
3.  **Ingestion Layer**: A structured Python script (`sensors.py`) will subscribe to MQTT topics and update the `scenario_input.json` (or in-memory dict) in real-time (~1Hz).

## Zero-Trust Protocol
-   **Heartbeat**: Every sensor must send a pulse every 5 seconds. Missing pulse = "SENSOR FAILURE" (not silence).
-   **Anti-Spoofing**: Sign packets with a rolling hash key to prevent injection attacks.
