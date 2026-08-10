# Product Manager Central Launch Materials

**Draft status:** These materials have not been posted, published, sent, or
uploaded. PMC v1.0.0 has not been tagged or released, the demo video has not
been recorded, and the planned external beta has not been conducted.

## Draft LinkedIn post

I’ve been building Product Manager Central, a local workspace for Product
Managers to organize product context, create BRDs and PRDs, and explore
AI-assisted drafting without losing sight of the source material or the human
decision maker.

The product started with a simple question: how can an AI workflow help a PM
move faster while keeping approval, evidence, and accountability visible?

PMC treats those safeguards as part of the experience. Only Approved BRDs and
PRDs are eligible for retrieval. Generated drafts show traceable citations,
remain unsaved during review, and require an explicit acceptance action.
Before saving, PMC checks the cited sources again. Accepted output is stored as
a separate artifact and never changes the original source documents.

The application runs locally with Streamlit and SQLite. Non-AI workflows work
without an API key, and the optional provider connection is isolated behind an
environment-configured boundary. I also built deterministic offline tests and
an explicit-manifest source-package builder designed to exclude databases,
secrets, backups, and other local artifacts.

The current portfolio materials use fictional Trailwise data. Native validation
currently covers macOS 26.5.2 arm64 with Python 3.14.6; Windows and Python
3.11–3.13 have structural coverage only. The external beta and public release
are still future work.

Building PMC reinforced a product lesson I care about: responsible AI controls
are strongest when users can see and act on them in the workflow—not when they
are hidden in a disclaimer.

## Résumé bullets

- Designed and built Product Manager Central, a local Streamlit/SQLite workspace
  for structured product records, BRD/PRD authoring, search, lifecycle
  management, and optional grounded AI drafting.
- Defined an Approved-only retrieval and citation model with human review,
  explicit acceptance, acceptance-time source revalidation, and separate
  persistence for generated artifacts so source documents remain unchanged.
- Created deterministic offline evaluation and automated workflow coverage using
  temporary databases and fake or mocked AI providers, avoiding real keys and
  live-model dependencies in tests.
- Established evidence-based cross-platform release governance with pinned
  direct dependencies, Mac and Windows launch helpers, explicit compatibility
  boundaries, and a reproducible allowlist-based source-package builder.
- Developed UAT, responsible-use, beta-planning, architecture, demo, and
  recruiter-facing materials while distinguishing implemented capabilities
  from unvalidated external outcomes.

## Interview talking points

### Product problem and prioritization

- Product context is fragmented, and general-purpose AI can obscure where an
  answer came from. I prioritized structured source documents and visible trust
  states before expanding generation capabilities.
- The MVP stays local and single-user to validate the workflow without taking on
  authentication, collaboration, hosted databases, billing, and enterprise
  operations prematurely.

### Human control and responsible AI

- Approved status is a retrieval eligibility decision, not a guarantee that a
  document is true, current, or authorized for every use.
- Citations expose the evidence path but do not guarantee factual correctness.
- Generated content stays pending until review and explicit acceptance.
- Acceptance-time revalidation handles the case where a source changes after
  generation but before persistence.
- Accepted content is stored separately so the source of record is never
  silently rewritten by AI output.

### Technical and delivery choices

- I kept module boundaries focused: validation, templates, persistence,
  retrieval, prompts, generation, review, and evaluation can be tested
  independently.
- Temporary databases and injected providers make safety and failure states
  deterministic without a live API call.
- The release builder uses an explicit allowlist instead of broad repository
  zipping, making prohibited-file inclusion fail closed.
- Compatibility claims are evidence-based: native validation covers macOS
  26.5.2 arm64 with Python 3.14.6; Windows and Python 3.11–3.13 remain
  structurally tested only.

### What I would do next

- Complete separately approved release-candidate verification.
- Validate native Windows and additional Python environments.
- Run the planned four-to-six-Product-Manager beta with fictional or
  non-sensitive content and predefined stop conditions.
- Use observed workflow evidence—not invented adoption or outcome metrics—to
  prioritize subsequent improvements.

## Concise portfolio summary

Product Manager Central is a local Streamlit and SQLite workspace for product
records, BRDs, PRDs, search, and optional AI-assisted drafting. Its trust model
limits retrieval to Approved source documents, displays traceable citations,
requires human review and explicit acceptance, revalidates source eligibility
before saving, and stores generated artifacts separately from original BRDs and
PRDs. The project includes deterministic offline evaluation, UAT and
responsible-use guidance, cross-platform source launchers, and reproducible
allowlist-based packaging. It does not yet claim an external beta, native
Windows validation, production usage, or a published v1.0.0 release.
