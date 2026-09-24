import os
import sys
import json
from datetime import datetime, timezone
from pathlib import Path

from crewai import Agent, Task, Crew, Process
from cryptography.fernet import Fernet
from langchain_openai import ChatOpenAI


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            "Copy /home/runner/work/huginn/huginn/.env.example to .env and set it before running."
        )
    return value


def _default_path(relative_path: str) -> str:
    base_dir = Path(__file__).resolve().parent
    return str((base_dir / relative_path).resolve())


def _get_autopilot_cipher() -> Fernet:
    key_path = Path(os.environ.get("AUTOPILOT_LOG_KEY_PATH", _default_path("tmp/autopilot_history.key")))
    key_path.parent.mkdir(parents=True, exist_ok=True)

    if key_path.exists():
        key = key_path.read_bytes().strip()
    else:
        key = Fernet.generate_key()
        key_path.write_bytes(key)
        os.chmod(key_path, 0o600)

    return Fernet(key)


def _write_encrypted_history(event_type: str, payload: dict | None = None) -> None:
    cipher = _get_autopilot_cipher()
    log_path = Path(os.environ.get("AUTOPILOT_HISTORY_LOG_PATH", _default_path("tmp/autopilot_history.log.enc")))
    log_path.parent.mkdir(parents=True, exist_ok=True)

    body = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "payload": payload or {}
    }
    encrypted = cipher.encrypt(json.dumps(body).encode("utf-8")).decode("utf-8")
    with log_path.open("a", encoding="utf-8") as f:
        f.write(encrypted + "\n")


def _validate_runtime_configuration() -> None:
    required_vars = [
        "OPENROUTER_API_KEY",
        "SMTP_SERVER",
        "SMTP_PORT",
        "SMTP_EMAIL",
        "SMTP_PASSWORD",
        "MY_INBOX_ROUTING"
    ]
    for name in required_vars:
        _require_env(name)


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
# AGENT 3: THE CREDENTIAL GOVERNANCE LEAD
# ==========================================
credential_guardian = Agent(
    role="Credential Governance Lead",
    goal="Verify required keys are configured and coordinate rotation tasks through official provider consoles.",
    backstory="""You are a security operations specialist responsible for credential hygiene.
    You never fabricate provider API keys and only coordinate rotation through approved provider mechanisms.""",
    verbose=True,
    llm=llm_runtime
)

# ==========================================
# AGENT 4: THE ENCRYPTED AUDIT CUSTODIAN
# ==========================================
audit_guardian = Agent(
    role="Encrypted Audit Custodian",
    goal="Maintain encrypted operational history and compliance evidence without exposing secrets.",
    backstory="""You are an audit and controls analyst who preserves operational history in encrypted form.
    You document run outcomes and control checks while avoiding secret disclosure.""",
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

task_verify_credentials = Task(
    description="""Confirm all required runtime credentials are present and identify which ones require
    provider-side rotation actions. Do not invent or fabricate API keys; only return a rotation action list.""",
    expected_output="A credential readiness and rotation checklist with provider-specific next actions.",
    agent=credential_guardian
)

task_audit_controls = Task(
    description="""Produce a concise audit summary of operational controls, including encrypted history
    logging status, runtime checks performed, and follow-up remediation actions.""",
    expected_output="An audit control summary suitable for compliance records, with no plaintext secrets.",
    agent=audit_guardian
)

autonomous_recovery_crew = Crew(
    agents=[records_researcher, skip_tracer, credential_guardian, audit_guardian],
    tasks=[task_gather_deeds, task_resolve_identity, task_verify_credentials, task_audit_controls],
    process=Process.sequential,
    verbose=True
)

if __name__ == "__main__":
    try:
        _validate_runtime_configuration()
        _write_encrypted_history("run_started", {"component": "autonomous_recovery_crew"})
        print("🚀 Initiating Fiduciary Identity Resolution on Autopilot...")
        result = autonomous_recovery_crew.kickoff()
        _write_encrypted_history("run_succeeded", {"result": str(result)[:1000]})
    except Exception as exc:
        _write_encrypted_history("run_failed", {"error": str(exc)})
        print(f"Autopilot run failed: {exc}", file=sys.stderr)
        raise
