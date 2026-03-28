# Form template catalog

JSON files in this folder define **built-in** FastForms templates (title, description, optional `appearance`, questions).

- **Licensing:** These definitions are **original** content for this project (MIT-licensed repo). Do **not** commit verbatim copies of third-party or proprietary form text from the web without permission and compatible license.
- **Adding templates:** Copy `schema.example.json`, give a unique `id`, validate `question_type` values against `Question.Types` in code.
- **`appearance` (optional):** Beyond `accent` / `pageBg` / `cardBg` / `radius`, you can set gradients (`pageGradient`, `headerGradient`), `fontFamily`, `cardShadow`, `animation` (`fadeIn` | `rise` | `pulse` | `glow`), `borderTop` or `headerBorderWidth`, `bodyBorder`, `darkMode`, and text overrides (`bodyText`, `mutedText`). The fill page maps these to CSS variables (see frontend `appearanceToCssVars`).
- **`fill_mode` (optional):** `all_at_once` (default) or `wizard` — one question per step on the fill page.
- **Per-question `disabled` (optional):** If `true`, the question stays in the editor but is hidden from respondents and is not required on submit (even if `required` is true).
- **Remote packs:** To load templates from a URL at runtime, add a separate feature (signed URLs, allowlist); not implemented here.
