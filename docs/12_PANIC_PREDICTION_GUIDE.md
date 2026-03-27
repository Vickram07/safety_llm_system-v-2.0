# Panic & Crowd Behavior Prediction

## Concept
People do not flow like water. They panic, stampede, and freeze.

## Modeling (Future)
-   **Social Force Model**: Simulate crowd dynamics where `F_panic > F_logic`.
-   **Real-time Adjustment**:
    -   If Camera sees "Running", switch signs to "CALM/SLOW".
    -   If Camera sees "Freezing", switch signs to "FLASHING URGENT + Voice Encouragement".

## Integration
The LLM receives a "Panic Index" (0-10) per zone.
-   **Low Panic**: Detailed voice instructions.
-   **High Panic**: Simple, repetitive, loud commands ("GO LEFT. GO LEFT.").
