# Product Manager Central UAT, Beta, and Responsible-Use Guide

This guide defines Phase 10 Checkpoint 4 acceptance preparation for Product
Manager Central (PMC) v1.0.0. It consolidates internal user acceptance testing
(UAT), the planned Product Manager beta, troubleshooting, known limitations,
and responsible use of AI-generated content.

Checkpoint 4 does not publish PMC or create an official release package. It
also does not claim that an external beta, native Windows validation, or native
Python 3.11 through 3.13 validation has occurred.

## Validation states and evidence boundaries

PMC distinguishes three forms of evidence:

- **Automated validation** uses deterministic tests, fake or mocked AI
  providers, temporary databases, and temporary package directories. It does
  not use a real API key or make a live OpenAI API call.
- **Internal UAT** applies the scenarios below to the source-controlled product
  and documentation. Checkpoint 4 internal execution uses isolated temporary
  databases and records test names or review evidence.
- **External beta** is a future, separately coordinated study with four to six
  Product Managers. This guide prepares that study; no participant was
  contacted, invited, observed, or asked for feedback during Checkpoint 4.

The clean-install workflow was natively validated on macOS 26.5.2 arm64 with
Python 3.14.6. Windows launchers and Python 3.11 through 3.13 have automated
structural coverage only and have **not** been natively validated.

## UAT purpose and pass criteria

UAT checks that a Product Manager can install and use the local workflow while
the product preserves data, trusted-source, citation, review, and acceptance
safeguards. Unless a scenario explicitly says that native or external evidence
is pending, it passes only when all steps complete without an unexpected error,
the expected result is observed, and the listed evidence is retained. Any
unexpected production-data access, live API call, secret exposure, source
document mutation, unapproved-source retrieval, or generated-content save
without explicit acceptance is an immediate failure and release blocker.

### Internal UAT prerequisites and environment

- Start from a clean Git worktree at the approved Checkpoint 3 baseline.
- Use the pinned direct dependencies in `requirements.txt`.
- Set `PMC_DATABASE_FILE` to a new path inside an isolated temporary directory.
- Ensure `OPENAI_API_KEY` is absent. Use only injected fakes or mocks for AI
  paths that require provider output.
- Never open `data/pmc.db` for write access and never use the protected local
  screenshot as test input.
- Record the production database and protected screenshot hashes before and
  after execution.
- Keep any package build, extraction, checksum, or temporary database outside
  the repository and remove it through automatic temporary-directory cleanup.

## UAT scenarios

### UAT-01 — Clean startup with an empty temporary database

- **Preconditions:** `PMC_DATABASE_FILE` points to a nonexistent path in an
  isolated temporary directory; no API key is present.
- **Steps:** Start PMC; open the Dashboard; inspect the product list and sample
  controls; stop PMC.
- **Expected result:** PMC creates only the temporary database, displays an
  empty workspace and Getting Started guidance, makes no OpenAI call, and does
  not load fictional data.
- **Pass/fail:** Pass only if startup has no application exception, products are
  empty, and the mocked OpenAI constructor is unused.
- **Evidence:**
  `test_release_package.ArchiveBuildTests.test_extracted_package_starts_clean_without_sample_or_openai_call`
  and
  `test_checkpoint2_onboarding.FictionalSampleDataTests.test_application_start_does_not_load_sample_or_call_openai`.
- **Status:** Passed by internal deterministic validation; native external
  installation remains outside this scenario.

### UAT-02 — Product lifecycle and deletion safeguards

- **Preconditions:** Empty temporary database; PMC running without an API key.
- **Steps:** Create a product; view its details; edit it; search for it; begin a
  delete; cancel once; begin again and explicitly confirm deletion.
- **Expected result:** Valid data persists by stable product ID, search finds
  the product, the first delete action does not delete, cancel preserves it,
  and confirmation removes it once.
- **Pass/fail:** Pass only if every workflow completes and no deletion occurs
  without the confirmation step.
- **Evidence:** `tests/test_app_workflows.py` edit, delete, search, dashboard,
  and regression cases plus canonical CRUD tests in `tests/test_database.py`.
