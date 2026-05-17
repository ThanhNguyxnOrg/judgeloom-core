# Security Policy

We take the security of JudgeLoom seriously. Thank you for helping keep the project and its users safe.

## Supported versions

JudgeLoom is in active early development. Until a stable `1.0` is released, only the latest commit on the `master` branch receives security fixes.

| Version | Supported          |
| :------ | :----------------: |
| `master` (HEAD) | ✅ |
| Older commits / tags | ❌ |

## Reporting a vulnerability

**Please do not open public GitHub issues for security vulnerabilities.**

Instead, report them privately through one of the following channels:

1. **Preferred:** [GitHub Security Advisories](https://github.com/ThanhNguyxnOrg/judgeloom-core/security/advisories/new) — open a private advisory directly on the repository.
2. **Alternative:** Contact the maintainer privately through GitHub: [@ThanhNguyxn07](https://github.com/ThanhNguyxn07).

When reporting, please include as much of the following as you can:

- A clear description of the issue and its potential impact
- Steps to reproduce, including any required configuration
- Affected versions or commit SHAs
- Proof-of-concept code, payloads, or screenshots if applicable
- Whether the issue has been disclosed elsewhere (e.g., to a CVE numbering authority)

## Our process

1. We aim to acknowledge new reports within **3 business days**.
2. We will triage and confirm the vulnerability, then propose a fix or mitigation.
3. We target a fix within **30 days** for high-severity issues; lower-severity issues may take longer.
4. Once a fix lands and is deployed, we will publish a security advisory crediting the reporter (unless they prefer to remain anonymous).

## Coordinated disclosure

We follow a **coordinated disclosure** model. Please give us reasonable time to investigate and ship a fix before any public disclosure. We are happy to coordinate timing and credit with you.

## Out of scope

The following are generally **not** considered security vulnerabilities:

- Reports based purely on automated scanner output without a working proof-of-concept
- Issues that require physical access to a user's device
- Self-XSS that requires the victim to paste malicious content into their own browser
- Missing security headers on non-sensitive endpoints when no concrete impact can be demonstrated
- Lack of rate-limiting on endpoints where rate-limiting would not meaningfully reduce risk
- Vulnerabilities in third-party dependencies that are already publicly disclosed and have an open Dependabot PR

## Safe harbour

We will not pursue legal action against researchers who:

- Make a good-faith effort to follow this policy
- Do not access, modify, or destroy data belonging to other users
- Do not run denial-of-service attacks against production systems
- Give us reasonable time to fix the issue before public disclosure

Thank you for helping keep JudgeLoom and its users safe. 🛡️
