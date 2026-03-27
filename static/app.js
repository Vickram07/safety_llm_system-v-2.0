const canvas = document.getElementById('simCanvas');
const ctx = canvas.getContext('2d');
const container = document.getElementById('canvasContainer');
const scenarioSelector = document.getElementById('scenarioSelector');
const rosterList = document.getElementById('rosterList');
const connectionStatus = document.getElementById('connectionStatus');
const threatLevel = document.getElementById('threatLevel');
const paOverlayContainer = document.getElementById('paOverlayContainer');
const clearFireBtn = document.getElementById('clearFireBtn');
const focusedTrackingPanel = document.getElementById('focusedTrackingPanel');
const focusName = document.getElementById('focusName');
const focusId = document.getElementById('focusId');
const focusStatus = document.getElementById('focusStatus');
const focusHp = document.getElementById('focusHp');
const focusRoute = document.getElementById('focusRoute');

let ws;
let simState = null;
let lastTime = performance.now();
let frameCount = 0;
let lastFpsTime = performance.now();
let mouseX = 0;
let mouseY = 0;
let hoveredPerson = null;
let currentPOV = "OPERATOR";
const MAP_OFFSET_X = 50;
const MAP_OFFSET_Y = 50;
const SCALE = 1.0;

// Constants matching server
const ZONES = {
    "Zone A1 (Lobby)": { x: 330, y: 70, w: 200, h: 180 },
    "Zone C1 (Command)": { x: 692, y: 70, w: 200, h: 180 },
    "Zone A2 (Cafeteria)": { x: 1054, y: 70, w: 200, h: 180 },
    "Zone B1 (Server)": { x: 330, y: 310, w: 200, h: 180 },
    "Zone C2 (Medical)": { x: 692, y: 310, w: 200, h: 180 },
    "Zone B2 (Chem Lab)": { x: 1054, y: 310, w: 200, h: 180 },
    "Hallway West Top": { x: 530, y: 110, w: 162, h: 100 },
    "Hallway East Top": { x: 892, y: 110, w: 162, h: 100 },
    "Hallway West Bot": { x: 530, y: 350, w: 162, h: 100 },
    "Hallway East Bot": { x: 892, y: 350, w: 162, h: 100 },
    "Central Spine": { x: 742, y: 250, w: 100, h: 60 }
};

const EXITS = {
    "North Gate": { x: 742, y: 10, w: 100, h: 60 },
    "South Gate": { x: 742, y: 490, w: 100, h: 60 },
    "West Emergency": { x: 280, y: 110, w: 50, h: 100 }
};

function resizeCanvas() {
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;
}
window.addEventListener('resize', resizeCanvas);
resizeCanvas();

function initWebSocket() {
    ws = new WebSocket(`ws://${window.location.host}/ws`);

    ws.onopen = () => {
        connectionStatus.textContent = "● CONNECTED";
        connectionStatus.className = "text-xs text-system-safe font-mono";
    };

    ws.onclose = () => {
        connectionStatus.textContent = "○ DISCONNECTED (RETRYING...)";
        connectionStatus.className = "text-xs text-system-alert font-mono";
        setTimeout(initWebSocket, 2000);
    };

    ws.onmessage = (event) => {
        simState = JSON.parse(event.data);
    };
}