- **Status:** Passed by internal deterministic validation.

### UAT-03 — BRD and PRD draft creation and editing

- **Preconditions:** Temporary database containing one valid product.
- **Steps:** Create Draft BRD and PRD documents; view each preview; edit by
  stable document ID; return to the product document list.
- **Expected result:** Both document types remain associated with the selected
  product, Draft documents may contain incomplete sections, and edits preserve
  type, association, and creation identity.
- **Pass/fail:** Pass only if both document workflows persist correctly without
  changing the product or another document.
- **Evidence:** `tests/test_document_workflows.py`,
  `tests/test_document_database.py`, and `tests/test_document_validation.py`.
- **Status:** Passed by internal deterministic validation.

### UAT-04 — Approval validation

- **Preconditions:** Temporary database containing incomplete and complete
  Draft BRD/PRD documents.
- **Steps:** Attempt to approve an incomplete document; complete every required
  section; approve it again.
- **Expected result:** PMC reports all incomplete required sections and performs
  no partial update; the complete document can be approved atomically.
- **Pass/fail:** Pass only if incomplete approval is rejected and complete
  approval succeeds with all values preserved.
- **Evidence:** Approval cases in `tests/test_document_validation.py`,
  `tests/test_document_database.py`, and `tests/test_document_workflows.py`.
- **Status:** Passed by internal deterministic validation.

### UAT-05 — Approved-only retrieval and ineligible-source exclusion

- **Preconditions:** Temporary database with an Approved BRD or PRD, a Draft
  document, and an unsupported document type.
- **Steps:** Request retrievable sections and run deterministic semantic
  retrieval using an injected embedding provider.
- **Expected result:** Only non-empty sections from current Approved BRDs and
  PRDs are eligible; Draft, unsupported, deleted, or newly unapproved sources
  are excluded.
- **Pass/fail:** Any ineligible result is an immediate failure.
- **Evidence:** `tests/test_approved_document_retrieval.py` and integration
  cases in `tests/test_semantic_retrieval.py`.
- **Status:** Passed by internal deterministic validation.

### UAT-06 — Visible and traceable citations

- **Preconditions:** Deterministic generated draft grounded in eligible
  Approved source sections.
- **Steps:** Generate with injected fake providers; inspect each displayed
  source; compare its metadata with the retrieved source.
- **Expected result:** Citations show source number, product name and ID,
  document title and ID, type, and section, and correspond to retrieved text.
- **Pass/fail:** Pass only if every grounded source has complete, matching,
  visible citation metadata.
- **Evidence:** Grounded-prompt and integration cases in
  `tests/test_grounded_generation.py`, citation scoring in
  `tests/test_rag_evaluation.py`, and Streamlit citation checks in
  `tests/test_generated_content.py`.
- **Status:** Passed by internal deterministic validation.

### UAT-07 — No-key non-AI workflows

- **Preconditions:** `OPENAI_API_KEY` absent; temporary database selected.
- **Steps:** Start PMC and exercise Dashboard, product, document, search, and
  accepted-artifact-history paths without opening an AI generation request.
- **Expected result:** Non-AI workflows remain available and no OpenAI client
  is constructed.
- **Pass/fail:** Pass only if the workflows complete without a key and without
  a provider call.
- **Evidence:** App workflow, onboarding, document workflow, and package
  clean-start tests.
- **Status:** Passed by internal deterministic validation.

### UAT-08 — Graceful AI behavior when no key is present

- **Preconditions:** `OPENAI_API_KEY` absent; temporary database selected.
- **Steps:** Open AI Assistant and attempt to begin a grounded generation.
- **Expected result:** PMC reports that AI is optional and inactive, exposes no
  sensitive configuration detail, and stops before retrieval or generation.
- **Pass/fail:** Pass only if the message is actionable and the OpenAI client,
  embedding call, and response call are not invoked.
- **Evidence:** Missing-configuration cases in `tests/test_ai_service.py`,
  `tests/test_assistant_workflow.py`, and `tests/test_grounded_generation.py`.
