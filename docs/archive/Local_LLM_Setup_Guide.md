# Local LLM Setup & Creation Guide

This guide explains how a brand new user can install a local LLM, access it entirely offline, and create their own custom AI personalities (like `InfernalX`) using Ollama.

---

## 1. What is an LLM and Why Run it Locally?
A Large Language Model (LLM) is the brain that powers AI systems like ChatGPT. By running it **locally** (on your own computer), you ensure:
- **Zero Latency**: Agents don't need internet queries.
- **Total Privacy**: Corporate blueprints, security data, and personnel tracking never hit a cloud server.
- **Uncapped Usage**: No API costs for our 100+ simulated autonomous agents.

## 2. Installing the Engine (Ollama)
We use **Ollama** as the local runtime because it is extremely fast and manages memory flawlessly.

1. **Download Ollama**: Go to [https://ollama.com/download](https://ollama.com/download) and install the Windows/Mac/Linux executable.
2. **Verify Installation**: Open a new terminal (Command Prompt or PowerShell) and type:
   ```bash
   ollama --version
   ```
   *If it prints a version number, you are ready.*

## 3. Downloading a Base Model
AI brains are large files called "weights". We primarily use **Meta's LLaMa 3.1** because it is open-source and highly intelligent.

In your terminal, run:
```bash
ollama pull llama3.1
```
*(This will download a ~4.7GB file. This only needs to happen once.)*

## 4. How to Make Your Own Custom Model (The Modelfile)
In our project, we don't just use standard `llama3.1`. We crafted a specific, highly-restrictive variant called **InfernalX** which is trained strictly to obey safety protocols.

To make your own custom model, you need a **Modelfile**. It looks like a Dockerfile.

### Example Modelfile:
Create a text file named `Modelfile` (no extension) in your folder:
```text
FROM llama3.1
SYSTEM "You are a Safety Overseer AI. You must never hallucinate. Keep all answers under 20 words. Your priority is saving lives."
PARAMETER temperature 0.1
```

### Build Your Model
In the terminal, navigate to the folder where you made the `Modelfile` and run:
```bash
ollama create my-custom-ai -f Modelfile
```

### Select Your Model in the Python Code
Open `server.py` in your code editor. At the very top of the script, find the LLM integration line and change `"llama3.1"` to your new name `"my-custom-ai"`:

```python
# Open server.py
# Change this:
# llm = Ollama(model="llama3.1", base_url="http://127.0.0.1:11434")

# To this:
llm = Ollama(model="my-custom-ai", base_url="http://127.0.0.1:11434")
```

Whenever you run `python server.py`, your specific custom AI will now act as the brain of the simulation!
