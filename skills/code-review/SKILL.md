---
name: code-review
description: |
  Systematic review of a pull request or diff. Walks 8 categories (security,
  correctness, error handling, types, performance, testing, observability,
  maintainability) in order of severity. Outputs structured findings with
  severity, location, and remediation pointer. Designed to be applied
  consistently across reviewers — same rubric every time.

  Use when the user says: "review this PR", "review my changes", "code
  review", "audit this diff", "what's wrong with this PR?", "check before
  merge".

  Do NOT use for: simplification only (use simplify skill), security-focused
  audit (deeper scope), performance-focused profiling, or pure architectural
  review.
license: MIT
allowed-tools: [shell]
---

# Code Review

Systematic walk through 8 review categories, in order of severity. Same
rubric every reviewer, same questions every PR. Reduces "why didn't they
catch X?" by ensuring X was always going to be checked.

## Scope

What this skill reviews:
- A diff (`git diff main...HEAD` or a PR URL)
- Recently changed files

What this skill does NOT review:
- Full architectural decisions (ultrathink skill for that)
- Brand-new green-field design
- Files not in the diff (out of scope by design)

## The 8 categories — in order

Walk the categories in this order. Skip none. Order matters because earlier
categories produce findings that block merge regardless of later categories.

### 1. Security

Highest priority. A `CRITICAL` security finding blocks merge regardless of
everything else.

Check for:
- **Hardcoded secrets** — API keys, connection strings, passwords. Use
  `grep -E '(api[_-]?key|password|secret|token)\s*=\s*["\']' <files>`
- **SQL injection risk** — string-interpolation in DB queries vs parameters
- **Path traversal** — user input in file paths without sanitization
- **XXE / unsafe deserialization** — `pickle.load`, `yaml.load` (vs safe_load)
- **PII leakage** — logging full request bodies, user data in error messages
- **Auth bypass** — endpoints without `@require_auth` or equivalent
- **CSRF / SSRF** — see security review skill for deeper checks

Severity policy: CRITICAL for any hardcoded secret. WARN for missing
sanitization at boundaries. INFO for defensive-coding opportunities.

### 2. Correctness

Does the code do what it says it does?

Check for:
- **Off-by-one errors** — loops, slices, array indices
- **Edge cases** — empty input, single-item input, very large input,
  Unicode, negative numbers, zero, infinity, NaN
- **Race conditions** — shared state without locks, async code with
  ordering assumptions
- **Misuse of library APIs** — calling sync method in async context,
  passing wrong type
- **Logic errors in conditions** — `and` vs `or` confusion, negation errors
- **Resource leaks** — file handles, connections, async tasks not closed

Severity: CRITICAL for race conditions in money / auth code. WARN for edge
cases not handled. INFO for unlikely-but-possible misuse.

### 3. Error handling

How does this code behave when things fail?

