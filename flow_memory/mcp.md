# MCP Notes

## Session MCP Usage

Date: 2026-04-07

- Parallel sub-agent teams were used as manager-led MCP execution units for design and reliability analysis.
- Team A (Layout): geometry, map clarity, responsive structure.
- Team B (UX): logging surfaces and interactive stack compression.
- Team C (LLM): Modelfile policy and transfer-learning prompt guidance.
- Team D (Verification): command and runtime validation matrix.

## Policy

- Keep backend simulation state as source of truth.
- Use MCP/sub-agent analysis to speed design and verification, not to override runtime truth.
- Record manager decisions in `flow_memory/session.md` after each major team pass.
