# Implementation Plan

## Objective

Rebuild the current prototype into a review-ready INFERNAL X demo aligned with the final PDF concept while staying truthful to the implemented code.

## Workstreams

### 1. Frontend Redesign

Target:

- one-page map-first interface
- remove oversized side panels and raw layout clutter
- move compact assistant, log, and occupant detail below the map

Files:

- `ui/src/App.jsx`
- `ui/src/App.css`

### 2. Backend Simulation Logic

Target:

- improve occupant pacing
- reduce route jitter
- improve trapped behavior
- improve deterministic status and suppression answers

Files:

- `server.py`

### 3. LLM / Transfer-Learning Track

Target:

- keep current `infernalx` model for reasoning
- scaffold a transfer-learning pipeline for fire/smoke vision
- provide review-safe documentation for how a trained perception layer fits the system

Files:

- `vision_training/`
- `docs/Transfer_Learning_Vision.md`

### 4. Review and Verification

Target:

- inspect frontend clarity
- inspect command correctness
- inspect prompt/result quality
- report issues back to manager

Outputs:

- review notes
- test findings
- integration risks

## Execution Order

1. manager creates memory and plan
2. agents run in parallel on disjoint ownership
3. manager reviews outputs
4. manager integrates and verifies
5. manager reports what is done, what is review-ready, and what remains roadmap

## Current Status

- frontend redesign: completed for review build
- backend deterministic assistant and pacing pass: completed for review build
- transfer-learning scaffold: completed
- review and verification pass: completed