- **Status:** Passed by internal deterministic validation.

### UAT-09 — Human review before persistence

- **Preconditions:** Fake-provider output with eligible citations in a
  temporary database.
- **Steps:** Generate a draft; inspect the output and citations; optionally
  apply a revision; stop before acceptance.
- **Expected result:** Original and revised content remain pending and unsaved;
  review warnings identify the content as AI-generated and separate.
- **Pass/fail:** Any generated-artifact row before explicit acceptance fails.
- **Evidence:** Review and persistence cases in
  `tests/test_generated_content.py`.
- **Status:** Passed by internal deterministic validation.

### UAT-10 — Explicit acceptance before saving

- **Preconditions:** Pending reviewed generated content with valid citations.
- **Steps:** Choose **Accept and save** once; repeat the same submission or
  Streamlit rerun.
- **Expected result:** One separately stored artifact is created only after the
  explicit action; repeated acceptance is idempotent.
- **Pass/fail:** Pass only if exactly one artifact is stored and the accepted
  content and citations match the reviewed state.
- **Evidence:** Acceptance and rerun cases in
  `tests/test_generated_content.py` and the successful Phase 9 end-to-end case.
- **Status:** Passed by internal deterministic validation.

### UAT-11 — Source-eligibility revalidation at acceptance

- **Preconditions:** Pending grounded review whose cited document is changed
  from Approved to Draft before acceptance.
- **Steps:** Attempt **Accept and save** after the source status change.
- **Expected result:** PMC blocks persistence, gives a safe instruction to
  generate and review again, and stores no artifact.
- **Pass/fail:** Any saved artifact after source invalidation fails.
- **Evidence:**
  `test_generated_content.ReviewAndPersistenceTests.test_source_made_draft_before_acceptance_blocks_save`.
- **Status:** Passed by internal deterministic validation.

### UAT-12 — Generated/source-content separation

- **Preconditions:** Approved source documents and a pending generated draft in
  a temporary database.
- **Steps:** Review, revise, reject, and in a separate case accept generated
  content; compare source documents before and after.
- **Expected result:** Rejecting saves nothing; accepting stores a separate
  generated artifact; no BRD or PRD field is modified.
- **Pass/fail:** Any source-document mutation caused by generation, review,
  rejection, or acceptance fails.
- **Evidence:** `tests/test_generated_content.py`,
  `tests/test_grounded_generation.py`, and `tests/test_phase9_end_to_end.py`.
- **Status:** Passed by internal deterministic validation.

### UAT-13 — Fictional samples remain explicit

- **Preconditions:** Clean temporary database and default Dashboard.
- **Steps:** Start PMC without selecting the sample action; verify emptiness;
  separately select **Load fictional sample data** twice in an isolated test.
- **Expected result:** No sample loads automatically; the explicit action loads
  one marked fictional workspace; repetition creates no duplicate and does not
  replace user data.
- **Pass/fail:** Automatic loading, uncontrolled duplication, or user-data
  replacement fails.
- **Evidence:** Fictional sample cases in
  `tests/test_checkpoint2_onboarding.py`.
- **Status:** Passed by internal deterministic validation.

### UAT-14 — Backup and restoration guidance

- **Preconditions:** PMC stopped; user has identified the exact application
  directory and a private backup location outside it.
- **Steps:** Review the documented stop, copy, restore, and post-restore
  verification sequence without operating on the production database.
- **Expected result:** Guidance requires stopping PMC, preserving the current
  database before replacement, restoring explicitly, and verifying data before
  deleting a backup.
- **Pass/fail:** Pass only if no automated command can overwrite or delete the
  database and the documentation states every safeguard.
- **Evidence:** Documentation inspection of `docs/INSTALLATION.md` and focused
  Checkpoint 4 metadata tests.
- **Status:** Passed by internal documentation validation; no production
  restore was performed.

### UAT-15 — Update, uninstall, and clean-start guidance

