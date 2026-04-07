# INFERNAL X Real-Time Implementation Guide

## Purpose

This guide explains how the current INFERNAL X prototype maps to a real-time production system inspired by the reference material in `ref/`.

The goal is to show how the same architecture can evolve from a simulation into a real building-safety platform with:

- AI-CCTV camera analysis
- dynamic fire suppression control
- autonomous emergency agents
- personalized evacuation guidance for each person

## Real-Time Architecture

In a real deployment, the system should run as five coordinated layers.

### 1. Sensor and Camera Ingestion Layer

This layer receives live inputs from:

- AI-CCTV camera streams
- smoke and heat sensors
- suppression system telemetry
- occupant location systems such as RFID, BLE, badge readers, or indoor positioning

Expected real-time behavior:

- camera feeds are processed continuously for smoke, flame, obstruction, crowd density, and blocked-exit detection
- sensor packets are time-stamped and fused into a shared incident state
- each occupant record is updated with live zone, movement direction, and risk level

### 2. Data Fusion and Safety State Layer

This layer converts raw inputs into a synchronized building state.

Core outputs:

- current fire origin and spread estimate
- safe and unsafe zones
- suppression candidate zones
- exit availability
- per-person risk status

In the current repository, `server.py` plays this role in simulation form by maintaining:

- `fire_cells`
- `water_cells`
- `active_fire_zones`
- live occupant states
- layout graph and routing state

## 3. Autonomous Agent Layer

This is where CrewAI, LangChain, and LangGraph fit.

Recommended role split:

- Fire Chief Agent:
  decides severity, containment strategy, and sprinkler priority
- Evacuation Agent:
  chooses safest exits and rerouting strategy
- PA / Guidance Agent:
  generates localized, human-readable instructions
- Vision / CCTV Agent:
  summarizes camera evidence and validates blocked or dangerous routes

LangGraph should orchestrate these agents in a fixed loop:

1. read current safety state
2. ask agents for structured decisions
3. merge decisions into one execution brief
4. send results to suppression, UI, and guidance systems

In the current prototype:

- `agents/crew.py` defines the role agents
- `agents/langgraph_flow.py` coordinates the reasoning flow
- `server.py` injects the resulting brief into live state

## 4. Dynamic Fire Suppression Engine

In a real-time implementation, suppression must not be zone-wide by default.

It should:

- target only the affected zone or corridor segment
- keep suppression active while heat or smoke remains above threshold
- avoid flooding safe corridors needed for evacuation
- support fallback escalation to multi-zone suppression when fire spread increases

Production execution model:

- the Fire Chief Agent proposes sprinkler targets
- a suppression controller validates hardware availability
- the building-control interface dispatches the final command
- sensor feedback confirms whether the fire is shrinking

In the current repository, this behavior is simulated through:

- targeted water deployment
- fire cell decay over time
- command interception from chat phrases such as `put off fire`, `extinguish fire`, `turn off fire`, and similar variants

## 5. Personalized Evacuation Guidance

This is the most important real-time layer.

Each person should receive guidance based on:

- current position
- nearby fire and smoke
- crowd density
- blocked routes
- mobility or accessibility needs

Expected behavior:

- each occupant has a current safe path
- the path is recalculated when fire spreads or exits become unsafe
- guidance can be shown on operator dashboards, mobile apps, corridor displays, and PA systems

In the current prototype:

- each simulated person carries a route
- the route is recalculated against hazards
- the UI highlights routes and statuses
- the assistant can answer status questions about target areas

## Command Handling in Real Time

The operator assistant should support two command classes.

### Suppression Commands

Examples:

- `put off fire`
- `turn off fire with sprinkler`
- `extinguish fire`
- `activate sprinklers in block one`

Expected flow:

1. classify command as suppression intent
2. resolve the target area using zone or block aliases
3. deploy suppression to the requested or currently active fire zones
4. return a structured directive and log the action

### Status Commands

Examples:

- `status of block one`
- `what is happening in block two`
- `report on zone alpha`

Expected flow:

1. resolve area aliases
2. inspect live zone state
3. summarize occupants, trapped count, panic count, and fire status
4. return a concise directive with live values

## How to Move This Prototype into Production

Use this order:

1. Replace simulated occupant state with real badge or indoor-position feeds.
2. Replace mock or normalized layout inputs with validated facility CAD or digital twin imports.
3. Add AI-CCTV stream processing for flame, smoke, blockage, and crowd signals.
4. Connect suppression outputs to a real building control or PLC layer.
5. Route all agent outputs through a safety policy layer before hardware execution.
6. Add audit logging, replay, and operator approval rules for high-risk commands.

## Recommended Safety Rule

The LLM should never directly actuate hardware without an execution guard.

Safe real-time flow:

- sensors and cameras create evidence
- agents propose decisions
- policy and control layer validates decisions
- hardware interface executes only approved commands

## Current Repository Mapping

Use these files as the current implementation base:

- `server.py`
- `agents/crew.py`
- `agents/langgraph_flow.py`
- `agents/layout_manager.py`
- `ui/src/App.jsx`

## Positioning Statement

Use this wording for the current stage:

`INFERNAL X is a real-time simulation prototype for LLM-assisted fire monitoring, dynamic suppression, and occupant evacuation orchestration, designed to evolve into a production system integrating AI-CCTV, live building telemetry, and autonomous safety agents.`
