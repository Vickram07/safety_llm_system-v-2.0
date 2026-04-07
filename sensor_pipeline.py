import copy
import math
import threading
import time
from collections import defaultdict
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


PIPELINE_ORDER = [
    {
        "stage": "input_layer",
        "order": 1,
        "description": "Collect environmental, CCTV, RFID/BLE, exit, and sprinkler telemetry.",
        "target_latency_ms": 250,
    },
    {
        "stage": "fusion_layer",
        "order": 2,
        "description": "Normalize packets, resolve zones, compute fire probability, and estimate occupancy.",
        "target_latency_ms": 500,
    },
    {
        "stage": "reasoning_layer",
        "order": 3,
        "description": "Feed fused state into the LLM and agent workflow for suppression and evacuation decisions.",
        "target_latency_ms": 1500,
    },
    {
        "stage": "action_layer",
        "order": 4,
        "description": "Apply suppression targets, exit availability, PA guidance, and operator dashboard updates.",
        "target_latency_ms": 1000,
    },
]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def normalize_label(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())


class EnvironmentalReading(BaseModel):
    sensor_id: str
    zone: str
    sensor_type: str
    value: float
    unit: str = ""
    status: str = "nominal"
    confidence: float = 0.9
    timestamp: Optional[float] = None


class CameraObservation(BaseModel):
    camera_id: str
    zone: str
    flame_score: float = 0.0
    smoke_score: float = 0.0
    blockage_score: float = 0.0
    person_count: int = 0
    verified_fire: bool = False
    confidence: float = 0.85
    notes: Optional[str] = None
    timestamp: Optional[float] = None


class OccupantObservation(BaseModel):
    occupant_id: str
    zone: str
    source: str = "rfid"
    x: Optional[float] = None
    y: Optional[float] = None
    confidence: float = 0.9
    status: str = "detected_active"
    timestamp: Optional[float] = None


class ExitTelemetry(BaseModel):
    exit_id: str
    available: bool = True
    blockage_score: float = 0.0
    smoke_score: float = 0.0
    confidence: float = 0.85
    timestamp: Optional[float] = None


class SprinklerTelemetry(BaseModel):
    zone: str
    active: bool = False
    flow_rate_lpm: float = 0.0
    pressure_kpa: float = 0.0
    confidence: float = 0.9
    timestamp: Optional[float] = None


class SensorFusionPacket(BaseModel):
    building_id: str = "INFERNALX-HQ"
    packet_id: Optional[str] = None
    timestamp: Optional[float] = None
    source: str = "api"
    environmental: List[EnvironmentalReading] = Field(default_factory=list)
    cameras: List[CameraObservation] = Field(default_factory=list)
    occupants: List[OccupantObservation] = Field(default_factory=list)
    exits: List[ExitTelemetry] = Field(default_factory=list)
    sprinklers: List[SprinklerTelemetry] = Field(default_factory=list)


def model_to_dict(model_obj):
    if hasattr(model_obj, "model_dump"):
        return model_obj.model_dump()
    return model_obj.dict()


