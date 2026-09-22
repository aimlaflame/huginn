import os
import sys

from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            "Copy /home/runner/work/huginn/huginn/.env.example to .env and set it before running."
        )
    return value


# Connects to the free stealth/ox-alpha model via OpenRouter API
openrouter_key = _require_env("OPENROUTER_API_KEY")
llm_runtime = ChatOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=openrouter_key,
    model="stealth/ox-alpha"
)

# ==========================================
# AGENT 1: THE TITLE & DEED INVESTIGATOR
# ==========================================
records_researcher = Agent(
    role="County Recorder Specialist",
    goal="Extract and verify historical ownership records, trust entities, and corporate agents.",
    backstory="""You are an elite title officer specializing in northern California land records.
    You excel at cross-referencing parcel entries on the El Dorado Recorder-Clerk Index and
    California Bizfile Online to determine true legal ownership.""",
    verbose=True,
    llm=llm_runtime
)

# ==========================================
# AGENT 2: THE SKIP TRACER
# ==========================================
skip_tracer = Agent(
    role="Probate and Corporate Skip-Tracer",
    goal="Locate current verified addresses, phone numbers, and emails of fiduciaries.",
    backstory="""You are a licensed private investigator specialized in locating heirs, executors,
    corporate registered agents, and trustees. You know how to parse court probate registries
    and business records to find the person legally authorized to execute documents.""",
    verbose=True,
    llm=llm_runtime
)

# ==========================================
# THE OPERATION PROMPTS (TASKS)
# ==========================================
task_gather_deeds = Task(
    description="""Query public databases to isolate official Grant Deeds, Corporate filings,
    and Registered Agent records associated with your target. Verify and aggregate the total
    value of their properties in the El Dorado tax sale.""",
    expected_output="A structured JSON schema outlining current corporate status, Registered Agent, and parcel values.",
    agent=records_researcher
)

task_resolve_identity = Task(
    description="""Using the gathered registration data, identify the specific authorized officer, trustee,
    or registered agent. Find their current verified physical address, direct phone number,
    and secure email for official legal notification service.""",
    expected_output="An identity resolution profile featuring confirmed service addresses and contact lines.",
    agent=skip_tracer
)

autonomous_recovery_crew = Crew(
    agents=[records_researcher, skip_tracer],
    tasks=[task_gather_deeds, task_resolve_identity],
    process=Process.sequential,
    verbose=True
)

if __name__ == "__main__":
    try:
        print("🚀 Initiating Fiduciary Identity Resolution on Autopilot...")
        autonomous_recovery_crew.kickoff()
    except Exception as exc:
        print(f"Autopilot run failed: {exc}", file=sys.stderr)
        raise
