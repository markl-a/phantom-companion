# Security Policy

## Supported Versions

Until the first public release, only the current main branch is supported for security review.

## Reporting A Vulnerability

Do not open a public issue for a vulnerability, exploit path, secret leak, or private-data exposure. Use a private GitHub security advisory when available, or contact the repository owner through a private maintainer channel.

Include:

- affected commit or version;
- reproduction steps using synthetic data where possible;
- impact and affected safety boundary;
- whether credentials, private data, or live systems were involved.

We aim to acknowledge valid reports within 7 days. Public disclosure should wait until a fix or mitigation is available.

## Scope And Safety Boundaries

- Public artifacts must contain no private data and no credentials.
- Default demos must remain synthetic, fixture-based, offline, mock, dry-run, or read-only.
- Live services, external networks, brokers, real connectors, active scanning, real training, or regulated data require explicit opt-in documentation.
- Do not submit runnable exploit payloads, live secrets, customer records, private health data, proprietary datasets, or raw production logs.
- Security fixes that change public behavior must update `docs/OPEN_SOURCE_READINESS.md`.