def normalize_sensor_payload(payload) -> SensorFusionPacket:
    if isinstance(payload, SensorFusionPacket):
        return payload

    if isinstance(payload, BaseModel):
        payload = model_to_dict(payload)

    if not isinstance(payload, dict):
        raise ValueError("Sensor payload must be a dictionary or SensorFusionPacket.")

    if any(key in payload for key in ("environmental", "cameras", "occupants", "exits", "sprinklers")):
        return SensorFusionPacket(**payload)

    environmental: List[EnvironmentalReading] = []
    cameras: List[CameraObservation] = []
    occupants: List[OccupantObservation] = []

    for sensor_id, sensor_data in (payload.get("sensors") or {}).items():
        zone = sensor_data.get("zone") or sensor_id.replace("_", " ").replace("-", " ")
        sensor_type = (sensor_data.get("type") or "generic").lower()
        added_any = False

        if "value_temp_c" in sensor_data:
            environmental.append(
                EnvironmentalReading(
                    sensor_id=f"{sensor_id}-temp",
                    zone=zone,
                    sensor_type="temperature",
                    value=float(sensor_data["value_temp_c"]),
                    unit="C",
                    status=sensor_data.get("status", "nominal"),
                )
            )
            added_any = True
        if "value_humidity" in sensor_data:
            environmental.append(
                EnvironmentalReading(
                    sensor_id=f"{sensor_id}-humidity",
                    zone=zone,
                    sensor_type="humidity",
                    value=float(sensor_data["value_humidity"]),
                    unit="percent",
                    status=sensor_data.get("status", "nominal"),
                )
            )
            added_any = True
        if "value_obscuration" in sensor_data:
            environmental.append(
                EnvironmentalReading(
                    sensor_id=f"{sensor_id}-smoke",
                    zone=zone,
                    sensor_type="smoke",
                    value=float(sensor_data["value_obscuration"]),
                    unit="obs",
                    status=sensor_data.get("status", "nominal"),
                )
            )
            added_any = True
        if "value_co_ppm" in sensor_data:
            environmental.append(
                EnvironmentalReading(
                    sensor_id=f"{sensor_id}-co",
                    zone=zone,
                    sensor_type="co",
                    value=float(sensor_data["value_co_ppm"]),
                    unit="ppm",
                    status=sensor_data.get("status", "nominal"),
                )
            )
            added_any = True
        if "value" in sensor_data and not added_any:
            environmental.append(
                EnvironmentalReading(
                    sensor_id=sensor_id,
                    zone=zone,
                    sensor_type=sensor_type,
                    value=float(sensor_data["value"]),
                    unit=sensor_data.get("unit", ""),
                    status=sensor_data.get("status", "nominal"),
                )
            )

    for camera_id, camera_data in (payload.get("cctv") or {}).items():
        analysis = (camera_data.get("analysis") or "").lower()
        smoke_score = 0.8 if "smoke" in analysis or "obscuration" in analysis else 0.1
        flame_score = 0.85 if camera_data.get("verified_fire") or "fire" in analysis or "flame" in analysis else 0.0
        blockage_score = 0.75 if "blocked" in analysis else 0.0
        cameras.append(
            CameraObservation(
                camera_id=camera_id,
                zone=camera_data.get("location", "Unknown Zone"),
                flame_score=flame_score,
                smoke_score=smoke_score,
                blockage_score=blockage_score,
                person_count=int(camera_data.get("person_count", 0)),
                verified_fire=bool(camera_data.get("verified_fire", False)),
                notes=camera_data.get("analysis"),
            )
        )

    rfid_logs = payload.get("rfid_logs") or {}
    for sighting in rfid_logs.get("last_seen", []):
        occupants.append(
            OccupantObservation(
                occupant_id=sighting.get("id", "unknown"),
                zone=sighting.get("zone", "Unknown Zone"),
                source="rfid",
                status=sighting.get("status", "detected_active"),
                confidence=0.85,
            )
        )

    return SensorFusionPacket(
        building_id=payload.get("building_id", "INFERNALX-HQ"),
        packet_id=payload.get("packet_id"),
        source=payload.get("source", "legacy"),
        environmental=environmental,
        cameras=cameras,
        occupants=occupants,
    )


