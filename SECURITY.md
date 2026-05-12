# Security policy

## Supported versions

Security fixes are applied to the **current release line** on [PyPI](https://pypi.org/project/fluxlit/). Older versions may not receive backports; upgrade when possible.

| Version   | Support note                                      |
| --------- | ------------------------------------------------- |
| **0.8.x** | Active                                            |
| **0.7.x** | Best-effort fixes; upgrade to 0.8.x recommended   |
| **0.6.x** | Best-effort fixes; upgrade to 0.8.x recommended   |
| **0.5.x** | Best-effort fixes; upgrade to 0.8.x recommended   |
| **0.4.x** | Best-effort fixes; upgrade to 0.8.x recommended   |
| **0.3.x** | Best-effort fixes; upgrade to 0.8.x recommended   |
| **0.2.x** | Best-effort fixes; upgrade to 0.8.x recommended   |
| **< 0.2** | Upgrade recommended; limited backporting        |

Pre-release installs (e.g. from `main`) should track the latest commit for fixes.

## Reporting a vulnerability

**Please do not** open a public GitHub issue for undisclosed security vulnerabilities.

1. Open a **[private vulnerability report](https://github.com/eddiethedean/fluxlit/security/advisories/new)** for this repository (GitHub *Security* → *Advisories* → *Report a vulnerability*), **or**
2. If that route is unavailable, contact the maintainers through a private channel with enough detail to reproduce the issue.

Include affected versions, component (gateway, `ApiClient`, JWT/OIDC helpers, etc.), and impact if you can. We aim to acknowledge reports within a few business days and work with you on a disclosure timeline.

## Dependency and supply chain

- **CI** runs **`pip-audit`** after `pip install -e ".[auth]"` (default dependencies plus the **`auth`** extra: PyJWT, cryptography). That matches what security-sensitive deployments typically install without pulling in contributor-only tools.
- **SBOM:** the same workflow job builds a **CycloneDX JSON** SBOM with **`cyclonedx-py environment`** (root metadata from `pyproject.toml`) and uploads it as a workflow artifact named **`cyclonedx-sbom`**. Download it from the GitHub Actions run summary (artifact retention follows repository/org settings).
- **Local** — same as CI:

  ```bash
  python -m pip install pip-audit
  python -m pip install -e ".[auth]"
  pip-audit
  ```

  To scan a contributor environment (tests, docs, Streamlit stack), install `".[dev,auth,docs]"` and run `pip-audit`; expect more transitive packages and possible advisories outside FluxLit’s direct control.

## Hardening references

- Runtime and Streamlit/API security patterns: [Security architecture](https://fluxlit.readthedocs.io/en/stable/security.html) (documentation).
- [Secrets and rotation](https://fluxlit.readthedocs.io/en/stable/secrets.html), [Production TLS and proxies](https://fluxlit.readthedocs.io/en/stable/production-tls.html).
- JWT/OIDC usage: [Auth recipes](https://fluxlit.readthedocs.io/en/stable/auth-recipes.html).
- How auth and `ApiClient` logging are tested (including that bearer secrets must not appear in debug logs): [Testing](https://fluxlit.readthedocs.io/en/stable/testing.html).
- Structured logging and OpenTelemetry-style notes: [Observability](https://fluxlit.readthedocs.io/en/stable/observability.html).

**OIDC BFF:** Default route registration keeps OAuth ``state`` and Streamlit ``auth_code`` in **process memory**. Deploy with **one worker/replica** for that API process, or replace the store for high availability. ``id_token`` is validated with IdP JWKS when using ``GenericOIDCClient``.
