# RFID Identity Guide

## Current State
Identities are mocked as `user_id` strings in JSON.

## Future Implementation (NOT IMPLEMENTED NOW)
1.  **Hardware**: UHF RFID Readers at doorways and choke points.
2.  **Database**: A secure local SQL DB mapping `TagID` -> `Name`, `Role`, `Medical_Info` (Encrypted).
3.  **Logic**:
    -   If `TagID` detected in Zone B (Fire), add "Name" to "At Risk" list.
    -   If `TagID` detected at Exit, remove from "At Risk" list.

## Lost RFID Fallback strategies
-   If a person is seen on Camera but no RFID tag is read:
    -   System flags: "UNIDENTIFIED PERSON IN DANGER".
    -   System attempts "Face Re-ID" (if enabled/legal) or tracks movement vector to estimate identity from last known RFID ping.
