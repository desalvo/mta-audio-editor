# r210 — User language, dynamic legal PDFs and initial storage quota

Version remains **0.3.0-r210**. No commit, push, tag, release or live-server change was performed.

## Behavior / Comportamento

- Login and self-registration expose exactly two legal links, privacy and terms, in the browser's supported language. Weighted `Accept-Language` supports Italian and English regional variants; unsupported languages fall back to English.
- Legal HTML and PDF use a fresh snapshot of the server's legal configuration and retention settings. Empty identity/contact rows and empty instance-disclosure sections are omitted completely, including their labels/headings. There are no missing-data placeholder values. An unreviewed HTML document still displays the existing review notice.
- PDFs are generated in memory for each request, without remote assets or disk exports, with `Cache-Control: no-store`. Both languages remain available through direct document URLs. The document's PDF button downloads that same language.
- The profile exposes **Auto (browser language)**, **Italiano**, **English**. New and migrated accounts default to Auto. Explicit preferences override the browser for authenticated application pages; login legal links use the browser.
- Auto stores the last supported browser language observed during an authenticated request. Background emails and AI resource digests use the recipient's explicit preference or that stored language. Recipients are delivered separately so administrators with different preferences receive different languages. The former independent AI email language control follows the global profile preference.
- New bootstrap, password and social accounts receive **5 GiB = 5,368,709,120 bytes**. Existing quotas, including custom and unlimited quotas, are retained. Account creation explicitly supplies the quota even on databases whose historical SQL default was zero.
- A shared bilingual catalog and HTML/browser localization cover page labels, menus, inserted dialogs, tooltips, placeholders, alerts, confirmation prompts and browser notifications. Icon prefixes and parameterized UI messages retain their symbols and captured values. Date and numeric display formatting uses the selected language, including AI history and sample counts. Already-translated labels stay stable under repeated DOM updates. Track names, editable text, lyrics and marked user-content nodes are excluded from translation.
- The native bundle includes the JSON catalog; server packages already include the complete application tree. Changed scripts have updated cache keys. Native Auto follows the embedded browser language; existing explicit native IT/EN settings remain available.

## URLs

Browser-language entry points:

- `https://mta.apps.desalvo.eu/privacy`
- `https://mta.apps.desalvo.eu/terms`

Direct PDF endpoints:

- `https://mta.apps.desalvo.eu/privacy/it.pdf`
- `https://mta.apps.desalvo.eu/privacy/en.pdf`
- `https://mta.apps.desalvo.eu/terms/it.pdf`
- `https://mta.apps.desalvo.eu/terms/en.pdf`

The existing `/privacy/it`, `/privacy/en`, `/terms/it`, `/terms/en` HTML routes remain available. PDFs also accept `/privacy/it/pdf` and the corresponding language/document variants.

## Validation

Targeted tests cover browser negotiation, profile persistence and override, new-account quota on all creation paths, migration preserving custom quota, public legal routes and authentication boundaries, current PDF facts after configuration edits, omitted empty fields, escaped facts, catalog consistency and repeated translation, JavaScript execution, recipient-specific email language and native packaging. The four PDFs were generated, text-extracted and inspected; the first Italian privacy page was visually rendered.

**Final result:** 3,872 passed, 5 skipped, 10 deselected; zero failures. Ruff and all nine JavaScript syntax checks pass.

Full regression outcome is recorded in `validation/r210-user-locale-full.log`, JUnit XML and coverage XML. Ruff and JavaScript syntax checks also run. Five optional SDK/Win32 checks require their external runtime; ten existing Unix-socket tests cannot run in this workspace because its sandbox disallows their AF_UNIX fixtures.

The catalog covers application-owned UI text; engine tracebacks, external provider responses, model/product names, identifiers and user-authored content retain their original text. Automated tests do not constitute exhaustive visual validation of every screen or a new certification of the installed server. A final native Windows/macOS smoke test and live-server browser verification remain installation checks.

## Cumulative contents

The package starts from `MTA-0.3.0-r210-mixer-input-gain-cumulative.zip`; all baseline entries are retained, including the mixer input Gain feature and all earlier development. Packaging verifies version/revision, Markdown placement, ZIP CRCs and every archived file against the final source bytes, then emits SHA-256.

Suggested cumulative commit message:

`Add mixer input gain, per-user IT/EN localization, dynamic legal PDFs and 5 GiB default account quotas`
