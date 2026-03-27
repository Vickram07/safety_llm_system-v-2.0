import pygame
import sys
import threading
import queue
import time
import requests
import math
import speech_recognition as sr
import pyttsx3
import heapq
import random

# ==========================================
# CONFIGURATION
# ==========================================
WINDOW_WIDTH = 1500 # Increased for 3-Panel Layout
WINDOW_HEIGHT = 800 # Fixed for standard screens
FPS = 60
COLOR_BG = (10, 10, 15)
COLOR_ZONE = (30, 30, 40)
COLOR_EXIT = (0, 200, 100)
PEOPLE_COLORS = [(0, 255, 255), (255, 0, 255), (255, 255, 0), (0, 255, 128)]

OLLAMA_URL = "http://127.0.0.1:11434/api/generate" # Use IP to avoid DNS lag
MODEL_NAME = "safety_llm" # Updated to match run_llm.py

# ... (Previous imports and config remain)

SYSTEM_PROMPT_FILE = "live_commander_prompt.txt"

ZONES = {
    # ROW 1 (Top) -- SHIFTED +280px
    "Zone A1 (Lobby)":    pygame.Rect(330, 70, 200, 180),
    "Zone C1 (Command)":  pygame.Rect(692, 70, 200, 180),
    "Zone A2 (Cafeteria)":pygame.Rect(1054, 70, 200, 180),

    # ROW 2 (Bottom)
    "Zone B1 (Server)":   pygame.Rect(330, 310, 200, 180),
    "Zone C2 (Medical)":  pygame.Rect(692, 310, 200, 180),
    "Zone B2 (Chem Lab)": pygame.Rect(1054, 310, 200, 180),
    
    # CORRIDORS
    "Hallway West Top":    pygame.Rect(530, 110, 162, 100), 
    "Hallway East Top":    pygame.Rect(892, 110, 162, 100), 
    "Hallway West Bot":    pygame.Rect(530, 350, 162, 100), 
    "Hallway East Bot":    pygame.Rect(892, 350, 162, 100), 
    "Central Spine":       pygame.Rect(742, 250, 100, 60)   
}

EXITS = {
    "North Gate": pygame.Rect(742, 10, 100, 60),      
    "South Gate": pygame.Rect(742, 490, 100, 60),     
    "West Emergency": pygame.Rect(280, 110, 50, 100)    
}

ADJACENCY = {
    "Zone A1 (Lobby)":    ["Hallway West Top", "West Emergency"],
    "Hallway West Top":   ["Zone A1 (Lobby)", "Zone C1 (Command)"],
    
    "Zone C1 (Command)":  ["Hallway West Top", "Hallway East Top", "Central Spine", "North Gate"],
    "North Gate":         ["Zone C1 (Command)"],
    
    "Hallway East Top":   ["Zone C1 (Command)", "Zone A2 (Cafeteria)"],
    "Zone A2 (Cafeteria)":["Hallway East Top"],
    
    "Central Spine":      ["Zone C1 (Command)", "Zone C2 (Medical)"],
    
    "Zone B1 (Server)":   ["Hallway West Bot"],
    "Hallway West Bot":   ["Zone B1 (Server)", "Zone C2 (Medical)"],
    
    "Zone C2 (Medical)":  ["Hallway West Bot", "Central Spine", "Hallway East Bot", "South Gate"],
    "South Gate":         ["Zone C2 (Medical)"],
    
    "Hallway East Bot":   ["Zone C2 (Medical)", "Zone B2 (Chem Lab)"],
    "Zone B2 (Chem Lab)":["Hallway East Bot"]
}

class Person:
    def __init__(self, name, x, y, role_id):
        self.name = name
        self.x = x
        self.y = y
        self.role_id = role_id
        self.color = PEOPLE_COLORS[role_id % len(PEOPLE_COLORS)] # Restored color
        self.hp = 100.0
        self.status = "EVACUATING" # EVACUATING, RESCUING, SECURING_DATA, SECURED
        self.mission_timer = 0
        self.target_person = None

