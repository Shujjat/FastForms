# FastForms — Subprocessors and infrastructure

**Purpose:** Transparency list for privacy policies and DPAs. **Update this file** whenever you change vendors or regions.

**Operator:** [Your company name]  
**Last reviewed:** 2026-03-28

## How to use this document

- For **self-hosted** deployments, the “subprocessor” is often **only your own** cloud account; still list your hosting and email providers here for internal records.
- For **SaaS**, list every third party that can access or process customer data (not just payment).

## Typical categories

| Category | Provider (example) | Data involved | Region / notes |
|----------|---------------------|---------------|----------------|
| **Application hosting** | [e.g. AWS EC2 / Fly.io / Railway] | App runtime, env secrets | [region] |
| **Database** | [e.g. RDS Postgres / managed Postgres] | All application data | [region] |
| **Object storage** | [e.g. S3] | If used for uploads/exports | [region] |
| **Cache / queue** | [e.g. Redis] | Ephemeral jobs, sessions if used | [region] |
| **Email delivery** | [e.g. SendGrid / SES] | Email addresses, reset links | [region] |
| **DNS / CDN** | [e.g. Cloudflare] | IP, TLS metadata | [global / region] |
| **Error / logs** | [e.g. Sentry] | Stack traces, may contain PII if misconfigured — use scrubbers | [region] |
| **Analytics** | [e.g. Plausible / none] | Prefer privacy-oriented or first-party only | [region] |
| **Payments** | [e.g. Stripe] | Billing identity, card handled by Stripe | [per Stripe] |
| **Optional LLM** | [e.g. self-hosted Ollama / OpenAI] | AI prompt text when feature is used | [per deployment] |

## AI / LLM

- **Local Ollama:** Often **no third-party** model vendor; data stays on your infrastructure. Still document the **host machine** and network path in your DPA if customers ask.
- **Cloud LLM API:** Add the vendor as a **subprocessor**; update [PRIVACY.md](PRIVACY.md) transfer and retention sections.

## Changes

Maintain a short changelog at the bottom when you add or remove vendors:

| Date | Change |
|------|--------|
| 2026-03-28 | Initial template |
