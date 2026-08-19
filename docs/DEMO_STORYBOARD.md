# Product Manager Central Demo Storyboard

**Target duration:** 3 minutes 20 seconds

**Status:** Storyboard and recording checklist only. The demo video has not been
recorded.

Use only the deterministic fictional Trailwise workspace. Do not enter a real
API key or show personal, employer, customer, or production information.

## Storyboard

| Time | Screen and action | Narration goal |
|---|---|---|
| 0:00–0:25 | Title, then fictional Dashboard | Product context is often fragmented across records and documents. PMC gives an individual Product Manager a structured local workspace with optional, controlled AI assistance. |
| 0:25–0:50 | Dashboard metrics and Getting Started | Explain local SQLite storage, no-key non-AI workflows, and explicit fictional sample loading. State that the displayed Trailwise workspace is fictional. |
| 0:50–1:20 | Open Trailwise product detail | Show structured product context, lifecycle status, searchability, and the relationship between a product and its BRDs/PRDs. |
| 1:20–1:45 | Show Approved PRD, Draft BRD, and PRD Success Matrix | Explain that Draft supports work in progress, while only complete, explicitly Approved BRDs and PRDs can become AI sources. Point out the Epic → Capability → Feature → User Story hierarchy and independent acceptance criteria. |
| 1:45–2:15 | Open the prepared fictional AI review | Show the typed Epic review, traceable citations, claim-support results, and fail-closed gates. Clarify that the displayed output was prepared with a deterministic fake provider, not a live model call, and that a citation identifies supplied evidence but does not guarantee correctness. |
| 2:15–2:45 | Review, revision, rejection, and **Accept and save** controls | Explain that generation does not persist automatically. Acceptance revalidates cited sources and stores an artifact separately; it never modifies the original PRD or BRD. |
| 2:45–3:05 | Accepted history and Word/PDF downloads | Show that accepted content remains read-only and distinct from sources, then show local Word and PDF download controls for the saved PRD. Explain that export is read-only and requires no API key. |
| 3:05–3:20 | Architecture diagram and limitations | Close with the local Streamlit/SQLite architecture, Approved-only trust boundary, responsible-AI controls, controlled-beta positioning, native Google Docs and platform-validation limitations, and the absence of production or customer-outcome claims. |

## Recording checklist

### Prepare

- Use a fresh isolated temporary database selected with `PMC_DATABASE_FILE`.
- Load only the source-controlled fictional Trailwise sample.
- Use a deterministic fake provider for any prepared AI-review state.
- Confirm `OPENAI_API_KEY` is absent and make no live API call.
- Use a clean browser window and capture only the application viewport.
- Close notifications and unrelated applications.
- Set a readable zoom and window size; verify text is not clipped.
- Rehearse to remain between two and four minutes.

### Privacy and accuracy review

- Confirm every product and document is explicitly fictional.
- Check for names, usernames, paths, bookmarks, extensions, desktop content,
  notifications, keys, tokens, private data, and browser chrome.
- Do not show terminal output, environment variables, database files, or API
  provider dashboards.
- Say that AI content may be incorrect and requires source and citation review.
- Show that Agile acceptance criteria belong independently to each Epic,
  Capability, Feature, or User Story, and that Word/PDF output is local.
- Do not imply an external beta, native Windows validation, production usage,
  real-user results, a published release, or a recorded demo before one exists.
- State that Windows and Python 3.11–3.13 validation is structural only; native
  validation currently covers macOS 26.5.2 arm64 with Python 3.14.6.

### Final review

- Watch the complete recording at full resolution.
- Verify the duration and that every narrated claim matches repository evidence.
- Inspect representative frames again for private or identifying information.
- Confirm audio contains no names or confidential background conversation.
- Retain no recording until it passes the approved privacy and claims review.