- **Preconditions:** Existing installation is stopped; future source archive is
  independently verified; no production file is used for test startup.
- **Steps:** Review the new-directory update sequence, explicit data migration
  boundary, uninstall safeguards, and clean temporary-database startup.
- **Expected result:** Updates never extract over the existing installation;
  uninstall requires an explicit backup decision; clean startup creates no
  sample records.
- **Pass/fail:** Pass only if the guidance prevents implicit data replacement or
  deletion and isolated startup is empty.
- **Evidence:** `docs/INSTALLATION.md`, package clean-start tests, and focused
  Checkpoint 4 metadata tests.
- **Status:** Passed by internal documentation and deterministic validation.

### UAT-16 — macOS launcher and security guidance

- **Preconditions:** Valid source tree; macOS helper permissions retained; test
  process uses fake Python/Streamlit boundaries and no key.
- **Steps:** Verify location-relative setup/run behavior, supported Python range,
  masked session-key prompt, shutdown guidance, and narrow Gatekeeper advice.
- **Expected result:** Helpers resolve their own application directory, stop on
  prerequisite failure, do not persist a key, and never recommend disabling
  machine-wide protections.
- **Pass/fail:** Pass only if executable and documentation checks succeed.
- **Evidence:** `tests/test_launchers.py` and `docs/INSTALLATION.md`. Native
  clean-install evidence remains the Checkpoint 3 macOS 26.5.2 arm64/Python
  3.14.6 validation.
- **Status:** Passed by internal regression validation.

### UAT-17 — Windows launcher instructions and evidence boundary

- **Preconditions:** Windows PowerShell helpers available in the source tree;
  no native Windows environment is claimed.
- **Steps:** Inspect path resolution, virtual-environment Python use, masked
  session-key handling, supported-version checks, and narrow `Unblock-File`
  guidance.
- **Expected result:** Structural tests pass and documentation clearly says
  Windows has not been natively validated.
- **Pass/fail:** Pass for Checkpoint 4 preparation only if structural checks and
  evidence labels are correct; native Windows support remains pending until the
  complete clean-install, full-suite, and no-key smoke sequence passes there.
- **Evidence:** Windows structure cases in `tests/test_launchers.py` and
  `docs/INSTALLATION.md`.
- **Status:** Passed structurally; native Windows validation remains pending.

## Four-to-six-Product-Manager beta plan

### Objectives

The planned beta will evaluate whether Product Managers can understand the
local data model, create and approve BRDs/PRDs, recognize Approved-only AI
sources, trace citations, retain human control over persistence, and recover
from common setup or workflow errors. It will also test whether installation
and responsible-use guidance is understandable without facilitator rescue.

### Participant profile and selection

Recruit four to six Product Managers only after separate approval to begin the
external beta. Seek a mix of early-career and experienced PMs, Mac and Windows
users, and participants with and without prior AI-product experience. Every
participant must be able to use fictional or non-sensitive content and agree
not to enter employer-confidential, personal, regulated, or proprietary data.
Do not select anyone who must use production data or a real project secret to
complete the study.

### Onboarding and session outline

1. Send the approved source/checksum and installation instructions only after a
   beta build and distribution path receive separate authorization.
2. Explain local storage, optional AI, fictional-only study content, and how to
   stop the application before backup or removal.
3. Ask participants to complete representative UAT-01 through UAT-13 workflows
   with isolated study data.
4. Observe where instructions, status labels, citations, review state, or error
   recovery are unclear. Do not collect API keys, source documents, database
   files, screenshots containing private content, or provider payloads.
5. End with a structured feedback form and explain how to report a later issue.

### Feedback to collect

- Participant role/experience band and operating system, without unnecessary
  identifying information.
- Task completion, time-on-task bands, points of confusion, and facilitator
  interventions.
- Confidence distinguishing Draft from Approved, source from generated content,
  and review from acceptance.
- Citation usefulness and whether warnings led to appropriate human checks.
- Installation, launcher, troubleshooting, and recovery clarity.
- Severity, reproducible steps using fictional data, expected result, actual
  result, and a sanitized attachment only when necessary.