Check for:
- **Bare `except:`** or `except Exception: pass` (silently swallowing errors)
- **Errors that crash the whole process** when they could be isolated
- **Missing retry logic** for transient failures (HTTP 429/503, network)
- **Retrying on permanent errors** (4xx that's not 429) — wastes tokens / quota
- **No timeout** on network calls, file I/O, locks
- **Generic error messages** that hide the actual cause
- **Errors logged AND re-raised AND wrapped** (triple-handling)

Severity: WARN for bare excepts. WARN for missing timeouts. INFO for
ergonomic improvements.

### 4. Types and contracts

Are the types right? Are the function contracts honored?

Check for:
- **Missing type hints** on public APIs (Python)
- **`# type: ignore`** without an error code or explanation
- **`Any` used where a specific type would work** (especially in return types)
- **`dict[str, Any]` from external sources without Pydantic validation**
- **Mutable default arguments** (`def f(x=[])`)
- **Type narrowing not done** — `Optional[T]` accessed without None check

Severity: WARN for type holes in public APIs. INFO for tightening
opportunities.

### 5. Performance

Does this code perform reasonably under realistic load?

Check for:
- **N+1 queries** — DB call inside a loop
- **O(n²) or worse** algorithms when O(n) was achievable
- **Synchronous blocking calls** in async code
- **Unbounded iteration** over user input
- **Missing pagination** on potentially-large queries
- **No caching** of repeated expensive computations
- **Loading whole tables / files into memory** when streaming would do
- **Cold-start expensive imports** at module top-level

Severity: WARN for clear N+1. INFO for potential issues without measurement.

For LLM code specifically:
- Missing prompt caching on a >2000 token system prompt
- No retry on 429/529 (transient errors)
- Unbounded tool-use loop
- No cost / token logging

### 6. Testing

Is the new behavior tested?

Check for:
- **New code without any test** — at all
- **Tests that pass but don't actually exercise the new behavior**
  (assertion that matches anything)
- **Tests hitting the real paid API by default** (no opt-in marker)
- **`assert result == expected` on stochastic LLM output**
- **Tests with `time.sleep`** (use proper async / fixtures)
- **Mocks returning unrealistic types** (raw dicts vs SDK objects)
- **No test for the failure case** (only happy path)
- **Test that depends on previous test state** (shared mutable fixture)

Severity: WARN for code without any test. INFO for test quality issues.

### 7. Observability

When this fails in production, can we debug it?

Check for:
- **Missing structured logging** — `print()` instead of `logger.info(...)`
- **Logs without context** — no operation_id / trace correlation
- **No metrics emitted** for operations the team would want to dashboard
- **Errors logged at wrong severity** (`info` for what should be `error`)
- **Logging full prompts / responses** (PII + log volume)
- **No span / trace creation** for new operations in OTel-instrumented code

Severity: INFO mostly. WARN if production-bound code with no error logging.

### 8. Maintainability

Will future-you (or the next person) be able to work with this?

Check for:
- **Duplicate logic** — could be extracted (link to simplify skill)
- **Names that hide intent** — single-letter, abbreviations, ambiguous predicates
- **Functions doing 5+ things** — should be decomposed
- **Comments restating WHAT** (cruft) — but keep WHY comments
- **Magic numbers without names**
- **Inconsistency with project conventions** — (formatter / linter / naming)

Severity: INFO almost always. Don't escalate style preferences to WARN.

## Workflow

### Step 1 — Get the diff

```bash
# For a local branch
git diff main...HEAD --name-only           # files changed
git diff main...HEAD                       # full diff

# For a remote PR (via gh CLI)
gh pr diff <PR-number>
```

### Step 2 — Walk the 8 categories

For each changed file, walk categories 1-8 IN ORDER. Don't jump ahead. Don't
skip security to get to maintainability faster.

### Step 3 — Categorize each finding

```
type:        SECURITY | CORRECTNESS | ERROR_HANDLING | TYPES |
             PERFORMANCE | TESTING | OBSERVABILITY | MAINTAINABILITY
severity:    CRITICAL | WARN | INFO
target:      file:line
message:     <plain-language description>
remediation: <pointer to fix or KB reference>
```

### Step 4 — Sort and emit

Sort findings by severity (CRITICAL → WARN → INFO). Within severity, sort by
type (security first, maintainability last). Emit using the output template.

## Output template

```markdown
# Code Review

**Diff scope:** <commit range or PR>
**Files reviewed:** <count>
**Findings:** <CRITICAL>: N, <WARN>: N, <INFO>: N

---

## CRITICAL

### 1. <type>: <one-line summary>
**File:** `path/to/file.py:42`
**Issue:** <description>
**Fix:**
```diff
- bad code
+ good code
```
**Why:** <reasoning>

---

## WARN

<...same shape...>

---

## INFO

<...same shape — bullet list OK if many small findings...>

---

## Summary

- Categories with findings: <list>
- Categories clean: <list>
- Highest-priority action: <one line>
- Suggested next skill: <simplify | tests | architect>
```

## Severity policy (when in doubt)

| Situation | Severity |
|---|---|
| Hardcoded secret | CRITICAL |
| SQL injection / unsafe deserialization | CRITICAL |
| Race condition in money/auth code | CRITICAL |
| Bare `except:` swallowing real errors | WARN |
| Missing retry on transient errors | WARN |
| Missing timeout on network call | WARN |
| Missing test for new code | WARN |
| Type hole in public API | WARN |
| N+1 query | WARN |
| Style inconsistency | INFO |
| Could-be-clearer naming | INFO |
| Missing structured log | INFO |
| Duplicate that could be extracted | INFO (link to simplify) |

## When to recommend a different skill

After review, if findings cluster:
- 5+ MAINTAINABILITY findings → recommend `simplify` skill
- 2+ TESTING findings → recommend writing tests before merging
- 1+ CRITICAL → block merge, no skill needed; just fix
- Architectural concern surfaced → recommend `ultrathink` skill

## See also

- `references/review-checklist.md` — printable single-page checklist
- `simplify` skill — for refactoring after review
- `ultrathink` skill — when review surfaces an architectural concern
