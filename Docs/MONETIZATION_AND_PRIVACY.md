# Monetization and privacy-friendly defaults

FastForms is designed so **trust** and **compliance** stay compatible with sustainable revenue.

## Recommended priority (privacy-preserving)

1. **Subscriptions / tiers** — Different limits (forms, responses per month, retention, collaborators) without surveillance ads.
2. **Remove branding** — Paid option to hide “Powered by” or custom domain.
3. **Compliance tier** — Longer retention, export audit, DPA, priority support, SSO (when built).
4. **API / automation** — Metered API access for developers.

## Advertising (if used)

- **Do not** load behavioral ad networks on **`/fill/`** (respondent experience) or authenticated **designer** pages that display response content.
- **Do** place optional ads only on **marketing** or **logged-out** pages, after **cookie consent** (see frontend `CookieConsent` and `ff_cookie_consent` in `localStorage`).
- Update [PRIVACY.md](PRIVACY.md) and [SUBPROCESSORS.md](SUBPROCESSORS.md) with every ad or analytics vendor.

## Product default

The open-source UI ships **without** third-party ad scripts. Integrations are **your** choice as operator.
