# Dataset Layout

This folder defines the expected dataset structure for fire and smoke transfer learning.

## Suggested Structure

```text
dataset/
  raw/
    fire/
    smoke/
    blocked_exit/
    crowd_risk/
    clear/
  processed/
    train/
    val/
    test/
  manifests/
    train.jsonl
    val.jsonl
    test.jsonl
```

## Label Set

Recommended labels for the first review-safe version:

- `clear`
- `fire`
- `smoke`
- `blocked_exit`
- `crowd_risk`

## Example Record

```json
{
  "image_path": "dataset/processed/train/fire/frame_000123.jpg",
  "label": "fire",
  "source": "cctv",
  "zone": "Zone Beta (Engineering)",
  "timestamp": "2026-04-07T12:00:00Z"
}
```

## Preparation Rule

Before training, each frame should be:

- resized consistently
- normalized with the same backbone transform
- split into train, validation, and test sets
- checked for label balance

## Review Note

This repository does not yet include a real labeled camera dataset.
The structure is here so the transfer-learning pipeline has a clear destination.

