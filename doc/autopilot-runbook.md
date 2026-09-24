# Autopilot Runbook (CrewAI + OpenRouter)

Use this checklist to run the two-agent autopilot flow in `/home/runner/work/huginn/huginn/autopilot_agents.py`.

## 1) One-time setup

- [ ] Install Python 3.12.
- [ ] From repo root, install dependencies:
  - `pip install -r /home/runner/work/huginn/huginn/requirements.txt`
- [ ] Copy env template:
  - `cp /home/runner/work/huginn/huginn/.env.example /home/runner/work/huginn/huginn/.env`
- [ ] Set required values in `.env`:
  - `OPENROUTER_API_KEY`
  - `SMTP_SERVER`
  - `SMTP_PORT`
  - `SMTP_EMAIL`
  - `SMTP_PASSWORD`
  - `MY_INBOX_ROUTING`
  - `AUTOPILOT_LOG_KEY_PATH`
  - `AUTOPILOT_HISTORY_LOG_PATH`
- [ ] Confirm `.env` stays uncommitted.
- [ ] Generate/rotate provider API keys in official provider consoles (never from this script).

## 2) Manual run

- [ ] Load environment variables from `.env` in your shell.
- [ ] Run:
  - `python /home/runner/work/huginn/huginn/autopilot_agents.py`
- [ ] Run parcel-targeted lead research with CLI inputs:
  - `python /home/runner/work/huginn/huginn/recovery_crew.py --apn 123-456-78 --owner "SMITH FAMILY TRUST" --county "El Dorado" --excess 48210.55`
- [ ] Verify the run completes and output is produced.
- [ ] Confirm JSON report is written to `RECOVERY_REPORTS_DIR`.

## 3) n8n import and environment mapping checklist

- [ ] Import your workflow JSON into n8n (`n8n-autopilot-workflow.json`).
- [ ] Open each workflow node and confirm credentials/variables are mapped.
- [ ] Map OpenRouter runtime variable:
  - `OPENROUTER_API_KEY`
  - `OPENROUTER_MODEL`
  - `OPENROUTER_BASE_URL`
- [ ] Map web evidence variable:
  - `SERPER_API_KEY`
- [ ] Map SMTP variables:
  - `SMTP_SERVER`
  - `SMTP_PORT`
  - `SMTP_EMAIL`
  - `SMTP_PASSWORD`
  - `MY_INBOX_ROUTING`
- [ ] Map encrypted history variables:
  - `AUTOPILOT_LOG_KEY_PATH`
  - `AUTOPILOT_HISTORY_LOG_PATH`
- [ ] Map report output directory:
  - `RECOVERY_REPORTS_DIR`
- [ ] Set the trigger schedule to run daily at 8:00 AM.
- [ ] Execute one test run from n8n and verify success status.

## 4) Daily operations checklist

- [ ] Verify OpenRouter key is active.
- [ ] Verify SMTP login still works.
- [ ] Trigger the daily workflow (n8n schedule at 8:00 AM).
- [ ] Confirm notification emails were sent.
- [ ] Confirm encrypted history entries are appended at `AUTOPILOT_HISTORY_LOG_PATH`.
- [ ] Confirm new parcel report JSON files appear in `RECOVERY_REPORTS_DIR`.
- [ ] Archive output/logs for audit tracking.

## 5) Quick troubleshooting

- Missing `OPENROUTER_API_KEY`: set it in `.env` before running.
- Missing `SERPER_API_KEY`: add a valid key for web search evidence gathering.
- SMTP failures: verify app password, server, port, and mailbox provider policy.
- Missing encrypted log output: verify `AUTOPILOT_LOG_KEY_PATH` and `AUTOPILOT_HISTORY_LOG_PATH` paths are writable.
- Runtime errors: rerun manually first, then check scheduler configuration.

## 6) Next step: county-list batch execution

- [ ] Read the county excess proceeds list (CSV/XLSX/JSON) into a batch job.
- [ ] Sort parcels by excess proceeds amount (highest first).
- [ ] Execute `recovery_crew.py` per parcel with `--apn`, `--owner`, `--county`, and `--excess`.
- [ ] Store all report JSON outputs and aggregate a daily summary index.

## 7) iPhone, iPad, and Windows operations

- [ ] Keep your repository synced on the server and your local device.
- [ ] Use the same `.env` values across environments (without committing `.env`).
- [ ] Validate one manual run after any credential or workflow change.
- [ ] For iOS automation with Working Copy, configure a Shortcut with:
  - `working-copy://x-callback-url/push/?repo=your_repo_name`
- [ ] After each update, confirm the branch includes:
  - `autopilot_agents.py`
  - `.github/copilot-instructions.md`
  - `.env.example`
  - `requirements.txt`
  - `doc/autopilot-runbook.md`
