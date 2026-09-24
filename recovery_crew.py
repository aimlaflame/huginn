import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup
from crewai import Agent, Crew, Process, Task
from cryptography.fernet import Fernet


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _default_path(relative_path: str) -> str:
    base_dir = Path(__file__).resolve().parent
    return str((base_dir / relative_path).resolve())


def _get_cipher() -> Fernet:
    key_path = Path(os.environ.get("AUTOPILOT_LOG_KEY_PATH", _default_path("tmp/autopilot_history.key")))
    key_path.parent.mkdir(parents=True, exist_ok=True)

    if key_path.exists():
        key = key_path.read_bytes().strip()
    else:
        key = Fernet.generate_key()
        key_path.write_bytes(key)
        os.chmod(key_path, 0o600)
    return Fernet(key)


def _write_encrypted_history(event_type: str, payload: dict[str, Any] | None = None) -> None:
    cipher = _get_cipher()
    log_path = Path(
        os.environ.get("AUTOPILOT_HISTORY_LOG_PATH", _default_path("tmp/autopilot_history.log.enc"))
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)

    body = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "payload": payload or {},
    }
    encrypted = cipher.encrypt(json.dumps(body).encode("utf-8")).decode("utf-8")
    with log_path.open("a", encoding="utf-8") as f:
        f.write(encrypted + "\n")


def _build_llm() -> Any:
    openrouter_key = _require_env("OPENROUTER_API_KEY")
    model_name = os.environ.get("OPENROUTER_MODEL", "openrouter/openai/gpt-4o-mini")
    base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    try:
        from crewai import LLM

        return LLM(model=model_name, api_key=openrouter_key, base_url=base_url)
    except Exception:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model_name, api_key=openrouter_key, base_url=base_url)