// Draw Map
function drawMap() {
    ctx.lineWidth = 2;
    // Draw Zones
    for (const [name, rect] of Object.entries(ZONES)) {
        ctx.fillStyle = 'rgba(20, 25, 35, 0.8)';
        ctx.strokeStyle = 'rgba(50, 150, 200, 0.4)';
        if (simState && simState.active_fire_zones.includes(name)) {
            ctx.strokeStyle = 'rgba(255, 50, 50, 0.8)';
            ctx.fillStyle = 'rgba(50, 10, 10, 0.8)';
        }

        ctx.beginPath();
        ctx.rect(MAP_OFFSET_X + rect.x, MAP_OFFSET_Y + rect.y, rect.w, rect.h);
        ctx.fill();
        ctx.stroke();

        // Label
        ctx.fillStyle = 'rgba(255, 255, 255, 0.3)';
        ctx.font = '12px JetBrains Mono';
        ctx.fillText(name, MAP_OFFSET_X + rect.x + 10, MAP_OFFSET_Y + rect.y + 20);
    }

    // Draw Exits
    for (const [name, rect] of Object.entries(EXITS)) {
        ctx.fillStyle = 'rgba(0, 200, 100, 0.2)';
        ctx.strokeStyle = 'rgba(0, 255, 128, 0.8)';
        ctx.beginPath();
        ctx.rect(MAP_OFFSET_X + rect.x, MAP_OFFSET_Y + rect.y, rect.w, rect.h);
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = '#00ff80';
        ctx.fillText("EXIT", MAP_OFFSET_X + rect.x + 5, MAP_OFFSET_Y + rect.y + 20);
    }
}

function drawFire() {
    if (!simState || !simState.fire_cells) return;
    const GRID_SIZE = 10;

    for (const cell of simState.fire_cells) {
        const [gx, gy] = cell;
        const x = MAP_OFFSET_X + gx * GRID_SIZE;
        const y = MAP_OFFSET_Y + gy * GRID_SIZE;

        // Dynamic jitter for fire
        const jx = (Math.random() - 0.5) * 2;
        const jy = (Math.random() - 0.5) * 2;

        const gradient = ctx.createRadialGradient(x + 5 + jx, y + 5 + jy, 0, x + 5 + jx, y + 5 + jy, 8);
        gradient.addColorStop(0, 'rgba(255, 255, 100, 0.9)');
        gradient.addColorStop(0.4, 'rgba(255, 100, 0, 0.8)');
        gradient.addColorStop(1, 'rgba(255, 0, 0, 0)');

        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(x + 5, y + 5, 10, 0, Math.PI * 2);
        ctx.fill();
    }
}

function getZoneCenter(name) {
    const all = { ...ZONES, ...EXITS };
    if (all[name]) {
        return {
            x: MAP_OFFSET_X + all[name].x + all[name].w / 2,
            y: MAP_OFFSET_Y + all[name].y + all[name].h / 2
        };
    }
    return { x: 0, y: 0 };
}

