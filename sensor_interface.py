import json
import os
import time
from typing import Callable, List, Optional

from sensor_pipeline import (
    CameraObservation,
    EnvironmentalReading,
    ExitTelemetry,
    OccupantObservation,
    SensorFusionPacket,
    SprinklerTelemetry,
    model_to_dict,
    normalize_sensor_payload,
)


class SensorProvider:
    """
    Base sensor provider for the INFERNAL X input layer.

    Providers return packets compatible with the sensor fusion pipeline so the
    same data contract can be used in simulation mode and with real devices.
    """

    def get_packet(self) -> SensorFusionPacket:
        raise NotImplementedError("Subclasses must implement get_packet().")


class RealSensorProvider(SensorProvider):
    """
    Adapter-driven provider for real sensors.

    Each adapter is a callable that returns a partial SensorFusionPacket or a
    dictionary compatible with it. This keeps the provider generic enough for
    MQTT, serial, HTTP, BLE, or vendor SDK integrations.
    """

    def __init__(self, adapters: Optional[List[Callable[[], object]]] = None, building_id: str = "INFERNALX-HQ"):
        self.adapters = adapters or []
        self.building_id = building_id

    def get_packet(self) -> SensorFusionPacket:
        merged = {
            "building_id": self.building_id,
            "source": "real-sensors",
            "environmental": [],
            "cameras": [],
            "occupants": [],
            "exits": [],
            "sprinklers": [],
        }

        for adapter in self.adapters:
            packet = adapter()
            if isinstance(packet, SensorFusionPacket):
                packet = model_to_dict(packet)
            if not isinstance(packet, dict):
                continue
            for key in ("environmental", "cameras", "occupants", "exits", "sprinklers"):
                merged[key].extend(packet.get(key, []))

        return SensorFusionPacket(**merged)


class SimulatedSensorProvider(SensorProvider):
    """
    Emits ordered sensor packets aligned to the current INFERNAL X layout.

    This is useful for presentation mode and for testing the end-to-end sensor
    ingestion path before live hardware is connected.
    """

    def __init__(self):
        self.start_time = time.time()

    def get_packet(self) -> SensorFusionPacket:
        elapsed = time.time() - self.start_time

        if elapsed < 10:
            temp_beta = 31.0
            smoke_beta = 1.5
            flame_score = 0.0
            verified_fire = False
            exit_available = True
            sprinkler_active = False
            note = "Normal thermal activity."
        elif elapsed < 20:
            temp_beta = 58.0
            smoke_beta = 15.0
            flame_score = 0.35
            verified_fire = False
            exit_available = True
            sprinkler_active = False
            note = "Smoke plume forming near engineering desks."
        elif elapsed < 30:
            temp_beta = 78.0
            smoke_beta = 32.0
            flame_score = 0.82
            verified_fire = True
            exit_available = False
            sprinkler_active = False
            note = "Visible flame at workstation cluster."
        else:
            temp_beta = 61.0
            smoke_beta = 18.0
            flame_score = 0.28
            verified_fire = True
            exit_available = False
            sprinkler_active = True
            note = "Suppression active, heat receding but smoke still present."

        packet = SensorFusionPacket(
            building_id="INFERNALX-HQ",
            source="simulated-input-layer",
            timestamp=time.time(),
            environmental=[
                EnvironmentalReading(
                    sensor_id="temp-beta-01",
                    zone="Zone Beta (Engineering)",
                    sensor_type="temperature",
                    value=temp_beta,
                    unit="C",
                    status="ALERT" if temp_beta >= 50 else "nominal",
                    confidence=0.95,
                ),
                EnvironmentalReading(
                    sensor_id="smoke-beta-01",
                    zone="Zone Beta (Engineering)",
                    sensor_type="smoke",
                    value=smoke_beta,
                    unit="obs",
                    status="ALERT" if smoke_beta >= 10 else "nominal",
                    confidence=0.96,
                ),
                EnvironmentalReading(
                    sensor_id="co-west-01",
                    zone="West Corridor",
                    sensor_type="co",
                    value=64.0 if elapsed >= 20 else 12.0,
                    unit="ppm",
                    status="WARNING" if elapsed >= 20 else "nominal",
                    confidence=0.88,
                ),
            ],
            cameras=[
                CameraObservation(
                    camera_id="cam-beta-01",
                    zone="Zone Beta (Engineering)",
                    flame_score=flame_score,
                    smoke_score=min(1.0, smoke_beta / 35.0),
                    blockage_score=0.75 if not exit_available else 0.15,
                    person_count=6,
                    verified_fire=verified_fire,
                    confidence=0.94,
                    notes=note,
                )
            ],
            occupants=[
                OccupantObservation(occupant_id="p1", zone="Zone Beta (Engineering)", source="rfid", confidence=0.91),
                OccupantObservation(occupant_id="p2", zone="West Corridor", source="ble", confidence=0.84),
                OccupantObservation(occupant_id="p3", zone="Zone Eta (R&D)", source="rfid", confidence=0.89),
            ],
            exits=[
                ExitTelemetry(
                    exit_id="Exit Beta North",
                    available=exit_available,
                    blockage_score=0.78 if not exit_available else 0.1,
                    smoke_score=0.82 if not exit_available else 0.05,
                    confidence=0.92,
                )
            ],
            sprinklers=[
                SprinklerTelemetry(
                    zone="Zone Beta (Engineering)",
                    active=sprinkler_active,
                    flow_rate_lpm=58.0 if sprinkler_active else 0.0,
                    pressure_kpa=212.0 if sprinkler_active else 0.0,
                    confidence=0.95,
                )
            ],
        )
        return packet


def load_packet_from_file(path: str) -> SensorFusionPacket:
    with open(path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if isinstance(raw, dict):
        raw.setdefault("source", f"file:{os.path.basename(path)}")
    return normalize_sensor_payload(raw)