class SensorFusionEngine:
    def __init__(self):
        self.lock = threading.RLock()
        self.zone_layout: Dict[str, Dict[str, float]] = {}
        self.exit_layout: Dict[str, Dict[str, float]] = {}
        self.adjacency: Dict[str, List[str]] = {}
        self.last_snapshot = self._empty_snapshot()

    def _empty_snapshot(self):
        return {
            "status": "idle",
            "building_id": "INFERNALX-HQ",
            "last_ingest_at": None,
            "packets_processed": 0,
            "pipeline": copy.deepcopy(PIPELINE_ORDER),
            "zones": {},
            "exits": {},
            "tracked_occupants": [],
            "summary": {
                "highest_risk_zone": "NONE",
                "highest_probability": 0.0,
                "active_fire_zones": [],
                "blocked_exits": [],
                "occupants_tracked": 0,
            },
        }

    def update_layout(self, zones: Dict[str, Dict[str, float]], exits: Dict[str, Dict[str, float]], adjacency: Dict[str, List[str]]):
        with self.lock:
            self.zone_layout = copy.deepcopy(zones)
            self.exit_layout = copy.deepcopy(exits)
            self.adjacency = copy.deepcopy(adjacency)

    def get_snapshot(self):
        with self.lock:
            return copy.deepcopy(self.last_snapshot)

    def _resolve_name(self, label: str, candidates: Dict[str, Dict[str, float]]) -> str:
        if not label:
            return label
        if label in candidates:
            return label

        lookup = {normalize_label(name): name for name in candidates.keys()}
        normalized = normalize_label(label)
        if normalized in lookup:
            return lookup[normalized]

        for alias, actual in lookup.items():
            if normalized and (normalized in alias or alias in normalized):
                return actual
        return label

    def _zone_center(self, zone_name: str):
        rect = self.zone_layout.get(zone_name)
        if not rect:
            return None
        return (rect["x"] + rect["w"] / 2.0, rect["y"] + rect["h"] / 2.0)

    def _direction_to(self, source_zone: str, target_zone: str) -> str:
        src = self._zone_center(source_zone)
        dst = self._zone_center(target_zone)
        if not src or not dst:
            return "LOCALIZED"
        dx = dst[0] - src[0]
        dy = dst[1] - src[1]
        if abs(dx) > abs(dy):
            return "EAST" if dx > 0 else "WEST"
        return "SOUTH" if dy > 0 else "NORTH"

    def _score_environment(self, readings: List[EnvironmentalReading]) -> Dict[str, float]:
        contributions = {
            "temperature": 0.0,
            "smoke": 0.0,
            "co": 0.0,
            "gas": 0.0,
        }
        metrics = {
            "temperature_c": 0.0,
            "smoke_level": 0.0,
            "co_ppm": 0.0,
            "gas_level": 0.0,
        }

        for reading in readings:
            value = float(reading.value)
            confidence = clamp(float(reading.confidence), 0.0, 1.0)
            sensor_type = reading.sensor_type.lower()
            if sensor_type in ("temperature", "temp", "heat"):
                metrics["temperature_c"] = max(metrics["temperature_c"], value)
                if value >= 80:
                    contributions["temperature"] = max(contributions["temperature"], 55.0 * confidence)
                elif value >= 65:
                    contributions["temperature"] = max(contributions["temperature"], 42.0 * confidence)
                elif value >= 50:
                    contributions["temperature"] = max(contributions["temperature"], 24.0 * confidence)
            elif sensor_type in ("smoke", "smoke_detector", "obscuration"):
                metrics["smoke_level"] = max(metrics["smoke_level"], value)
                if value >= 40:
                    contributions["smoke"] = max(contributions["smoke"], 40.0 * confidence)
                elif value >= 20:
                    contributions["smoke"] = max(contributions["smoke"], 30.0 * confidence)
                elif value >= 10:
                    contributions["smoke"] = max(contributions["smoke"], 18.0 * confidence)
            elif sensor_type in ("co", "carbonmonoxide"):
                metrics["co_ppm"] = max(metrics["co_ppm"], value)
                if value >= 120:
                    contributions["co"] = max(contributions["co"], 25.0 * confidence)
                elif value >= 60:
                    contributions["co"] = max(contributions["co"], 16.0 * confidence)
            elif sensor_type in ("gas", "gas_leak"):
                metrics["gas_level"] = max(metrics["gas_level"], value)
                if value >= 50:
                    contributions["gas"] = max(contributions["gas"], 18.0 * confidence)

        metrics["environment_score"] = sum(contributions.values())
        return metrics

    def ingest(self, payload) -> Dict[str, object]:
        packet = normalize_sensor_payload(payload)
        ingested_at = time.time()

        with self.lock:
            zone_env: Dict[str, List[EnvironmentalReading]] = defaultdict(list)
            zone_cameras: Dict[str, List[CameraObservation]] = defaultdict(list)
            zone_occupants: Dict[str, List[OccupantObservation]] = defaultdict(list)
            zone_sprinklers: Dict[str, List[SprinklerTelemetry]] = defaultdict(list)

            for reading in packet.environmental:
                resolved = self._resolve_name(reading.zone, self.zone_layout) if self.zone_layout else reading.zone
                reading.zone = resolved
                zone_env[resolved].append(reading)

            for camera in packet.cameras:
                resolved = self._resolve_name(camera.zone, self.zone_layout) if self.zone_layout else camera.zone
                camera.zone = resolved
                zone_cameras[resolved].append(camera)

            for occupant in packet.occupants:
                resolved = self._resolve_name(occupant.zone, self.zone_layout) if self.zone_layout else occupant.zone
                occupant.zone = resolved
                zone_occupants[resolved].append(occupant)

            for sprinkler in packet.sprinklers:
                resolved = self._resolve_name(sprinkler.zone, self.zone_layout) if self.zone_layout else sprinkler.zone
                sprinkler.zone = resolved
                zone_sprinklers[resolved].append(sprinkler)

            all_zone_names = set(self.zone_layout.keys()) or set(zone_env.keys()) | set(zone_cameras.keys()) | set(zone_occupants.keys())
            zone_states = {}
            highest_zone = "NONE"
            highest_probability = 0.0

            for zone_name in sorted(all_zone_names):
                env_metrics = self._score_environment(zone_env.get(zone_name, []))
                cameras = zone_cameras.get(zone_name, [])
                occupants = zone_occupants.get(zone_name, [])
                sprinklers = zone_sprinklers.get(zone_name, [])

                flame_score = max((camera.flame_score for camera in cameras), default=0.0)
                smoke_camera_score = max((camera.smoke_score for camera in cameras), default=0.0)
                blockage_score = max((camera.blockage_score for camera in cameras), default=0.0)
                verified_fire = any(camera.verified_fire for camera in cameras)
                camera_people = max((camera.person_count for camera in cameras), default=0)
                suppression_active = any(s.active for s in sprinklers)
                flow_rate = max((s.flow_rate_lpm for s in sprinklers), default=0.0)

                fire_probability = env_metrics["environment_score"]
                fire_probability += flame_score * 45.0
                fire_probability += smoke_camera_score * 20.0
                if verified_fire:
                    fire_probability += 15.0
                if suppression_active:
                    fire_probability -= 12.0
                fire_probability = clamp(fire_probability, 0.0, 100.0)

                if fire_probability >= 80:
                    intensity = "critical"
                elif fire_probability >= 60:
                    intensity = "high"
                elif fire_probability >= 35:
                    intensity = "moderate"
                elif fire_probability >= 15:
                    intensity = "low"
                else:
                    intensity = "clear"

                occupant_count = max(camera_people, len(occupants))
                evidence = []
                if env_metrics["temperature_c"]:
                    evidence.append(f"TEMP={round(env_metrics['temperature_c'], 1)}C")
                if env_metrics["smoke_level"]:
                    evidence.append(f"SMOKE={round(env_metrics['smoke_level'], 1)}")
                if flame_score:
                    evidence.append(f"FLAME_SCORE={round(flame_score, 2)}")
                if smoke_camera_score:
                    evidence.append(f"CAMERA_SMOKE={round(smoke_camera_score, 2)}")
                if verified_fire:
                    evidence.append("VISUAL_FIRE_CONFIRMED")
                if suppression_active:
                    evidence.append(f"SPRINKLER_ACTIVE={round(flow_rate, 1)}LPM")

                zone_states[zone_name] = {
                    "fire_probability": round(fire_probability, 2),
                    "intensity": intensity,
                    "temperature_c": round(env_metrics["temperature_c"], 2),
                    "smoke_level": round(env_metrics["smoke_level"], 2),
                    "co_ppm": round(env_metrics["co_ppm"], 2),
                    "gas_level": round(env_metrics["gas_level"], 2),
                    "blockage_score": round(blockage_score, 2),
                    "occupant_count": occupant_count,
                    "suppression_active": suppression_active,
                    "evidence": evidence,
                    "spread_direction": "LOCALIZED",
                }

                if fire_probability > highest_probability:
                    highest_probability = fire_probability
                    highest_zone = zone_name

            for zone_name, zone_state in zone_states.items():
                neighbors = [
                    node
                    for node in self.adjacency.get(zone_name, [])
                    if node in zone_states and zone_states[node]["fire_probability"] >= 25.0
                ]
                if neighbors:
                    hottest_neighbor = max(neighbors, key=lambda item: zone_states[item]["fire_probability"])
                    zone_state["spread_direction"] = self._direction_to(zone_name, hottest_neighbor)

            exit_states = {}
            explicit_exits = {self._resolve_name(entry.exit_id, self.exit_layout): entry for entry in packet.exits}
            for exit_name in sorted(self.exit_layout.keys()):
                entry = explicit_exits.get(exit_name)
                adjacent_zones = [
                    node for node in self.adjacency.get(exit_name, []) if node in zone_states
                ]
                adjacent_risk = max((zone_states[name]["fire_probability"] for name in adjacent_zones), default=0.0)
                inferred_blockage = max((zone_states[name]["blockage_score"] for name in adjacent_zones), default=0.0)

                available = True
                blockage_score = inferred_blockage
                smoke_score = 0.0
                confidence = 0.7
                if entry:
                    available = entry.available
                    blockage_score = max(blockage_score, float(entry.blockage_score))
                    smoke_score = float(entry.smoke_score)
                    confidence = float(entry.confidence)
                if adjacent_risk >= 70 or blockage_score >= 0.7:
                    available = False

                exit_states[exit_name] = {
                    "status": "AVAILABLE" if available else "BLOCKED",
                    "blockage_score": round(blockage_score, 2),
                    "smoke_score": round(smoke_score, 2),
                    "adjacent_risk": round(adjacent_risk, 2),
                    "confidence": round(confidence, 2),
                }

            tracked_occupants = [
                {
                    "occupant_id": occupant.occupant_id,
                    "zone": occupant.zone,
                    "source": occupant.source,
                    "x": occupant.x,
                    "y": occupant.y,
                    "status": occupant.status,
                    "confidence": round(float(occupant.confidence), 2),
                }
                for occupant in sorted(packet.occupants, key=lambda item: item.occupant_id)
            ]

            active_fire_zones = [
                name for name, state in zone_states.items() if state["fire_probability"] >= 60.0
            ]
            blocked_exits = [
                name for name, state in exit_states.items() if state["status"] != "AVAILABLE"
            ]

            snapshot = {
                "status": "active",
                "building_id": packet.building_id,
                "last_ingest_at": ingested_at,
                "packets_processed": self.last_snapshot["packets_processed"] + 1,
                "pipeline": copy.deepcopy(PIPELINE_ORDER),
                "zones": zone_states,
                "exits": exit_states,
                "tracked_occupants": tracked_occupants,
                "summary": {
                    "highest_risk_zone": highest_zone,
                    "highest_probability": round(highest_probability, 2),
                    "active_fire_zones": active_fire_zones,
                    "blocked_exits": blocked_exits,
                    "occupants_tracked": len(tracked_occupants),
                    "packet_source": packet.source,
                },
            }
            self.last_snapshot = snapshot
            return copy.deepcopy(snapshot)
