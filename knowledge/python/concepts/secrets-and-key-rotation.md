# Secrets, API keys, and rotation

> **Last validated**: 2026-04-26
> **Confidence**: 0.95

## The rule

API keys NEVER appear in source code. Not in defaults, not in tests, not in fallbacks. Always loaded from environment or a secret manager.

## Loading from environment

```python
import os

api_key = os.environ["ANTHROPIC_API_KEY"]  # raises KeyError if missing
```

`os.environ[...]` is preferred over `os.getenv("KEY")` for required keys — it fails fast at startup instead of at first API call.

## With pydantic-settings

For a real application with multiple env vars, use `pydantic-settings`. Validation, defaults, and type coercion in one place:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr

class Settings(BaseSettings):
    anthropic_api_key: SecretStr
    openai_api_key: SecretStr | None = None
    azure_ai_project_connection_string: SecretStr
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

settings = Settings()  # raises ValidationError on missing required fields

# Use:
client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value())
```

`SecretStr` prevents the value from appearing in logs / repr / error messages by accident.

## .env file

Standard layout for local dev:

```
# .env (gitignored!)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
AZURE_AI_PROJECT_CONNECTION_STRING=...
LOG_LEVEL=DEBUG
```

```
# .env.example (committed — placeholder values)
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
AZURE_AI_PROJECT_CONNECTION_STRING=
LOG_LEVEL=INFO
```

`.gitignore` MUST include:

```
.env
.env.local
.env.*.local
```

Commit `.env.example` so new contributors know what to set, but never commit `.env` itself.

## Production: managed identity over keys

For Azure-hosted apps, prefer Microsoft Entra (formerly AAD) managed identity over API keys. The Foundry / Azure SDKs all support `DefaultAzureCredential`:

```python
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

cred = DefaultAzureCredential()
client = AIProjectClient(
    credential=cred,
    project_connection_string=settings.azure_ai_project_connection_string.get_secret_value(),
)
```

Benefits over API keys:
- No key to rotate or leak
- Per-environment isolation via separate identities
- Audit trail in Azure logs
- Works seamlessly local (uses your `az login`) and in production (uses the resource's identity)

## Key rotation strategy

When you must use API keys (third-party providers, etc.):

1. **Two active keys at a time** during rotation. Add the new key to env, restart, then revoke the old one.
2. **Automate revocation** — calendar reminder + script. Manual rotation gets skipped.
3. **Scope keys to least privilege** — separate keys for dev/staging/prod. Never share a prod key with a dev environment.
4. **Rotate on personnel change** — anyone with key access leaves → rotate.
5. **Rotate on suspected leak** — pushed to a public repo, in a screenshot — rotate immediately, not "soon".

## What goes where

| Item | Where |
|---|---|
| API keys | env var or Azure Key Vault |
| Connection strings | env var or Azure Key Vault |
| Model deployment names | env var (changes per environment) |
| Resource group / subscription IDs | env var or app config |
| Log level | env var |
| Endpoint URLs | env var (changes per environment) |
| Code constants (timeouts, retry counts) | source code is fine |

## Detecting leaks

Add `pre-commit` hooks that block commits containing key-shaped strings:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets
        args: ["--baseline", ".secrets.baseline"]
```

GitHub Push Protection (free for public repos, included in GitHub Advanced Security) catches API keys on push.

## Anti-patterns to flag

- `api_key="sk-..."` literal in source
- `api_key=os.getenv("KEY", "default-key-here")` — defaults make leaks survive
- `print(settings)` or `logger.debug(settings)` — leaks SecretStr if not careful (use `.get_secret_value()` only at the call site)
- Same key for dev + prod
- `.env` committed to repo
- Keys in URL query strings (logged by every proxy in the path)
- Keys in error messages or stack traces

## See also

- `concepts/cost-tracking-tokens.md` — tracking is also done via env-var-loaded clients
- `anti-patterns.md` (items 11, 17)