Store only the minimum approved feedback. Never request a database, API key,
secret-bearing environment file, real product document, or unsanitized log.

### Issue severity

- **S0 — Stop immediately:** data loss/corruption, secret exposure, production
  data inclusion, live call without explicit user action, unapproved-source use,
  source-document mutation, or persistence without explicit acceptance.
- **S1 — Blocking:** installation or a core workflow cannot complete and no safe
  workaround exists.
- **S2 — Major:** workflow completes only with a safe but material workaround,
  or guidance causes repeated misunderstanding.
- **S3 — Minor:** localized clarity, presentation, or documentation issue that
  does not weaken a safeguard.

S0 and S1 issues stop affected sessions. Resume only after triage, a scoped fix,
full regression verification, and explicit approval. S2 issues require a release
decision before beta exit. S3 issues may be scheduled with documented rationale.

### Exit criteria

- Four to six participants complete the approved study or the study is formally
  stopped with reasons recorded.
- No open S0 or S1 issue remains.
- Every S2 issue has a verified fix or explicit release-blocking disposition.
- Participants can explain Approved-only sources, citation review, explicit
  acceptance, and source separation without unsafe prompting.
- Installation and recovery findings are recorded by platform without turning
  structural evidence into a native-support claim.
- Feedback contains no secrets, personal/production databases, or proprietary
  source content.

### Rollback and stop conditions

Stop distribution and affected sessions for any S0 event, repeated database
error, checksum mismatch, unexpected network behavior, secret-bearing report,
unapproved-source result, missing citation, source mutation, or automatic save.
Preserve sanitized reproduction details, revoke access to the affected beta
artifact if possible, and return to the last verified source commit. Do not ask
participants to disable security controls or continue with potentially damaged
data.

**External-beta status:** Planned only. It has not been conducted, and no
participant outreach or feedback collection occurred in Checkpoint 4.

## Troubleshooting

### Setup cannot find or accept Python

Install Python from python.org and confirm it is version 3.11 through 3.14. Use
the setup helper from the extracted application folder. A structural version
check is not native support evidence; only macOS 26.5.2 arm64 with Python 3.14.6
has completed native validation.

### Dependency or virtual-environment setup fails

Keep the terminal output, confirm the application folder is writable, verify
network access to the package index, and retry the same setup helper. Do not
install undeclared packages into the release or add a real key to diagnose
dependency installation.

### macOS or Windows blocks a launcher

Verify the archive checksum and source first. On macOS, Control-click and open
only the verified `.command` file. On Windows, use the file's **Unblock** option
or `Unblock-File` only for the two verified PMC scripts. Never disable
Gatekeeper or weaken the machine-wide PowerShell execution policy.

### PMC starts with no products

That is the correct clean-start state. Create a product, or deliberately choose
**Load fictional sample data**. PMC never loads the sample automatically.

### AI is inactive

Non-AI workflows require no key. For later authorized AI use, provide your own
key only through the documented process environment or masked session launcher
prompt. Never save it in `.env`, source, a screenshot, a database, or feedback.

### No Approved sources or no relevant evidence

Confirm that a complete BRD or PRD is associated with the intended product and
has been explicitly changed to Approved. Draft and unsupported documents are
correctly excluded. Low-relevance evidence correctly produces no grounded
draft; do not lower the trust boundary to force an answer.

### Acceptance is blocked after review

A cited document may have been deleted, edited, or changed from Approved to
Draft. Generate a fresh draft from current eligible sources and review it
again. Do not bypass source revalidation.

### Database access error

Stop PMC before touching the database. Preserve the current file, confirm the
exact application directory, and follow the backup/restore instructions in
`docs/INSTALLATION.md`. Do not delete sidecars while PMC is running, overwrite
the database speculatively, or send the database as a support attachment.

### Checksum mismatch

Do not extract or run the archive. Download the ZIP and `.sha256` again from the
approved source. Continue only when the independently computed SHA-256 matches.

## Known limitations

