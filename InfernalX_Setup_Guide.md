# InfernalX Custom AI Setup Guide

This document is a step-by-step guide for your teammates to cleanly replicate and build the custom `InfernalX` autonomous monitoring LLM on any new machine for presentations.

## Prerequisites
1. You must have **Ollama** installed on the host machine. (Download from [ollama.com](https://ollama.com/download))
2. Open a new Terminal (PowerShell or Command Prompt).
3. Ensure you have the `Modelfile` present in your project directory.

## Step 1: Pull the Foundation Model
The `InfernalX` agent runs on top of the extremely fast `llama3.1` foundation model. First, we need to pull the weights locally so that it can run entirely offline without internet requirements or API keys:

```bash
ollama pull llama3.1
```
*(Note: This might take a few minutes depending on network speed, as it downloads a ~4.7GB file.)*

## Step 2: Build the Custom InfernalX Model
We use a `Modelfile` to "bake" the exact system prompts, constraints, and operational guidelines directly into the weights of the model. The current Modelfile restricts the AI from using markdown or chatting, forcing it into a purely robotic, reactive state with zero latency.

Make sure your terminal is inside the `safety_llm_system v 2.0` directory where the `Modelfile` is located, then run:

```bash
ollama create infernalx-llm -f Modelfile
```

Upon success, you should see `success` printed in the terminal indicating the new custom agent has been instantiated locally in the Ollama registry.

## Step 3: Verify the Installation
To ensure the LLM has built successfully and is ready to be utilized by the Python safety simulation server, verify that `infernalx-llm` appears in your local model list:

```bash
ollama list
```
You should see:
```text
NAME                     ID              SIZE      MODIFIED
infernalx-llm:latest     <some-hash>     4.7 GB    X seconds ago
```

## Step 4: Run the Backend Python Server
Once the `infernalx-llm` is installed, you no longer need to interact with the terminal manually. The web application will automatically query it in the background on `localhost:11434`. 

You can now start the FastAPI server:
```bash
python server.py
```

Then in a separate terminal window, start the React interface:
```bash
cd ui
npm run dev
```

### Presentation Notes
- **Speed**: We have capped the output via the payload configuration in `server.py` (`"num_predict": 25`) meaning the AI will only yield the maximum amount of tokens required for 1-2 raw sentences.
- **Privacy**: No organizational data leaves the computer. The entire LLM runs natively on your GPU/CPU architecture.
- **Log Location**: Remind your audience that any manual or automatic breaches are silently permanently recorded to `incident_report.log` for auditable paper trails.
