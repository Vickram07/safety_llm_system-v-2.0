# Cybersecurity & Zero Trust Architecture

## The Problem
A hacked safety AI is a weapon. We must assume the network is compromised.

## Solutions (NOT IMPLEMENTED NOW)
1.  **Air-Gapped Core**: The LLM sever should have NO internet access. It communicates only via a strictly filtered internal LAN.
2.  **Cryptographically Sealed Commands**:
    -   Every command issued (e.g., "Open Door") is signed by the AI's Private Key.
    -   The Door Controller verifies the signature with the AI's Public Key before opening.
3.  **Sensor Anti-Spoofing**:
    -   Sensors must solve a cryptographic puzzle (nonce) periodically to prove they are real hardware and not a replay script.
4.  **Offline Emergency Mode**: 
    -   If the network is jammed, the system downgrades to "Local Node Logic" (distributed intelligence).
