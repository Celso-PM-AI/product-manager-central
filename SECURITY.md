# Security Policy

## Current support status

Product Manager Central is preparing its first public portfolio release. No
published version is currently supported. The planned v1.0.0 release will be
covered by this policy only after it has passed Phase 10 release verification
and has been explicitly published.

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
to Git, screenshots, logs, prompts, databases, or release archives. When AI is
enabled, selected Approved BRD and PRD content is sent to the configured OpenAI
API; users are responsible for ensuring they are authorized to send that data.

Security fixes must preserve the trusted-source, citation, human-review,
explicit-acceptance, and source-separation safeguards established in Phase 9.