function drawPeopleAndPaths() {
    if (!simState) return;

    hoveredPerson = null;

    // First pass: Check hover
    for (const p of simState.people) {
        if (p.hp <= 0 || p.status === "ESCAPED") continue;
        const px = MAP_OFFSET_X + p.x;
        const py = MAP_OFFSET_Y + p.y;

        const distToMouse = Math.hypot(px - mouseX, py - mouseY);
        if (distToMouse < 20) {
            hoveredPerson = p.id;
        }
    }

    for (const p of simState.people) {
        if (p.hp <= 0 || p.status === "ESCAPED") continue;

        const px = MAP_OFFSET_X + p.x;
        const py = MAP_OFFSET_Y + p.y;

        const isHovered = hoveredPerson === p.id;
        const showPath = isHovered || currentPOV === "ADMIN" || currentPOV === "OPERATOR";

        // Draw Path
        if (showPath && p.path && p.path.length > 0) {
            ctx.beginPath();
            ctx.strokeStyle = isHovered ? 'rgba(0, 255, 255, 0.8)' : 'rgba(0, 255, 255, 0.3)';
            if (p.status === "PANIC") ctx.strokeStyle = isHovered ? 'rgba(255, 200, 0, 0.9)' : 'rgba(255, 200, 0, 0.4)';

            ctx.setLineDash([5, 5]);
            ctx.lineWidth = isHovered ? 3 : 2;
            ctx.moveTo(px, py);

            for (const node of p.path) {
                const center = getZoneCenter(node);
                ctx.lineTo(center.x, center.y);
            }
            ctx.stroke();
            ctx.setLineDash([]);

            // Draw path pulse
            const timeOffset = (performance.now() / 1000) % 1;
            ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
            if (p.path.length > 0) {
                const target = getZoneCenter(p.path[0]);
                const dx = target.x - px;
                const dy = target.y - py;
                ctx.beginPath();
                ctx.arc(px + dx * timeOffset, py + dy * timeOffset, isHovered ? 5 : 3, 0, Math.PI * 2);
                ctx.fill();
            }
        }

        // Draw CCTV Tracking Box
        let colorStr = '0, 255, 255';
        if (p.status === "PANIC") colorStr = '255, 100, 0';
        if (p.hp < 50) colorStr = '255, 0, 0';
        if (isHovered) colorStr = '255, 255, 255';

        const boxSize = isHovered ? 24 : 16;
        ctx.strokeStyle = `rgba(${colorStr}, 0.8)`;
        ctx.lineWidth = isHovered ? 2 : 1;
        ctx.strokeRect(px - boxSize / 2, py - boxSize / 2, boxSize, boxSize);

        // Draw blip
        ctx.fillStyle = `rgb(${colorStr})`;
        ctx.beginPath();
        ctx.arc(px, py, isHovered ? 6 : 4, 0, Math.PI * 2);
        ctx.fill();

        // Label
        if (isHovered || currentPOV === "CAMERA" || currentPOV === "OPERATOR") {
            ctx.fillStyle = 'white';
            ctx.font = '10px JetBrains Mono';
            ctx.fillText(`ID:${p.id}`, px + 15, py - 15);
            ctx.fillText(`HP:${Math.floor(p.hp)}`, px + 15, py - 3);

            if (isHovered && p.path && p.path.length > 0) {
                ctx.fillStyle = '#00ffff';
                ctx.fillText(`TARGET: ${p.path[p.path.length - 1]}`, px + 15, py + 10);
            }
        } else {
            ctx.fillStyle = `rgba(${colorStr}, 0.6)`;
            ctx.font = '10px JetBrains Mono';
            ctx.fillText(p.id, px + 8, py - 8);
        }
    }
}

// Manage UI Overlays (Roster, Threat, PA Announcements)
let displayedAnnouncements = new Set();

