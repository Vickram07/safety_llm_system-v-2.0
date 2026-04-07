from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Dict
import asyncio
from .crew import evaluate_emergency, parse_emergency_response

# ==========================================
# 1. STATE DEFINITION
# ==========================================
class SimulationState(TypedDict):
    active_fires: List[str]
    alive_count: int
    crewai_response: str
    pa_announcement: str
    crew_status: str
    sprinkler_zones: str
    primary_exit: str
    alternate_exit: str

# ==========================================
# 2. NODE FUNCTIONS
# ==========================================
def sensor_fusion(state: SimulationState) -> SimulationState:
    """Reads the current raw data metrics."""
    # In a real system, this would fetch from the database or hardware.
    # Here, we just pass the state right through logically.
    return state

def multi_agent_deliberation(state: SimulationState) -> SimulationState:
    """Invokes the CrewAI Swarm to make autonomous decisions."""
    try:
        # We invoke the CrewAI team for deliberation
        res = evaluate_emergency(state["active_fires"], state["alive_count"])
        parsed = parse_emergency_response(res)
        state["crewai_response"] = parsed["raw"]
        state["crew_status"] = parsed["status"]
        state["sprinkler_zones"] = parsed["sprinkler_zones"]
        state["primary_exit"] = parsed["primary_exit"]
        state["alternate_exit"] = parsed["alternate_exit"]
        state["pa_announcement"] = parsed["pa_message"] or parsed["raw"]
    except Exception as e:
        print(f"CrewAI Timeout / Crash: {e}")
        state["crewai_response"] = "OFFLINE."
        state["pa_announcement"] = "AI CREW UNAVAILABLE."
        state["crew_status"] = "OFFLINE"
        state["sprinkler_zones"] = "NONE"
        state["primary_exit"] = "NONE"
        state["alternate_exit"] = "NONE"

    return state

def execution_node(state: SimulationState) -> SimulationState:
    """Executes the specific CrewAI decisions back into physical reality (Simulated UI)."""
    # E.g. Turn on specific sprinklers or update the UI announcements flag.
    return state

# ==========================================
# 3. BUILD THE GRAPH
# ==========================================
workflow = StateGraph(SimulationState)

workflow.add_node("Sensor_Fusion", sensor_fusion)
workflow.add_node("CrewAI_Swarm", multi_agent_deliberation)
workflow.add_node("Execution", execution_node)

# Flow defined
workflow.add_edge("Sensor_Fusion", "CrewAI_Swarm")
workflow.add_edge("CrewAI_Swarm", "Execution")
workflow.add_edge("Execution", END)

workflow.set_entry_point("Sensor_Fusion")

app_graph = workflow.compile()

# Asynchronous execution bridge to not block main thread
async def run_langgraph_cycle(fire_data: List[str], alive_people: int):
    initial_state = SimulationState(
        active_fires=fire_data, 
        alive_count=alive_people, 
        crewai_response="", 
        pa_announcement="",
        crew_status="UNKNOWN",
        sprinkler_zones="NONE",
        primary_exit="NONE",
        alternate_exit="NONE"
    )
    # Run the graph compiled state machine via an async thread
    result = await asyncio.to_thread(app_graph.invoke, initial_state)
    return result
