# Security policy

## Supported versions

Security fixes are applied to the **current minor release line** on [PyPI](https://pypi.org/project/fluxlit/) (for example **0.13.x** while that line is current). Older minors may receive **best-effort** fixes only; upgrade to the latest patch on the current line when reporting or consuming fixes.

There is **no separate LTS branch** for **0.x**; policy matches [Support matrix](https://fluxlit.readthedocs.io/en/stable/support-matrix.html) (long-term support section).

| Version line | Support note |
| ------------ | ------------ |
| **Current minor** on PyPI (e.g. **0.13.x**) | **Active** — security-relevant fixes target this line first. |
| **Previous minors** (e.g. **0.12.x**, **0.11.x**) | **Best-effort** — upgrade to the current minor when practical. |
| **Older 0.x** | **Upgrade recommended** — limited backporting; same best-effort stance as previous minors. |

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

- **httpx bumps:** `ApiClient` imports a few **typing-only** symbols from `httpx._types` and `httpx._client` (see `src/fluxlit/client.py`). After any **httpx** upgrade, run the full test suite; `tests/test_httpx_import_contract.py` fails early if those private modules no longer export the symbols FluxLit expects.

## Hardening references

- Runtime and Streamlit/API security patterns: [Security architecture](https://fluxlit.readthedocs.io/en/stable/security.html) (documentation).
- [Secrets and rotation](https://fluxlit.readthedocs.io/en/stable/secrets.html), [Production TLS and proxies](https://fluxlit.readthedocs.io/en/stable/production-tls.html).
- JWT/OIDC usage: [Auth recipes](https://fluxlit.readthedocs.io/en/stable/auth-recipes.html).
- How auth and `ApiClient` logging are tested (including that bearer secrets must not appear in debug logs): [Testing](https://fluxlit.readthedocs.io/en/stable/testing.html).
- Structured logging and OpenTelemetry-style notes: [Observability](https://fluxlit.readthedocs.io/en/stable/observability.html).

**OIDC BFF:** Default route registration keeps OAuth ``state`` and Streamlit ``auth_code`` in **process memory**. Deploy with **one worker/replica** for that API process, or replace the store for high availability. ``id_token`` is validated with IdP JWKS when using ``GenericOIDCClient``.
