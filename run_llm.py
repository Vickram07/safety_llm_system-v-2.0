import json
import logging
import os
import subprocess
import time
import requests
import sys
from datetime import datetime
from model_config import MODEL_NAME, FALLBACK_MODEL_NAME, OLLAMA_BASE_URL, OLLAMA_GENERATE_URL

# CONFIGURATION
BASE_MODEL = FALLBACK_MODEL_NAME
OLLAMA_API_URL = OLLAMA_GENERATE_URL
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(PROJECT_DIR, "logs")

# SETUP LOGGING
log_filename = os.path.join(LOGS_DIR, f"execution_{int(time.time())}.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()
    ]
)

def read_file(filename):
    path = os.path.join(PROJECT_DIR, filename)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logging.error(f"Failed to read {filename}: {e}")
        return None

def check_ollama():
    try:
        subprocess.run(["ollama", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except FileNotFoundError:
        logging.error("Ollama not found in PATH. Please install Ollama.")
        return False
    except subprocess.CalledProcessError:
        logging.error("Ollama execution failed.")
        return False

def model_exists(model_name):
    try:
        result = subprocess.run(
            ["ollama", "show", model_name],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return result.returncode == 0
    except Exception:
        return False

def create_model():
    if model_exists(MODEL_NAME):
        logging.info(f"Using existing Ollama model '{MODEL_NAME}'.")
        return True

    logging.info("Custom model not found. Building from Modelfile...")
    modelfile_path = os.path.join(PROJECT_DIR, "Modelfile")
    
    # Using specific tag from user request if possible, otherwise rely on Modelfile content
    # We will use the 'ollama create' command.
    try:
        cmd = ["ollama", "create", MODEL_NAME, "-f", modelfile_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            logging.info(f"Model '{MODEL_NAME}' created successfully.")
            return True
        else:
            logging.error(f"Failed to create model: {result.stderr}")
            if "pull" in result.stderr.lower():
               logging.info("Attempting to pull base model...")
               # Attempt to pull the base model referenced in Modelfile?
               # For now, we assume user has valid base model or internet to pull.
               pass
            return False
    except Exception as e:
        logging.error(f"Exception during model creation: {e}")
        return False

def run_simulation():
    if not check_ollama():
        return

    # 1. Create Model
    if not create_model():
        logging.warning("Could not create custom model. Attempting to proceed (model might already exist or we fail gracefully).")

    # 2. Load Data
    scenario_json = read_file("scenario_input.json")

    if not scenario_json:
        logging.critical("Missing critical scenario_json file. Aborting.")
        return

    # 3. Construct Prompt
    full_prompt = f"""
LOG: SIMULATION START
TIMESTAMP: {datetime.now().isoformat()}

INPUT SENSOR DATA (JSON):
{scenario_json}

TASK:
Analyze the sensor data given the safety protocols. 
Identify threats.
Provide an advisory recommendation.
"""

    logging.info("Sending request to Local LLM...")
    print(f"\n--- SENDING TO {MODEL_NAME} ---\n")

    payload = {
        "model": MODEL_NAME,
        "prompt": full_prompt,
        "stream": False,
        "options": {
            "temperature": 0.0 # Reinforcing deterministic behavior
        }
    }

    try:
        # INITIAL ANALYSIS (STREAMED)
        print("\n" + "="*40)
        print(" GOD-LEVEL SAFETY SYSTEM OUTPUT")
        print("="*40 + "\n")
        
        payload["stream"] = True # ENABLE STREAMING
        context = []
        full_response_text = ""
        
        with requests.post(OLLAMA_API_URL, json=payload, stream=True) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    body = json.loads(line)
                    token = body.get("response", "")
                    print(token, end='', flush=True) # TYPEWRITER EFFECT
                    full_response_text += token
                    if "context" in body:
                        context = body["context"]
        
        print("\n\n" + "="*40)
        
        # Log initial response
        logging.info("Initial analysis complete.")
        
        # INTERACTIVE CHAT LOOP
        print("\n[SYSTEM] Interactive Mode Active. Type 'exit' to quit.")
        print("[SYSTEM] You can now ask follow-up questions (e.g., 'Where am I? Exits?').\n")

        while True:
            try:
                user_msg = input("OPERATOR > ")
                if user_msg.lower() in ["exit", "quit", "q"]:
                    print("Session ended.")
                    break
                
                # Prepare follow-up request with CONTEXT (Memory)
                chat_payload = {
                    "model": MODEL_NAME,
                    "prompt": user_msg,
                    "context": context,  # Pass back the memory
                    "stream": True,      # ENABLE STREAMING
                    "options": {"temperature": 0.0}
                }
                
                print("\nAI:", end=' ', flush=True)
                
                new_response_text = ""
                with requests.post(OLLAMA_API_URL, json=chat_payload, stream=True) as chat_response:
                    chat_response.raise_for_status()
                    for line in chat_response.iter_lines():
                        if line:
                            body = json.loads(line)
                            token = body.get("response", "")
                            print(token, end='', flush=True)
                            new_response_text += token
                            if "context" in body:
                                context = body["context"]
                
                print("\n")
                
                # Append to log
                with open(log_filename, 'a', encoding='utf-8') as f:
                    f.write(f"\n\nOPERATOR: {user_msg}\nAI: {new_response_text}")

            except KeyboardInterrupt:
                print("\nSession interrupted.")
                break
            except Exception as e:
                print(f"Error: {e}")

    except requests.exceptions.ConnectionError:
        logging.error(f"Could not connect to Ollama. Is the server running? ({OLLAMA_BASE_URL})")
        print("ERROR: Could not connect to Ollama. Make sure 'ollama serve' is running.")
    except Exception as e:
        logging.error(f"Error during inference: {e}")
        print(f"ERROR: {e}")

if __name__ == "__main__":
    run_simulation()
