# Blockchain Audit Guide (Immutable Event Ledger)

## Purpose
In the aftermath of a disaster, "Who decided to lock that door?" is a legal question. We need an incorruptible black box.

## Future Implementation (NOT IMPLEMENTED NOW)
1.  **Private Chain**: A lightweight internal blockchain (e.g., Hyperledger Fabric or a simpler Merkle Tree log).
2.  **Data Blocks**:
    -   Timestamp
    -   Sensor State Hash
    -   LLM Reasoning Hash
    -   Action Taken
3.  **Write-Once**: Once written, the log cannot be altered by admins, the AI, or hackers.
4.  **Legal Discovery**: This ledger serves as the primary evidence for post-incident investigations.
