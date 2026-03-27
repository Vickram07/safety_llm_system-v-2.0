# AI CCTV Integration Guide

## Current State
Visual data is text-based ("Visual obscuration detected") in the JSON file.

## Future Implementation (NOT IMPLEMENTED NOW)
1.  **Vision Model**: Deploy `YOLOv8` or `Llama-3.2-Vision` locally.
2.  **Pipeline**:
    -   RTSP Stream from IP Cameras.
    -   Frame extraction (1 FPS).
    -   Object Detection (Person, Fire, Smoke, Weapon).
3.  **Textualization**: The vision model output must be converted to text:
    -   *Raw*: `{"class": "person", "conf": 0.9, "bbox": [...]}`
    -   *LLM Input*: `"Camera 05 sees 1 person standing in smoke."`

## Anti-Spoofing
-   Analyze pixel noise patterns to detect loop-playing (replay attacks).
-   Cross-reference with PIR motion sensors. If Camera sees movement but PIR does not, declare "GHOST/HACK ANOMALY".