class SimulationState:
    def __init__(self):
        # UPDATE START POSITIONS (Shifted +280px)
        self.people = [
            Person("Operator", 430, 160, 0),         
            Person("Civilian 1", 1150, 160, 1),       
            Person("Civilian 2", 1150, 400, 2),       
            Person("Medic", 792, 400, 3),
            # NEW CIVILIANS
            Person("Civilian 3", 430, 400, 4), # Zone B1 (Server)
            Person("Civilian 4", 792, 160, 5), # Zone C1 (Command)
            Person("Civilian 5", 400, 120, 6), # Zone A1 (Lobby)
            Person("Civilian 6", 610, 400, 7), # Hallway West Bot
            Person("Civilian 7", 970, 160, 8), # Hallway East Top
        ]
        self.escaped_people = [] 
        self.active_idx = 0 
        self.start_time = time.time()
        
        # MESSAGING STATE
        self.system_alert = ""
        self.proximity_alert = "" 
        self.ai_message = "System Online. Waiting for queries..."
        self.last_user_query = ""
        self.live_guidance = "Initializing Tactical Support..."
        
        self.active_fire_zones = []
        self.active_smoke_zones = []
        self.voice_input_q = queue.Queue()
        self.is_recording = False
        self.is_typing = False
        self.input_text = ""
        self.current_path = [] 
        self.lock = threading.RLock() 
        self.event_log = []
        self.chat_history = [f"AI: {self.ai_message}"] 
        self.damage_tracker = set()
        self.casualties = [] # Track dead people
        self.treated_people = [] 
        self.last_treated_time = {} 
        self.chat_scroll_offset = 0
        
        # CELLULAR FIRE SYSTEM
        self.fire_cells = set() # Stores (grid_x, grid_y)
        self.water_cells = set() # Stores (grid_x, grid_y) for sprinklers
        self.active_sprinkler_zones = set() # Track WHICH zones are sprinkling
        self.sprinklers_active = False # Legacy flag for compatibility, mainly unused now
        self.fire_spread_timer = 0
        self.GRID_SIZE = 10 # 10px blocks for detailed fire

    def log_event(self, msg):
        ts = time.strftime("%H:%M:%S")
        entry = f"[{ts}] {msg}"
        with self.lock:
            self.event_log.append(entry)
            if len(self.event_log) > 20: self.event_log.pop(0)

    def start_sprinklers(self, target_zone=None):
        with self.lock:
            if target_zone:
                self.log_event(f"SYSTEM: SPRINKLER ACTIVATED IN {target_zone}")
                targets = {target_zone: ZONES.get(target_zone, EXITS.get(target_zone))}
                self.active_sprinkler_zones.add(target_zone)
            else:
                if not self.active_sprinkler_zones:
                    self.log_event("SYSTEM: ALL SPRINKLERS ACTIVATED")
                targets = {**ZONES, **EXITS}
                self.active_sprinkler_zones.update(targets.keys())

            # Extinguish fire in target zones
            for zname, zrect in targets.items():
                if not zrect: continue 
                
                start_gx = int(zrect.x // self.GRID_SIZE)
                start_gy = int(zrect.y // self.GRID_SIZE)
                end_gx = int(zrect.right // self.GRID_SIZE)
                end_gy = int(zrect.bottom // self.GRID_SIZE)
                
                for gx in range(start_gx, end_gx):
                    for gy in range(start_gy, end_gy):
                        self.water_cells.add((gx, gy))
                        if (gx, gy) in self.fire_cells:
                            self.fire_cells.remove((gx, gy))

    def stop_sprinklers(self, target_zone=None):
        with self.lock:
            if target_zone:
                if target_zone in self.active_sprinkler_zones:
                    self.active_sprinkler_zones.remove(target_zone)
                    self.log_event(f"SYSTEM: SPRINKLERS STOPPED IN {target_zone}")
                    
                    # Optional: Clear water cells in that zone to show it stopping?
                    # For now, let's keep water (puddles) but stop spreading
            else:
                self.active_sprinkler_zones.clear()
                self.log_event("SYSTEM: ALL SPRINKLERS DEACTIVATED")

    def manual_start_fire(self, target_zone):
        with self.lock:
            zrect = ZONES.get(target_zone, EXITS.get(target_zone))
            if zrect:
                gx = int(zrect.centerx // self.GRID_SIZE)
                gy = int(zrect.centery // self.GRID_SIZE)
                # Cluster
                for dx in range(-2, 3):
                    for dy in range(-2, 3):
                        self.fire_cells.add((gx+dx, gy+dy))
                self.log_event(f"WARNING: MANUAL FIRE STARTED IN {target_zone}")

    def is_valid_move(self, x, y):
        # Allow exiting!
        pt = (x, y)
        all_rects = list(ZONES.values()) + list(EXITS.values())
        for r in all_rects:
            if r.collidepoint(pt): return True
        return False
        
    def check_future_hazard(self, x, y):
        pt = (x, y)
        for name, rect in ZONES.items():
            if name in self.active_fire_zones:
                if rect.collidepoint(pt): return f"STOP! FIRE IN {name}!"
        return None

    def get_current_person(self):
        with self.lock:
            if self.people and self.active_idx < len(self.people):
                return self.people[self.active_idx]
            return None

    def switch_person(self):
        with self.lock:
            if not self.people: return "No Active Personnel"
            self.active_idx = (self.active_idx + 1) % len(self.people)
            return self.people[self.active_idx].name

    def get_zone_of(self, person):
        p_rect = pygame.Rect(person.x - 5, person.y - 5, 10, 10)
        for name, rect in ZONES.items():
            if rect.contains(p_rect) or rect.colliderect(p_rect): return name
        for name, rect in EXITS.items():
            if rect.colliderect(p_rect): return f"EXIT ({name})"
        closest = None
        min_dist = 9999
        for name, rect in ZONES.items():
            dx = max(rect.left - person.x, 0, person.x - rect.right)
            dy = max(rect.top - person.y, 0, person.y - rect.bottom)
            d = math.sqrt(dx*dx + dy*dy)
            if d < min_dist:
                min_dist = d
                closest = name
        if min_dist < 30 and closest: return closest
        return "Corridor"

    def get_ground_truth_context(self):
        with self.lock:
            active_p = self.get_current_person()
            fire_z = list(self.active_fire_zones)
            
            roster = []
            global_alerts = []
            
            for p in self.people:
                loc = self.get_zone_of(p)
                status = "HEALTHY"
                if p.hp < 40: status = "CRITICAL INJURY"
                elif p.hp < 80: status = "INJURED"
                
                if "EXIT" in loc: status = "ESCAPING..."
                
                for fz in fire_z:
                    if fz == loc:
                        status = "DANGER: IN FIRE"
                        msg = f"FIRE IN {loc}!"
                        if msg not in global_alerts: global_alerts.append(msg)
                
                roster.append(f"{p.name} [HP:{int(p.hp)} | {status}] @ {loc}")
            
            escaped_str = ", ".join(self.escaped_people) if self.escaped_people else "None"
            
            if active_p:
                active_loc = self.get_zone_of(active_p)
                active_threat = "SAFE"
                active_action = "Maintain Awareness"
                if any(active_loc in alert for alert in global_alerts):
                    active_threat = "IMMEDIATE THREAT"
                    active_action = "EVACUATE NOW"
                focus_name = active_p.name
            else:
                active_loc = "N/A"
                active_threat = "N/A"
                active_action = "All Personnel Evacuated"
                focus_name = "System"

        return {
            "roster_text": "\n".join(roster),
            "escaped_text": escaped_str,
            "global_alerts": global_alerts,
            "focus_name": focus_name,
            "focus_loc": active_loc,
            "threat": active_threat,
            "action": active_action
        }

    def update_logic(self):
        elapsed = time.time() - self.start_time
        with self.lock:
            # 1. FIRE LOGIC (Grid Based)
            # Ignition at T+10
            if elapsed > 10 and not self.fire_cells and not self.sprinklers_active:
                # Start in Chem Lab (Zone B2) - center
                chem = ZONES["Zone B2 (Chem Lab)"]
                gx = int(chem.centerx // self.GRID_SIZE)
                gy = int(chem.centery // self.GRID_SIZE)
                self.fire_cells.add((gx, gy))
                self.log_event("FIRE STARTED: Ignition in Zone B2 (Chem Lab)")
            
            # Spread (Every 2.0s - Very Slow spread)
            if elapsed > 10 and elapsed - self.fire_spread_timer > 2.0:
                self.fire_spread_timer = elapsed
                
                new_cells = set()
                candidates = list(self.fire_cells)
                if len(candidates) > 200:
                    candidates = random.sample(candidates, 200)
                
                all_rects = list(ZONES.values()) + list(EXITS.values())
                
                for (cx, cy) in candidates:
                    neighbors = [(cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)]
                    for nx, ny in neighbors:
                        if (nx, ny) not in self.fire_cells and (nx, ny) not in self.water_cells:
                             test_rect = pygame.Rect(nx*self.GRID_SIZE, ny*self.GRID_SIZE, self.GRID_SIZE, self.GRID_SIZE)
                             valid = False
                             for r in all_rects:
                                 if r.contains(test_rect) or r.colliderect(test_rect):
                                     valid = True; break
                             
                             if valid:
                                 new_cells.add((nx, ny))
                
                if new_cells:
                    self.fire_cells.update(new_cells)
            
            # 2. SPRINKLER SYSTEM (Selective)
            if not self.people and not self.active_sprinkler_zones:
                pass # Wait for manual command
            
            if self.active_sprinkler_zones:
                # Spread Water (Faster than fire to clean up)
                water_spread_needed = False
                if elapsed % 0.1 < 0.05:
                     water_spread_needed = True
                
                if water_spread_needed:
                     new_water = set()
                     # Only spread from active zones
                     all_rects = list(ZONES.values()) + list(EXITS.values())
                     
                     # 1. Seed active zones continually to ensure coverage (PRIMARY MECHANISM NOW)
                     for z in self.active_sprinkler_zones:
                         rect = ZONES.get(z, EXITS.get(z))
                         if rect:
                             gx = int(rect.centerx // self.GRID_SIZE)
                             gy = int(rect.centery // self.GRID_SIZE)
                             self.water_cells.add((gx, gy))

                     # DISABLED SPREADING LOGIC FOR PRECISE CONTROL
                     # candidates = list(self.water_cells)
                     # ... (removed for strict localization)
                    
                     # if new_water: self.water_cells.update(new_water)

            # Update High-Level Zones status for AI/Alerts
            current_fire_zones = set()
            for (gx, gy) in self.fire_cells:
                px, py = gx * self.GRID_SIZE + 5, gy * self.GRID_SIZE + 5
                for name, r in ZONES.items():
                    if r.collidepoint(px, py): current_fire_zones.add(name)
            
            self.active_fire_zones = list(current_fire_zones)

            # 2. ESCAPE & DAMAGE LOGIC
            remaining_people = []
            for p in self.people:
                if p.hp <= 0:
                    ts = time.strftime("%H:%M:%S")
                    dead_msg = f"[{ts}] {p.name} died in {self.get_zone_of(p)}"
                    self.log_event(f"FATALITY: {p.name}") 
                    self.casualties.append(dead_msg)
                    continue 

                # Check collision with EXITS
                p_rect = pygame.Rect(p.x-5, p.y-5, 10, 10)
                escaped = False
                for ename, erect in EXITS.items():
                    if erect.contains(p_rect) or erect.colliderect(p_rect):
                        ts = time.strftime("%H:%M:%S")
                        self.escaped_people.append(f"{p.name} (via {ename}) at {ts}")
                        self.log_event(f"ESCAPED: {p.name} via {ename}")
                        escaped = True
                        break
                
                if not escaped:
                    pgx, pgy = int(p.x // self.GRID_SIZE), int(p.y // self.GRID_SIZE)
                    # DAMAGE FIX: Water protects you!
                    if (pgx, pgy) in self.fire_cells and (pgx, pgy) not in self.water_cells:
                        p.hp -= 1.0 
                        if p.name not in self.damage_tracker:
                            self.damage_tracker.add(p.name)
                            self.log_event(f"DAMAGE: {p.name} burned in fire!")
                        
                        if current := self.get_current_person():
                             if p == current: self.system_alert = "WARNING: IN FIRE!"
                    else:
                        if p.name in self.damage_tracker: self.damage_tracker.remove(p.name)

                    p.hp = max(0, min(100, p.hp))
                    remaining_people.append(p)
            
            self.people = remaining_people
            if self.active_idx >= len(self.people) and len(self.people) > 0:
                self.active_idx = 0

            # 3. SMART PATHFINDING (Role-Based)
            p = self.get_current_person()
            if p:
                start_node = self.get_zone_of(p)
                if start_node not in ADJACENCY and start_node not in ZONES and start_node not in EXITS:
                     closest = self.get_nearest_zone_name(p)
                     if closest: start_node = closest
                
                targets = ["North Gate", "South Gate", "West Emergency"]
                hazards = set(self.active_fire_zones + self.active_smoke_zones)
                
                if "Medic" in p.name:
                    injured_candidates = [o for o in self.people if o.hp < 100 and o != p and o.status != "SECURED"]
                    if injured_candidates:
                        injured_candidates.sort(key=lambda o: math.hypot(o.x - p.x, o.y - p.y))
                        patient = injured_candidates[0] 
                        p.status = f"RESCUING {patient.name}"
                        p_zone = self.get_zone_of(patient)
                        dist = math.hypot(p.x - patient.x, p.y - patient.y)
                        if dist < 50:
                            patient.hp += 1.0 
                            if patient.hp >= 100: 
                                patient.hp = 100
                                now = time.time()
                                last = self.last_treated_time.get(patient.name, 0)
                                if (now - last) > 5.0:
                                    self.treated_people.append(patient.name)
                                    self.log_event(f"MEDIC: Treated {patient.name}")
                                    self.last_treated_time[patient.name] = now
                        else:
                            targets = [p_zone] 
                    else:
                        p.status = "EVACUATING"

                elif "Operator" in p.name:
                     p.status = "EVACUATING"
                     pass
                         
                self.current_path = self.find_shortest_path(start_node, targets, hazards)
                
                if self.proximity_alert:
                    self.live_guidance = f"HAZARD: {self.proximity_alert}"
                elif self.current_path:
                    final = self.current_path[-1] 
                    nxt = self.current_path[0]
                    self.live_guidance = f"TACTICAL: {p.status} -> Moving to {nxt}"
                else:
                    status_text = "Holding Position" if p.status == "SECURING DATA" else "Area Secure"
                    self.live_guidance = f"STATUS: {status_text}"
            else:
                self.current_path = []
                self.live_guidance = "ALL UNITS CLEARED."

    def get_nearest_zone_name(self, person):
        closest = None
        min_dist = 9999
        all_rects = {**ZONES, **EXITS}
        for name, rect in all_rects.items():
            d = math.hypot(rect.centerx - person.x, rect.centery - person.y)
            if d < min_dist:
                min_dist = d
                closest = name
        return closest

    def get_node_pos(self, name):
        all_rects = {**ZONES, **EXITS}
        if name in all_rects:
            return all_rects[name].center
        return (0,0)

    def find_shortest_path(self, start, targets, hazards):
        # DIJKSTRA'S ALGORITHM (Shortest Path)
        if not start: return []
        
        # Priority Queue: (current_cost, current_node, path_so_far)
        pq = [(0, start, [start])]
        visited_costs = {start: 0}
        
        while pq:
            cost, node, path = heapq.heappop(pq)
            
            # Found a target?
            if node in targets:
                return path
            
            # Optimization: If we found a shorter path to this node already, skip
            if cost > visited_costs.get(node, float('inf')):
                 continue
            
            neighbors = ADJACENCY.get(node, [])
            cx, cy = self.get_node_pos(node)
            
            for neighbor in neighbors:
                if neighbor in hazards: continue
                
                nx, ny = self.get_node_pos(neighbor)
                
                # Weight = Euclidean Distance
                dist_weight = math.hypot(nx - cx, ny - cy)
                new_cost = cost + dist_weight
                
                if new_cost < visited_costs.get(neighbor, float('inf')):
                    visited_costs[neighbor] = new_cost
                    heapq.heappush(pq, (new_cost, neighbor, path + [neighbor]))
                    
        return []

# ... (draw_dynamic_path, wrap_text)

def wrap_text(text, font, max_width):
    words = text.split(' ')
    lines = []
    current_line = []
    for word in words:
        test_line = ' '.join(current_line + [word])
        if font.size(test_line)[0] <= max_width:
            current_line.append(word)
        else:
            lines.append(' '.join(current_line))
            current_line = [word]
    lines.append(' '.join(current_line))
    return lines

def draw_professional_interface(screen, font_ui, font_lg, state, ai_status):
    # ==========================================
    # 1. LEFT SIDEBAR: AI COMMAND CENTER
    # ==========================================
    left_w = 280
    pygame.draw.rect(screen, (10, 12, 16), (0, 0, left_w, WINDOW_HEIGHT))
    pygame.draw.line(screen, (0, 200, 200), (left_w, 0), (left_w, WINDOW_HEIGHT), 2)
    
    # Title
    pygame.draw.rect(screen, (0, 40, 50), (0, 0, left_w, 40))
    t1 = font_ui.render("AI TACTICAL COMMAND", True, (0, 255, 255))
    screen.blit(t1, (20, 12))
    
    # Connection Indicator
    # Use the passed argument 'ai_status' instead of state.ai_status
    ind_col = (0, 255, 0) if ai_status == "ONLINE" or ai_status == "THINKING..." else (255, 0, 0)
    pygame.draw.circle(screen, ind_col, (left_w - 20, 20), 5)
    
    # Status
    stat_col = (0, 255, 0) if "ONLINE" in ai_status else (255, 255, 0)
    if "OFFLINE" in ai_status: stat_col = (255, 0, 0)
    
    stat = font_ui.render(f"STATUS: {ai_status}", True, stat_col)
    screen.blit(stat, (20, 50))
    
    # LIVE TACTICAL
    guide_y = 80
    pygame.draw.rect(screen, (0, 30, 40), (10, guide_y, left_w-20, 60), border_radius=4)
    if state.live_guidance:
        # wrap
        wrapped_g = wrap_text(state.live_guidance, font_ui, left_w-30)
        for i, lie in enumerate(wrapped_g):
             screen.blit(font_ui.render(lie, True, (0, 255, 255)), (15, guide_y+5+i*18))
             
    # ALERTS
    alert_y = 150
    if state.system_alert:
        pygame.draw.rect(screen, (150, 0, 0), (10, alert_y, left_w-20, 40), border_radius=4)
        screen.blit(font_lg.render("⚠ ALERT", True, (255, 255, 255)), (20, alert_y+10))

    # CHAT HISTORY (Main Feature)
    chat_y = 200
    chat_h = WINDOW_HEIGHT - 400
    chat_rect = pygame.Rect(10, chat_y, left_w-20, chat_h)
    
    pygame.draw.rect(screen, (5, 5, 8), chat_rect, border_radius=4)
    pygame.draw.rect(screen, (50, 60, 80), chat_rect, 1, border_radius=4)
    
    # Internal Padding
    padding = 10
    line_h = 18
    max_lines_visible = (chat_h - 2 * padding) // line_h
    
    with state.lock:
        # Pre-calculate wrapped lines for everything to handle scrolling correctly
        all_wrapped_lines = []
        for msg in state.chat_history:
            # Color logic
            col = (200, 200, 0) # Default User
            if "AI:" in msg: col = (0, 255, 255)
            elif "SYSTEM:" in msg: col = (255, 100, 100)
            
            wrapped = wrap_text(msg, font_ui, chat_rect.width - 25) # -25 for scrollbar space
            for w in wrapped:
                all_wrapped_lines.append((w, col))
            all_wrapped_lines.append(("", (0,0,0))) # Spacer
            
        total_wrapped = len(all_wrapped_lines)
        
        # Scroll Logic
        max_scroll = max(0, total_wrapped - max_lines_visible)
        state.chat_scroll_offset = max(0, min(state.chat_scroll_offset, max_scroll))
        
        # Invert logic: Scroll 0 means BOTTOM (latest), Higher means OLDER? 
        # Actually standard is: 0 is top. Let's stick to standard terminal scroll.
        # But usually prompts auto-scroll to bottom.
        # Let's define: offset 0 = Show Bottom. offset > 0 = scroll up.
        
        display_start_idx = max(0, total_wrapped - max_lines_visible - state.chat_scroll_offset)
        display_end_idx = display_start_idx + max_lines_visible
        
        visible_lines = all_wrapped_lines[display_start_idx:display_end_idx]
        
        # Render Text
        curr_y = chat_y + padding
        for line_text, line_col in visible_lines:
            if line_text:
                screen.blit(font_ui.render(line_text, True, line_col), (chat_rect.x + 8, curr_y))
            curr_y += line_h

        # Render Scrollbar
        if total_wrapped > max_lines_visible:
            sb_w = 6
            sb_h_total = chat_h - 10
            sb_x = chat_rect.right - 8
            sb_y = chat_rect.top + 5
            
            # Track bg
            pygame.draw.rect(screen, (20, 30, 40), (sb_x, sb_y, sb_w, sb_h_total), border_radius=3)
            
            # Thumb handle
            view_ratio = max_lines_visible / total_wrapped
            thumb_h = max(20, int(sb_h_total * view_ratio))
            
            # Position: 0 offset (bottom) -> bottom of scrollbar
            # We need to map offset (0..max_scroll) to position (bottom..top)
            scroll_ratio = state.chat_scroll_offset / max_scroll if max_scroll > 0 else 0
            
            # Invert visual: scroll_offset 0 is bottom (latest), so thumb should be at bottom
            avail_travel = sb_h_total - thumb_h
            thumb_pos = sb_y + avail_travel - (scroll_ratio * avail_travel)
            
            pygame.draw.rect(screen, (0, 150, 200), (sb_x, thumb_pos, sb_w, thumb_h), border_radius=3)

    # INPUT FIELD
    input_y = WINDOW_HEIGHT - 130
    input_w = left_w - 20
    if state.is_typing:
        pygame.draw.rect(screen, (40, 40, 50), (10, input_y, input_w, 30), border_radius=5)
        pygame.draw.rect(screen, (255, 200, 0), (10, input_y, input_w, 30), 1, border_radius=5)
        
        full_txt = f"{state.input_text}_"
        # Text Scrolling Logic
        max_input_w = input_w - 10
        display_txt = full_txt
        while font_ui.size(display_txt)[0] > max_input_w:
            display_txt = display_txt[1:] # Chop from front to show end
            
        screen.blit(font_ui.render(display_txt, True, (255, 255, 255)), (15, input_y+5))
    else:
        pygame.draw.rect(screen, (20, 20, 30), (10, input_y, left_w-20, 30), border_radius=5)
        screen.blit(font_ui.render("Click [TYPE] to chat...", True, (100, 100, 120)), (15, input_y+5))

    # BUTTONS
    btn_y = WINDOW_HEIGHT - 80
    r1 = pygame.Rect(10, btn_y, 80, 30)   # TYPE
    r2 = pygame.Rect(100, btn_y, 80, 30)  # VOICE
    r3 = pygame.Rect(190, btn_y, 80, 30)  # TAB
    
    current_buttons = {}
    if not state.is_typing:
        pygame.draw.rect(screen, (0, 100, 200), r1, border_radius=3)
        screen.blit(font_ui.render("TYPE", True, (255,255,255)), (r1.x+20, r1.y+8))
        
        col_v = (200, 0, 0) if state.is_recording else (0, 100, 200)
        pygame.draw.rect(screen, col_v, r2, border_radius=3)
        screen.blit(font_ui.render("TALK", True, (255,255,255)), (r2.x+20, r2.y+8))
        
        pygame.draw.rect(screen, (0, 150, 100), r3, border_radius=3)
        screen.blit(font_ui.render("TAB", True, (255,255,255)), (r3.x+25, r3.y+8))
        
        current_buttons = {"TYPE": r1, "VOICE": r2, "SWITCH": r3}

    # ==========================================
    # 2. CENTER HEADER (Map Info)
    # ==========================================
    start_map_x = left_w
    center_w = WINDOW_WIDTH - left_w - 260 # 260 is right width
    pygame.draw.rect(screen, (0, 0, 0), (start_map_x, 0, center_w, 40))
    pygame.draw.line(screen, (0, 255, 128), (start_map_x, 40), (start_map_x+center_w, 40), 1)
    
    p = state.get_current_person()
    head_txt = f"UNIT: {p.name.upper()}  HP: {int(p.hp)}%" if p else "ALL SECURED"
    screen.blit(font_lg.render(head_txt, True, (255, 255, 255)), (start_map_x+20, 10))

    # ==========================================
    # 2b. CENTER BOTTOM (DEDICATED ALERT BOARD)
    # ==========================================
    # Map area ends ~550. Window is 800. Space is 250px.
    board_y = 560
    board_h = WINDOW_HEIGHT - board_y - 10
    pygame.draw.rect(screen, (5, 10, 15), (start_map_x, board_y, center_w, board_h), border_radius=8)
    pygame.draw.rect(screen, (0, 100, 100), (start_map_x, board_y, center_w, board_h), 2, border_radius=8)

    # Header
    pygame.draw.rect(screen, (0, 50, 60), (start_map_x+2, board_y+2, center_w-4, 30), border_radius=8)
    screen.blit(font_lg.render("BUILDING SAFETY ALERT STATUS", True, (255, 200, 0)), (start_map_x+20, board_y+7))
    
    # Stats 
    stat_y = board_y + 45
    total_p = len(state.people) + len(state.escaped_people) + len(state.casualties) # Estimate
    active_c = len(state.people)
    dead_c = len(state.casualties)
    esc_c = len(state.escaped_people)
    
    stats_str = f"TOTAL: {total_p} | ACTIVE: {active_c} | ESCAPED: {esc_c} | CASUALTIES: {dead_c}"
    screen.blit(font_ui.render(stats_str, True, (200, 200, 200)), (start_map_x+20, stat_y))
    
    # Big Alerts (Prioritize FIRE over Personal Alerts)
    alert_y = stat_y + 35
    
    current_threats = []
    if state.active_fire_zones:
        current_threats.append(f"FIRE: {state.active_fire_zones[0]}")
    if state.active_smoke_zones:
        current_threats.append("SMOKE SPREAD")
    if state.system_alert:
        current_threats.append(state.system_alert)
        
    if current_threats:
         # Show top priority threat
         alert_msg = current_threats[0]
         pygame.draw.rect(screen, (200, 0, 0), (start_map_x+10, alert_y, center_w-20, 50), border_radius=5)
         # blink effect
         if int(time.time()*2) % 2 == 0:
             text_col = (255, 255, 0)
         else: text_col = (255, 255, 255)
         
         alert_surf = font_lg.render(f"⚠ {alert_msg}", True, text_col)
         screen.blit(alert_surf, (start_map_x+30, alert_y+15))
    else:
         pygame.draw.rect(screen, (0, 100, 0), (start_map_x+10, alert_y, center_w-20, 50), border_radius=5)
         safe_surf = font_lg.render("NO ACTIVE CRITICAL ALERTS", True, (255, 255, 255))
         screen.blit(safe_surf, (start_map_x+30, alert_y+15))
    
    # Live Guidance
    guidance_y = alert_y + 60
    if state.live_guidance:
         screen.blit(font_ui.render("TACTICAL FEED:", True, (0, 255, 255)), (start_map_x+20, guidance_y))
         screen.blit(font_lg.render(state.live_guidance, True, (200, 255, 255)), (start_map_x+20, guidance_y+20))

    right_w = 260
    sidebar_x = WINDOW_WIDTH - right_w
    pygame.draw.rect(screen, (5, 5, 10), (sidebar_x, 0, right_w, WINDOW_HEIGHT))
    pygame.draw.line(screen, (0, 100, 100), (sidebar_x, 0), (sidebar_x, WINDOW_HEIGHT), 1)

    # Title
    pygame.draw.rect(screen, (0, 20, 30), (sidebar_x, 0, right_w, 40))
    screen.blit(font_ui.render("SYSTEM LOG", True, (0, 255, 255)), (sidebar_x + 10, 12))

    log_y = 50
    with state.lock:
        rev_events = list(state.event_log)
        rev_events.reverse()
        for entry in rev_events:
            if "AI:" in entry or "USER:" in entry: continue

            col = (200, 200, 200)
            if "ESCAPED" in entry: col = (0, 255, 0)
            elif "FATALITY" in entry: col = (255, 0, 0)
            elif "FIRE" in entry: col = (255, 100, 0)
            elif "DAMAGE" in entry: col = (255, 50, 50)
            
            wrapped = wrap_text(entry, font_ui, right_w-20)
            for line in wrapped:
                screen.blit(font_ui.render(line, True, col), (sidebar_x+10, log_y))
                log_y += 18
            log_y += 8
            if log_y > WINDOW_HEIGHT - 20: break

    return current_buttons

    def get_ground_truth_context(self):
        with self.lock:
            active_p = self.get_current_person()
            fire_z = list(self.active_fire_zones)
            
            roster = []
            global_alerts = []
            
            # Active People Stats
            for p in self.people:
                loc = self.get_zone_of(p)
                
                # IMPROVED HEALTH CONTEXT
                status = "HEALTHY"
                if p.hp < 40: status = "CRITICAL INJURY (REQUIRES MEDEVAC)"
                elif p.hp < 80: status = "INJURED"
                
                if "EXIT" in loc: status = "ESCAPING..."
                
                # Check Local Danger
                for fz in fire_z:
                    if fz == loc:
                        status = "DANGER: IN FIRE ZONE"
                        msg = f"FIRE IN {loc}!"
                        if msg not in global_alerts: global_alerts.append(msg)
                
                roster.append(f"{p.name} [HP:{int(p.hp)} | {status}] @ {loc}")
            
            # Escaped People Stats
            escaped_str = ", ".join(self.escaped_people) if self.escaped_people else "None"
            
            # Focus
            if active_p:
                active_loc = self.get_zone_of(active_p)
                active_threat = "SAFE"
                active_action = "Maintain Awareness"
                if any(active_loc in alert for alert in global_alerts):
                    active_threat = "IMMEDIATE THREAT"
                    active_action = "EVACUATE NOW"
                focus_name = active_p.name
            else:
                active_loc = "N/A"
                active_threat = "N/A"
                active_action = "All Personnel Evacuated"
                focus_name = "System"

        return {
            "roster_text": "\n".join(roster),
            "escaped_text": escaped_str,
            "global_alerts": global_alerts,
            "focus_name": focus_name,
            "focus_loc": active_loc,
            "threat": active_threat,
            "action": active_action
        }


class VoiceHandler(threading.Thread):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.recognizer = sr.Recognizer()
        self.mic = sr.Microphone()
        self.daemon = True
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True

    def run(self):
        while True:
            if self.state.is_recording:
                try:
                    with self.mic as source:
                        audio = self.recognizer.listen(source, timeout=1.5, phrase_time_limit=3.0)
                    text = self.recognizer.recognize_google(audio)
                    self.state.voice_input_q.put(text)
                except: pass
            else:
                time.sleep(0.2)

class AICommander(threading.Thread):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.daemon = True
        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', 160)
        except: self.engine = None
        self.running = True
        self.ai_status = "INIT"

    def speak(self, text):
        if self.engine:
            try:
                self.engine.stop()
                self.engine.say(text)
                self.engine.runAndWait()
            except: pass

    def perform_llm_request(self, payload, callback_queue):
        # ... (Same as before, but currently unused as we use requests directly in run)
        pass

    def generate_fallback_response(self, query, state):
        query = query.lower()
        
        # 1. Specific Person Status check (Dead or Alive)
        for name in ["Civilian 1", "Civilian 2", "Operator", "Medic"]:
            if name.lower() in query:
                # Check if dead
                for c in state.casualties:
                     if name in c:
                         return f"STATUS: {name} is DECEASED. {c}"
                # Check if alive
                for p in state.people:
                     if p.name == name:
                         return f"STATUS: {name} is ALIVE at {state.get_zone_of(p)}. HP: {int(p.hp)}%"
                # Check if escaped
                for e in state.escaped_people:
                     if name in e:
                         return f"STATUS: {name} extracted/safe."

        # 2. General Fatalities
        if "dead" in query or "died" in query or "fatality" in query or "killed" in query or "casualties" in query:
             if not state.casualties:
                 return "Negative. No fatalities reported. All units active or secured."
             else:
                 return f"Confirmed Fatalities: {', '.join(state.casualties)}"
        
        # 3. Safety / Status
        if "safe" in query or "secure" in query or "everyone" in query:
             if state.casualties:
                 return f"ALERT: {len(state.casualties)} CASUALTIES CONFIRMED. {len(state.people)} still active."
             active_count = len(state.people)
             if active_count == 0 and not state.casualties:
                 return "Affirmative. All remaining personnel are SECURED."
             else:
                 return f"Negative. {active_count} units still active in the facility."

        # 4. Fire / Smoke
        if "fire" in query or "smoke" in query:
             hazards = state.active_fire_zones + state.active_smoke_zones
             if hazards:
                 return f"Hazard Alert: {', '.join(hazards)}"
             else:
                 return "No active fire or smoke detected."

        # Default
        return "System Online. Monitoring Tactical Feed. Repeat query."

    def run(self):
        sys_prompt = "You are a tactical safety assistant. Brief answers."
        try: 
            with open(SYSTEM_PROMPT_FILE, "r") as f: 
                sys_prompt = f.read()
        except: 
            pass
        
        last_threat_time = 0
        last_auto_msg_time = 0
        llm_response_q = queue.Queue()
        llm_busy = False
        
        try: 
            requests.get("http://localhost:11434", timeout=1)
            self.ai_status = "ONLINE"
        except: 
            self.ai_status = "OFFLINE"

        while self.running:
            try:
                # 0. AUTO-SAFETY MONITOR (Smart Water Management)
                with self.state.lock:
                    # Initialize tracking set for alerts to prevent spamming
                    if not hasattr(self, 'alerted_zones'): self.alerted_zones = set()

                    current_fire = set(self.state.active_fire_zones)
                    current_sprinklers = set(self.state.active_sprinkler_zones)
                    
                    # A. Detect UNTREATED Fire -> ALERT ONLY (Manual Start)
                    untreated = current_fire - current_sprinklers
                    
                    # Only alert for NEW zones we haven't warned about yet
                    new_alerts = untreated - self.alerted_zones
                    for zone in new_alerts:
                        alert_msg = f"AI WARNING: Fire detected in {zone}. Awaiting authorization."
                        self.state.ai_message = alert_msg
                        self.state.chat_history.append(f"AI: {alert_msg}")
                        self.state.chat_scroll_offset = 0
                        try: threading.Thread(target=lambda: self.speak(f"Warning. Fire in {zone}"), daemon=True).start()
                        except: pass
                        self.alerted_zones.add(zone)
                    
                    # Reset alerts for zones that are no longer untreated (e.g. handled or fire gone)
                    self.alerted_zones = self.alerted_zones.intersection(untreated)

                    # B. Detect EXTINGUISHED Fire -> AUTO OFF (Efficiency)
                    cleaning_up = current_sprinklers - current_fire
                    if cleaning_up:
                         for zone in cleaning_up:
                             self.state.stop_sprinklers(zone) # Auto-Stop to prevent flooding/spam
                             info_msg = f"AI SAFETY: Target neutralized in {zone}. Deactivating sprinklers."
                             self.state.ai_message = info_msg
                             self.state.chat_history.append(f"AI: {info_msg}")

                # 1. Check for inputs
                user_text = ""
                try:
                    user_text = self.state.voice_input_q.get_nowait()
                except queue.Empty:
                    pass

                if user_text:
                    with self.state.lock:
                        self.state.chat_history.append(f"USER: {user_text}")
                        self.state.chat_scroll_offset = 0 # Auto-scroll to bottom
                        if len(self.state.chat_history) > 500:
                             self.state.chat_history = self.state.chat_history[-500:]
                    self.ai_status = "THINKING..."
                    ctx = self.state.get_ground_truth_context()
                    
                    health_report = []
                    for p in self.state.people:
                        h_status = "HEALTHY"
                        if p.hp < 80: h_status = "INJURED"
                        if p.hp < 40: h_status = "CRITICAL"
                        health_report.append(f"- {p.name}: {int(p.hp)}% [{p.status}] at {self.state.get_zone_of(p)}")
                    
                    escaped_report = []
                    for name in self.state.escaped_people:
                         escaped_report.append(f"- {name}: SECURED")

                    health_str = "\n".join(health_report) if health_report else "No Active Personnel"
                    escaped_str = "\n".join(escaped_report) if escaped_report else "None"
                    
                    # === INTELLIGENT COMMAND PARSING ===
                    lower_input = user_text.lower()
                    
                    if any(w in lower_input for w in ["sprinkler", "sprinkle", "water", "extinguish", "suppress"]) or ("fire" in lower_input and "off" in lower_input):

                        # Detect Zone FIRST (shared for both ON and OFF commands)
                        target_zone = None
                        zone_map = {
                            "lobby": "Zone A1 (Lobby)", "a1": "Zone A1 (Lobby)",
                            "command": "Zone C1 (Command)", "c1": "Zone C1 (Command)",
                            "cafeteria": "Zone A2 (Cafeteria)", "kitchen": "Zone A2 (Cafeteria)", "a2": "Zone A2 (Cafeteria)",
                            "server": "Zone B1 (Server)", "b1": "Zone B1 (Server)",
                            "medical": "Zone C2 (Medical)", "medic": "Zone C2 (Medical)", "medbay": "Zone C2 (Medical)", "c2": "Zone C2 (Medical)",
                            "chem": "Zone B2 (Chem Lab)", "lab": "Zone B2 (Chem Lab)", "chemical": "Zone B2 (Chem Lab)", "b2": "Zone B2 (Chem Lab)",
                            "north": "North Gate", "south": "South Gate", "west": "West Emergency",
                            "hallway": "Hallway" 
                        }
                        sorted_keys = sorted(zone_map.keys(), key=len, reverse=True)
                        for k in sorted_keys:
                            if k in lower_input:
                                target_zone = zone_map[k]
                                break
                        
                        # DETERMINE INTENT: ON or OFF?
                        # "turn off fire" -> ON (Extinguish)
                        # "turn off sprinklers" -> OFF
                        # "stop" -> OFF
                        
                        is_turn_off = False
                        if "stop" in lower_input: 
                            is_turn_off = True
                        elif "off" in lower_input:
                            if "fire" in lower_input and "sprinkler" not in lower_input:
                                # "turn off fire" -> Extinguish -> ON
                                is_turn_off = False 
                            else:
                                # "turn off sprinklers", "water off" -> OFF
                                is_turn_off = True

                        if is_turn_off:
                             self.state.stop_sprinklers(target_zone)
                             if target_zone:
                                 ai_reply = f"COMMAND ACCEPTED: STOPPING SPRINKLERS IN {target_zone}."
                             else:
                                 ai_reply = "COMMAND ACCEPTED: STOPPING ALL SPRINKLERS."
                             
                             with self.state.lock:
                                self.state.ai_message = ai_reply
                                self.state.chat_history.append(f"AI: {ai_reply}")
                                self.state.chat_scroll_offset = 0
                             time.sleep(0.5)
                             continue
                        
                        # TURN ON (Default if not off)
                        # TURN ON (Strict Fire-Only Policy)
                        if target_zone:
                            # User specified a zone. Verify fire.
                            # Note: active_fire_zones is a list of names
                            if target_zone in self.state.active_fire_zones:
                                self.state.start_sprinklers(target_zone)
                                ai_reply = f"COMMAND ACCEPTED: ACTIVATING SPRINKLERS IN {target_zone} (CONFIRMED FIRE)."
                            else:
                                ai_reply = f"REQUEST DENIED: NO FIRE DETECTED IN {target_zone}. WATER CONSERVED."
                        else:
                            # User said "turn on sprinklers" generic.
                            # Find ALL active fire zones.
                            fires = self.state.active_fire_zones
                            if fires:
                                for fz in fires:
                                    self.state.start_sprinklers(fz)
                                valid_zones = ", ".join(fires)
                                ai_reply = f"COMMAND ACCEPTED: ACTIVATING SPRINKLERS IN FIRE ZONES: {valid_zones}."
                            else:
                                ai_reply = "REQUEST DENIED: NO ACTIVE FIRES DETECTED. PRESERVING WATER RESOURCES."
                        
                        with self.state.lock:
                            self.state.ai_message = ai_reply
                            self.state.chat_history.append(f"AI: {ai_reply}")
                            self.state.chat_scroll_offset = 0
                        time.sleep(0.5)
                        continue

                    # MANUAL FIRE START
                    if "start fire" in lower_input or "create fire" in lower_input:
                        zone_map = {
                            "lobby": "Zone A1 (Lobby)", "a1": "Zone A1 (Lobby)",
                            "command": "Zone C1 (Command)", "c1": "Zone C1 (Command)",
                            "cafeteria": "Zone A2 (Cafeteria)", "kitchen": "Zone A2 (Cafeteria)", "a2": "Zone A2 (Cafeteria)",
                            "server": "Zone B1 (Server)", "b1": "Zone B1 (Server)",
                            "medical": "Zone C2 (Medical)", "medic": "Zone C2 (Medical)", "medbay": "Zone C2 (Medical)", "c2": "Zone C2 (Medical)",
                            "chem": "Zone B2 (Chem Lab)", "lab": "Zone B2 (Chem Lab)", "chemical": "Zone B2 (Chem Lab)", "b2": "Zone B2 (Chem Lab)"
                        }
                        tgt = None
                        for k,v in zone_map.items():
                             if k in lower_input: tgt = v; break
                        
                        if tgt:
                            self.state.manual_start_fire(tgt)
                            ai_reply = f"WARNING: INITIATING SIMULATED FIRE IN {tgt}"
                        else:
                            ai_reply = "ERROR: Please specify a valid zone for fire test."

                        with self.state.lock:
                            self.state.ai_message = ai_reply
                            self.state.chat_history.append(f"AI: {ai_reply}")
                        continue

                    # 2. STATUS SHORTCUTS
                    if any(x in lower_input for x in ["safe", "status", "everyone", "anyone", "dead", "alive", "okay", "report", "how many"]):
                        active_count = len(self.state.people)
                        esc_c = len(self.state.escaped_people)
                        dead_c = len(self.state.casualties)
                        
                        summary = f"{active_count} Active, {esc_c} Evacuated."
                        if dead_c > 0:
                             ai_reply = f"CRITICAL: {dead_c} FATALITIES. {summary}"
                        else:
                             ai_reply = f"ALL CLEAR ON FATALITIES. {summary}"

                        with self.state.lock:
                            self.state.ai_message = ai_reply
                            self.state.chat_history.append(f"AI: {ai_reply}")
                            self.state.chat_scroll_offset = 0
                        time.sleep(0.5)
                        continue

                    # 3. LLM QUERY
                    context_str = "CURRENT STATUS:\n"
                    if self.state.active_fire_zones:
                        context_str += f"FIRE ZONES: {', '.join(self.state.active_fire_zones)}\n"
                    else:
                        context_str += "FIRE ZONES: None\n"
                        
                    context_str += f"UNITS: {health_str.replace(chr(10), ', ')}\n" 
                    
                    # Few-shot
                    prompt = (
                        f"{context_str}\n\n"
                        "User: Where is the fire?\n"
                        "Assistant: Fire is located in Zone B2 (Chem Lab).\n\n"
                        f"User: {user_text}\n"
                        "Assistant:"
                    )
                    
                    payload = {
                        "model": MODEL_NAME,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "num_ctx": 1024,
                            "num_predict": 40, 
                            "stop": ["User:", "Assistant:", "\n"] 
                        }
                    }
                    
                    try:
                        # Increased timeout to 20s for slower models
                        resp = requests.post(OLLAMA_URL, json=payload, timeout=20) 
                        if resp.status_code == 200:
                            raw = resp.json().get("response", "").strip().replace("System:", "").replace("Assistant:", "")
                            if not raw: raise Exception("Empty Response")
                            ai_reply = raw
                            self.ai_status = "ONLINE"
                        else: 
                             raise Exception(f"Status {resp.status_code}")
                    except Exception as e: 
                        print(f"LLM Error: {e}")
                        # Fallback to rule-based response
                        ai_reply = self.generate_fallback_response(user_text, self.state)
                        self.ai_status = "OFFLINE (Fallback)"

                    with self.state.lock:
                        self.state.ai_message = ai_reply
                        self.state.chat_history.append(f"AI: {ai_reply}")
                        self.state.chat_scroll_offset = 0
                
                time.sleep(0.5)
                
            except Exception as e:
                print(f"AI Loop Error: {e}")
                time.sleep(1)

# ==========================================
# UI & DRAWING
# ==========================================

def draw_dynamic_path(screen, state):
    if not state.current_path or len(state.current_path) < 1: return
    p = state.get_current_person()
    if not p: return 
    
    all_rects = {**ZONES, **EXITS}
    
    # Resolve path to coordinates
    path_coords = []
    valid_path_nodes = []
    for zone_name in state.current_path:
        if zone_name in all_rects:
            path_coords.append(all_rects[zone_name].center)
            valid_path_nodes.append(zone_name)
            
    if not path_coords: return

    # --- PATH SMOOTHING LOGIC ---
    # Attempt to skip the first node if we are "past" it towards the second node
    start_idx = 0
    if len(path_coords) >= 2:
        start_center = path_coords[0]
        next_center = path_coords[1]
        
        # Distances
        dist_p_next = math.hypot(p.x - next_center[0], p.y - next_center[1])
        dist_start_next = math.hypot(start_center[0] - next_center[0], start_center[1] - next_center[1])
        
        # If we are closer to the next node than the start node was -> We are "en route"
        # Skip drawing the line *back* to the start node
        if dist_p_next <= dist_start_next:
            start_idx = 1 # Skip first node visually
            
    points = []
    points.append((p.x, p.y)) # Player always start
    
    for i in range(start_idx, len(path_coords)):
        points.append(path_coords[i])
    
    if len(points) > 1:
        # Glow Effect
        pygame.draw.lines(screen, (0, 100, 100), False, points, 10)
        pygame.draw.lines(screen, (0, 255, 255), False, points, 4)
        # End Cap
        pygame.draw.circle(screen, (0, 255, 255), points[-1], 6)

def wrap_text(text, font, max_width):
    words = text.split(' ')
    lines = []
    current_line = []
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        w, h = font.size(test_line)
        if w < max_width:
            current_line.append(word)
        else:
            lines.append(' '.join(current_line))
            current_line = [word]
    lines.append(' '.join(current_line))
    return lines


        
    ai_thread.running = False
    pygame.quit()
    sys.exit()



def draw_blueprint_map(screen, font_md, state):
    # 1. Base Floors with Grid
    all_rects = {**ZONES, **EXITS}
    
    for name, rect in all_rects.items():
        # Determine Floor Color
        col = (30, 35, 45) # Dark Blue Grey
        if "Hallway" in name: col = (25, 30, 40) # Slightly darker hallway
        if "EXIT" in name: col = (40, 60, 40)
        
        pygame.draw.rect(screen, col, rect)
        
        # Grid Texture
        for x in range(rect.x, rect.right, 20):
            pygame.draw.line(screen, (40, 45, 55), (x, rect.y), (x, rect.bottom))
        for y in range(rect.y, rect.bottom, 20):
             pygame.draw.line(screen, (40, 45, 55), (rect.x, y), (rect.right, y))

    # 1b. FIRE CELLS (Grid)
    fire_col = (255, 69, 0) # Red Orange
    for (gx, gy) in state.fire_cells:
        # Flicker
        f_col = (255, random.randint(50, 150), 0)
        cell_rect = pygame.Rect(gx*state.GRID_SIZE, gy*state.GRID_SIZE, state.GRID_SIZE, state.GRID_SIZE)
        pygame.draw.rect(screen, f_col, cell_rect)

    # 1c. WATER CELLS (Grid)
    for (gx, gy) in state.water_cells:
        w_col = (0, 150, 255) # Deep Cyan
        if random.randint(0,10) > 8: w_col = (100, 200, 255) # Sparkle
        cell_rect = pygame.Rect(gx*state.GRID_SIZE, gy*state.GRID_SIZE, state.GRID_SIZE, state.GRID_SIZE)
        pygame.draw.rect(screen, w_col, cell_rect)

    # 2. Thick Walls (Borders)

    # 2. Thick Walls (Borders)
    # We draw borders for all, simulating walls.
    for name, rect in all_rects.items():
         border_col = (100, 120, 140)
         if "EXIT" in name: border_col = (50, 200, 100)
         pygame.draw.rect(screen, border_col, rect, 3) # Thick wall
         
         # Room Label
         if "Hallway" not in name and "EXIT" not in name:
             label = name.split("(")[-1].strip(")")
             screen.blit(font_md.render(label, True, (150, 180, 200)), (rect.centerx - 30, rect.centery))
         elif "EXIT" in name:
             screen.blit(font_md.render(name.upper(), True, (150, 255, 150)), (rect.x+5, rect.y+5))

def draw_realistic_person(screen, p, is_active, font_sm):
    # Body (Shoulders)
    bx, by = int(p.x), int(p.y)
    
    # Body Color
    body_col = p.color
    if is_active: body_col = (255, 255, 255) # Highlight active

    # Draw Shoulders (Rounded Rect)
    sh_w, sh_h = 16, 10
    pygame.draw.rect(screen, body_col, (bx - sh_w//2, by - 2, sh_w, sh_h), border_radius=5)
    
    # Head
    pygame.draw.circle(screen, (220, 200, 180), (bx, by - 4), 5) # Skin tone head
    
    # Selection Ring
    if is_active:
         pygame.draw.circle(screen, (0, 255, 255), (bx, by), 12, 1)

    # HP Bar (Floating)
    hp_w = 24
    hp_x = bx - hp_w // 2
    hp_y = by - 16
    
    hp_c = (0, 255, 0)
    if p.hp < 60: hp_c = (255, 165, 0)
    if p.hp < 30: hp_c = (255, 0, 0)
    
    pygame.draw.rect(screen, (0,0,0), (hp_x, hp_y, hp_w, 4))
    pygame.draw.rect(screen, hp_c, (hp_x, hp_y, int(hp_w * (p.hp/100)), 4))
    
    # Name Label (only if active or mouse hover - simplified to active for now)
    if is_active or p.hp < 100:
         lbl = font_sm.render(p.name, True, (200, 200, 200))
         screen.blit(lbl, (bx - lbl.get_width()//2, by - 30))


def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Safety LLM - Live Command v6.0 (Realistic)")
    
    font_sm = pygame.font.SysFont("Consolas", 12) 
    font_md = pygame.font.SysFont("Arial", 14) # Smaller, cleaner
    font_lg = pygame.font.SysFont("Verdana", 16, bold=True)
    
    clock = pygame.time.Clock()
    state = SimulationState()
    
    ai_thread = AICommander(state)
    ai_thread.start()
    VoiceHandler(state).start()
    
    running = True
    speed = 5
    
    ui_buttons = {}
    
    try:
        while running:
            # 1. EVENT HANDLING
            for event in pygame.event.get():
                if event.type == pygame.QUIT: running = False

                if event.type == pygame.MOUSEWHEEL:
                    state.chat_scroll_offset += event.y
                    
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1: 
                        pos = event.pos
                        if ui_buttons:
                            if "TYPE" in ui_buttons and ui_buttons["TYPE"].collidepoint(pos):
                                state.is_typing = True
                                state.input_text = ""
                            elif "VOICE" in ui_buttons and ui_buttons["VOICE"].collidepoint(pos):
                                state.is_recording = not state.is_recording
                            elif "SWITCH" in ui_buttons and ui_buttons["SWITCH"].collidepoint(pos):
                                state.switch_person()

                if event.type == pygame.KEYDOWN:
                    if state.is_typing:
                        if event.key == pygame.K_RETURN:
                            if state.input_text.strip():
                                txt = state.input_text.strip()
                                state.last_user_query = txt
                                state.voice_input_q.put(txt)
                                state.input_text = ""
                            state.is_typing = False
                        elif event.key == pygame.K_BACKSPACE:
                            state.input_text = state.input_text[:-1]
                        elif event.key == pygame.K_ESCAPE:
                            state.is_typing = False
                        else:
                            state.input_text += event.unicode
                    else:
                        if event.key == pygame.K_v: state.is_recording = not state.is_recording
                        if event.key == pygame.K_TAB: state.switch_person()
                        if event.key == pygame.K_t: 
                            state.is_typing = True
                            state.input_text = ""

            keys = pygame.key.get_pressed()
            p = state.get_current_person()
            
            if p and not state.is_typing:
                mx, my = 0, 0
                if keys[pygame.K_LEFT]: mx = -speed
                if keys[pygame.K_RIGHT]: mx = speed
                if keys[pygame.K_UP]: my = -speed
                if keys[pygame.K_DOWN]: my = +speed
                
                future_x = p.x + mx
                future_y = p.y + my
                
                hazard = state.check_future_hazard(future_x, future_y)
                state.proximity_alert = hazard if hazard else ""

                if state.is_valid_move(future_x, future_y):
                    p.x = future_x
                    p.y = future_y

            state.update_logic()
            
            screen.fill(COLOR_BG)
            
            # 2. DRAW REALISTIC MAP
            draw_blueprint_map(screen, font_md, state)
                
            # 3. DRAW PATH
            if p: draw_dynamic_path(screen, state)
            
            # 4. DRAW REALISTIC PEOPLE
            active_name = p.name if p else ""
            
            for person in state.people:
                is_active = (person.name == active_name)
                draw_realistic_person(screen, person, is_active, font_sm)
            
            # 5. DRAW INTERFACE
            ui_buttons = draw_professional_interface(screen, font_sm, font_lg, state, ai_thread.ai_status)
            
            pygame.display.flip()
            clock.tick(FPS)
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"CRITICAL ERROR: {e}")
    finally:
        ai_thread.running = False
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    main()
