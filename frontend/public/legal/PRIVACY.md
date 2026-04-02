# FastForms — Privacy Policy (draft)

**Status:** Draft for operators and counsel review. Replace bracketed placeholders before publishing on your live site. This is not legal advice.

**Last updated:** 2026-03-28

## Who we are

**Controller / Operator:** [Your legal entity name], [address], [contact email].

FastForms (“we”, “us”) provides form-building and response collection software. Depending on your deployment, the **operator** of the service may be you (self-hosted) or us (hosted SaaS). This policy describes processing when we operate the service for you.

## Data we process

| Category | Examples | Purpose |
|----------|----------|---------|
| **Account data** | Email, username, password hash, role, profile fields | Authentication, account management, support |
| **Form content** | Titles, descriptions, question text, validation rules, appearance | Operating the product you requested |
| **Responses** | Answers submitted to forms, timestamps, optional respondent account link | Collecting data on behalf of **form owners** |
| **Technical logs** | IP, user agent, timestamps, error metadata (we aim to minimize content in logs) | Security, reliability, abuse prevention |
| **Optional AI** | Text you submit to “AI form draft” is sent to your configured LLM (e.g. Ollama) per [Ollama_AI_Integration_Plan.md](Ollama_AI_Integration_Plan.md) | Optional assistive feature |

We do **not** sell personal data. We do not use form responses for advertising profiling when operating FastForms as described in [MONETIZATION_AND_PRIVACY.md](MONETIZATION_AND_PRIVACY.md).

## Roles (GDPR-style)

- For **account and billing data**, we are typically the **controller** (or you are, if self-hosted).
- For **response data** entered into your forms, you (the form owner) are typically the **controller** and we are the **processor**, acting on your instructions to store and display that data.

## Legal bases (where GDPR applies)

- **Contract** — providing the service you signed up for.
- **Legitimate interests** — security, fraud prevention, product improvement (where not overridden by your rights).
- **Consent** — where required for non-essential cookies or marketing (see cookie notice on the app).

## Retention

- **Accounts:** Until you delete the account or we terminate the service, subject to legal holds.
- **Forms and responses:** Until deleted by the form owner or removed by automated retention if you enable it — see [DATA_LIFECYCLE.md](DATA_LIFECYCLE.md).
- **Logs:** Short retention (e.g. days to weeks) unless longer is required for security; avoid logging sensitive answer text by design.

## Your rights

Depending on jurisdiction, you may have rights to **access**, **rectify**, **erase**, **restrict**, **port**, or **object** to processing, and to **withdraw consent** where processing is consent-based. Contact **[privacy email]** to exercise rights. Form **respondents** should contact the **form owner** first for copies or deletion of their answers.

## International transfers

If data is stored or processed outside your country (e.g. US cloud), we use appropriate safeguards such as **[SCCs / adequacy / other]** where required.

## Subprocessors

See [SUBPROCESSORS.md](SUBPROCESSORS.md). Update it when you change hosting, email, analytics, or payment providers.

## Children

FastForms is not directed at children under 13 (or 16 where applicable). Do not use it to collect data from children without lawful basis and parental consent where required.

## Changes

We will post updates here and, where appropriate, notify you by email or in-product notice.

## Contact

**Privacy:** [privacy@example.com]  
**Security issues:** See [SECURITY.md](SECURITY.md).
