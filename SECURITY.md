# Security Policy

## Current support status

Product Manager Central v1.0.0 is the published portfolio baseline. The current
source prepares v1.0.1 as a controlled-beta/portfolio release for technical
evaluation. PMC is not a commercial production application and does not claim
multi-user, hosted, regulated, or enterprise security support.

## Reporting a vulnerability

Do not disclose suspected vulnerabilities, API keys, personal data, database
contents, or other sensitive details in a public issue. Prefer GitHub's private
vulnerability-reporting feature for this repository when it is available. If a
private report cannot be opened, create a public issue containing no sensitive
details and request a private contact channel.

Include the affected version or commit, operating system, reproduction steps,
impact, and any safe supporting evidence. Never include a real OpenAI API key or
production database.

## Local security model

PMC is a single-user local application. It does not provide authentication,
authorization, encrypted SQLite storage, hosted infrastructure, or enterprise
security controls. Anyone with access to the local account and application
files may be able to read the local database.

OpenAI capability is optional. Users supply their own key through the local
process environment. Keys must not be stored in source, configuration committed
to Git, screenshots, logs, prompts, documents, exports, SQLite databases, or
release packages. A key authorizes the configured AI provider; it does not grant
automatic access to company information or establish permission to submit it.
Enterprise users must obtain an organization-approved key and data-use
authorization from their IT, security, AI-governance, or platform-administration
team. Confidential, proprietary, regulated, personal, export-controlled, or
customer information must not be sent to an external provider without
organizational approval. When AI is enabled, only deliberately selected Approved
BRD and PRD content is sent to the configured OpenAI API.

Security fixes must preserve the trusted-source, citation, human-review,
explicit-acceptance, and source-separation safeguards established in Phase 9.

## Grounded-generation and acceptance controls

- Prompt injection and prompt-injection-like text in a BRD or PRD remain
  untrusted source data. They
  cannot replace application instructions, the selected Product, source scope,
  prompt version, behavior profile, artifact type, or structured-output schema.
- Source selection and retrieval are constrained to the selected Product and
  selected Approved BRDs/PRDs. Cross-product or Draft evidence is rejected.
- Strict structured output, stable source references, hierarchy validation,
  and owner-specific citations reject malformed or fabricated relationships.
- Citation presence alone never proves an unsupported claim. Unsupported,
  ambiguous, contradicted, or missing-source claims, absent measurable
  criteria, source gaps, and non-saveable proposals block every profile.
- Revision reruns the same checks. Acceptance revalidates source eligibility
  and freshness, and the database boundary independently repeats claim and
  full-section checks inside the transaction. A stale source or failed gate
  saves no partial record.
- Product Manager requests, source records, parent context, retrieval Top-K,
  structured responses, accepted text, product/document fields, and export
  components have explicit input limits to reduce denial-of-service risk.
- Provider errors are replaced with user-safe messages. Credentials, hidden
  instructions, provider payloads, raw SQL, and local paths are not displayed
  or persisted as error detail.

Word and PDF export is local and read-only. PMC does not send exported content
to Microsoft Word, a hosted converter, OpenAI, or another provider. Export
filenames are sanitized and bytes are generated in memory; users remain
responsible for protecting downloaded files that may contain product content.

User-controlled export names cannot select a directory or path: traversal,
separator, control, markup-like, and unsupported filename characters are
normalized into bounded deterministic components. Word output is macro-free
and has no external relationships; PDF markup-sensitive text is escaped.
Path traversal is therefore rejected. Normal export creates no repository
temporary files, and a rendering failure is
reported without exposing a local path. Release-package tests reject databases,
sidecars, generated DOCX/PDF files, archives, secrets, caches, and temporary
artifacts.

Checkpoint 13 regression verified these boundaries with fictional content,
temporary databases, injected providers, and no real API key or live provider
call. This verification is not a claim that PMC is released or supported for
multi-user, hosted, regulated, or adversarially shared environments.