- PMC is a single-user local Streamlit/SQLite application without
  authentication, authorization roles, collaboration, cloud hosting, telemetry,
  billing, or hosted backup.
- Native validation currently covers only macOS 26.5.2 arm64 with Python
  3.14.6. Windows and Python 3.11 through 3.13 have structural coverage only.
- The helpers are source launchers, not signed or notarized native installers.
- The database remains inside the application directory, so update and
  uninstall operations require explicit user backup discipline.
- AI requires a user-supplied OpenAI API key and authorized transmission of
  Approved document content. Non-AI workflows remain available without it.
- Semantic retrieval may omit relevant wording or rank imperfect evidence.
  Approved status and citations improve control but do not establish truth.
- AI output may be incomplete, incorrect, stale, biased, or unsupported.
- Accepted artifacts are read-only in PMC; there is no artifact edit, delete,
  regeneration, export, or automatic source-document update operation.
- PMC does not export BRDs/PRDs to Word or PDF and has no analytics integration.
- The external beta has not been conducted. No beta outcome or general user
  suitability is claimed.
- Portfolio screenshots use deterministic fictional Trailwise data. They do not
  provide external-beta, native-Windows, production-use, or customer-outcome
  evidence.

## Responsible use of AI-generated content

- Use only content you are authorized to send to the configured provider.
  Approved in PMC means human-reviewed for workflow use; it does not itself
  establish confidentiality clearance, legal permission, accuracy, or recency.
- Treat every generated draft as untrusted until a person reviews the content
  and every citation. A citation shows the supplied evidence path; it does not
  prove the conclusion is correct.
- Never use PMC output as the sole basis for legal, medical, safety-critical,
  employment, financial, security, or other high-impact decisions. Obtain
  qualified review appropriate to the context.
- Reject unsupported output. Revise only when the correction is understood, and
  still use the separate **Accept and save** action after revision.
- Do not change a Draft to Approved merely to force retrieval, lower relevance
  controls to force an answer, bypass acceptance-time revalidation, or copy
  generated text into a source document without an independent review process.
- Keep original BRDs/PRDs separate from generated artifacts so source evidence
  and AI-assisted synthesis remain distinguishable.
- Never disclose an API key in source, `.env`, logs, screenshots, databases,
  beta feedback, or support material. Rotate a key immediately if exposed.
- The Product Manager remains accountable for source approval, provider-use
  authorization, interpretation, revision, acceptance, sharing, and downstream
  decisions. PMC does not transfer that responsibility to a model.

## Checkpoint 4 completion record

Internal Checkpoint 4 validation passed all 17 scenarios at their documented
internal or structural evidence level, supported by 126 focused tests and the
complete 246-test suite. Compilation and syntax checks, isolated deterministic
package/checksum verification, extracted no-key clean startup,
secret/prohibited-artifact review, and before/after protected-file comparisons
also passed.

External beta execution, native Windows testing, additional native Python
version testing, recruiter assets, release-candidate work, tags, publication,
and GitHub Release creation remained outside Checkpoint 4.

## Checkpoint 5 completion record

Checkpoint 5 added the recruiter-facing case study, Mermaid architecture guide,
three sanitized fictional screenshots, demo storyboard, and draft launch
materials. Screenshot preparation used an isolated temporary database and a
deterministic fictional review harness with no API key or live provider call.
Full-resolution visual, visible-text, and metadata reviews found no browser
chrome, local paths, credentials, personal information, private data, or
identifying metadata.

Six focused portfolio tests, all 20 release-metadata tests, and the complete
252-test suite passed. Compilation, Bash/Zsh syntax, Windows structural tests,
two deterministic 38-member archive builds, checksum and exact-member checks,
extracted no-key clean startup, secret/prohibited-artifact review, and protected-
file comparisons also passed.

The demo has not been recorded, the external beta has not been conducted, and
no material was posted, published, sent, or uploaded. Native Windows and Python
3.11–3.13 validation, an official release candidate, tagging, publication, and
GitHub Release creation remain future work. Checkpoint 6 is not started.
