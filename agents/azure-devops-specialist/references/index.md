# Azure DevOps Knowledge Base — Index

> **Last validated**: 2026-04-26
> **Confidence**: 0.91
> **Scope**: Pipeline YAML, REST API (Repos, Wiki, Pipelines, Boards), branch policies, service connections, workload identity federation, PR automation.

## KB Structure

### Concepts

| File | Topic | Status |
|---|---|---|
| `concepts/pipeline-yaml-structure.md` | Stages, jobs, steps, templates, conditions, variables | Validated |
| `concepts/triggers-and-schedules.md` | CI / PR / scheduled / manual; path filters; branches include/exclude | Validated |
| `concepts/auth-and-service-connections.md` | WIF, service principal, PAT, managed identity, System.AccessToken | Validated |
| `concepts/branch-policies.md` | Required reviewers, build validation, merge strategies | Validated |
| `concepts/azure-devops-rest-api.md` | API basics, auth headers, versioning, rate limits | Validated |
| `concepts/wiki-and-pages-api.md` | Wiki tree, page CRUD, ETag handling, attachments | Validated |

### Patterns

| File | Topic |
|---|---|
| `patterns/pipeline-with-wif.md` | Pipeline using workload identity federation (no secrets) |
| `patterns/scheduled-pipeline-with-cron.md` | Daily / nightly job with `always: true` |
| `patterns/pr-creation-via-rest.md` | Branch + push + create PR + assign reviewers |
| `patterns/pipeline-template-extends.md` | `extends:` template for reusable pipeline shape |
| `patterns/wiki-incremental-sync.md` | Sync wiki pages with content-hash dedup |
| `patterns/build-validation-policy.md` | Branch policy requiring CI to pass before merge |

### Reference

| File | Topic |
|---|---|
| `anti-patterns.md` | 20 Azure DevOps anti-patterns to flag on sight |

## Reading Protocol

1. Start here (`index.md`) to identify relevant files for the task.
2. For task type → file map:
   - "create a pipeline YAML" → `concepts/pipeline-yaml-structure.md` + matching pattern
   - "schedule a job" → `concepts/triggers-and-schedules.md` + `patterns/scheduled-pipeline-with-cron.md`
   - "auth from a pipeline to Azure" → `concepts/auth-and-service-connections.md` + `patterns/pipeline-with-wif.md`
   - "create a PR via API" → `concepts/azure-devops-rest-api.md` + `patterns/pr-creation-via-rest.md`
   - "sync wiki pages" → `concepts/wiki-and-pages-api.md` + `patterns/wiki-incremental-sync.md`
   - "extract reusable pipeline" → `patterns/pipeline-template-extends.md`
   - "set up branch protection" → `concepts/branch-policies.md` + `patterns/build-validation-policy.md`
   - "review my pipeline" → `anti-patterns.md`
3. If any file has `last_validated` older than 90 days, use `web` tool to re-validate against:
   - https://learn.microsoft.com/en-us/azure/devops/pipelines/yaml-schema/
   - https://learn.microsoft.com/en-us/azure/devops/
   - https://learn.microsoft.com/en-us/rest/api/azure/devops/
4. Check `anti-patterns.md` whenever reviewing user pipeline YAML or API code.
