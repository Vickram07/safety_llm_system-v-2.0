import random
import time
import json

class SensorProvider:
    """
    Base class for Sensor Data.
    In the future, you will replace 'SimulatedSensorProvider' with 'RealSensorProvider'.
    """
    def get_state(self):
        raise NotImplementedError("Subclasses must implement get_state()")

class RealSensorProvider(SensorProvider):
    """
    Use this class when you have REAL IoT sensors (MQTT, API, Serial).
    """
    def __init__(self):
        print("[SYSTEM] INITIALIZING REAL SENSORS...")
        # TODO: Initialize your connection here
        # self.mqtt_client = mqtt.Client(...)
        # self.serial_port = serial.Serial(...)
        pass

    def get_state(self):
        # TODO: Return real data from your sensors
        # return {
        #     "timestamp": time.time(),
        #     "zones": {
        #         "Zone_A1": self.read_sensor("A1"),
        #         "Zone_B2": self.read_sensor("B2")
        #     }
        # }
        return {"status": "REAL_DATA_NOT_IMPLEMENTED_YET"}

class SimulatedSensorProvider(SensorProvider):
    """
    Simulates a spreading fire for development and testing.
    """
    def __init__(self):
        self.start_time = time.time()
        self.fire_intensity = 0
        self.smoke_spread = 0
        self.user_position = "Zone A1 (Lobby)"
        
    def get_state(self):
        """
        Simulates time-based fire growth.
        """
        elapsed = time.time() - self.start_time
        
        # 1. Simulate Fire Growth
        if elapsed > 10:
            self.fire_intensity = 50 # Fire starts
            fire_status = "IGNITION DETECTED"
        elif elapsed > 20:
            self.fire_intensity = 100 # Full blaze
            self.smoke_spread = 50 # Smoke starts leaking
            fire_status = "CRITICAL - SPREADING"
        elif elapsed > 30:
            self.smoke_spread = 100 # Hallway blocked
            fire_status = "CONTAINMENT BREACHED - HALLWAY A BLOCKED"
        else:
            fire_status = "NORMAL"

        # 2. Simulate User Movement (Mock)
        # In a real game, this would come from the Player Controller
        user_status = "STATIONARY" 
        
        return {
            "timestamp": round(elapsed, 1),
            "environment": {
                "Zone_B2 (Lab)": {"fire_level": self.fire_intensity, "status": fire_status},
                "Hallway_B": {"smoke_level": self.smoke_spread},
                "North_Exit": "CLEAR",
                "South_Exit": "BLOCKED" if self.smoke_spread > 80 else "CLEAR"
            },
            "user": {
                "location": self.user_position,
                "status": user_status
            }
        }
