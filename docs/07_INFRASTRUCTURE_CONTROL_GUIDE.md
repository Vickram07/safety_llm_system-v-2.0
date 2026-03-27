# Infrastructure Control Guide

## Concept
The LLM acts as the brain; this module acts as the hands.

## Current State
Advisory text only ("Recommend closing gas valve").

## Future Implementation (NOT IMPLEMENTED NOW)
1.  **BACnet/Modbus Gateway**: Interface with building automation systems.
2.  **Actuation Logic**:
    -   **Gas Lines**: Cut immediately on confirmed fire.
    -   **Elevators**: Ground immediately; disable for non-firefighters.
    -   **HVAC**: Switch to positive pressure in stairwells (keep smoke out) and negative pressure in fire zones.
3.  **Smart Sprinklers (Rail-Based)**:
    -   Instead of flooding a whole floor, motorized heads target the specific heat signature identified by the Thermal Camera.
    -   LLM directs the nozzle: "Aim coordinates X:50, Y:12."

## Safety Lock
-   Hardware kill-switch: A human must be able to override the AI's "Lockdown" command physically.
