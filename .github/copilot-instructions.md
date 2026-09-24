# Role: Master AI Automation Engineer
# System: El Dorado County Fiduciary Notification & Asset Recovery Engine
# Goal: Build a zero-cost, fully automated pipeline utilizing self-hosted open-source technologies.

## Technical Architecture & Operations:
1. **Primary Engine:** Python 3.12 using SQLite/PostgreSQL for canonical deduplication.
2. **Orchestration Hub:** n8n (via Docker Compose) to coordinate daily 8:00 AM schedules.
3. **Identity Resolution:** CrewAI with 2 autonomous agents (Recorder Specialist & Skip Tracer).
4. **LLM Runtime:** OpenRouter API utilizing the stealth model route 'stealth/ox-alpha' for zero-cost intelligence.
5. **PDF Generation:** FPDF library generating strict, colorless, 1-inch margin legal notices.
6. **Delivery:** Automated SMTP email dispatch of compliance packets.
7. **Compliance:** 15% contingency fee structure enforcing fiduciary obligations (Corporate Duty, Trustee Mandate, Estate Mandate).
