import asyncio
import os
import json
import math
import heapq
import time
import requests
import random
import threading
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ==========================================
# CONFIGURATION
# ==========================================
GRID_SIZE = 10
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "tinyllama"
PA_PROMPT_FILE = "pa_system_prompt.txt"

ZONES = {
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

EXITS = {
    "Exit Alpha North":   {"x":200,  "y":0,   "w":50, "h":50},
    "Exit Beta North":    {"x":475,  "y":0,   "w":50, "h":50},
    "Exit Delta North":   {"x":1025, "y":0,   "w":50, "h":50},
    "Exit Epsilon North": {"x":1300, "y":0,   "w":50, "h":50},
    "Exit Zeta South":    {"x":200,  "y":600, "w":50, "h":50},
    "Exit Eta South":     {"x":475,  "y":600, "w":50, "h":50},
    "Exit Iota South":    {"x":1025, "y":600, "w":50, "h":50},
    "Exit Kappa South":   {"x":1300, "y":600, "w":50, "h":50},
    "Exit West Hub":      {"x":50,   "y":300, "w":50, "h":50},
    "Exit East Hub":      {"x":1450, "y":300, "w":50, "h":50}
}

ADJACENCY = {
    "Zone Alpha (Executive)":   ["Exit Alpha North", "West Corridor"],
    "Zone Beta (Engineering)":  ["Exit Beta North", "West Corridor", "Zone Gamma (Datacenter)"],
    "Zone Gamma (Datacenter)":  ["Central Hub", "Zone Beta (Engineering)", "Zone Delta (Operations)"],
    "Zone Delta (Operations)":  ["Exit Delta North", "East Corridor", "Zone Epsilon (Logistics)", "Zone Gamma (Datacenter)"],
    "Zone Epsilon (Logistics)": ["Exit Epsilon North", "East Corridor", "Zone Delta (Operations)"],
    "West Corridor":            ["Exit West Hub", "Zone Alpha (Executive)", "Zone Beta (Engineering)", "Zone Zeta (Lobby)", "Zone Eta (R&D)", "Central Hub"],
    "Central Hub":              ["West Corridor", "East Corridor", "Zone Gamma (Datacenter)", "Zone Theta (Cafeteria)"],
    "East Corridor":            ["Exit East Hub", "Zone Delta (Operations)", "Zone Epsilon (Logistics)", "Zone Iota (Medical)", "Zone Kappa (Security)", "Central Hub"],
    "Zone Zeta (Lobby)":        ["Exit Zeta South", "West Corridor", "Zone Eta (R&D)"],
    "Zone Eta (R&D)":           ["Exit Eta South", "West Corridor", "Zone Zeta (Lobby)", "Zone Theta (Cafeteria)"],
    "Zone Theta (Cafeteria)":   ["Central Hub", "Zone Eta (R&D)", "Zone Iota (Medical)"],
    "Zone Iota (Medical)":      ["Exit Iota South", "East Corridor", "Zone Theta (Cafeteria)", "Zone Kappa (Security)"],
    "Zone Kappa (Security)":    ["Exit Kappa South", "East Corridor", "Zone Iota (Medical)"],
    "Exit Alpha North":         ["Zone Alpha (Executive)"],
    "Exit Beta North":          ["Zone Beta (Engineering)"],
    "Exit Delta North":         ["Zone Delta (Operations)"],
    "Exit Epsilon North":       ["Zone Epsilon (Logistics)"],
    "Exit Zeta South":          ["Zone Zeta (Lobby)"],
    "Exit Eta South":           ["Zone Eta (R&D)"],
    "Exit Iota South":          ["Zone Iota (Medical)"],
    "Exit Kappa South":         ["Zone Kappa (Security)"],
    "Exit West Hub":            ["West Corridor"],
    "Exit East Hub":            ["East Corridor"]
}

def rect_contains(rect, pt_x, pt_y):
    return rect["x"] <= pt_x <= rect["x"] + rect["w"] and rect["y"] <= pt_y <= rect["y"] + rect["h"]

def rect_intersects(r1, r2):
    return not (r2["x"] > r1["x"] + r1["w"] or 
                r2["x"] + r2["w"] < r1["x"] or 
                r2["y"] > r1["y"] + r1["h"] or
                r2["y"] + r2["h"] < r1["y"])

class Person:
    def __init__(self, pid, name, role_type, x, y):
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
        self.speed = 2.0
        self.last_pa_time = 0
        self.next_roam_time = time.time() + random.uniform(5, 20)
        self.last_pos = (x, y)
        self.stuck_count = 0

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
        self.recent_logs = {}
        self.last_global_pa_time = 0.0  # System-wide PA throttle
        self.suppression_mode = False # REALISM: Gradual fire removal
        self.sitrep = "FACILITY SECURE. INFERNALX STANDBY."

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

    def populate(self):
        with self.lock:
            self.people = []
            roles = ["Worker", "Worker", "Worker", "Tech Support", "Manager", "Security Guard", "Cleaner"]
            for i in range(1, 101): # Spawn 100 people
                role_type = random.choice(roles)
                zone_name = random.choice(list(ZONES.keys()))
                z = ZONES[zone_name]
                x = random.randint(z["x"] + 15, z["x"] + z["w"] - 15)
                y = random.randint(z["y"] + 15, z["y"] + z["h"] - 15)
                self.people.append(Person(f"p{i}", f"{role_type} {i}", role_type, x, y))
            
            self.fire_cells.clear()
            self.water_cells.clear()
            self.pa_announcements.clear()
            self.global_events.clear()
            self.last_global_pa_time = 0.0 # Reset throttle
            self.suppression_mode = False # Reset suppression
            self.start_time = time.time()
            self.log_event("FACILITY ONLINE. 100 PERSONNEL DETECTED AND TRACKED.")

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
            
            neighbors = ADJACENCY.get(node, [])
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

    def load_scenario(self, scenario_name):
        with self.lock:
            self.scenario = scenario_name
            self.people.clear()
            self.fire_cells.clear()
            self.water_cells.clear()
            self.pa_announcements.clear()
            
            if scenario_name in ["OPERATOR", "DEFAULT"]:
                self.populate()
            elif scenario_name == "CAMERA":
                self.people = [
                    Person("p1", "Security Guard", "Security Guard", 1300, 300),
                    Person("p2", "Janitor", "Cleaner", 200, 110)
                ]
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

    def deploy_suppression(self, zone_name):
        all_rects = {**ZONES, **EXITS}
        if zone_name in all_rects:
            rect = all_rects[zone_name]
            gx_start = int(rect["x"] // GRID_SIZE)
            gx_end = int((rect["x"] + rect["w"]) // GRID_SIZE)
            gy_start = int(rect["y"] // GRID_SIZE)
            gy_end = int((rect["y"] + rect["h"]) // GRID_SIZE)
            
            new_water = set()
            # Precision suppression: Only target cells actively on fire (No more 'Flood Disaster')
            with self.lock:
                for dx in range(gx_start, gx_end + 1):
                    for dy in range(gy_start, gy_end + 1):
                        if (dx, dy) in self.fire_cells:
                            new_water.add((dx, dy))
                            # Add 1 grid radius for realistic spread margin without flooding entire rooms
                            for ox in [-1, 0, 1]:
                                for oy in [-1, 0, 1]:
                                    nc = (dx+ox, dy+oy)
                                    if gx_start <= nc[0] <= gx_end and gy_start <= nc[1] <= gy_end:
                                        new_water.add(nc)
                            
                self.water_cells.update(new_water)
                for w in new_water:
                    if w in self.fire_cells:
                        self.fire_cells.remove(w)

    def update_cycle(self):
        with self.lock:
            elapsed = time.time() - self.start_time
            
            # 1. Spread Fire
            if elapsed > 2 and len(self.fire_cells) > 0 and random.random() < 0.2: # Slower spread
                new_cells = set()
                candidates = random.sample(list(self.fire_cells), min(50, len(self.fire_cells)))
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

            # 1b. Gradual Suppression Mode (REALISM)
            if self.suppression_mode and self.fire_cells:
                # Remove 15 cells per frame for a "fading" effect
                to_kill = random.sample(list(self.fire_cells), min(len(self.fire_cells), 15))
                for c in to_kill:
                    self.fire_cells.remove(c)
                if not self.fire_cells:
                    self.suppression_mode = False
                    self.active_fire_zones = []

            # Update High-Level Zones status for AI/Alerts
            current_fire_zones = set()
            for (gx, gy) in self.fire_cells:
                px, py = gx * GRID_SIZE + 5, gy * GRID_SIZE + 5
                for name, r in ZONES.items():
                    if rect_contains(r, px, py): current_fire_zones.add(name)
                for name, r in EXITS.items():
                    if rect_contains(r, px, py): current_fire_zones.add(name)
            self.active_fire_zones = list(current_fire_zones)

            # 1c. Heuristic SITREP Generation (Instant Technical reporting)
            if not self.fire_cells:
                self.sitrep = "FACILITY SECURE. ALL SYSTEMS NOMINAL."
            else:
                counts = {}
                for z in self.active_fire_zones:
                    counts[z] = sum(1 for c in self.fire_cells if self.get_zone_of(c[0]*GRID_SIZE+5, c[1]*GRID_SIZE+5) == z)
                top_zone = max(counts, key=counts.get) if counts else "Unknown"
                self.sitrep = f"CRITICAL: THERMAL BREACH IN PROGRESS.\nPRIMARY IMPACT: {top_zone.upper()} ({counts.get(top_zone, 0)} cells).\nTHREAT LEVEL: SEVERE. EVACUATION PROTOCOLS ACTIVE."

            # 2. Update People & Continuous AI Routing
            exit_names = list(EXITS.keys())
            for p in self.people:
                if p.hp <= 0: continue

                # Check Escape
                escaped = False
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
                
                # Facility-Wide Alert Threshold (Phase 1 Fix)
                # If ANY fire exists anywhere, the AI routes everyone immediately.
                facility_alert = len(self.active_fire_zones) > 0
                
                # Proximity determines absolute PANIC vs orderly EVACUATING
                is_panic_proximity = False
                for fz in self.active_fire_zones:
                    if fz == p_zone or p_zone in ADJACENCY.get(fz, []):
                        is_panic_proximity = True
                        break

                if is_panic_proximity and p.status != "PANIC" and p.status != "TRAPPED":
                    p.status = "PANIC"
                    p.speed = 3.5 # Run faster
                elif facility_alert and p.status == "IDLE":
                    p.status = "EVACUATING"
                    p.speed = 2.5 # Brisk walk
                elif not facility_alert and p.status != "IDLE":
                    # Stand down from evac/panic
                    p.status = "IDLE"
                    p.path = []
                    
                # Dynamic Roaming during peacetime
                if p.status == "IDLE" and not facility_alert:
                    if p.role in ["Manager", "Security Guard", "Cleaner"]:
                        if time.time() > p.next_roam_time:
                            if not p.path:
                                target_zone = random.choice(list(ZONES.keys()))
                                if target_zone != p_zone:
                                    p.path = self.find_shortest_path(p_zone, [target_zone], set())
                                p.next_roam_time = time.time() + random.uniform(10, 30)
                            elif len(p.path) == 0:
                                p.next_roam_time = time.time() + random.uniform(5, 15)
                    
                # Dynamic Routing (Continuous AI Overseer)
                if p.status in ["EVACUATING", "PANIC", "TRAPPED"]:
                    # Check if current path is blocked by active fire zones
                    path_blocked = False
                    for node in p.path:
                        if node in self.active_fire_zones:
                            path_blocked = True
                            break
                    
                    if not p.path or path_blocked:
                        new_path = self.find_shortest_path(p_zone, exit_names, set(self.active_fire_zones))
                        p.path = new_path
                        
                        if not p.path and p.status != "TRAPPED":
                            p.status = "TRAPPED"
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
                            threading.Thread(target=self.trigger_pa_announcement, args=(p, p_zone, self.active_fire_zones[0] if self.active_fire_zones else "Unknown", p.path)).start()

                # Movement Execution

                if p.path:
                    # Target node is the first node in path that is NOT the current node, or just the next one
                    target_node = p.path[0]
                    if target_node == p_zone and len(p.path) > 1:
                        target_node = p.path[1]
                        
                    tx, ty = self.get_node_pos(target_node)
                    dist = math.hypot(tx - p.x, ty - p.y)
                    
                    if dist > 15: 
                        dx = (tx - p.x) / dist
                        dy = (ty - p.y) / dist
                        
                        # STUCK RECOVERY: If position hasn't moved 2px in 10 frames, force push
                        move_dist = math.hypot(p.x - p.last_pos[0], p.y - p.last_pos[1])
                        if move_dist < 0.5:
                            p.stuck_count += 1
                        else:
                            p.stuck_count = 0
                            
                        if p.stuck_count > 10:
                            # Force teleport towards target node to break collision
                            p.x += dx * 10 
                            p.y += dy * 10
                            p.stuck_count = 0
                        else:
                            # NOCLIP LOGIC: If near a door-connector, ignore minor boundary jitter
                            # This ensures they "glide" into corridors
                            is_near_door = False
                            for z_name, z in ZONES.items():
                                if "Corridor" in z_name or "Hub" in z_name:
                                    if z['x']-20 <= p.x <= z['x']+z['w']+20 and z['y']-20 <= p.y <= z['y']+z['h']+20:
                                        is_near_door = True
                                        break
                            
                            p.x += dx * p.speed
                            p.y += dy * p.speed
                            
                            # Boundary snap if NOT near a door. Covers all exits up to boundaries.
                            if not is_near_door:
                                p.x = max(0, min(1480, p.x))
                                p.y = max(0, min(650, p.y))
                        
                        p.last_pos = (p.x, p.y)
                    else:
                        if len(p.path) > 0 and (p.path[0] == p_zone or p.path[0] == target_node):
                            p.path.pop(0)

                elif p.status == "TRAPPED" and self.fire_cells:
                    # REALISTIC PANIC PHYSICS: Run actively away from the nearest fire
                    # Resolves the 'banging on wall' user feedback where trapped entities froze
                    best_f = None
                    min_d = float('inf')
                    for (gx, gy) in self.fire_cells:
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
                            
                            # Move frantically away
                            p.x += (dx * p.speed * 1.5) + random.uniform(-1, 1)
                            p.y += (dy * p.speed * 1.5) + random.uniform(-1, 1)
                            
                            # Clamp to current zone boundaries to prevent clipping out of bounds
                            all_zones = {**ZONES, **EXITS}
                            if p_zone in all_zones:
                                curr_zone_rect = all_zones[p_zone]
                                p.x = max(curr_zone_rect["x"] + 10, min(curr_zone_rect["x"] + curr_zone_rect["w"] - 10, p.x))
                                p.y = max(curr_zone_rect["y"] + 10, min(curr_zone_rect["y"] + curr_zone_rect["h"] - 10, p.y))

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

            return {
                "scenario": self.scenario,
                "people": [{"id": p.id, "name": p.name, "x": p.x, "y": p.y, "hp": p.hp, "status": p.status, "path": p.path} for p in self.people if p.status != "ESCAPED"],
                "fire_cells": list(self.fire_cells),
                "water_cells": list(self.water_cells),
                "active_fire_zones": list(self.active_fire_zones),
                "pa_announcements": self.pa_announcements,
                "global_events": list(self.global_events),
                "sitrep": self.sitrep,
            }

sim_engine = SimulationEngine()
sim_engine.populate()

def simulation_loop():
    while sim_engine.running:
        sim_engine.update_cycle()
        time.sleep(1/30.0) # 30 updates per second

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
import os
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
def startup_event():
    sim_thread = threading.Thread(target=simulation_loop, daemon=True)
    sim_thread.start()

@app.on_event("shutdown")
def shutdown_event():
    sim_engine.running = False

@app.get("/")
def read_root():
    return FileResponse("static/index.html")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Send state at 30fps
            state = sim_engine.get_state()
            await websocket.send_json(state)
            await asyncio.sleep(1/30.0)
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
    return {"status": "error"}

@app.post("/api/summarize")
async def summarize_situation():
    with sim_engine.lock:
        state = sim_engine.get_state()
    
    # Condense State for Context
    alive = sum(1 for p in state["people"] if p["hp"] > 0)
    escaped = sum(1 for p in state["people"] if p["status"] == "ESCAPED")
    trapped = sum(1 for p in state["people"] if p["status"] == "TRAPPED")
    panicking = sum(1 for p in state["people"] if p["status"] == "PANIC")
    fire_zones = state["active_fire_zones"]
    water_active = len(state["water_cells"]) > 0

    prompt_text = f"[INFERNALX FEED]: {alive} alive, {escaped} escaped, {trapped} trapped, {panicking} panicking. Active Fire Zones: {fire_zones}. Water Sprinklers Active: {water_active}."

    try:
        payload = {
            "model": MODEL_NAME,
            "prompt": prompt_text,
            "stream": False,
            "options": {"num_predict": 25}
        }
        res = await asyncio.to_thread(requests.post, OLLAMA_URL, json=payload, timeout=45.0)
        if res.status_code == 200:
            summary = res.json().get("response", "").strip()
            return {"summary": summary}
        else:
            return {"summary": "INFERNALX OFFLINE: LLM Engine Unreachable."}
    except Exception as e:
        print(f"Summarize API Error: {e}")
        return {"summary": "INFERNALX CRASH: Communication failure."}

@app.post("/api/chat")
async def chat_interaction(payload_input: dict):
    query = payload_input.get("message", "")
    with sim_engine.lock:
        state = sim_engine.get_state()
    
    # Contextualize chat
    alive = sum(1 for p in state["people"] if p["hp"] > 0)
    escaped = sum(1 for p in state["people"] if p["status"] == "ESCAPED")
    trapped = sum(1 for p in state["people"] if p["status"] == "TRAPPED")
    fire_zones = state["active_fire_zones"]
    
    # Read last 10 lines of incident log for persistent memory
    incident_history = ""
    try:
        if os.path.exists("incident_report.log"):
            with open("incident_report.log", "r") as f:
                lines = f.readlines()
                incident_history = "\n".join(lines[-2:])
    except: pass

    # Autonomous Action Interception
    intercepted_action = False
    lower_query = query.lower()
    
    # Expanded interceptor array per Phase 14
    suppression_keywords = [
        "phase 2", "sprinkler", "water", "suppress", "extinguish", "put out",
        "turn off", "stop fire", "disable fire", "kill fire", "put off"
    ]
    
    if any(kw in lower_query for kw in suppression_keywords):
        intercepted_action = True
        with sim_engine.lock:
            sim_engine.suppression_mode = True # Trigger gradual removal
            msg = "COMMAND RECEIVED: PHASE 2 FIRE SUPPRESSION SEQUENCES INITIATED."
            sim_engine.global_events.append(time.strftime("[%H:%M:%S]") + " " + msg)
            sim_engine.log_incident(msg)
            # Deploy precision suppression (which reads fire_cells)
            for fz in fire_zones:
                sim_engine.deploy_suppression(fz)
            # Instantly cover all active fire with water guaranteeing immediate suppression
            sim_engine.water_cells.update(sim_engine.fire_cells)
            sim_engine.fire_cells.clear()
            
    context = f"[SYSTEM STATE: {alive} ALIVE, {escaped} ESCAPED, {trapped} TRAPPED. FIRE: {fire_zones}]\n"
    context += f"[INCIDENT HISTORY (LAST 10 ENTRIES)]:\n{incident_history}\n"
    if intercepted_action:
        context += "[SYSTEM ACTION LOGGED: YOU HAVE ACTIVATED THE PHASE 2 SPRINKLERS AND PUT OUT ALL FIRES.]\n"
        
    rule_directive = "SYSTEM DIRECTIVE: You are the InfernalX Overseer. Cold, technical, technical-only response. ONE SENTENCE MAX. DO NOT EXCEED 15 WORDS. NO HALLUCINATIONS. If input is unclear or short (like 'h'), respond 'AWAITING OPERATOR INPUT.' NO MARKDOWN. NO BULLETS."
    full_prompt = f"CONTEXT: {context}\n{rule_directive}\nOPERATOR: {query}"
    
    try:
        payload = {
            "model": MODEL_NAME,
            "prompt": full_prompt,
            "stream": False,
            "options": {"num_predict": 20}
        }
        res = await asyncio.to_thread(requests.post, OLLAMA_URL, json=payload, timeout=45.0)
        if res.status_code == 200:
            resp_text = res.json().get("response", "").strip()
            return {"response": resp_text}
        else:
            return {"response": "OFFLINE."}
    except Exception as e:
        return {"response": "CRASH."}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
