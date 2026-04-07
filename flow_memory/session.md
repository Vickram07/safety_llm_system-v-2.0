# Session

## Current Sprint

Date: `2026-04-07`

Goal: prepare INFERNAL X for project review by rebuilding the product into a clearer one-page operator experience aligned with `ref/INFERNAL_X_Final_Done.pdf`.

## Manager Priorities

1. make the UI review-ready and map-first
2. fix people movement and evacuation pacing
3. make the assistant deterministic, faster, and more accurate
4. align the runtime story to the PDF architecture
5. scaffold the transfer-learning vision module honestly and clearly

## Current Constraints

- one-page UI only
- main map must dominate the screen
- supporting panels must shrink under the map
- chat must return correct operational facts quickly
- avoid making unsupported claims about full real deployment

## Active Agent Ownership

### Manager

- owns final integration
- owns memory, session, and plan files
- reviews all agent outputs before merge

### Frontend Worker

- owns `ui/src/App.jsx`
- owns `ui/src/App.css`

### Backend Worker

- owns `server.py`

### Vision / Transfer-Learning Worker

- owns `vision_training/`
- owns transfer-learning docs

### Verification Review Agents

- read-only review of frontend flow
- read-only review of API, prompt, and command behavior

## Review Standard

The final review build should demonstrate:

- fire map
- zone risk
- blocked exits
- suppression intent
- occupant movement
- concise operator assistant
- clear connection to sensors and PDF architecture

## Current Progress

- one-page map-first UI is active in `ui/src/App.jsx` and `ui/src/App.css`
- advanced layout tools are now moved into an overlay instead of the main review flow
- support strip under the map now contains:
  - incident log
  - selected occupant
  - autonomous assistant
- on-map hover tooltip now shows live occupant details:
  - member number
  - ID
  - role
  - status
  - HP
  - zone
  - pace
  - next waypoint
- selected/hover occupant panel now explains:
  - intent
  - next waypoint
  - route preview
- deterministic assistant answers are active in `server.py` for:
  - status report
  - critical zone
  - trapped count
  - blocked exits
  - sprinkler active state
  - suppression recommendation
- default map evacuation capacity is improved with:
  - `Exit Gamma North`
  - `Exit Theta South`
- routing now uses calmer deterministic behavior:
  - longer reroute cooldown
  - deterministic patrol stepping by role
  - committed-exit memory during evacuation
- explicit fire-clear commands can now fully extinguish target fire zones:
  - `turn off fire completely`
  - `extinguish all`
  - `put out all`
- transfer-learning scaffold is active in `vision_training/`
- review-safe transfer-learning document exists in `docs/Transfer_Learning_Vision.md`
- header and assistant were compressed further to keep the map dominant on laptop review screens
- default facility population is reduced for the review build so the map is easier to read

## Verified This Session

- `python -m py_compile server.py sensor_pipeline.py sensor_interface.py live_simulation.py vision_training\\scripts\\train_fire_smoke.py vision_training\\scripts\\infer_fire_smoke.py`
- `npm.cmd run lint`
- `npm.cmd run build`
- live API review checks for:
  - `status report`
  - `which zone is most critical?`
  - `how many occupants are trapped?`
  - `which exits are blocked?`
  - `is the sprinkler active?`
  - `should i deploy suppression now?`
- live suppression clear check:
  - `turn off fire completely in block two`
  - verified `FIRE_ZONES_AFTER=[]`
  - verified `FIRE_CELLS_AFTER=0`

## Remaining Risk

- CrewAI still logs shutdown warnings if a temporary active-fire smoke-test server is stopped immediately during review-style API tests.
- real CCTV, RFID/BLE, and sprinkler hardware are still scaffolded or simulated, not physically integrated.

## Continuation Update

Date: `2026-04-07` (late session continuation)

- enforced true single-page dashboard behavior for review mode:
  - locked viewport height and disabled page-level scroll
  - converted map/support sections to flex ratios with internal panel scroll only
  - compressed top metrics and spacing so laptop screens fit the full layout in one frame
