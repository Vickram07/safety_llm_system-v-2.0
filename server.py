import asyncio
import copy
import os
import json
import math
import heapq
import re
import time
import requests
import random
import threading
import subprocess
import logging
from typing import Dict, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from model_config import (
    MODEL_NAME,
    FALLBACK_MODEL_NAME,
    OLLAMA_BASE_URL,
    OLLAMA_GENERATE_URL,
    VISION_MODEL_NAME,
    CHAT_PROMPT_VERSION,
    INFERNALX_SYSTEM_DIRECTIVE,
    VALID_DIRECTIVE_PREFIXES,
)
from agents.layout_manager import build_navigation_graph, normalize_rect
from sensor_pipeline import SensorFusionEngine, normalize_sensor_payload

# ==========================================
# CONFIGURATION
# ==========================================
GRID_SIZE = 10
OLLAMA_URL = OLLAMA_GENERATE_URL
DEFAULT_ROAM_SPEED = 1.6
EVACUATING_SPEED = 2.15
PANIC_SPEED = 2.9
TRAPPED_SPEED = 1.45
WAYPOINT_EPSILON = 10.0
VELOCITY_BLEND = 0.35
ARRIVAL_SLOW_RADIUS = 42.0
ROUTE_RECALC_INTERVAL = 1.0
STUCK_RECALC_INTERVAL = 2.0
FIRE_REPULSION_RADIUS = 55.0
FIRE_REPULSION_WEIGHT = 2.2
TRAPPED_REPULSION_WEIGHT = 3.2
MAX_FIRE_SAMPLES = 12
MAX_FIRE_CELLS = 2200
CHAT_LLM_TIMEOUT_SECONDS = 18.0  # phi3:mini responds in ~5-12s; cap at 18s so UI is never blocked
MAX_GLOBAL_EVENTS = 50
MAX_PA_ANNOUNCEMENTS = 5
STATE_REFRESH_HZ = 30
WEBSOCKET_REFRESH_HZ = 15
MIN_ACTIVE_OCCUPANTS = 40
PATROL_STEP_BY_ROLE = {
    "Security Assistant": 3,
    "Janitor": 2,
    "Product Manager": 1,
    "Software Engineer": 1,
    "Analyst": 1,
    "HR Coordinator": 1,
}

ROLE_SPEED_FACTORS = {
    "Security Assistant": 1.12,
    "Janitor": 1.0,
    "Product Manager": 0.96,
    "Software Engineer": 1.0,
    "Analyst": 0.98,
    "HR Coordinator": 0.92,
}

# LangChain Setup Integration for future Hugging Face Scaling
from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from agents.langgraph_flow import run_langgraph_cycle
from agents.crew import get_manager_team_workflow_summary

llm_chain = OllamaLLM(
    model=MODEL_NAME,
    base_url=OLLAMA_BASE_URL,
    temperature=0.3,
    num_predict=80,
    num_ctx=1024,
)
fallback_llm_chain = OllamaLLM(
    model=FALLBACK_MODEL_NAME,
    base_url=OLLAMA_BASE_URL,
    temperature=0.3,
    num_predict=80,
    num_ctx=1024,
)
logger = logging.getLogger("infernalx.chat")

LLM_ROUTING_METRICS = {
    "deterministic_hits": 0,
    "llm_primary_hits": 0,
    "llm_fallback_hits": 0,
    "fallback_state_hits": 0,
    "timeouts": 0,
    "last_primary_latency_ms": 0.0,
    "last_fallback_latency_ms": 0.0,
    "last_route": "none",
    "last_error": "",
}
LLM_METRICS_LOCK = threading.Lock()


def update_llm_metrics(route: str, *, latency_ms: float = 0.0, error: str = "", timeout: bool = False):
    with LLM_METRICS_LOCK:
        LLM_ROUTING_METRICS["last_route"] = route
        if error:
            LLM_ROUTING_METRICS["last_error"] = error[:220]
        if timeout:
            LLM_ROUTING_METRICS["timeouts"] += 1
        if route == "deterministic":
            LLM_ROUTING_METRICS["deterministic_hits"] += 1
        elif route == "llm_primary":
            LLM_ROUTING_METRICS["llm_primary_hits"] += 1
            LLM_ROUTING_METRICS["last_primary_latency_ms"] = round(latency_ms, 2)
        elif route == "llm_fallback":
            LLM_ROUTING_METRICS["llm_fallback_hits"] += 1
            LLM_ROUTING_METRICS["last_fallback_latency_ms"] = round(latency_ms, 2)
        elif route == "state_fallback":
            LLM_ROUTING_METRICS["fallback_state_hits"] += 1


def is_valid_directive_response(text: str, prompt_version: str = "2.1") -> bool:
    return True

DEFAULT_ZONES = {
    "Zone Alpha (Executive)":   {"x":100, "y":50,  "w":250, "h":200},
    "Zone Beta (Engineering)":  {"x":350, "y":50,  "w":300, "h":200},
    "Zone Gamma (Datacenter)":  {"x":650, "y":50,  "w":250, "h":200},
    "Zone Delta (Operations)":  {"x":900, "y":50,  "w":300, "h":200},
    "Zone Epsilon (Logistics)": {"x":1200,"y":50,  "w":250, "h":200},
    "West Corridor":            {"x":100, "y":250, "w":550, "h":150},
    "Central Hub":              {"x":650, "y":250, "w":250, "h":150},
    "East Corridor":            {"x":900, "y":250, "w":550, "h":150},
    "Zone Zeta (Lobby)":        {"x":100, "y":400, "w":250, "h":200},
    "Zone Eta (R&D)":           {"x":350, "y":400, "w":300, "h":200},
    "Zone Theta (Cafeteria)":   {"x":650, "y":400, "w":250, "h":200},
    "Zone Iota (Medical)":      {"x":900, "y":400, "w":300, "h":200},
    "Zone Kappa (Security)":    {"x":1200,"y":400, "w":250, "h":200}
}

DEFAULT_EXITS = {
    "Exit Alpha North":   {"x":200,  "y":0,   "w":50, "h":50},
    "Exit Beta North":    {"x":475,  "y":0,   "w":50, "h":50},
    "Exit Gamma North":   {"x":775,  "y":0,   "w":50, "h":50},
    "Exit Delta North":   {"x":1025, "y":0,   "w":50, "h":50},
    "Exit Epsilon North": {"x":1300, "y":0,   "w":50, "h":50},
    "Exit Zeta South":    {"x":200,  "y":600, "w":50, "h":50},
    "Exit Eta South":     {"x":475,  "y":600, "w":50, "h":50},
    "Exit Theta South":   {"x":775,  "y":600, "w":50, "h":50},
    "Exit Iota South":    {"x":1025, "y":600, "w":50, "h":50},
    "Exit Kappa South":   {"x":1300, "y":600, "w":50, "h":50},
    "Exit West Hub":      {"x":50,   "y":300, "w":50, "h":50},
    "Exit East Hub":      {"x":1450, "y":300, "w":50, "h":50}
}

def clone_rect_map(rect_map: Dict[str, Dict[str, float]]) -> Dict[str, Dict[str, float]]:
    return {name: rect.copy() for name, rect in rect_map.items()}

ZONES = clone_rect_map(DEFAULT_ZONES)
EXITS = clone_rect_map(DEFAULT_EXITS)

def restore_default_layout() -> None:
    ZONES.clear()
    ZONES.update(clone_rect_map(DEFAULT_ZONES))
    EXITS.clear()
    EXITS.update(clone_rect_map(DEFAULT_EXITS))

def normalize_layout_map(layout_map: Dict[str, Dict[str, float]]) -> Dict[str, Dict[str, float]]:
    normalized: Dict[str, Dict[str, float]] = {}
    for name, rect in layout_map.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Layout names must be non-empty strings.")
        if not isinstance(rect, dict):
            raise ValueError(f"Layout item '{name}' must be a mapping with x, y, w, h.")
        try:
            x = float(rect["x"])
            y = float(rect["y"])
            w = float(rect["w"])
            h = float(rect["h"])
        except Exception as exc:
            raise ValueError(f"Layout item '{name}' is missing numeric x, y, w, h values.") from exc
        if w <= 0 or h <= 0:
            raise ValueError(f"Layout item '{name}' must have positive width and height.")
        normalized[name] = {"x": x, "y": y, "w": w, "h": h}
    return normalized

ADJACENCY = {
    "Zone Alpha (Executive)":   ["Exit Alpha North", "West Corridor"],
    "Zone Beta (Engineering)":  ["Exit Beta North", "West Corridor", "Zone Gamma (Datacenter)"],
    "Zone Gamma (Datacenter)":  ["Exit Gamma North", "Central Hub", "Zone Beta (Engineering)", "Zone Delta (Operations)"],
    "Zone Delta (Operations)":  ["Exit Delta North", "East Corridor", "Zone Epsilon (Logistics)", "Zone Gamma (Datacenter)"],
    "Zone Epsilon (Logistics)": ["Exit Epsilon North", "East Corridor", "Zone Delta (Operations)"],
    "West Corridor":            ["Exit West Hub", "Zone Alpha (Executive)", "Zone Beta (Engineering)", "Zone Zeta (Lobby)", "Zone Eta (R&D)", "Central Hub"],
    "Central Hub":              ["West Corridor", "East Corridor", "Zone Gamma (Datacenter)", "Zone Theta (Cafeteria)"],
    "East Corridor":            ["Exit East Hub", "Zone Delta (Operations)", "Zone Epsilon (Logistics)", "Zone Iota (Medical)", "Zone Kappa (Security)", "Central Hub"],
    "Zone Zeta (Lobby)":        ["Exit Zeta South", "West Corridor", "Zone Eta (R&D)"],
    "Zone Eta (R&D)":           ["Exit Eta South", "West Corridor", "Zone Zeta (Lobby)", "Zone Theta (Cafeteria)"],
    "Zone Theta (Cafeteria)":   ["Exit Theta South", "Central Hub", "Zone Eta (R&D)", "Zone Iota (Medical)"],
    "Zone Iota (Medical)":      ["Exit Iota South", "East Corridor", "Zone Theta (Cafeteria)", "Zone Kappa (Security)"],
    "Zone Kappa (Security)":    ["Exit Kappa South", "East Corridor", "Zone Iota (Medical)"],
    "Exit Alpha North":         ["Zone Alpha (Executive)"],
    "Exit Beta North":          ["Zone Beta (Engineering)"],
    "Exit Gamma North":         ["Zone Gamma (Datacenter)"],
    "Exit Delta North":         ["Zone Delta (Operations)"],
    "Exit Epsilon North":       ["Zone Epsilon (Logistics)"],
    "Exit Zeta South":          ["Zone Zeta (Lobby)"],
    "Exit Eta South":           ["Zone Eta (R&D)"],
    "Exit Theta South":         ["Zone Theta (Cafeteria)"],
    "Exit Iota South":          ["Zone Iota (Medical)"],
    "Exit Kappa South":         ["Zone Kappa (Security)"],
    "Exit West Hub":            ["West Corridor"],
    "Exit East Hub":            ["East Corridor"]
}

BASE_ZONES = copy.deepcopy(ZONES)
BASE_EXITS = copy.deepcopy(EXITS)
BASE_ADJACENCY = copy.deepcopy(ADJACENCY)

def rect_contains(rect, pt_x, pt_y):
    return rect["x"] <= pt_x <= rect["x"] + rect["w"] and rect["y"] <= pt_y <= rect["y"] + rect["h"]

def rect_intersects(r1, r2):
    return not (r2["x"] >= r1["x"] + r1["w"] or 
                r2["x"] + r2["w"] <= r1["x"] or 
                r2["y"] >= r1["y"] + r1["h"] or
                r2["y"] + r2["h"] <= r1["y"])

def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))

def get_door_pos(z1_name, z2_name):
    # Returns the physical coordinate (x, y) of the doorway between two overlapping zones
    all_rects = {**ZONES, **EXITS}
    if z1_name not in all_rects or z2_name not in all_rects:
        return None
    r1, r2 = all_rects[z1_name], all_rects[z2_name]
    
    # Calculate intersection rectangle
    x1 = max(r1["x"], r2["x"])
    y1 = max(r1["y"], r2["y"])
    x2 = min(r1["x"] + r1["w"], r2["x"] + r2["w"])
    y2 = min(r1["y"] + r1["h"], r2["y"] + r2["h"])
    
    if x1 <= x2 and y1 <= y2:
        return (x1 + x2) / 2.0, (y1 + y2) / 2.0
    return None

