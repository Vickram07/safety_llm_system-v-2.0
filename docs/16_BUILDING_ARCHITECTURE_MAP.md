# Building Architecture & Floor Plan (Headquarters HQ-01)

## Overview
This document defines the physical layout of the building used in the simulation. The AI uses this mental model to calculate evacuation routes.

## Floor Plan: Level 1 (Ground Floor)

```text
+---------------------------------------------------------------+
|                        [ NORTH EXIT ]                         |
|                               |                               |
|   +-------------------+       |       +-------------------+   |
|   |                   |       |       |                   |   |
|   |     ZONE A1       |-------+-------|     ZONE A2       |   |
|   |  (Lobby / Rec)    |   HALLWAY A   |   (Cafeteria)     |   |
|   |                   |       |       |                   |   |
|   +--------+----------+       |       +---------+---------+   |
|            |                  |                 |             |
|            |                  |                 |             |
|   +--------+----------+       |       +---------+---------+   |
|   |                   |       |       |                   |   |
|   |     ZONE B1       |-------+-------|     MAX DANGER    |   |
|   |   (Server Room)   |   HALLWAY B   |     ZONE B2       |   |
|   |                   |       |       |   (Chemical Lab)  |   |
|   +-------------------+       |       +---------+---------+   |
|                               |                 |             |
|                        [ SOUTH EXIT ]      [ STAIRWELL B ]    |
+---------------------------------------------------------------+
```

## Zones & Sensors

| Zone | Description | Sensors | Camera ID | Status (Current) |
| :--- | :--- | :--- | :--- | :--- |
| **Zone A1** | Main Lobby. Safe gathering point. | Temp, Occ | Cam_01 | **SAFE** (User is here) |
| **Zone A2** | Cafeteria. Kitchen hazards. | Smoke, Heat | Cam_02 | **SAFE** |
| **Hallway A**| Connects North Exit to Zones. | Motion | Cam_03 | **SAFE** |
| **Zone B1** | Server Room. Fire suppression fitted. | Term, Smoke | Cam_04 | **SAFE** |
| **Zone B2** | **Chemical Lab**. High risk area. | Multi-Sensor| Cam_05 | **FIRE DETECTED** |
| **Hallway B**| Connects South Exit to Zones. | Motion | Cam_06 | **SMOKE DETECTED** |

## Evacuation Logic for This Scenario

1.  **The Threat**: Fire in **Zone B2** (South-East).
2.  **The Spread**: Smoke is filling **Hallway B**, blocking the **South Exit**.
3.  **The User**: Located in **Zone A1** (North-West).
4.  **The Path**:
    *   User cannot go South (Blocked by smoke in Hallway B).
    *   User must go East into **Hallway A**.
    *   User must exit via **North Exit**.

## AI Verification
When you run the simulation, check if the AI suggests:
> "Evacuate via **North Exit**."

If the AI suggests "South Exit", it is **WRONG** because that path leads through the fire zone.
