import time
import json
import logging
import requests
import pyttsx3
import os
import sys

# Import our sensor interface
from sensor_interface import SimulatedSensorProvider, RealSensorProvider

# CONFIGURATION
# ---------------------------------------------------------
USE_REAL_SENSORS = False # Set to True when you actually have sensors connected
MODEL_NAME = "safety_llm"
OLLAMA_URL = "http://localhost:11434/api/generate"
# ---------------------------------------------------------

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def init_voice():
    """Initialize Text-to-Speech Engine"""
    try:
        engine = pyttsx3.init()
        # Tune voice settings
        rate = engine.getProperty('rate')
        engine.setProperty('rate', rate + 20) # Speak slightly faster (Urgent)
        return engine
    except Exception as e:
        logging.error(f"Failed to init voice: {e}")
        return None

def get_system_prompt():
    """Load the voice-specific strict prompt"""
    try:
        with open("live_commander_prompt.txt", "r") as f:
            return f.read()
    except:
        return "You are a Safety Commander. Give short, urgent commands."

def run_live_system():
    print("==========================================")
    print("   LIVE SAFETY COMMANDER (SIMULATION)     ")
    print("==========================================")
    print("1. Initializing Sensors...")
    
    if USE_REAL_SENSORS:
        sensors = RealSensorProvider()
    else:
        sensors = SimulatedSensorProvider()
        
    print("2. Initializing Voice Engine...")
    voice = init_voice()
    
    print("3. Loading AI Commander...")
    system_prompt = get_system_prompt()
    
    print("\n[SYSTEM IS LIVE] - Press Ctrl+C to Stop")
    print("Simulating Fire Growth... Listen to the Commander.\n")
    
    # Memoizing last state to avoid spamming if nothing changes?
    # For now, we want the "Live" feel, so we'll just run every 3 seconds.
    
    try:
        while True:
            # 1. READ SENSORS
            current_state = sensors.get_state()
            
            # Print state for debug visibility
            # print(f"\n[DEBUG STATE]: {current_state}")
            
            # 2. ASK AI
            payload = {
                "model": MODEL_NAME,
                "prompt": f"CURRENT DATA: {json.dumps(current_state)}",
                "system": system_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1, # Deterministic
                    "num_predict": 50   # Keep it short
                }
            }
            
            try:
                response = requests.post(OLLAMA_URL, json=payload)
                if response.status_code == 200:
                    ai_command = response.json().get("response", "").strip()
                    
                    # 3. BROADCAST COMMAND
                    print(f"\n[COMMANDER]: {ai_command.upper()}")
                    
                    if voice:
                        voice.say(ai_command)
                        voice.runAndWait()
                else:
                    print(f"! Error: {response.text}")
                    
            except requests.exceptions.ConnectionError:
                print("! Connection Error: Is Ollama running?")
            
            # 4. SLEEP
            # In a real game, this might be shorter, or event-driven
            time.sleep(3) 

    except KeyboardInterrupt:
        print("\n[SYSTEM SHUTDOWN]")

if __name__ == "__main__":
    # Ensure raw directory is correct if running from elsewhere
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    run_live_system()