function updateUI() {
    if (!simState) return;

    // Roster
    rosterList.innerHTML = '';
    let isSystemCritical = false;

    simState.people.forEach(p => {
        if (p.hp <= 0 || p.status === "ESCAPED") return;

        const div = document.createElement('div');
        div.className = `p-2 rounded border text-sm font-mono flex justify-between ${p.status === 'PANIC' || p.hp < 50 ? 'bg-red-900/30 border-red-500/50' : 'bg-slate-800/50 border-cyan-900/50'
            }`;

        let statusCol = p.status === 'PANIC' ? 'text-orange-400' : 'text-cyan-400';
        div.innerHTML = `
            <div>
                <span class="text-white">${p.name}</span>
                <span class="text-xs text-slate-400 block tracking-tight">ID: ${p.id}</span>
            </div>
            <div class="text-right">
                <span class="${statusCol}">${p.status}</span>
                <span class="block text-xs text-slate-400">HP: ${Math.floor(p.hp)}</span>
            </div>
        `;
        rosterList.appendChild(div);

        if (p.status === "PANIC") isSystemCritical = true;
    });

    // Threat Level
    if (simState.active_fire_zones.length > 0) {
        threatLevel.className = "py-2 px-3 rounded bg-red-900/30 border border-red-500 flex items-center space-x-3";
        threatLevel.innerHTML = `
            <span class="text-xl animate-pulse text-red-500">⚠</span>
            <div class="flex flex-col">
                <span class="font-bold text-red-500 tracking-wide text-sm">CRITICAL EMERGENCY</span>
                <span class="text-xs text-red-400">FIRE IN SECTORS: ${simState.active_fire_zones.join(', ')}</span>
            </div>
        `;
    } else {
        threatLevel.className = "py-2 px-3 rounded bg-system-safe/20 border border-system-safe flex items-center space-x-3";
        threatLevel.innerHTML = `
            <span class="text-xl text-system-safe">✓</span>
            <span class="font-bold text-system-safe tracking-wide text-sm">ALL SYSTEMS NOMINAL</span>
        `;
    }

    // Hovered Tracking Panel
    if (hoveredPerson) {
        const hpn = simState.people.find(p => p.id === hoveredPerson);
        if (hpn) {
            focusedTrackingPanel.classList.remove("hidden");
            focusName.textContent = hpn.name;
            focusId.textContent = hpn.id;
            focusStatus.textContent = hpn.status;
            focusStatus.className = hpn.status === "PANIC" ? "font-bold text-red-500 text-right" : "font-bold text-cyan-500 text-right";
            focusHp.textContent = Math.floor(hpn.hp) + "%";

            if (hpn.path && hpn.path.length > 0) {
                focusRoute.innerHTML = hpn.path.join('<br><span class="text-slate-500 pl-2">↓</span><br>');
            } else {
                focusRoute.textContent = "STANDBY";
            }
        }
    } else {
        focusedTrackingPanel.classList.add("hidden");
    }

    // PA Announcements
    const currentAnnIds = new Set(simState.pa_announcements.map(a => a.id));

    // Remove stale ones
    Array.from(paOverlayContainer.children).forEach(child => {
        if (!currentAnnIds.has(child.dataset.id)) {
            child.style.opacity = '0';
            setTimeout(() => child.remove(), 300);
        }
    });

    // Add new ones
    simState.pa_announcements.forEach(ann => {
        if (!document.querySelector(`[data-id="${ann.id}"]`)) {
            const el = document.createElement('div');
            el.dataset.id = ann.id;
            el.className = 'absolute pa-popup bg-red-950/90 border border-red-500 p-3 rounded-lg shadow-[0_0_20px_rgba(255,0,0,0.5)] max-w-xs z-50';
            // Position based on person's location
            el.style.left = `${MAP_OFFSET_X + ann.x + 20}px`;
            el.style.top = `${MAP_OFFSET_Y + ann.y - 40}px`;

            el.innerHTML = `
                <div class="flex items-center space-x-2 mb-1">
                    <div class="w-2 h-2 rounded-full bg-red-500 pa-icon-pulse"></div>
                    <span class="text-[10px] font-bold text-red-400 tracking-widest">PA BROADCAST OVERRIDE</span>
                </div>
                <p class="text-xs font-mono text-white leading-tight">"${ann.text}"</p>
            `;
            paOverlayContainer.appendChild(el);
        } else {
            // Update position if moving
            const el = document.querySelector(`[data-id="${ann.id}"]`);
            el.style.left = `${MAP_OFFSET_X + ann.x + 20}px`;
            el.style.top = `${MAP_OFFSET_Y + ann.y - 40}px`;
        }
    });
}

function render() {
    const now = performance.now();
    frameCount++;
    if (now - lastFpsTime >= 1000) {
        document.getElementById('fpsCounter').textContent = `${frameCount} FPS`;
        frameCount = 0;
        lastFpsTime = now;
    }

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    drawMap();
    drawFire();
    drawPeopleAndPaths();
    updateUI();

    requestAnimationFrame(render);
}

// Interactions
canvas.addEventListener('mousemove', (e) => {
    const rect = canvas.getBoundingClientRect();
    mouseX = e.clientX - rect.left;
    mouseY = e.clientY - rect.top;
});

canvas.addEventListener('mousedown', (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left - MAP_OFFSET_X;
    const y = e.clientY - rect.top - MAP_OFFSET_Y;

    // Send click to spawn fire
    fetch('/api/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'manual_fire', x: x, y: y })
    });
});

scenarioSelector.addEventListener('change', (e) => {
    currentPOV = e.target.value;

    // Update container classes for CSS overrides
    container.className = "flex-1 relative bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-slate-900 to-black overflow-hidden";
    if (currentPOV === "CAMERA") container.classList.add("pov-camera");
    if (currentPOV === "FIRE_EMERGENCY") container.classList.add("pov-fire");
    if (currentPOV === "ADMIN") container.classList.add("pov-admin");

    fetch('/api/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'set_scenario', target: currentPOV })
    });
});

initWebSocket();
requestAnimationFrame(render);
