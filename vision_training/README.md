# Vision Transfer Learning Track

This folder is a review-safe scaffold for the future fire and smoke vision module described in the INFERNAL X project PDF.

It does not claim a trained perception model yet. Instead, it defines:

- dataset structure
- transfer-learning config
- training script skeleton
- inference script skeleton
- export contract for plugging into the sensor fusion pipeline

## Current Goal

Fine-tune a lightweight image classifier or detector so camera frames can produce structured signals such as:

- fire present
- smoke present
- blocked exit
- crowd density risk
- clear frame

## Recommended Model Path

For a review-ready presentation, the safest path is:

1. start with a pretrained backbone such as `ResNet50` or `MobileNetV2`
2. fine-tune it on labeled fire / smoke / blockage frames
3. export a compact inference wrapper that returns JSON-friendly outputs
4. plug those outputs into `sensor_pipeline.py`

## Folder Map

- `dataset/` - dataset layout and sample manifests
- `configs/` - training and experiment settings
- `scripts/` - training and inference skeletons
- `artifacts/` - placeholder for checkpoints and exports

## Honest Status

This track is not trained yet.
It is the implementation bridge for a future fine-tuned vision model.