class Person:
    def __init__(self, pid, name, role_type, x, y):
        seed = sum(ord(ch) for ch in str(pid))
        self.id = pid
        self.name = name
        self.role = role_type
        self.x = x
        self.y = y
        self.base_x = x
        self.base_y = y
        self.hp = 100.0
        self.status = "IDLE"
        self.path = []
        self.speed = DEFAULT_ROAM_SPEED
        self.target_speed = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.last_pa_time = 0
        self.next_roam_time = time.time() + 6 + (seed % 10)
        self.last_pos = (x, y)
        self.stuck_count = 0
        self.last_route_recalc = 0.0
        self.zone = ""
        self.committed_exit = ""

class SimulationEngine:
    def __init__(self):
        self.people = []
        self.fire_cells = set()
        self.water_cells = set()
        self.start_time = time.time()
        self.running = True
        self.lock = threading.RLock()
        self.active_fire_zones = []
        self.pa_announcements = []
        self.global_events = []
        self.scenario = "DEFAULT"
        self.layout_name = "Default Layout"
        self.layout_source = "default"
        self.layout_revision = 0
        self.navigation_graph = copy.deepcopy(ADJACENCY)
        self.last_crew_status = "UNKNOWN"
        self.last_crew_sprinklers = "NONE"
        self.last_crew_exit = "NONE"
        self.last_crew_pa = ""
        self.last_crew_update = 0.0
        self.recent_logs = {}
        self.last_global_pa_time = 0.0  # System-wide PA throttle
        self.last_crewai_run = 0.0      # Limit heavy multi-agent orchestration
        self.suppression_mode = False
        self.sitrep = "FACILITY SECURE. INFERNALX STANDBY."
        self.layout_name = "Default Layout"
        self.layout_version = 1
        self.layout_source = "default"
        self.blocked_exits = set()
        self.last_sensor_summary = {
            "highest_risk_zone": "NONE",
            "highest_probability": 0.0,
            "active_fire_zones": [],
            "blocked_exits": [],
            "occupants_tracked": 0,
            "packet_source": "none",
        }
        self.sensor_tracked_people = {}
        # --- Autonomous Mode: AI-controlled auto-suppression ---
        self.autonomous_mode = False          # Toggle: when True, auto-suppress fire
        self.last_auto_suppress_time = 0.0   # Throttle: at most once every 3 s
        self.auto_suppress_log = []          # Recent autonomous actions

    def log_event(self, msg):
        with self.lock:
            # Debounce spam: Ignore exact same message strings if fired < 5 seconds apart.
            # E.g. 50 people saying "Facility Online"
            now = time.time()
            base_msg = msg.split(":")[0] if "trapped" in msg else msg # generic deduplication heuristic
            
            if base_msg in self.recent_logs and (now - self.recent_logs[base_msg]) < 5.0:
                return
                
            self.recent_logs[base_msg] = now
            timestamp = time.strftime("[%H:%M:%S]")
            self.global_events.append(f"{timestamp} AI OVERSEER: {msg}")
            
            # Keep array clean
            if len(self.global_events) > 50:
                self.global_events.pop(0)

    def log_incident(self, message):
        """Hidden logging system for official crisis review."""
        timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
        try:
            with open("incident_report.log", "a") as f:
                f.write(f"{timestamp} {message}\n")
        except Exception as e:
            print(f"Failed to log incident: {e}")

    def get_nearest_fire_cells(self, x: float, y: float, limit: int = MAX_FIRE_SAMPLES):
        if not self.fire_cells:
            return []
        return heapq.nsmallest(
            limit,
            self.fire_cells,
            key=lambda cell: math.hypot(x - (cell[0] * GRID_SIZE + GRID_SIZE / 2), y - (cell[1] * GRID_SIZE + GRID_SIZE / 2))
        )

    def steer_person(self, person: Person, target_x: float, target_y: float, move_speed: float, repel_x: float = 0.0, repel_y: float = 0.0):
        dx = target_x - person.x
        dy = target_y - person.y
        dist = math.hypot(dx, dy)
        if dist <= 0.001:
            person.vx *= 0.4
            person.vy *= 0.4
            return dist

        dx /= dist
        dy /= dist
        dx += repel_x
        dy += repel_y

        mag = math.hypot(dx, dy)
        if mag > 0:
            dx /= mag
            dy /= mag

        slow_factor = clamp(dist / ARRIVAL_SLOW_RADIUS, 0.4, 1.0) if dist < ARRIVAL_SLOW_RADIUS else 1.0
        effective_speed = max(move_speed * slow_factor, 0.08)
        target_vx = dx * effective_speed
        target_vy = dy * effective_speed

        person.vx = (person.vx * (1.0 - VELOCITY_BLEND)) + (target_vx * VELOCITY_BLEND)
        person.vy = (person.vy * (1.0 - VELOCITY_BLEND)) + (target_vy * VELOCITY_BLEND)

        current_speed = math.hypot(person.vx, person.vy)
        if current_speed > effective_speed and current_speed > 0:
            scale = effective_speed / current_speed
            person.vx *= scale
            person.vy *= scale

        person.x += person.vx
        person.y += person.vy
        person.x = max(20, min(1480, person.x))
        person.y = max(20, min(650, person.y))
        person.last_pos = (person.x, person.y)
        return dist

    def get_role_speed_factor(self, person: Person) -> float:
        return ROLE_SPEED_FACTORS.get(person.role, 1.0)

    def get_person_next_waypoint(self, person: Person) -> str:
        if not person.path:
            return "NONE"
        current_zone = person.zone or self.get_zone_of(person.x, person.y)
        for node in person.path:
            if node != current_zone:
                return node
        return person.path[-1]

    def get_person_intent(self, person: Person) -> str:
        if person.status == "TRAPPED":
            return "Awaiting extraction support and a reopened safe route."
        if person.status == "PANIC":
            return f"Moving urgently toward {self.get_person_next_waypoint(person)} while avoiding the hazard."
        if person.status == "EVACUATING":
            return f"Following the safest active route toward {self.get_person_next_waypoint(person)}."
        return f"Holding in {person.zone or self.get_zone_of(person.x, person.y)} until a new instruction is issued."

    def get_person_route_preview(self, person: Person) -> str:
        if not person.path:
            return "No active route."
        preview = " -> ".join(person.path[:4])
        return f"{preview} -> ..." if len(person.path) > 4 else preview

    def get_patrol_target_zone(self, person: Person, current_zone: str) -> str:
        zone_names = sorted(ZONES.keys())
        if not zone_names:
            return current_zone
        if current_zone not in zone_names:
            return zone_names[0]
        step = PATROL_STEP_BY_ROLE.get(person.role, 1)
        curr_idx = zone_names.index(current_zone)
        return zone_names[(curr_idx + step) % len(zone_names)]

    def should_recalculate_route(self, person: Person, path_blocked: bool) -> bool:
        now = time.time()
        if path_blocked or not person.path:
            if now - person.last_route_recalc >= ROUTE_RECALC_INTERVAL:
                person.last_route_recalc = now
                return True
        elif person.stuck_count >= 12 and now - person.last_route_recalc >= STUCK_RECALC_INTERVAL:
            person.last_route_recalc = now
            person.stuck_count = 0
            return True
        return False

    def compute_stats(self):
        alive = sum(1 for p in self.people if p.hp > 0 and p.status != "ESCAPED")
        evacuated = sum(1 for p in self.people if p.status == "ESCAPED")
        trapped = sum(1 for p in self.people if p.status == "TRAPPED" and p.hp > 0)
        casualties = sum(1 for p in self.people if p.hp <= 0)
        panicking = sum(1 for p in self.people if p.status == "PANIC" and p.hp > 0)
        return {
            "alive": alive,
            "evacuated": evacuated,
            "trapped": trapped,
            "casualties": casualties,
            "panicking": panicking,
            "active_fires": len(self.active_fire_zones),
        }

    def zone_has_fire(self, zone_name):
        zone_rect = ZONES.get(zone_name)
        if not zone_rect:
            return False
        for gx, gy in self.fire_cells:
            px, py = gx * GRID_SIZE + 5, gy * GRID_SIZE + 5
            if rect_contains(zone_rect, px, py):
                return True
        return False

    def reset_layout(self):
        global ZONES, EXITS, ADJACENCY
        restore_default_layout()
        ADJACENCY.clear()
        ADJACENCY.update(copy.deepcopy(BASE_ADJACENCY))
        self.navigation_graph = copy.deepcopy(BASE_ADJACENCY)
        self.layout_name = "Default Layout"
        self.layout_source = "default"
        self.layout_revision += 1
        self.layout_version = self.layout_revision
        self.blocked_exits.clear()
        if "sensor_bus" in globals():
            sensor_bus.update_layout(ZONES, EXITS, self.navigation_graph)

    def apply_layout(self, layout_name, zones, exits, population=None, source="json", notes=None):
        global ZONES, EXITS, ADJACENCY

        normalized_zones = normalize_layout_map(zones)
        normalized_exits = normalize_layout_map(exits)

        if not normalized_zones or not normalized_exits:
            raise ValueError("A layout must include at least one zone and one exit.")

        ZONES.clear()
        ZONES.update(normalized_zones)
        EXITS.clear()
        EXITS.update(normalized_exits)

        self.navigation_graph = build_navigation_graph(ZONES, EXITS)
        ADJACENCY.clear()
        ADJACENCY.update(copy.deepcopy(self.navigation_graph))

        self.layout_name = layout_name or "Custom Layout"
        self.layout_source = source
        self.layout_revision += 1
        self.layout_version = self.layout_revision
        self.blocked_exits.clear()

        if population is None:
            population = max(MIN_ACTIVE_OCCUPANTS, min(60, len(ZONES) * 6))

        self.populate(member_count=population)
        if notes:
            self.log_event(f"LAYOUT UPDATED: {self.layout_name}. {notes}")
        else:
            self.log_event(f"LAYOUT UPDATED: {self.layout_name}.")
        if "sensor_bus" in globals():
            sensor_bus.update_layout(ZONES, EXITS, self.navigation_graph)
        return {
            "name": self.layout_name,
            "source": self.layout_source,
            "revision": self.layout_revision,
            "population": population,
            "zone_count": len(ZONES),
            "exit_count": len(EXITS),
        }

    def populate(self, member_count=50):
        with self.lock:
            member_count = max(MIN_ACTIVE_OCCUPANTS, int(member_count or MIN_ACTIVE_OCCUPANTS))
            self.people = []
            roles = ["Software Engineer", "Product Manager", "Analyst", "HR Coordinator", "Janitor", "Security Assistant"]
            zones_list = sorted(ZONES.keys())
            for i in range(1, member_count + 1):
                z_name = zones_list[(i - 1) % len(zones_list)]
                r = ZONES[z_name]
                role = roles[(i - 1) % len(roles)]

                columns = max(1, min(4, int(r["w"] // 90)))
                rows = max(1, min(4, int(r["h"] // 80)))
                slot_count = max(1, columns * rows)
                slot_index = ((i - 1) // len(zones_list)) % slot_count
                col = slot_index % columns
                row = slot_index // columns

                margin_x = 24.0
                margin_y = 24.0
                usable_w = max(20.0, r["w"] - (margin_x * 2))
                usable_h = max(20.0, r["h"] - (margin_y * 2))
                px = r["x"] + margin_x + ((col + 0.5) * usable_w / columns)
                py = r["y"] + margin_y + ((row + 0.5) * usable_h / rows)

                self.people.append(Person(f"p{i}", f"{role} {i}", role, px, py))
            
            self.fire_cells.clear()
            self.water_cells.clear()
            self.pa_announcements.clear()
            self.global_events.clear()
            self.last_global_pa_time = 0.0 # Reset throttle
            self.last_crewai_run = 0.0
            self.last_crew_status = "UNKNOWN"
            self.last_crew_sprinklers = "NONE"
            self.last_crew_exit = "NONE"
            self.last_crew_pa = ""
            self.suppression_mode = False # Reset suppression
            self.blocked_exits.clear()
            self.start_time = time.time()
            self.log_event(f"FACILITY ONLINE. {member_count} PERSONNEL DETECTED AND TRACKED.")

    def get_zone_of(self, x, y):
        for name, rect in ZONES.items():
            if rect_contains(rect, x, y): return name
        for name, rect in EXITS.items():
            if rect_contains(rect, x, y): return name
        # Nearest fallback
        closest = "Corridor"
        min_dist = 9999
        for name, rect in ZONES.items():
            cx = rect["x"] + rect["w"]/2
            cy = rect["y"] + rect["h"]/2
            d = math.hypot(cx - x, cy - y)
            if d < min_dist:
                min_dist = d
                closest = name
        return closest

    def get_node_pos(self, name):
        all_rects = {**ZONES, **EXITS}
        if name in all_rects:
            r = all_rects[name]
            return (r["x"] + r["w"]/2, r["y"] + r["h"]/2)
        return (0,0)

    def get_zone_center(self, zone_name):
        all_rects = {**ZONES, **EXITS}
        if zone_name in all_rects:
            rect = all_rects[zone_name]
            return rect["x"] + rect["w"] / 2.0, rect["y"] + rect["h"] / 2.0
        return 0.0, 0.0

    def apply_sensor_fusion(self, sensor_snapshot):
        with self.lock:
            self.last_sensor_summary = copy.deepcopy(sensor_snapshot.get("summary", self.last_sensor_summary))

            previous_blocked = set(self.blocked_exits)
            next_blocked = set(self.last_sensor_summary.get("blocked_exits", []))
            self.blocked_exits = {exit_name for exit_name in next_blocked if exit_name in EXITS}

            for exit_name in sorted(self.blocked_exits - previous_blocked):
                self.log_event(f"SENSOR ALERT: {exit_name} reported blocked.")
            for exit_name in sorted(previous_blocked - self.blocked_exits):
                self.log_event(f"SENSOR UPDATE: {exit_name} reported clear.")

            for zone_name, zone_state in sensor_snapshot.get("zones", {}).items():
                if zone_name not in ZONES:
                    continue
                if float(zone_state.get("fire_probability", 0.0)) >= 60.0 and not self.zone_has_fire(zone_name):
                    self.spawn_fire_in_zone(zone_name)

            tracked_people = {}
            for sighting in sensor_snapshot.get("tracked_occupants", []):
                tracked_people[sighting["occupant_id"]] = copy.deepcopy(sighting)
                for person in self.people:
                    if sighting["occupant_id"] not in {person.id, person.name}:
                        continue
                    zone_name = sighting.get("zone")
                    if zone_name in ZONES:
                        if sighting.get("x") is not None and sighting.get("y") is not None:
                            person.x = float(sighting["x"])
                            person.y = float(sighting["y"])
                        else:
                            person.x, person.y = self.get_zone_center(zone_name)
                        person.zone = zone_name
                        person.last_pos = (person.x, person.y)
            self.sensor_tracked_people = tracked_people

    def find_shortest_path(self, start, targets, hazards):
        if not start: return []
        pq = [(0, start, [start])]
        visited_costs = {start: 0}
        
        while pq:
            cost, node, path = heapq.heappop(pq)
            if node in targets:
                return path
            if cost > visited_costs.get(node, float('inf')):
                 continue
            
            neighbors = self.navigation_graph.get(node, [])
            cx, cy = self.get_node_pos(node)
            for neighbor in neighbors:
                if neighbor in hazards: continue
                nx, ny = self.get_node_pos(neighbor)
                dist_weight = math.hypot(nx - cx, ny - cy)
                new_cost = cost + dist_weight
                if new_cost < visited_costs.get(neighbor, float('inf')):
                    visited_costs[neighbor] = new_cost
                    heapq.heappush(pq, (new_cost, neighbor, path + [neighbor]))
        return []

    def find_path_to_target(self, start: str, target: str, hazards: set) -> List[str]:
        if not target:
            return []
        return self.find_shortest_path(start, [target], hazards)

    def load_scenario(self, scenario_name):
        with self.lock:
            self.scenario = scenario_name
            self.people.clear()
            self.fire_cells.clear()
            self.water_cells.clear()
            self.pa_announcements.clear()
            # self.reset_layout()
            self.suppression_mode = False
            self.blocked_exits.clear()
            
            if scenario_name in ["OPERATOR", "DEFAULT"]:
                self.populate()
            elif scenario_name == "CAMERA":
                self.populate(member_count=MIN_ACTIVE_OCCUPANTS)
            elif scenario_name == "FIRE_EMERGENCY":
                self.populate()
                self.spawn_fire_in_zone("Zone Iota (Medical)")
                self.spawn_fire_in_zone("East Corridor")
            elif scenario_name == "ADMIN":
                self.populate()
                # Admin spawns a chaotic multi-fire scenario
                self.spawn_fire_in_zone("West Corridor")
                self.spawn_fire_in_zone("Zone Theta (Cafeteria)")
            else:
                self.populate()

    def spawn_fire_in_zone(self, zone_name):
        all_rects = {**ZONES, **EXITS}
        if zone_name in all_rects:
            rect = all_rects[zone_name]
            gx = int((rect["x"] + rect["w"]/2) // GRID_SIZE)
            gy = int((rect["y"] + rect["h"]/2) // GRID_SIZE)
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    self.fire_cells.add((gx+dx, gy+dy))
            msg = f"CRITICAL: Thermal runaway detected in {zone_name}."
            self.log_event(msg)
            self.log_incident(msg)

    def deploy_suppression(self, target_name, force_clear: bool = False):
        all_rects = {**ZONES, **EXITS}

        if target_name.lower() in ["all", "everywhere", "facility"]:
            targets = all_rects.items()
        elif target_name in all_rects:
            targets = [(target_name, all_rects[target_name])]
        else:
            return

        if force_clear and target_name.lower() in ["all", "everywhere", "facility"]:
            with self.lock:
                # Low-water full clear: remove fire immediately and keep only sparse water traces.
                if self.fire_cells:
                    sparse_water = set(list(self.fire_cells)[::6])
                    self.water_cells.update(sparse_water)
                self.fire_cells.clear()
            self.log_event("FULL FACILITY FIRE CLEAR EXECUTED")
            return

        for zone_name, rect in targets:
            gx_start = int(rect["x"] // GRID_SIZE)
            gx_end = int((rect["x"] + rect["w"]) // GRID_SIZE)
            gy_start = int(rect["y"] // GRID_SIZE)
            gy_end = int((rect["y"] + rect["h"]) // GRID_SIZE)
            
            new_water = set()
            # Precision suppression by default. In force-clear mode, remove all fire in target bounds.
            with self.lock:
                for dx in range(gx_start, gx_end + 1):
                    for dy in range(gy_start, gy_end + 1):
                        if force_clear:
                            cell = (dx, dy)
                            if cell in self.fire_cells:
                                new_water.add(cell)
                            continue
                        if (dx, dy) in self.fire_cells:
                            new_water.add((dx, dy))
                            # Add 1 grid radius for realistic spread margin without flooding entire rooms
                            for ox in [-1, 0, 1]:
                                for oy in [-1, 0, 1]:
                                    nc = (dx+ox, dy+oy)
                                    if gx_start <= nc[0] <= gx_end and gy_start <= nc[1] <= gy_end:
                                        new_water.add(nc)

                if force_clear:
                    self.fire_cells = {
                        cell for cell in self.fire_cells
                        if not (gx_start <= cell[0] <= gx_end and gy_start <= cell[1] <= gy_end)
                    }
                # In full-clear mode, keep water footprint minimal.
                if force_clear:
                    self.water_cells.update(set(list(new_water)[::4]))
                else:
                    self.water_cells.update(new_water)
                for w in new_water:
                    if w in self.fire_cells:
                        self.fire_cells.remove(w)
            if force_clear:
                self.log_event(f"FORCE CLEAR EXECUTED IN {zone_name.upper()}")
            else:
                self.log_event(f"SUPPRESSANT DEPLOYED TO {zone_name.upper()}")

    def update_cycle(self):
        with self.lock:
            elapsed = time.time() - self.start_time
            
            # 1. Spread Fire
            if (
                elapsed > 2
                and len(self.fire_cells) > 0
                and len(self.fire_cells) < MAX_FIRE_CELLS
                and random.random() < 0.12
            ):
                new_cells = set()
                candidates = random.sample(list(self.fire_cells), min(24, len(self.fire_cells)))
                all_rects = list(ZONES.values()) + list(EXITS.values())
                
                for (cx, cy) in candidates:
                    neighbors = [(cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)]
                    for nx, ny in neighbors:
                        if (nx, ny) not in self.fire_cells and (nx, ny) not in self.water_cells:
                            px, py = nx*GRID_SIZE, ny*GRID_SIZE
                            for r in all_rects:
                                if rect_contains(r, px, py):
                                    new_cells.add((nx, ny))
                                    break
                self.fire_cells.update(new_cells)

            if len(self.fire_cells) > MAX_FIRE_CELLS:
                self.fire_cells = set(random.sample(list(self.fire_cells), MAX_FIRE_CELLS))

            # 1b. Realistic Water Suppression Physics
            if self.water_cells and self.fire_cells:
                # Water eats fire slowly if they overlap or are very close
                to_kill_fire = set()
                to_kill_water = set()
                # Check for overlap
                for w in list(self.water_cells):
                    for dx in range(-1, 2):
                        for dy in range(-1, 2):
                            f_check = (w[0]+dx, w[1]+dy)
                            if f_check in self.fire_cells:
                                to_kill_fire.add(f_check)
                                if random.random() < 0.1: # water evaporates sometimes
                                    to_kill_water.add(w)
                
                self.fire_cells.difference_update(to_kill_fire)
                self.water_cells.difference_update(to_kill_water)

            # Evaporate water slowly
            if self.water_cells and random.random() < 0.5:
                to_evap = random.sample(list(self.water_cells), min(len(self.water_cells), 5))
                for w in to_evap: self.water_cells.remove(w)

            # Update High-Level Zones status for AI/Alerts
            current_fire_zones = set()
            for (gx, gy) in self.fire_cells:
                px, py = gx * GRID_SIZE + 5, gy * GRID_SIZE + 5
                for name, r in ZONES.items():
                    if rect_contains(r, px, py): current_fire_zones.add(name)
                for name, r in EXITS.items():
                    if rect_contains(r, px, py): current_fire_zones.add(name)
            self.active_fire_zones = sorted(current_fire_zones)

            # 1c. Heuristic SITREP Generation (Instant Technical reporting)
            if not self.fire_cells:
                self.sitrep = "FACILITY SECURE. ALL SYSTEMS NOMINAL."
            else:
                counts = {}
                for z in self.active_fire_zones:
                    counts[z] = sum(1 for c in self.fire_cells if self.get_zone_of(c[0]*GRID_SIZE+5, c[1]*GRID_SIZE+5) == z)
                top_zone = max(counts, key=counts.get) if counts else "Unknown"
                self.sitrep = f"CRITICAL: THERMAL BREACH IN PROGRESS.\nPRIMARY IMPACT: {top_zone.upper()} ({counts.get(top_zone, 0)} cells).\nTHREAT LEVEL: SEVERE. EVACUATION PROTOCOLS ACTIVE."
                
                # CREW AI SWARM DELIBERATION (Every 5 seconds)
                curr_t = time.time()
                if curr_t - self.last_crewai_run > 5.0 and self.active_fire_zones:
                    self.last_crewai_run = curr_t
                    alive_count = sum(1 for p in self.people if p.hp > 0)
                    
                    def crewai_callback(f_zones, a_count):
                        loop = asyncio.new_event_loop()
                        try:
                            # Starts the Langgraph flow inside an async loop on a new thread
                            res = loop.run_until_complete(run_langgraph_cycle(f_zones, a_count))
                            status = res.get("crew_status", "UNKNOWN")
                            sprinklers = res.get("sprinkler_zones", "NONE")
                            route = res.get("primary_exit", "NONE")
                            msg = res.get("pa_announcement", "")
                            self.last_crew_status = status
                            self.last_crew_sprinklers = sprinklers
                            self.last_crew_exit = route
                            self.last_crew_pa = msg
                            self.last_crew_update = time.time()

                            self.log_event(f"CREW-AI STATUS: {status} | SPRINKLERS: {sprinklers} | EXIT: {route}")
                            
                            # Automatically trigger physical suppression based on crewai directive
                            if sprinklers and sprinklers.upper() != "NONE":
                                zones_to_suppress = [z.strip() for z in sprinklers.split(",")]
                                for z in zones_to_suppress:
                                    # Use self.deploy_suppression since we are in a subclass/method of SimulationEngine
                                    # Wait, crewai_callback is a nested def inside update_cycle! 
                                    # The enclosing instance `self` points to SimulationEngine.
                                    if z in ZONES or z in EXITS:
                                        self.deploy_suppression(z)
                                    elif z.upper() in ["ALL", "EVERYWHERE", "FACILITY"]:
                                        self.deploy_suppression("facility")

                            if msg:
                                self.log_event(f"CREW-AI DIRECTIVE: {msg[:120]}")
                        except Exception as e:
                            print(f"[CrewAI Thread Error] {e}")
                        finally:
                            loop.close()

                    t = threading.Thread(target=crewai_callback, args=(list(self.active_fire_zones), alive_count), daemon=True)
                    t.start()

            # 2. Update People & Continuous AI Routing
            exit_names = [name for name in EXITS.keys() if name not in self.blocked_exits]
            facility_is_on_fire_global = len(self.active_fire_zones) > 0
            for p in self.people:
                if p.hp <= 0: continue

                # Check Escape
                escaped = False
                if facility_is_on_fire_global or p.status in ["EVACUATING", "PANIC", "TRAPPED"]:
                    for ex in EXITS.keys():
                        if rect_contains(EXITS[ex], p.x, p.y):
                            p.status = "ESCAPED"
                            escaped = True
                            break
                if escaped: continue

                # Check Fire Proximity / Damage
                pgx, pgy = int(p.x // GRID_SIZE), int(p.y // GRID_SIZE)
                in_fire = (pgx, pgy) in self.fire_cells and (pgx, pgy) not in self.water_cells
                if in_fire:
                    p.hp -= 0.5
                
                p_zone = self.get_zone_of(p.x, p.y)
                p.zone = p_zone
                role_speed = self.get_role_speed_factor(p)
                
                # Proximity determines PANIC vs orderly EVACUATING
                is_panic_proximity = False
                facility_is_on_fire = len(self.active_fire_zones) > 0
                for fz in self.active_fire_zones:
                    if fz == p_zone or p_zone in self.navigation_graph.get(fz, []):
                        is_panic_proximity = True
                        break

                if is_panic_proximity and p.status != "PANIC" and p.status != "TRAPPED":
                    p.status = "PANIC"
                    p.target_speed = PANIC_SPEED * role_speed
                elif facility_is_on_fire and p.status == "IDLE":
                    # Evacuate calmly if far away, but LLM can override
                    p.status = "EVACUATING"
                    p.target_speed = EVACUATING_SPEED * role_speed
                elif not facility_is_on_fire and p.status != "IDLE":
                    # Stand down from evac/panic
                    p.status = "IDLE"
                    p.path = []
                    p.committed_exit = ""
                    p.target_speed = 0.0
                elif p.status == "IDLE":
                    p.target_speed = DEFAULT_ROAM_SPEED * role_speed if p.path else 0.0
                elif p.status == "TRAPPED":
                    p.target_speed = TRAPPED_SPEED * role_speed

                # Keep the movement pace deterministic across cycles.
                if p.status == "PANIC":
                    p.target_speed = PANIC_SPEED * role_speed
                elif p.status == "EVACUATING":
                    p.target_speed = EVACUATING_SPEED * role_speed
                elif p.status == "TRAPPED":
                    p.target_speed = TRAPPED_SPEED * role_speed
                else:
                    p.target_speed = DEFAULT_ROAM_SPEED * role_speed if p.path else 0.0
                    
                # Dynamic Roaming during peacetime
                if p.status == "IDLE" and not facility_is_on_fire:
                    if p.role in ["Product Manager", "Security Assistant", "Janitor"]:
                        if time.time() > p.next_roam_time:
                            if not p.path:
                                target_zone = self.get_patrol_target_zone(p, p_zone)
                                if target_zone != p_zone:
                                    p.path = self.find_shortest_path(p_zone, [target_zone], set())
                                p.next_roam_time = time.time() + 12
                            elif len(p.path) == 0:
                                p.next_roam_time = time.time() + 8

                # Dynamic Routing (Continuous AI Overseer)
                if p.status in ["EVACUATING", "PANIC", "TRAPPED"]:
                    # Check if current path is blocked by active fire zones
                    path_blocked = False
                    for node in p.path:
                        if node in self.active_fire_zones or node in self.blocked_exits:
                            path_blocked = True
                            break
                    
                    if self.should_recalculate_route(p, path_blocked):
                        hazard_nodes = set(self.active_fire_zones) | set(self.blocked_exits)
                        if p.committed_exit in hazard_nodes:
                            p.committed_exit = ""
                            path_blocked = True
                        new_path = []
                        if (
                            p.committed_exit
                            and p.committed_exit in exit_names
                            and p.committed_exit not in hazard_nodes
                        ):
                            new_path = self.find_path_to_target(p_zone, p.committed_exit, hazard_nodes)
                        if not new_path:
                            new_path = self.find_shortest_path(p_zone, exit_names, hazard_nodes)
                            if new_path:
                                p.committed_exit = new_path[-1]
                        p.path = new_path
                        
                        if not p.path and p.status != "TRAPPED":
                            p.status = "TRAPPED"
                            p.committed_exit = ""
                            self.log_event(f"EMERGENCY: {p.name} trapped in {p_zone}. Deploying autonomous targeted halon drops.")
                            # Phase 2 Water Sprinkler Optimization: Only drop where needed to unblock
                            self.deploy_suppression(p_zone)
                            for exit_opt in exit_names:
                                self.deploy_suppression(exit_opt)

                        elif p.path and p.status == "TRAPPED":
                            p.status = "PANIC" # Path cleared!
                            self.log_event(f"UPDATE: Route generated for {p.name}. Proceeding.")

                        # Trigger PA Announcement Simulation if we got a new path
                        # System-wide Rate Limit: Only 1 PA announcement allowed across all personnel every 10.0 seconds
                        curr_time = time.time()
                        if p.path and (curr_time - self.last_global_pa_time > 10.0):
                            self.last_global_pa_time = curr_time
                            threading.Thread(target=self.trigger_pa_announcement, args=(p, p_zone, self.active_fire_zones[0] if self.active_fire_zones else "Unknown", p.path), daemon=True).start()

                # Movement Execution
                if p.path:
                    # Drop hazardous nodes that appeared after the path was computed.
                    hazard_nodes = set(self.active_fire_zones) | set(self.blocked_exits)
                    while p.path and p.path[0] in hazard_nodes:
                        p.path.pop(0)
                    if not p.path:
                        p.stuck_count = max(p.stuck_count, 12)
                        continue

                    # Target node is the first node in path that is NOT the current node
                    target_node = p.path[0]
                    if target_node == p_zone and len(p.path) > 1:
                        target_node = p.path[1]
                        
                    # Smooth Doorway Pathing
                    door_pos = get_door_pos(p_zone, target_node)
                    if door_pos:
                        tx, ty = door_pos
                    else:
                        tx, ty = self.get_node_pos(target_node)
                        
                    repel_x = 0.0
                    repel_y = 0.0
                    if self.fire_cells:
                        for gx, gy in self.get_nearest_fire_cells(p.x, p.y):
                            fx = gx * GRID_SIZE + (GRID_SIZE / 2)
                            fy = gy * GRID_SIZE + (GRID_SIZE / 2)
                            fire_dist = math.hypot(p.x - fx, p.y - fy)
                            if fire_dist <= 0.001 or fire_dist > FIRE_REPULSION_RADIUS:
                                continue
                            weight = (FIRE_REPULSION_RADIUS - fire_dist) / FIRE_REPULSION_RADIUS
                            factor = FIRE_REPULSION_WEIGHT if p.status != "TRAPPED" else TRAPPED_REPULSION_WEIGHT
                            repel_x += ((p.x - fx) / fire_dist) * weight * factor
                            repel_y += ((p.y - fy) / fire_dist) * weight * factor

                    p.speed += (p.target_speed - p.speed) * 0.22
                    prev_x, prev_y = p.x, p.y
                    dist = self.steer_person(p, tx, ty, max(p.speed, 0.1), repel_x, repel_y)
                    moved_distance = math.hypot(p.x - prev_x, p.y - prev_y)
                    if moved_distance < 0.18:
                        p.stuck_count += 1
                    else:
                        p.stuck_count = max(0, p.stuck_count - 2)
                    if dist <= WAYPOINT_EPSILON:
                        if len(p.path) > 0 and (p.path[0] == p_zone or p.path[0] == target_node):
                            p.path.pop(0)
                        p.stuck_count = 0
                    else:
                        p.speed = max(p.speed * 0.92, 0.12)
                        if abs(p.vx) < 0.05:
                            p.vx = 0.0
                        if abs(p.vy) < 0.05:
                            p.vy = 0.0

                elif p.status == "TRAPPED" and self.fire_cells:
                    best_f = None
                    min_d = float('inf')
                    for (gx, gy) in self.get_nearest_fire_cells(p.x, p.y):
                        fx, fy = gx * GRID_SIZE + (GRID_SIZE/2), gy * GRID_SIZE + (GRID_SIZE/2)
                        d = math.hypot(p.x - fx, p.y - fy)
                        if d < min_d:
                            min_d = d
                            best_f = (fx, fy)
                    
                    if best_f and min_d < 400: # Only run if fire is relatively close
                        # Vector AWAY from fire
                        dx = p.x - best_f[0]
                        dy = p.y - best_f[1]
                        dist = math.hypot(dx, dy)
                        if dist > 0:
                            dx = dx / dist
                            dy = dy / dist
                            
                            # Move away deterministically at the trapped pace.
                            p.speed += (p.target_speed - p.speed) * 0.2
                            p.x += dx * p.speed
                            p.y += dy * p.speed
                            p.vx = dx * p.speed
                            p.vy = dy * p.speed
                            
                            # Clamp to current zone boundaries to prevent clipping out of bounds
                            all_zones = {**ZONES, **EXITS}
                            if p_zone in all_zones:
                                curr_zone_rect = all_zones[p_zone]
                                p.x = max(curr_zone_rect["x"] + 10, min(curr_zone_rect["x"] + curr_zone_rect["w"] - 10, p.x))
                                p.y = max(curr_zone_rect["y"] + 10, min(curr_zone_rect["y"] + curr_zone_rect["h"] - 10, p.y))
                                p.last_pos = (p.x, p.y)

            # Auto-reseed occupants when all have evacuated and no active fire remains.
            if not self.active_fire_zones and self.people:
                all_escaped = all(p.status == "ESCAPED" for p in self.people)
                if all_escaped and (time.time() - self.start_time) > 8.0:
                    self.log_event("AUTO-RESET: ALL OCCUPANTS EVACUATED. REPOPULATING FACILITY.")
                    self.populate(member_count=MIN_ACTIVE_OCCUPANTS)

            # Cap HP
            for p in self.people: p.hp = max(0, min(100, p.hp))

    def trigger_pa_announcement(self, person, loc, hazard, route):
        try:
            output = f"Attention {person.name}. Proceed to {' -> '.join(route)} immediately."
            with self.lock:
                self.pa_announcements.append({
                    "id": str(time.time()),
                    "person_id": person.id,
                    "text": output,
                    "x": person.x,
                    "y": person.y,
                    "timestamp": time.time()
                })
                if len(self.pa_announcements) > 5:
                    self.pa_announcements.pop(0)
        except Exception as e:
            print(f"PA Error: {e}")

    def get_state(self):
        with self.lock:
            # Clean old announcements
            curr_time = time.time()
            self.pa_announcements = [a for a in self.pa_announcements if curr_time - a["timestamp"] < 5.0]
            stats = self.compute_stats()
            sensor_snapshot = sensor_bus.get_snapshot()

            return {
                "scenario": self.scenario,
                "layout": {
                    "name": self.layout_name,
                    "source": self.layout_source,
                    "revision": self.layout_revision,
                    "zones": len(ZONES),
                    "exits": len(EXITS),
                },
                "zones": clone_rect_map(ZONES),
                "exits": clone_rect_map(EXITS),
                "stats": stats,
                "people": [
                    {
                        "id": p.id,
                        "member_index": index,
                        "name": p.name,
                        "role": p.role,
                        "zone": p.zone or self.get_zone_of(p.x, p.y),
                        "x": round(p.x, 2),
                        "y": round(p.y, 2),
                        "hp": round(p.hp, 1),
                        "status": p.status,
                        "path": p.path,
                        "speed": round(p.speed, 3),
                        "next_waypoint": self.get_person_next_waypoint(p),
                        "intent": self.get_person_intent(p),
                        "route_preview": self.get_person_route_preview(p),
                        "assigned_exit": p.committed_exit or (p.path[-1] if p.path else "NONE"),
                        "in_facility": p.status != "ESCAPED",
                    }
                    for index, p in enumerate(self.people, start=1)
                ],
                "fire_cells": list(self.fire_cells),
                "water_cells": list(self.water_cells),
                "active_fire_zones": list(self.active_fire_zones),
                "blocked_exits": sorted(self.blocked_exits),
                "pa_announcements": self.pa_announcements,
                "global_events": list(self.global_events),
                "sitrep": self.sitrep,
                "sensor_pipeline": sensor_snapshot,
                "autonomous_mode": self.autonomous_mode,
                "auto_suppress_log": list(self.auto_suppress_log),
                "agent_brief": {
                    "status": self.last_crew_status,
                    "sprinklers": self.last_crew_sprinklers,
                    "primary_exit": self.last_crew_exit,
                    "pa": self.last_crew_pa,
                    "updated_at": self.last_crew_update,
                },
            }

sim_engine = SimulationEngine()
sim_engine.populate()
sensor_bus = SensorFusionEngine()
sensor_bus.update_layout(ZONES, EXITS, ADJACENCY)

def simulation_loop():
    while sim_engine.running:
        sim_engine.update_cycle()

        # ---- AUTONOMOUS MODE: detect & suppress fire automatically ----
        if sim_engine.autonomous_mode and sim_engine.fire_cells:
            now = time.time()
            if now - sim_engine.last_auto_suppress_time >= 3.0:  # throttle: max 1 action / 3 s
                sim_engine.last_auto_suppress_time = now
                with sim_engine.lock:
                    burning_zones = list(sim_engine.active_fire_zones)
                if burning_zones:
                    # Target the most fire-loaded zone first (efficient water use)
                    def _fire_count_in_zone(zone_name):
                        rect = {**ZONES, **EXITS}.get(zone_name)
                        if not rect:
                            return 0
                        gx_s = int(rect["x"] // GRID_SIZE)
                        gy_s = int(rect["y"] // GRID_SIZE)
                        gx_e = int((rect["x"] + rect["w"]) // GRID_SIZE)
                        gy_e = int((rect["y"] + rect["h"]) // GRID_SIZE)
                        return sum(
                            1 for c in sim_engine.fire_cells
                            if gx_s <= c[0] <= gx_e and gy_s <= c[1] <= gy_e
                        )
                    # Sort zones by fire density descending
                    burning_zones.sort(key=_fire_count_in_zone, reverse=True)
                    target_zone = burning_zones[0]  # Highest-priority zone
                    with sim_engine.lock:
                        before = len(sim_engine.fire_cells)
                        # Efficient suppression: not force-clear — uses realistic water physics
                        sim_engine.deploy_suppression(target_zone, force_clear=False)
                        after = len(sim_engine.fire_cells)
                        reduced = max(0, before - after)
                        ts = time.strftime("[%H:%M:%S]")
                        action_msg = (
                            f"{ts} AUTO-SUPPRESS: InfernalX AI targeted {target_zone.upper()}, "
                            f"{reduced} fire cells suppressed. Water use optimised."
                        )
                        sim_engine.global_events.append(action_msg)
                        sim_engine.auto_suppress_log.append(action_msg)
                        # Keep only last 5 auto-suppress log entries
                        if len(sim_engine.auto_suppress_log) > 5:
                            sim_engine.auto_suppress_log = sim_engine.auto_suppress_log[-5:]
                        sim_engine.log_incident(action_msg)

        time.sleep(1 / STATE_REFRESH_HZ)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup React UI Delivery
if os.path.exists("ui/dist/assets"):
    app.mount("/assets", StaticFiles(directory="ui/dist/assets"), name="assets")
else:
    print("WARNING: 'ui/dist' not found. Ensure you run 'npm run build' inside the 'ui' directory.")

@app.on_event("startup")
def startup_event():
    sim_thread = threading.Thread(target=simulation_loop, daemon=True)
    sim_thread.start()
    # Warm up the model so the first real user query is fast
    # Fires a tiny dummy prompt in background â€” loads weights into RAM/VRAM
    def _warmup():
        try:
            time.sleep(2)  # Give server a moment to fully bind
            requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": MODEL_NAME, "prompt": "hi", "stream": False,
                      "options": {"num_predict": 1, "num_ctx": 128}},
                timeout=30,
            )
            logger.info(f"Model warm-up complete: {MODEL_NAME}")
        except Exception as exc:
            logger.warning(f"Model warm-up skipped: {exc}")
    threading.Thread(target=_warmup, daemon=True).start()

@app.on_event("shutdown")
def shutdown_event():
    sim_engine.running = False

@app.get("/")
def read_root():
    # Serve the compiled React UI
    if os.path.exists("ui/dist/index.html"):
        return FileResponse("ui/dist/index.html")
    # Fallback if no build
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"message": "No UI build found. Please run 'npm run build' inside the ui folder."}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Stream state at a lower UI cadence to reduce serialization and render load.
            state = sim_engine.get_state()
            await websocket.send_json(state)
            await asyncio.sleep(1 / WEBSOCKET_REFRESH_HZ)
    except WebSocketDisconnect:
        pass

@app.post("/api/command")
async def handle_command(cmd: dict):
    action = cmd.get("action")
    target = cmd.get("target")
    
    with sim_engine.lock:
        if action == "spawn_fire":
            # Target is a zone name or coordinates
            sim_engine.spawn_fire_in_zone(target)
            return {"status": "ok"}
        elif action == "set_scenario":
            sim_engine.load_scenario(target)
            return {"status": "ok"}
        elif action == "manual_fire":
            x, y = cmd.get("x"), cmd.get("y")
            # Spawn fire at clicked coordinates
            gx, gy = int(x // GRID_SIZE), int(y // GRID_SIZE)
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    sim_engine.fire_cells.add((gx+dx, gy+dy))
            msg = f"MANUAL THERMAL INJECTION DETECTED AT COORD: ({int(x)}, {int(y)})"
            sim_engine.log_event(msg) # Mirror to visual logs
            sim_engine.log_incident(msg)
            return {"status": "ok"}
        elif action == "deploy_suppression":
            full_clear = bool(cmd.get("full_clear", False))
            target = target or "facility"
            sim_engine.deploy_suppression(str(target), force_clear=full_clear)
            return {
                "status": "ok",
                "target": target,
                "full_clear": full_clear,
                "active_fire_zones": list(sim_engine.active_fire_zones),
            }
    return {"status": "error"}


@app.get("/api/sensor_snapshot")
async def get_sensor_snapshot():
    return sensor_bus.get_snapshot()


@app.post("/api/autonomous-mode")
async def toggle_autonomous_mode(payload: dict = {}):
    """Toggle InfernalX Autonomous Mode on/off.
    When ON: AI automatically detects and suppresses fire using efficient water targeting.
    """
    with sim_engine.lock:
        # If payload explicitly sends enabled=true/false, use that; otherwise flip the flag
        if "enabled" in payload:
            sim_engine.autonomous_mode = bool(payload["enabled"])
        else:
            sim_engine.autonomous_mode = not sim_engine.autonomous_mode
        mode = sim_engine.autonomous_mode
        now_ts = time.strftime("[%H:%M:%S]")
        if mode:
            msg = f"{now_ts} AUTONOMOUS MODE ACTIVATED — InfernalX AI will auto-suppress any detected fire."
        else:
            msg = f"{now_ts} AUTONOMOUS MODE DEACTIVATED — Manual control restored."
        sim_engine.global_events.append(msg)
        sim_engine.log_incident(msg)
    return {"autonomous_mode": mode, "message": msg}


@app.get("/api/llm_health")
async def llm_health():
    with LLM_METRICS_LOCK:
        metrics = copy.deepcopy(LLM_ROUTING_METRICS)
    return {
        "status": "ok",
        "primary_model": MODEL_NAME,
        "fallback_model": FALLBACK_MODEL_NAME,
        "timeout_seconds": CHAT_LLM_TIMEOUT_SECONDS,
        "routing": metrics,
    }


@app.post("/api/sensor_ingest")
async def ingest_sensor_packet(payload: dict):
    packet = normalize_sensor_payload(payload)
    snapshot = sensor_bus.ingest(packet)
    sim_engine.apply_sensor_fusion(snapshot)
    return {
        "status": "success",
        "summary": snapshot["summary"],
        "snapshot": snapshot,
    }


@app.post("/api/sensor_demo")
async def ingest_demo_sensor_packet():
    demo_path = "sensor_demo_packet.json"
    if not os.path.exists(demo_path):
        return {"status": "error", "message": "sensor_demo_packet.json not found."}

    with open(demo_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    packet = normalize_sensor_payload(payload)
    snapshot = sensor_bus.ingest(packet)
    sim_engine.apply_sensor_fusion(snapshot)
    return {
        "status": "success",
        "summary": snapshot["summary"],
        "snapshot": snapshot,
    }

class RectSpec(BaseModel):
    x: int
    y: int
    w: int
    h: int


class DesignLayout(BaseModel):
    name: str = "Custom Layout"
    population: Optional[int] = None
    notes: Optional[str] = None
    zones: Dict[str, RectSpec]
    exits: Dict[str, RectSpec]


class LayoutUpload(BaseModel):
    layout: Optional[DesignLayout] = None
    design_text: Optional[str] = None
    image_base64: Optional[str] = None


def extract_json_block(text: str) -> str:
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        return match.group(0)
    return text.strip()


def build_area_alias_map():
    zone_names = list(ZONES.keys())
    alias_map = {}
    ordinal_labels = {
        1: "one",
        2: "two",
        3: "three",
        4: "four",
        5: "five",
        6: "six",
        7: "seven",
        8: "eight",
        9: "nine",
        10: "ten",
        11: "eleven",
        12: "twelve",
    }
    ordinal_rank_labels = {
        1: "first",
        2: "second",
        3: "third",
        4: "fourth",
        5: "fifth",
        6: "sixth",
        7: "seventh",
        8: "eighth",
        9: "ninth",
        10: "tenth",
        11: "eleventh",
        12: "twelfth",
    }

    for index, zone_name in enumerate(zone_names, start=1):
        alias_map[zone_name.lower()] = zone_name
        simplified = re.sub(r"[^a-z0-9 ]", "", zone_name.lower())
        alias_map[simplified] = zone_name
        short_name = simplified.replace("zone ", "").strip()
        alias_map[short_name] = zone_name
        alias_map[f"block {index}"] = zone_name
        alias_map[f"zone {index}"] = zone_name
        if index in ordinal_labels:
            alias_map[f"block {ordinal_labels[index]}"] = zone_name
            alias_map[f"zone {ordinal_labels[index]}"] = zone_name
        if index in ordinal_rank_labels:
            alias_map[f"{ordinal_rank_labels[index]} block"] = zone_name
            alias_map[f"{ordinal_rank_labels[index]} zone"] = zone_name

    for exit_name in EXITS.keys():
        alias_map[exit_name.lower()] = exit_name
        alias_map[re.sub(r"[^a-z0-9 ]", "", exit_name.lower())] = exit_name

    return alias_map


def extract_area_targets(query_text: str):
    lowered = query_text.lower()
    alias_map = build_area_alias_map()
    matched = []

    for alias, target in alias_map.items():
        if alias and alias in lowered and target not in matched:
            matched.append(target)

    return matched


def summarize_area_status(state, targets):
    fire_zones = set(state["active_fire_zones"])
    people_by_zone = {}
    for person in state["people"]:
        people_by_zone.setdefault(person["zone"], []).append(person)
    sensor_people_by_zone = {}
    for tracked in state.get("sensor_pipeline", {}).get("tracked_occupants", []):
        sensor_people_by_zone.setdefault(tracked["zone"], []).append(tracked)

    summaries = []
    for target in targets:
        people = people_by_zone.get(target, [])
        tracked_people = sensor_people_by_zone.get(target, [])
        active = "ACTIVE FIRE" if target in fire_zones else "NO ACTIVE FIRE"
        trapped = sum(1 for p in people if p["status"] == "TRAPPED")
        panic = sum(1 for p in people if p["status"] == "PANIC")
        occupant_count = max(len(people), len(tracked_people))
        summaries.append(
            f"{target}: {active}; occupants={occupant_count}; trapped={trapped}; panic={panic}"
        )

    return summaries


def _normalize_text_token(value: str) -> str:
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())


def find_people_for_query(query_text: str, state) -> List[dict]:
    people = state.get("people", [])
    lowered = query_text.lower()
    compact_query = _normalize_text_token(query_text)
    matches: List[dict] = []

    role_keywords = {
        "janitor": ["janitor", "cleaner"],
        "security assistant": ["security", "guard"],
        "software engineer": ["engineer", "developer"],
        "product manager": ["product manager", "pm", "manager"],
        "analyst": ["analyst"],
        "hr coordinator": ["hr", "human resources"],
    }

    def append_match(person: dict):
        if person and person not in matches:
            matches.append(person)

    for person in people:
        name = str(person.get("name", "")).strip()
        role = str(person.get("role", "")).strip().lower()
        pid = str(person.get("id", "")).strip().lower()
        compact_name = _normalize_text_token(name)
        compact_role = _normalize_text_token(role)
        first_name_token = name.split()[0].lower() if name else ""

        if name and name.lower() in lowered:
            append_match(person)
            continue
        if pid and pid in lowered:
            append_match(person)
            continue
        if compact_name and compact_name in compact_query:
            append_match(person)
            continue
        if first_name_token and first_name_token in lowered and len(first_name_token) >= 2:
            append_match(person)
            continue

        for canonical_role, keys in role_keywords.items():
            if canonical_role in compact_role and any(key in lowered for key in keys):
                append_match(person)
                break

    # Friendly aliases requested by operator.
    if not matches and "jo" in lowered:
        janitor = next((p for p in people if "janitor" in str(p.get("role", "")).lower()), None)
        if janitor:
            append_match(janitor)
    if not matches and "variski" in lowered:
        security = next((p for p in people if "security" in str(p.get("role", "")).lower()), None)
        if security:
            append_match(security)

    return matches[:4]


def build_person_status_response(person: dict) -> str:
    route_preview = person.get("route_preview") or "No active route"
    return render_directive(
        f"PERSON TRACK READY: {person.get('name', 'UNKNOWN').upper()}",
        f"MAINTAIN EVACUATION FLOW FOR {person.get('name', 'UNKNOWN').upper()} IN {person.get('zone', 'UNKNOWN').upper()}",
        (
            f"ROLE={person.get('role', 'UNKNOWN')}; ZONE={person.get('zone', 'UNKNOWN')}; "
            f"STATUS={person.get('status', 'UNKNOWN')}; HP={person.get('hp', 'UNKNOWN')}; "
            f"NEXT_WAYPOINT={person.get('next_waypoint', 'NONE')}; ASSIGNED_EXIT={person.get('assigned_exit', 'NONE')}; "
            f"ROUTE_PREVIEW={route_preview}"
        ),
    )


def build_person_path_response(person: dict) -> str:
    route_preview = person.get("route_preview") or "No active route"
    return render_directive(
        f"EVACUATION PATH READY: {person.get('name', 'UNKNOWN').upper()}",
        f"KEEP {person.get('name', 'UNKNOWN').upper()} ON ROUTE TO {person.get('assigned_exit', 'NONE').upper()}",
        (
            f"CURRENT_ZONE={person.get('zone', 'UNKNOWN')}; NEXT_WAYPOINT={person.get('next_waypoint', 'NONE')}; "
            f"ASSIGNED_EXIT={person.get('assigned_exit', 'NONE')}; ROUTE_PREVIEW={route_preview}; "
            f"STATUS={person.get('status', 'UNKNOWN')}"
        ),
    )


def build_agent_workflow_response() -> str:
    workflow_summary = get_manager_team_workflow_summary()
    return render_directive(
        "AGENT WORKFLOW MAP READY",
        "RUN MANAGER ORCHESTRATION: ROUTING TEAM -> AI EDIT TEAM -> AI STACK & FRONTEND TEAM -> VERIFICATION",
        (
            f"{workflow_summary}; INSTALLED_RUNTIME=OLLAMA, LANGCHAIN, CREWAI, LANGGRAPH, FASTAPI, REACT"
        ),
    )


def render_directive(status: str, action: str, advisory: str) -> str:
    return (
        "[INFERNALX DIRECTIVE]\n"
        f"STATUS: {status}\n"
        f"MACRO-ACTION: {action}\n"
        f"ADVISORY: {advisory}"
    )


def build_response_state(state):
    stats = state.get("stats", {})
    sensor_summary = state.get("sensor_pipeline", {}).get("summary", {})
    fire_zones = state.get("active_fire_zones", [])
    blocked_exits = state.get("blocked_exits", [])
    critical_zone = sensor_summary.get("highest_risk_zone")
    if not critical_zone and fire_zones:
        zone_counts = {}
        zone_rects = state.get("zones", {})
        for gx, gy in state.get("fire_cells", []):
            px = gx * GRID_SIZE + (GRID_SIZE / 2)
            py = gy * GRID_SIZE + (GRID_SIZE / 2)
            for zone_name, rect in zone_rects.items():
                if rect_contains(rect, px, py):
                    zone_counts[zone_name] = zone_counts.get(zone_name, 0) + 1
                    break
        critical_zone = max(zone_counts, key=zone_counts.get) if zone_counts else fire_zones[0]
    if not critical_zone:
        critical_zone = "NONE"
    highest_probability = sensor_summary.get("highest_probability", 0.0)
    return {
        "alive": stats.get("alive", 0),
        "evacuated": stats.get("evacuated", 0),
        "trapped": stats.get("trapped", 0),
        "panicking": stats.get("panicking", 0),
        "fire_zones": fire_zones,
        "blocked_exits": blocked_exits,
        "critical_zone": critical_zone,
        "highest_probability": highest_probability,
        "suppression_active": len(state.get("water_cells", [])) > 0,
    }


def crew_brief_is_fresh(agent_brief: dict, max_age_seconds: float = 18.0) -> bool:
    updated_at = float(agent_brief.get("updated_at") or 0.0)
    return updated_at > 0 and (time.time() - updated_at) <= max_age_seconds


def is_explicit_suppression_command(query_text: str) -> bool:
    lowered = query_text.lower().strip()
    if any(token in lowered for token in ["?", "what", "which", "how many", "is the", "are the", "should i", "do we need"]):
        return False
    action_verbs = [
        "extinguish",
        "suppress",
        "deploy",
        "activate",
        "turn on",
        "turn off",
        "start",
        "engage",
        "contain",
        "cool",
        "put out",
        "put off",
        "stop fire",
        "kill fire",
    ]
    action_objects = ["fire", "sprinkler", "sprinklers", "suppression", "water"]
    return any(verb in lowered for verb in action_verbs) and any(obj in lowered for obj in action_objects)


def suppression_requires_full_clear(query_text: str) -> bool:
    lowered = query_text.lower().strip()
    full_clear_markers = [
        "completely",
        "fully",
        "full clear",
        "turn off fire",
        "turn off the fire",
        "stop fire completely",
        "extinguish all",
        "put out all",
        "kill fire completely",
        "fast and effectively",
        "low water",
    ]
    return any(marker in lowered for marker in full_clear_markers)


def build_generic_state_fallback(state) -> str:
    snapshot = build_response_state(state)
    fire_zones = snapshot["fire_zones"]
    if fire_zones:
        return render_directive(
            "LIVE STATE AVAILABLE",
            f"CONTAIN FIRE IN {', '.join(fire_zones).upper()} AND MAINTAIN EVACUATION ROUTING",
            f"CRITICAL_ZONE={snapshot['critical_zone']}; BLOCKED_EXITS={snapshot['blocked_exits'] or ['NONE']}; TRAPPED={snapshot['trapped']}; ALIVE={snapshot['alive']}",
        )
    return render_directive(
        "LIVE STATE AVAILABLE",
        "MAINTAIN PASSIVE MONITORING AND KEEP ALL RESPONSE SYSTEMS ON STANDBY",
        f"ALIVE={snapshot['alive']}; EVACUATED={snapshot['evacuated']}; BLOCKED_EXITS={snapshot['blocked_exits'] or ['NONE']}",
    )


def build_deterministic_operator_response(query_text: str, state) -> Optional[str]:
    return None
    
    lowered = query_text.lower()
    snapshot = build_response_state(state)
    fire_zones = snapshot["fire_zones"]
    fire_zone_text = fire_zones if fire_zones else [snapshot["critical_zone"]]
    blocked_exits = snapshot["blocked_exits"]
    critical_zone = snapshot["critical_zone"]
    trapped = snapshot["trapped"]
    suppression_active = snapshot["suppression_active"]

    person_lookup_intent = any(
        phrase in lowered
        for phrase in [
            "where is",
            "which portion",
            "which zone",
            "status of",
            "person status",
            "occupant status",
            "track",
            "locate",
            "janitor",
            "jo",
            "variski",
        ]
    )
    person_path_intent = any(
        phrase in lowered
        for phrase in ["leaving path", "exit path", "evacuation path", "route", "path", "next waypoint"]
    )

    if any(word in lowered for word in ["agent", "agents", "team", "manager", "workflow", "plugin", "plugins", "tech stack"]):
        if any(word in lowered for word in ["installed", "procedure", "orchestrate", "orchestration", "flow", "workflow", "who"]):
            return build_agent_workflow_response()

    if person_lookup_intent or person_path_intent:
        people_matches = find_people_for_query(query_text, state)
        if people_matches:
            primary = people_matches[0]
            if person_path_intent:
                return build_person_path_response(primary)
            return build_person_status_response(primary)

        if any(token in lowered for token in ["jo", "variski", "janitor", "person", "occupant", "employee"]):
            sample_people = ", ".join(p.get("name", "UNKNOWN") for p in state.get("people", [])[:6])
            return render_directive(
                "PERSON LOOKUP INCOMPLETE",
                "REQUEST PERSON BY EXACT NAME OR ROLE PLUS INDEX",
                f"SAMPLES={sample_people or 'NONE'}; TIP=USE QUERIES LIKE 'WHERE IS JANITOR 5' OR 'SHOW LEAVING PATH FOR ANALYST 3'",
            )

    if (
        any(phrase in lowered for phrase in ["status report", "overall status", "current status", "facility status"])
        or ("status" in lowered and any(token in lowered for token in ["what", "show", "give", "tell", "report"]))
    ):
        return render_directive(
            "FACILITY STATUS REPORT READY",
            f"MAINTAIN FOCUS ON {critical_zone.upper() if critical_zone != 'NONE' else 'FULL FACILITY MONITORING'}",
            (
                f"ALIVE={snapshot['alive']}; EVACUATED={snapshot['evacuated']}; TRAPPED={trapped}; PANICKING={snapshot['panicking']}; "
                f"CRITICAL_ZONE={critical_zone}; FIRE_ZONES={fire_zone_text}; BLOCKED_EXITS={blocked_exits or ['NONE']}; "
                f"SUPPRESSION_ACTIVE={suppression_active}; SENSOR_RISK={snapshot['highest_probability']}%"
            ),
        )

    if any(
        phrase in lowered
        for phrase in [
            "immediate strategy",
            "immediate plan",
            "next two minutes",
            "what should we do now",
            "autonomous strategy",
            "response strategy",
        ]
    ):
        if fire_zones:
            return render_directive(
                "IMMEDIATE RESPONSE STRATEGY READY",
                f"CONTAIN FIRE IN {', '.join(fire_zones).upper()} AND PROTECT PRIMARY EVACUATION ROUTES",
                (
                    f"CRITICAL_ZONE={critical_zone}; FIRE_ZONES={fire_zone_text}; BLOCKED_EXITS={blocked_exits or ['NONE']}; "
                    f"TRAPPED={trapped}; PANICKING={snapshot['panicking']}; SUPPRESSION_ACTIVE={suppression_active}"
                ),
            )
        return render_directive(
            "IMMEDIATE RESPONSE STRATEGY READY",
            "MAINTAIN PASSIVE MONITORING, KEEP EXITS CLEAR, AND HOLD SUPPRESSION ON STANDBY",
            (
                f"ALIVE={snapshot['alive']}; EVACUATED={snapshot['evacuated']}; TRAPPED={trapped}; "
                f"BLOCKED_EXITS={blocked_exits or ['NONE']}; SENSOR_RISK={snapshot['highest_probability']}%"
            ),
        )

    if any(phrase in lowered for phrase in ["most critical", "critical zone", "highest risk", "which zone is critical", "zone is most critical", "critical now"]):
        return render_directive(
            "CRITICAL ZONE ANALYSIS COMPLETE",
            f"PRIORITIZE {critical_zone.upper()} FOR CONTAINMENT AND ROUTE PROTECTION",
            f"ACTIVE_FIRE_ZONES={fire_zone_text}; SENSOR_RISK={snapshot['highest_probability']}%",
        )

    if "trapped" in lowered and any(token in lowered for token in ["how many", "count", "occupants", "people", "persons"]):
        return render_directive(
            "OCCUPANT TRAP COUNT AVAILABLE",
            f"PRIORITIZE EXTRACTION SUPPORT FOR {trapped} TRAPPED OCCUPANTS",
            f"ALIVE={snapshot['alive']}; PANICKING={snapshot['panicking']}; CRITICAL_ZONE={critical_zone}",
        )

    if "sprinkler active" in lowered or "sprinklers active" in lowered or "is suppression active" in lowered:
        return render_directive(
            "SUPPRESSION SYSTEM CHECK COMPLETE",
            "MAINTAIN CURRENT SUPPRESSION FLOW" if suppression_active else "KEEP SPRINKLERS ON STANDBY",
            f"SUPPRESSION_ACTIVE={suppression_active}; FIRE_ZONES={fire_zone_text}",
        )

    if (
        "blocked exit" in lowered
        or "blocked exits" in lowered
        or "which exits are blocked" in lowered
        or ("exit" in lowered and "blocked" in lowered)
    ):
        blocked_text = ", ".join(blocked_exits) if blocked_exits else "NONE"
        action_line = (
            f"AVOID {blocked_text} AND MAINTAIN REROUTING"
            if blocked_exits
            else "KEEP ALL EXITS OPEN AND CONTINUE NORMAL EVACUATION ROUTING"
        )
        return render_directive(
            "EXIT AVAILABILITY CHECK COMPLETE",
            action_line,
            f"BLOCKED_EXITS={blocked_text}; FIRE_ZONES={fire_zone_text}",
        )

    if (
        "should i deploy suppression" in lowered
        or "deploy suppression now" in lowered
        or "do we need suppression" in lowered
        or "should we suppress" in lowered
    ):
        if fire_zones:
            return render_directive(
                "SUPPRESSION RECOMMENDED",
                f"DEPLOY TARGETED SPRINKLERS TO {', '.join(fire_zones).upper()}",
                f"CRITICAL_ZONE={critical_zone}; BLOCKED_EXITS={blocked_exits or ['NONE']}",
            )
        return render_directive(
            "SUPPRESSION NOT REQUIRED",
            "KEEP SPRINKLERS ON STANDBY AND CONTINUE MONITORING",
            "NO ACTIVE FIRE ZONES DETECTED",
        )

    return None


def ollama_model_exists(model_name: str) -> bool:
    try:
        result = subprocess.run(
            ["ollama", "show", model_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


async def normalize_design_to_layout(prompt_text: str, source: str):
    raw = await asyncio.to_thread(llm_chain.invoke, prompt_text)
    parsed = json.loads(extract_json_block(raw))
    result = sim_engine.apply_layout(
        parsed.get("name", "Custom Layout"),
        parsed["zones"],
        parsed["exits"],
        population=parsed.get("population"),
        source=source,
        notes=parsed.get("notes"),
    )
    return result, parsed


def model_to_dict(model_obj):
    if hasattr(model_obj, "model_dump"):
        return model_obj.model_dump()
    return model_obj.dict()


@app.post("/api/upload_map")
async def process_ocr_map(layout: LayoutUpload):
    """
    Accepts a structured layout or a textual design brief and applies it as the
    active navigation model. This replaces the old mock-only path.
    """
    try:
        if layout.layout:
            payload = layout.layout
            result = sim_engine.apply_layout(
                payload.name,
                {name: model_to_dict(rect) for name, rect in payload.zones.items()},
                {name: model_to_dict(rect) for name, rect in payload.exits.items()},
                population=payload.population,
                source="structured",
                notes=payload.notes,
            )
            return {"status": "success", "layout": result}

        if layout.design_text:
            prompt_text = (
                "Normalize this building design into strict JSON only. "
                "Return exactly this schema: "
                '{"name": string, "population": number, "notes": string, "zones": {"Zone Name": {"x": number, "y": number, "w": number, "h": number}}, "exits": {"Exit Name": {"x": number, "y": number, "w": number, "h": number}}}. '
                "Use integer coordinates and keep zone/exits names concise.\n\n"
                f"DESIGN BRIEF:\n{layout.design_text}"
            )
            result, parsed = await normalize_design_to_layout(prompt_text, "llm-normalized")
            return {"status": "success", "layout": result, "normalized": parsed}

        if layout.image_base64:
            if not ollama_model_exists(VISION_MODEL_NAME):
                return {
                    "status": "needs_layout",
                    "message": "Image upload was received, but no vision-capable Ollama model is installed here. Please send a structured layout or a text design brief for normalization.",
                }
            payload = {
                "model": VISION_MODEL_NAME,
                "prompt": (
                    "You are converting a floor-plan image into strict JSON only. "
                    'Return exactly: {"name": string, "population": number, "notes": string, "zones": {"Zone Name": {"x": number, "y": number, "w": number, "h": number}}, '
                    '"exits": {"Exit Name": {"x": number, "y": number, "w": number, "h": number}}}. '
                    "Use integer coordinates and include at least one zone and one exit."
                ),
                "images": [layout.image_base64],
                "stream": False,
                "options": {"temperature": 0.0},
            }
            vision_response = await asyncio.to_thread(
                requests.post,
                OLLAMA_URL,
                json=payload,
                timeout=90.0,
            )
            vision_response.raise_for_status()
            raw = vision_response.json().get("response", "")
            parsed = json.loads(extract_json_block(raw))
            result = sim_engine.apply_layout(
                parsed.get("name", "Image Layout"),
                parsed["zones"],
                parsed["exits"],
                population=parsed.get("population"),
                source="vision-normalized",
                notes=parsed.get("notes"),
            )
            return {"status": "success", "layout": result, "normalized": parsed}

        return {"status": "error", "message": "No layout data supplied."}
    except Exception as e:
        print(f"Layout ingestion error: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/summarize")
async def summarize_situation():
    with sim_engine.lock:
        state = sim_engine.get_state()
    
    # Condense State for Context
    alive = state["stats"]["alive"]
    escaped = state["stats"]["evacuated"]
    trapped = state["stats"]["trapped"]
    panicking = state["stats"]["panicking"]
    fire_zones = state["active_fire_zones"]
    water_active = len(state["water_cells"]) > 0
    layout = state.get("layout", {})
    agent_brief = state.get("agent_brief", {})
    sensor_summary = state.get("sensor_pipeline", {}).get("summary", {})
    primary_exit = agent_brief.get("primary_exit", "NONE")
    sprinkler_plan = agent_brief.get("sprinklers", "NONE")
    layout_name = layout.get("name", "UNKNOWN")

    if not fire_zones:
        summary = (
            "[INFERNALX DIRECTIVE]\n"
            "STATUS: NO ACTIVE FIRE DETECTED\n"
            "MACRO-ACTION: MAINTAIN PASSIVE MONITORING AND KEEP SUPPRESSION ON STANDBY\n"
            f"ADVISORY: LAYOUT={layout_name}; ALIVE={alive}; EVACUATED={escaped}; TRAPPED={trapped}; PANICKING={panicking}"
        )
        return {"summary": summary}

    brief_is_fresh = crew_brief_is_fresh(agent_brief)
    status_line = agent_brief.get("status", "ACTIVE FIRE RESPONSE IN PROGRESS") if brief_is_fresh else "UNKNOWN"
    if not status_line or status_line == "UNKNOWN":
        status_line = f"SENSOR FUSION CONFIRMS ACTIVE FIRE IN {sensor_summary.get('highest_risk_zone', fire_zones[0])}"

    if not brief_is_fresh:
        sprinkler_plan = "STATE-DRIVEN CONTAINMENT"
    if not brief_is_fresh or not primary_exit or primary_exit == "NONE":
        primary_exit = "DYNAMIC EXIT RECOMPUTE IN PROGRESS"

    action_line = (
        f"GUIDE OCCUPANTS TO {primary_exit} AND CONTAIN FIRE IN {', '.join(fire_zones).upper()}"
        if "RECOMPUTE" not in primary_exit
        else f"CONTAIN FIRE IN {', '.join(fire_zones).upper()} AND RECALCULATE A SAFE PRIMARY EXIT"
    )
    advisory_bits = [
        f"LAYOUT={layout_name}",
        f"FIRE_ZONES={', '.join(fire_zones)}",
        f"SPRINKLERS={'ACTIVE' if water_active else 'STANDBY'}",
        f"PRIMARY_EXIT={primary_exit}",
        f"TARGETED_SUPPRESSION={sprinkler_plan}",
        f"SENSOR_RISK={sensor_summary.get('highest_risk_zone', 'NONE')}",
        f"SENSOR_PROBABILITY={sensor_summary.get('highest_probability', 0.0)}",
        f"BLOCKED_EXITS={sensor_summary.get('blocked_exits', [])}",
        f"ALIVE={alive}",
        f"EVACUATED={escaped}",
        f"TRAPPED={trapped}",
        f"PANICKING={panicking}",
    ]
    summary = (
        "[INFERNALX DIRECTIVE]\n"
        f"STATUS: {status_line}\n"
        f"MACRO-ACTION: {action_line}\n"
        f"ADVISORY: {'; '.join(advisory_bits)}"
    )
    return {"summary": summary}

@app.post("/api/chat")
async def chat_interaction(payload_input: dict):
    query = (payload_input.get("message") or payload_input.get("query") or "").strip()
    with sim_engine.lock:
        state = sim_engine.get_state()

    if not query:
        return {
            "response": (
                "[INFERNALX DIRECTIVE]\n"
                "STATUS: OPERATOR INPUT REQUIRED\n"
                "MACRO-ACTION: PROVIDE A FIRE CONTROL OR STATUS REQUEST\n"
                "ADVISORY: EXAMPLE COMMANDS: EXTINGUISH FIRE IN BLOCK ONE | WHAT IS THE STATUS OF BLOCK TWO"
            )
        }
    
    # Contextualize chat
    alive = state["stats"]["alive"]
    escaped = state["stats"]["evacuated"]
    trapped = state["stats"]["trapped"]
    fire_zones = state["active_fire_zones"]
    layout = state.get("layout", {})
    agent_brief = state.get("agent_brief", {})
    sensor_summary = state.get("sensor_pipeline", {}).get("summary", {})
    
    # Read last 10 lines of incident log for persistent memory
    incident_history = ""
    try:
        if os.path.exists("incident_report.log"):
            with open("incident_report.log", "r") as f:
                lines = f.readlines()
                incident_history = "".join(lines[-5:])  # Only last 5 lines â€” shorter prompt = faster response
    except: pass

    # Autonomous Action Interception
    intercepted_action = False
    lower_query = query.lower()
    target_areas = extract_area_targets(lower_query)
    
    status_keywords = [
        "status", "what is happening", "what's happening", "what is the condition",
        "condition", "state of", "report on", "how is"
    ]

    deterministic_reply = build_deterministic_operator_response(lower_query, state)
    if deterministic_reply:
         pass # Let the AI LLM generate the full dynamic response instead!

    if is_explicit_suppression_command(lower_query):
        intercepted_action = True
        full_clear = suppression_requires_full_clear(lower_query)
        with sim_engine.lock:
            targets = target_areas or list(sim_engine.active_fire_zones) or ["facility"]
            valid_targets = set(ZONES.keys()) | set(EXITS.keys()) | {"facility", "all", "everywhere"}
            invalid_targets = [target for target in targets if target not in valid_targets]
            if invalid_targets:
                update_llm_metrics("deterministic")
                return {
                    "response": render_directive(
                        "INVALID SUPPRESSION TARGET",
                        "USE A VALID ZONE OR EXIT NAME BEFORE DISPATCHING SUPPRESSION",
                        f"INVALID={invalid_targets}; VALID_ZONE_COUNT={len(ZONES)}; VALID_EXIT_COUNT={len(EXITS)}",
                    )
                }
            fire_before = len(sim_engine.fire_cells)
            for target in targets:
                sim_engine.deploy_suppression(target, force_clear=full_clear)
            fire_after = len(sim_engine.fire_cells)
            cleared = max(0, fire_before - fire_after)
            msg = f"COMMAND RECEIVED: TARGETED FIRE SUPPRESSION DEPLOYED TO {', '.join(targets).upper()}."
            sim_engine.global_events.append(time.strftime("[%H:%M:%S]") + " " + msg)
            sim_engine.log_incident(msg)
        update_llm_metrics("deterministic")
        return {
            "response": (
                "[INFERNALX DIRECTIVE]\n"
                f"STATUS: {'FIRE CLEAR EXECUTED' if full_clear else 'SUPPRESSION COMMAND ACCEPTED'}\n"
                f"MACRO-ACTION: {'FULLY EXTINGUISH FIRE IN' if full_clear else 'DEPLOY SPRINKLERS TO'} {', '.join(targets).upper()}\n"
                f"ADVISORY: FIRE_CELLS_BEFORE={fire_before}; FIRE_CELLS_AFTER={fire_after}; CLEARED={cleared}; WATER_MODE={'LOW-WATER FAST CLEAR' if full_clear else 'TARGETED SPRAY'}"
            )
        }

    # Build area context for the LLM if a specific zone was mentioned
    area_context_suffix = ""
    if target_areas and any(kw in lower_query for kw in status_keywords):
        summaries = summarize_area_status(state, target_areas)
        area_context_suffix = f"[AREA STATUS: {' | '.join(summaries)}]\n"

    context = f"[SYSTEM STATE: {alive} ALIVE, {escaped} ESCAPED, {trapped} TRAPPED. FIRE: {fire_zones}]\n"
    if layout:
        context += f"[LAYOUT: {layout.get('name', 'UNKNOWN')} | SOURCE: {layout.get('source', 'UNKNOWN')} | REV: {layout.get('revision', 0)}]\n"
    if agent_brief:
        context += f"[CREW OUTPUT: STATUS={agent_brief.get('status', 'UNKNOWN')} | SPRINKLERS={agent_brief.get('sprinklers', 'NONE')} | EXIT={agent_brief.get('primary_exit', 'NONE')}]\n"
    if sensor_summary:
        context += (
            f"[SENSOR FUSION: TOP_ZONE={sensor_summary.get('highest_risk_zone', 'NONE')} | "
            f"PROBABILITY={sensor_summary.get('highest_probability', 0.0)} | "
            f"BLOCKED_EXITS={sensor_summary.get('blocked_exits', [])} | "
            f"TRACKED={sensor_summary.get('occupants_tracked', 0)}]\n"
        )
    context += f"[INCIDENT HISTORY (LAST 10 ENTRIES)]:\n{incident_history}\n"
    if area_context_suffix:
        context += area_context_suffix
    if intercepted_action:
        context += "[SYSTEM ACTION LOGGED: YOU HAVE DEPLOYED WATER ONSITE TO GRADUALLY EXTINGUISH FIRES.]\n"

    rule_directive = INFERNALX_SYSTEM_DIRECTIVE
    full_prompt = f"CONTEXT: {context}\n{rule_directive}\nOPERATOR: {query}"
    
    try:
        chat_prompt = PromptTemplate.from_template("{prompt}")
        chain = chat_prompt | llm_chain | StrOutputParser()
        primary_start = time.time()
        resp_text = await asyncio.wait_for(
            asyncio.to_thread(chain.invoke, {"prompt": full_prompt}),
            timeout=CHAT_LLM_TIMEOUT_SECONDS,
        )
        primary_latency_ms = (time.time() - primary_start) * 1000.0
        resp_text = (resp_text or "").strip()
        logger.info(f"LLM primary responded in {primary_latency_ms:.0f}ms: {resp_text[:120]!r}")
        if not resp_text:
            logger.warning("Primary LLM returned empty response. Using fallback.")
            update_llm_metrics("state_fallback", latency_ms=primary_latency_ms, error="empty-primary-response")
            return {"response": build_generic_state_fallback(state)}
        update_llm_metrics("llm_primary", latency_ms=primary_latency_ms)
        return {"response": resp_text}
    except asyncio.TimeoutError as e:
        logger.warning(f"Primary LLM timed out after {CHAT_LLM_TIMEOUT_SECONDS}s: {e}")
        update_llm_metrics("llm_primary", timeout=True, error="timeout")
        try:
            chat_prompt = PromptTemplate.from_template("{prompt}")
            fallback_chain = chat_prompt | fallback_llm_chain | StrOutputParser()
            fallback_start = time.time()
            resp_text = await asyncio.wait_for(
                asyncio.to_thread(fallback_chain.invoke, {"prompt": full_prompt}),
                timeout=CHAT_LLM_TIMEOUT_SECONDS,
            )
            fallback_latency_ms = (time.time() - fallback_start) * 1000.0
            if not is_valid_directive_response(resp_text, prompt_version=CHAT_PROMPT_VERSION):
                update_llm_metrics("state_fallback", latency_ms=fallback_latency_ms, error="invalid-fallback-response")
                return {"response": build_generic_state_fallback(state)}
            update_llm_metrics("llm_fallback", latency_ms=fallback_latency_ms)
            return {"response": resp_text.strip()}
        except Exception as fallback_error:
            logger.error(f"Fallback model failed: {fallback_error}")
            update_llm_metrics("state_fallback", error=str(fallback_error))
            fallback = (
                render_directive(
                    "OFFLINE MODE ACTIVE",
                    "SUPPRESSION COMMAND EXECUTED AND STATE RESPONSE RETURNED",
                    f"TARGETS={target_areas or fire_zones or ['facility']}",
                )
                if intercepted_action
                else build_generic_state_fallback(state)
            )
            return {"response": fallback}
    except Exception as e:
        logger.error(f"Chat API Error (LangChain): {e}")
        update_llm_metrics("state_fallback", error=str(e))
        fallback = (
            render_directive(
                "OFFLINE MODE ACTIVE",
                "SUPPRESSION COMMAND EXECUTED AND STATE RESPONSE RETURNED",
                f"TARGETS={target_areas or fire_zones or ['facility']}",
            )
            if intercepted_action
            else build_generic_state_fallback(state)
        )
        return {"response": fallback}

# ---------------------------------------------------------------------------
# STREAMING CHAT â€” tokens appear on screen as they are generated
# ---------------------------------------------------------------------------

# Zones that are actual rooms (not corridors/exits) â€” used for deterministic layout answers
_ROOM_ZONES = [z for z in ZONES if not any(kw in z for kw in ("Corridor", "Hub", "Exit"))]
_ALL_ZONE_NAMES = list(ZONES.keys())
_EXIT_NAMES = list(EXITS.keys())


def _is_people_status_query(q: str) -> bool:
    """True ONLY if the question is specifically about people/personnel counts."""
    people_phrases = [
        "how many people", "how many person", "how many occupant", "how many personnel",
        "how many alive", "how many trapped", "how many evacuated", "how many panick",
        "number of people", "number of person", "number of occupant",
        "people status", "personnel status", "occupant status",
        "update on people", "update on personnel", "update on occupant",
        "people inside", "people in the building", "anyone trapped", "anyone alive",
        "who is trapped", "who is alive", "who is panick",
    ]
    return any(phrase in q for phrase in people_phrases)


def _is_layout_query(q: str) -> bool:
    """True if the question is about building layout, zones, blocks, floors, rooms."""
    layout_phrases = [
        "how many zone", "how many block", "how many room", "how many floor", "how many area",
        "how many section", "how many exit", "how many door", "how many wing",
        "list zone", "list block", "list room", "list area", "list exit",
        "which zone", "which block", "which room", "which area",
        "zone exist", "zone available", "zone name",
        "block exist", "block available", "building layout", "building structure",
        "building map", "building plan", "building have", "building contain",
        "zone in the building", "block in the building", "room in the building",
        "exit in the building", "exits in the building", "areas in the building",
    ]
    return any(phrase in q for phrase in layout_phrases)


def _build_rich_context(state: dict, alive: int, escaped: int, trapped: int,
                        panicking: int, fire_zones: list) -> str:
    """Build a comprehensive context string including layout, occupancy, and fire data."""
    # Zone-level occupant distribution from state
    zone_pops: dict = state.get("zone_population", {})

    fire_desc = f"fire active in: {', '.join(fire_zones)}" if fire_zones else "no active fire"

    # Build room zone data
    room_info_parts = []
    for z in _ROOM_ZONES:
        pop = zone_pops.get(z, 0)
        room_info_parts.append(f"{z}({pop} people)")

    zone_list_str = ", ".join(_ROOM_ZONES)
    exit_list_str = ", ".join(_EXIT_NAMES)

    ctx = (
        f"BUILDING_LAYOUT: {len(_ROOM_ZONES)} named zones, {len(_EXIT_NAMES)} exits. "
        f"ZONES: {zone_list_str}. "
        f"EXITS: {exit_list_str}. "
        f"CORRIDORS: West Corridor, Central Hub, East Corridor. "
        f"TOTAL_BLOCKS(zones+corridors+exits)={len(ZONES)+len(EXITS)}. "
        f"PEOPLE: {alive} alive, {escaped} evacuated, {trapped} trapped, {panicking} panicking. "
        f"FIRE: {fire_desc}. "
        f"ZONE_OCCUPANCY: {', '.join(room_info_parts) if room_info_parts else 'not available'}."
    )
    return ctx


@app.post("/api/chat/stream")
async def chat_stream(payload_input: dict):
    """Server-Sent Events streaming endpoint. Each token is sent immediately."""
    query = (payload_input.get("message") or payload_input.get("query") or "").strip()
    with sim_engine.lock:
        state = sim_engine.get_state()

    if not query:
        async def _empty():
            yield f'data: {json.dumps({"token": "Please type a message first."})}\n\n'
            yield "data: [DONE]\n\n"
        return StreamingResponse(_empty(), media_type="text/event-stream")

    alive     = state["stats"]["alive"]
    escaped   = state["stats"]["evacuated"]
    trapped   = state["stats"]["trapped"]
    panicking = state["stats"].get("panicking", 0)
    fire_zones = state["active_fire_zones"]
    agent_brief    = state.get("agent_brief", {})
    sensor_summary = state.get("sensor_pipeline", {}).get("summary", {})
    lower_query = query.lower()

    # ---- 1. INSTANT: suppression commands ----
    target_areas = extract_area_targets(lower_query)
    if is_explicit_suppression_command(lower_query):
        full_clear = suppression_requires_full_clear(lower_query)
        with sim_engine.lock:
            targets = target_areas or list(sim_engine.active_fire_zones) or ["facility"]
            fire_before = len(sim_engine.fire_cells)
            for t in targets:
                sim_engine.deploy_suppression(t, force_clear=full_clear)
            fire_after = len(sim_engine.fire_cells)
            cleared = max(0, fire_before - fire_after)
            msg = f"SUPPRESSION DEPLOYED TO {', '.join(targets).upper()}."
            sim_engine.global_events.append(time.strftime("[%H:%M:%S]") + " " + msg)
            sim_engine.log_incident(msg)
        reply = (f"Deploying {'full clear' if full_clear else 'sprinklers'} to "
                 f"{', '.join(targets)}. {cleared} fire cells cleared. Monitoring response.")
        async def _det_supp():
            yield f'data: {json.dumps({"token": reply})}\n\n'
            yield "data: [DONE]\n\n"
        return StreamingResponse(_det_supp(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # ---- 2. INSTANT: people/personnel count questions ----
    if _is_people_status_query(lower_query):
        fire_desc = f"fire active in {', '.join(fire_zones)}" if fire_zones else "no active fire"
        reply = (f"{alive} people alive inside the building, {escaped} evacuated safely, "
                 f"{trapped} trapped, {panicking} panicking. Currently {fire_desc}. "
                 f"All {len(state.get('exits', {}))} exits are monitored.")
        async def _det_people():
            yield f'data: {json.dumps({"token": reply})}\n\n'
            yield "data: [DONE]\n\n"
        return StreamingResponse(_det_people(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # ---- 3. INSTANT: layout / zone / block questions answered from real data ----
    if _is_layout_query(lower_query):
        room_count   = len(_ROOM_ZONES)
        exit_count   = len(_EXIT_NAMES)
        zone_list_str = ", ".join(_ROOM_ZONES)
        exit_list_str = ", ".join(_EXIT_NAMES)
        reply = (
            f"The building has {room_count} named zones: {zone_list_str}. "
            f"There are also 3 circulation areas (West Corridor, Central Hub, East Corridor) "
            f"and {exit_count} dedicated exits: {exit_list_str}. "
            f"Total addressable blocks: {room_count + 3 + exit_count}."
        )
        async def _det_layout():
            yield f'data: {json.dumps({"token": reply})}\n\n'
            yield "data: [DONE]\n\n"
        return StreamingResponse(_det_layout(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # ---- 4. LLM for complex / open-ended questions â€” with FULL context ----
    rich_context = _build_rich_context(state, alive, escaped, trapped, panicking, fire_zones)
    if sensor_summary:
        rich_context += f" TOP_RISK_ZONE={sensor_summary.get('highest_risk_zone', 'none')}."
    if agent_brief:
        rich_context += f" SPRINKLER_STATUS={agent_brief.get('sprinklers', 'none')}."

    full_prompt = (
        f"{INFERNALX_SYSTEM_DIRECTIVE}\n"
        f"CONTEXT: {rich_context}\n"
        f"OPERATOR QUESTION: {query}\n"
        f"INFERNALX (answer in 2-3 sentences using only the context above):"
    )

    async def _stream_llm():
        try:
            resp = await asyncio.wait_for(
                asyncio.to_thread(
                    lambda: requests.post(
                        f"{OLLAMA_BASE_URL}/api/generate",
                        json={"model": MODEL_NAME, "prompt": full_prompt, "stream": True,
                              "options": {"num_predict": 80, "num_ctx": 1536, "temperature": 0.2}},
                        stream=True,
                        timeout=22,
                    )
                ),
                timeout=25,
            )
            for raw_line in resp.iter_lines():
                if not raw_line:
                    continue
                try:
                    chunk = json.loads(raw_line)
                except Exception:
                    continue
                token = chunk.get("response", "")
                if token:
                    yield f'data: {json.dumps({"token": token})}\n\n'
                if chunk.get("done"):
                    break
        except Exception as exc:
            logger.warning(f"Stream LLM error: {exc}")
            fire_desc = f"fire in {', '.join(fire_zones)}" if fire_zones else "no fire"
            fallback = f"{alive} alive, {escaped} evacuated, {trapped} trapped. {fire_desc}."
            yield f'data: {json.dumps({"token": fallback})}\n\n'
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        _stream_llm(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