def _serper_search(query: str, num_results: int = 5) -> list[dict[str, str]]:
    api_key = _require_env("SERPER_API_KEY")
    response = requests.post(
        "https://google.serper.dev/search",
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        json={"q": query, "num": num_results},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    output: list[dict[str, str]] = []
    for item in data.get("organic", [])[:num_results]:
        output.append(
            {
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
            }
        )
    return output


def _fetch_page_excerpt(url: str, max_chars: int = 3000) -> str:
    try:
        response = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
    except Exception as exc:
        return f"NOT FOUND: unable to retrieve page ({exc})"

    soup = BeautifulSoup(response.text, "html.parser")
    text = " ".join(soup.get_text(" ", strip=True).split())
    return text[:max_chars] if text else "NOT FOUND: no readable content"


def _build_evidence(apn: str, owner: str, county: str, excess: float) -> list[dict[str, str]]:
    queries = [
        f'"{apn}" "{county}" county recorder',
        f'"{owner}" "{county}" trustee OR LLC OR corporation',
        f'"{owner}" California Secretary of State business search',
        f'"{owner}" probate court OR estate executor',
        f'"{apn}" "excess proceeds" "{excess}"',
    ]

    seen: set[str] = set()
    evidence: list[dict[str, str]] = []
    for query in queries:
        for item in _serper_search(query):
            url = item.get("url", "")
            if not url or url in seen:
                continue
            seen.add(url)
            evidence.append(
                {
                    "query": query,
                    "title": item.get("title", ""),
                    "url": url,
                    "snippet": item.get("snippet", ""),
                    "excerpt": _fetch_page_excerpt(url),
                }
            )
    return evidence


def _to_json_compatible(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _to_json_compatible(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_json_compatible(v) for v in value]
    return str(value)


def _extract_json(text: str) -> Any:
    if not text:
        return {"raw": text}
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return {"raw": text}
    return {"raw": text}


def _save_report(report: dict[str, Any], apn: str, county: str) -> Path:
    reports_dir = Path(os.environ.get("RECOVERY_REPORTS_DIR", _default_path("reports")))
    reports_dir.mkdir(parents=True, exist_ok=True)

    safe_apn = re.sub(r"[^A-Za-z0-9_-]", "_", apn)
    safe_county = re.sub(r"[^A-Za-z0-9_-]", "_", county)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = reports_dir / f"{safe_county}_{safe_apn}_{ts}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path


def _build_crew(llm: Any) -> Crew:
    records_researcher = Agent(
        role="County Recorder Specialist",
        goal="Find verifiable ownership evidence for the target parcel with citations only.",
        backstory=(
            "You are a meticulous title-research analyst. You only report facts supported by provided evidence URLs. "
            "Anything unsupported must be marked NOT FOUND."
        ),
        verbose=True,
        llm=llm,
    )

    skip_tracer = Agent(
        role="Probate and Corporate Skip-Tracer",
        goal="Identify the current signer and service contacts with confidence labels and citations.",
        backstory=(
            "You map owners to authorized signers (trustee, officer, executor, registered agent) and produce "
            "contact channels only when backed by source URLs."
        ),
        verbose=True,
        llm=llm,
    )

    task_gather_deeds = Task(
        description=(
            "Using `target_profile` and `web_evidence`, determine legal owner type (person/trust/LLC/estate), "
            "current entity status, registered agent if applicable, and ownership indicators for APN {apn}. "
            "Return strict JSON with keys: owner_classification, owner_details, source_urls, unresolved_records. "
            "All unknown values must be exactly 'NOT FOUND'."
        ),
        expected_output=(
            "Strict JSON only. Every factual field must map to at least one URL in source_urls. "
            "No narrative text outside JSON."
        ),
        agent=records_researcher,
    )

    task_resolve_identity = Task(
        description=(
            "Using prior task output plus `web_evidence`, identify who can sign claim paperwork and their contacts. "
            "Return strict JSON with keys: signer_profile, contacts, confidence, source_urls, unresolved_records. "
            "Confidence must be HIGH, MEDIUM, or LOW. Unknown values must be 'NOT FOUND'."
        ),
        expected_output=(
            "Strict JSON only. Include confidence rationale and a manual pull list for deed/probate records still needed."
        ),
        agent=skip_tracer,
    )

    return Crew(
        agents=[records_researcher, skip_tracer],
        tasks=[task_gather_deeds, task_resolve_identity],
        process=Process.sequential,
        verbose=True,
    )


def run_recovery(apn: str, owner: str, county: str, excess: float) -> Path:
    _require_env("OPENROUTER_API_KEY")
    _require_env("SERPER_API_KEY")

    _write_encrypted_history("recovery_run_started", {"apn": apn, "county": county})

    evidence = _build_evidence(apn=apn, owner=owner, county=county, excess=excess)
    llm = _build_llm()
    crew = _build_crew(llm)

    target_profile = {
        "apn": apn,
        "owner": owner,
        "county": county,
        "excess": excess,
    }

    crew_result = crew.kickoff(inputs={"target_profile": target_profile, "web_evidence": evidence, "apn": apn})

    raw_output = getattr(crew_result, "raw", str(crew_result))
    parsed = _extract_json(raw_output)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target_profile": target_profile,
        "evidence_count": len(evidence),
        "web_evidence": evidence,
        "crew_output": _to_json_compatible(parsed),
        "raw_output": str(raw_output),
        "compliance_note": (
            "External API credentials must be created and rotated through provider systems; "
            "this script does not fabricate third-party keys."
        ),
    }
    report_path = _save_report(report, apn=apn, county=county)

    _write_encrypted_history(
        "recovery_run_succeeded", {"apn": apn, "county": county, "report_path": str(report_path)}
    )
    return report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run two-agent excess-proceeds recovery research crew.")
    parser.add_argument("--apn", required=True, help="Assessor Parcel Number from county list")
    parser.add_argument("--owner", required=True, help="Listed owner/trust/entity name")
    parser.add_argument("--county", default="El Dorado", help="County name")
    parser.add_argument("--excess", required=True, type=float, help="Excess proceeds amount")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        path = run_recovery(apn=args.apn, owner=args.owner, county=args.county, excess=args.excess)
        print(f"✅ Saved recovery report: {path}")
    except Exception as exc:
        _write_encrypted_history("recovery_run_failed", {"error": str(exc)})
        print(f"Recovery crew failed: {exc}", file=sys.stderr)
        raise
