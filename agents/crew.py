import os
import re
from pathlib import Path
import appdirs

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CREWAI_LOCAL_DATA = PROJECT_ROOT / ".crewai_local"
CREWAI_LOCAL_DATA.mkdir(exist_ok=True)

# CrewAI/Chroma default to Windows app-data paths that are not writable in this
# workspace sandbox. Redirect them into the project so the agent layer can load.
# Disable telemetry/tracing so local agent execution stays clean in restricted
# environments and doesn't fail on blocked outbound network attempts.
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["CREWAI_DISABLE_TRACKING"] = "true"
os.environ["CREWAI_TRACING_ENABLED"] = "false"
os.environ["LOCALAPPDATA"] = str(CREWAI_LOCAL_DATA)
os.environ["APPDATA"] = str(CREWAI_LOCAL_DATA)
os.environ["CREWAI_STORAGE_DIR"] = "infernalx_runtime"
appdirs.user_data_dir = lambda appname, appauthor=None, version=None, roaming=False: str(
    CREWAI_LOCAL_DATA / (appauthor or "CrewAI") / appname
)

from crewai import Agent, Task, Crew, Process, LLM
from model_config import MODEL_NAME, OLLAMA_BASE_URL

# Use the same custom Ollama model across the whole project.
llm = LLM(model=f"ollama/{MODEL_NAME}", base_url=OLLAMA_BASE_URL, temperature=0.0)

MANAGER_TEAM_WORKFLOW = {
    "manager": "InfernalX Manager (power model)",
    "teams": [
        "Routing Logic Team",
        "AI Edit Team",
        "AI Tech Stack and Frontend Team",
    ],
    "order": [
        "Manager Planning",
        "Routing Logic",
        "AI Edits",
        "AI Stack and Frontend",
        "Verification",
    ],
}


def get_manager_team_workflow_summary() -> str:
    ordered = " -> ".join(MANAGER_TEAM_WORKFLOW["order"])
    teams = ", ".join(MANAGER_TEAM_WORKFLOW["teams"])
    return f"MANAGER={MANAGER_TEAM_WORKFLOW['manager']}; TEAMS={teams}; ORDER={ordered}"

# ==========================================
# 1. CORE AGENTS DEFINITION
# ==========================================

fire_chief = Agent(
    role="Fire Safety Chief",
    goal="Analyze thermal spread instantly and command macro-suppression (sprinklers) to prevent structural loss.",
    backstory="You are a veteran Fire Chief AI monitoring a 4-box architectural grid. You receive JSON coordinates of fire cells and determine if sprinklers must be triggered for particular zones to cut off the blaze.",
    verbose=False,
    allow_delegation=False,
    llm=llm
)

evacuation_officer = Agent(
    role="Evacuation Operations Officer",
    goal="Correlate fire positions with active personnel layout, assigning emergency exit priorities.",
    backstory="You observe the 50 occupants on a 4-box grid. Knowing where the Chief declared the fire, you must decide which exit (North Gate or South Gate) is optimal for the bulk of survivors.",
    verbose=False,
    allow_delegation=False,
    llm=llm
)

pa_announcer = Agent(
    role="Public Address System AI",
    goal="Translate the Evacuation Officer's routing strategy into a calm, direct, 1-sentence PA broadcast for the workers.",
    backstory="You operate the overhead speakers. Based on the Evacuation routing, command the 50 occupants clearly. Keep it under 15 words. DO NOT PANIC.",
    verbose=False,
    allow_delegation=False,
    llm=llm
)

# ==========================================
# 2. EMERGENCY ASSESSMENT TASKS
# ==========================================

def evaluate_emergency(fire_data, alive_people):
    task_analyze_fire = Task(
        description=(
            f"Analyze current active fire grid coordinates: {fire_data}. "
            "Return exactly two lines: "
            "STATUS: <brief assessment> "
            "SPRINKLER_ZONES: <comma-separated zone names or NONE>."
        ),
        expected_output="Two labeled lines with STATUS and SPRINKLER_ZONES.",
        agent=fire_chief
    )
    
    task_route_survivors = Task(
        description=(
            f"Given {alive_people} people are inside the facility and the Fire Chief has marked hazards, "
            "return exactly two lines: "
            "PRIMARY_EXIT: <best exit name> "
            "ALTERNATE_EXIT: <backup exit name or NONE>."
        ),
        expected_output="Two labeled lines with PRIMARY_EXIT and ALTERNATE_EXIT.",
        agent=evacuation_officer
    )
    
    task_broadcast = Task(
        description=(
            "Write exactly one labeled line: "
            "PA_MESSAGE: <one calm sentence directing occupants to evacuate>."
        ),
        expected_output="One labeled line with PA_MESSAGE.",
        agent=pa_announcer
    )

    crew = Crew(
        agents=[fire_chief, evacuation_officer, pa_announcer],
        tasks=[task_analyze_fire, task_route_survivors, task_broadcast],
        process=Process.sequential
    )
    
    return crew.kickoff()


def parse_emergency_response(raw_response):
    text = str(raw_response).strip()
    parsed = {
        "raw": text,
        "status": "UNKNOWN",
        "sprinkler_zones": "NONE",
        "primary_exit": "NONE",
        "alternate_exit": "NONE",
        "pa_message": "",
    }

    patterns = {
        "status": r"STATUS:\s*(.+)",
        "sprinkler_zones": r"SPRINKLER_ZONES:\s*(.+)",
        "primary_exit": r"PRIMARY_EXIT:\s*(.+)",
        "alternate_exit": r"ALTERNATE_EXIT:\s*(.+)",
        "pa_message": r"PA_MESSAGE:\s*(.+)",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            parsed[key] = match.group(1).strip().strip('"')

    return parsed
