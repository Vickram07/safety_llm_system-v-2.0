import os


# Shared Ollama configuration for the whole project.
# infernalx-transfer-v1 is the active default model used by backend,
# CLI runner, and agent workflow unless overridden by environment variables.
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_GENERATE_URL = f"{OLLAMA_BASE_URL}/api/generate"

MODEL_NAME = os.getenv("INFERNALX_MODEL", "phi3:mini")
FALLBACK_MODEL_NAME = os.getenv("INFERNALX_FALLBACK_MODEL", "phi3:mini")
VISION_MODEL_NAME = os.getenv("INFERNALX_VISION_MODEL", "llava")

CHAT_PROMPT_VERSION = os.getenv("INFERNALX_CHAT_PROMPT_VERSION", "2.1")
INFERNALX_SYSTEM_DIRECTIVE = (
    "You are InfernalX, the AI assistant for a smart building fire safety system. "
    "Answer in 2-3 SHORT sentences. Be direct and use only the CONTEXT data provided. "
    "Accurately report: alive/evacuated/trapped/panicking counts, fire zones, exits, and suppression status. "
    "Never invent data — only use what is in CONTEXT."
)
VALID_DIRECTIVE_PREFIXES = {
	"[INFERNALX DIRECTIVE]",
	"STATUS:",
	"MACRO-ACTION:",
}