- upgraded operator assistant panel behavior:
  - now shows recent chat history (cloud-GPT-style thread feel) instead of only latest query
  - improved frontend error reporting to surface backend failure reasons clearly
  - added quick prompt for fast low-water fire shutdown
- strengthened backend command execution and response correctness:
  - broadened deterministic intent matching for common operator phrasing
  - explicit suppression now reports before/after fire cell counts and cleared amount
  - low-water fast-clear mode now clears fire with sparse water footprint
  - added direct `/api/command` action for `deploy_suppression`
- improved continuous rerouting stability:
  - faster reroute and stuck-recalc intervals
  - invalidates committed exits as soon as they become hazardous
  - strips hazardous next-waypoint nodes mid-movement and forces immediate reroute
- bounded LLM latency in chat path with timeout protection for faster fail-safe behavior

## Manager Continuation Update (Team-Based)

Date: `2026-04-07` (manager triad execution)

### Team 1: Frontend Layout Team

- replaced the compressed stacked runtime with a side-by-side desktop layout:
  - map surface is left-dominant
  - operator/log/session stack is right-side vertical
- added layout-level auto-fit when layout revisions change:
  - map now recenters and rescales to zone/exit bounds
  - resolves the "everything shrunk" effect after resets or remaps
- increased readability in the interactive session panel:
  - larger message typography
  - larger quick action chips
  - expanded chat history viewport
- maintained one-page behavior with internal panel scrolling only

### Team 2: LLM Routing & API Reliability Team

- added explicit routing observability with metrics counters:
  - deterministic hits
  - primary LLM hits
  - fallback-model hits
  - state-fallback hits
  - timeout count
- added response validation gate for LLM replies:
  - non-directive malformed responses are blocked and replaced with safe state fallback
- added fallback model retry path using `llama3.1` when primary call times out or fails
- added suppression target validation before executing deterministic suppression actions
- introduced `GET /api/llm_health` for manager verification of model routing status

### Team 3: Verification & Integration Team

- validated compile and build after integration:
  - `npm.cmd run lint`
  - `npm.cmd run build`
  - `python -m py_compile server.py`
- restarted runtime on review port and verified live calls:
  - `GET /api/llm_health` -> `status=ok`
  - `POST /api/sensor_demo` -> `status=success`
  - `POST /api/chat` deterministic status and suppression responses verified
  - metrics confirmed deterministic route increments

### Current Manager Verdict

- layout issue root cause addressed (map no longer visually collapsed)
- interactive session is clearer and visually stronger
- LLM API reasoning path now has measurable health and safer fallback behavior
- system is in a better review-ready state for further style and autonomous-agent tuning

## Manager Continuation Update (Three-Team Geometry + Model Pass)

Date: `2026-04-07` (final compact geometry execution)

### Team 1: UI Geometry Team

- implemented exact three-column control geometry:
  - left rail split into `3/4` top command deck + `1/4` bottom incident feed
  - massive center map stage constrained as square-dominant visual core
  - right rail split into `1/4` routing log + `3/4` interactive stack
- reduced header to a minimal command bar
- removed map text clutter by replacing zone/exit labels with minimal visual markers

### Team 2: Interaction and Log Team

- tightened right-side interactive stack spacing, message density, and command input sizing
- retained only critical status context in compact cards
- kept one-page behavior while preserving internal panel scroll where needed

### Team 3: LLM and Transfer-Learning Team

- upgraded `Modelfile` with stricter deterministic parameters and directive policy
- added versioned prompt constants in `model_config.py`
- wired backend chat validation to prompt-version policy in `server.py`
- added transfer-learning system prompt blueprint:
  - `vision_training/TRANSFER_LEARNING_SYSTEM_PROMPT.md`

### Manager Note

- dedicated MCP team memory has been added in `flow_memory/mcp.md` for future multi-team continuation.
