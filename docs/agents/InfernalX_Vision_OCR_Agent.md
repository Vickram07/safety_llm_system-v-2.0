# InfernalX Vision OCR Agent

## Overview
The **Vision OCR Agent** dictates the ingestion of human structural designs. Hardcoded coordinate bounds are severely limited. This agent provides a dynamic interpretation pipeline, receiving raw structural concepts (via a Base64 POST upload of a photo/sketch) and digesting it into exact collision objects for the physics engine.

## RAG Translation & Custom Mapping
Currently hooked up to models handling vision (like `Llava` or `llama3.2-vision`), this agent uses Prompt RAG memory to extract strict JSON parameters. 
- A human draws boxes on a napkin.
- The OCR identifies text ("50 People").
- The Vision model calculates spatial dimension differences corresponding to safety protocols.
- The Agent overwrites the backend Python arrays bounding `ZONES` and `EXITS`, triggering an immediate visual update in the frontend webview populated with 50 entities.

## Long-Term LLM Pipeline Value
As the system evolves from physics engine representations to absolute LLM environmental approximations, the Vision Agent ensures no physical location requires 3D surveying or architectural scans before running safety models. In any unpredictable scenario, emergency responders upload satellite footage or rapid drone photography, and the Digital Twin generates a fully navigable physics landscape natively via LLaMA integration inside of 30 seconds.
