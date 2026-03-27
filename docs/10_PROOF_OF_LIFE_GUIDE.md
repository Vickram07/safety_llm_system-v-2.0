# Proof of Life Guide

## Concept
Determining if a room is empty vs. containing unconscious humans.

## Future Implementation (NOT IMPLEMENTED NOW)
1.  **mmWave Radar**: Can detect breathing patterns through smoke and even thin walls.
2.  **CO2 Spikes**: Rapid increase in CO2 in a closed room indicates panic/heavy breathing.
3.  **Acoustic Triangulation**: Detecting screams, coughs, or tapping.

## Protocol
-   If `Visuals = Clear` but `mmWave = Breathing Detected`:
    -   **Status**: "INVISIBLE SURVIVOR DETECTED".
    -   **Action**: Do not seal room. Direct rescuers to specific coordinates.
