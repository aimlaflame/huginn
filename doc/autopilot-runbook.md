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
- [ ] Confirm `.env` stays uncommitted.

## 2) Manual run

- [ ] Load environment variables from `.env` in your shell.
- [ ] Run:
  - `python /home/runner/work/huginn/huginn/autopilot_agents.py`
- [ ] Verify the run completes and output is produced.

## 3) Daily operations checklist

- [ ] Verify OpenRouter key is active.
- [ ] Verify SMTP login still works.
- [ ] Trigger the daily workflow (n8n schedule at 8:00 AM).
- [ ] Confirm notification emails were sent.
- [ ] Archive output/logs for audit tracking.

## 4) Quick troubleshooting

- Missing `OPENROUTER_API_KEY`: set it in `.env` before running.
- SMTP failures: verify app password, server, port, and mailbox provider policy.
- Runtime errors: rerun manually first, then check scheduler configuration.
