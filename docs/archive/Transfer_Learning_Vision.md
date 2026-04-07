# Transfer Learning Vision Track

## Purpose

This document explains how the PDF's camera-based fire detection idea maps to the current repository in a review-safe way.

## What This Track Is

This is the scaffold for a future fine-tuned vision module that will process CCTV frames and emit structured signals for the sensor fusion pipeline.

It is intended to support:

- fire detection
- smoke detection
- blocked-exit detection
- crowd-risk estimation
- verified visual confirmation for the assistant and dashboard

## What Is Implemented Now

The repository now includes a dedicated folder:

- `vision_training/`

Inside it you will find:

- a dataset layout
- a training config
- a training script skeleton
- an inference script skeleton
- the expected output contract for the sensor pipeline

## Review-Safe Transfer Learning Approach

The safest presentation strategy for tomorrow is:

1. use a pretrained backbone such as `ResNet50`
2. fine-tune it on labeled fire / smoke / blockage frames
3. export lightweight inference outputs
4. feed those outputs into `sensor_pipeline.py`

## Data Pipeline

1. CCTV frame arrives from camera stream
2. frame is resized and normalized
3. backbone predicts fire, smoke, blockage, and crowd risk
4. inference wrapper formats JSON output
5. `sensor_pipeline.py` converts it into zone-level risk
6. `server.py` uses that risk to update simulation, chat, and summary outputs

## Output Contract

The vision module should emit a structure that can be fused with the rest of the system:

```json
{
  "camera_id": "cam-beta-01",
  "zone": "Zone Beta (Engineering)",
  "flame_score": 0.92,
  "smoke_score": 0.87,
  "blockage_score": 0.32,
  "person_count": 6,
  "verified_fire": true,
  "confidence": 0.96,
  "notes": "Visible flame near engineering workstation cluster."
}
```

## Honest Status

This track is not trained yet.
The current files are scaffolding for a later real transfer-learning implementation.

## How It Fits The Current Project

The intended integration point is the ordered sensor pipeline:

- camera outputs become one input stream
- environmental sensors form another stream
- RFID/BLE occupant updates form another stream
- the fusion engine combines them into zone state
- the simulation and chat layers read the fused result

This keeps the project aligned with the PDF while staying honest about what is finished today.

