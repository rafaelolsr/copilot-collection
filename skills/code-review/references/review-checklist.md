# Code Review Checklist

> Single-page printable checklist for the `code-review` skill. Walk top-to-bottom.

---

## Before starting

- [ ] Have I read the PR description / issue?
- [ ] Do I understand what change is intended?
- [ ] Have I run the diff locally? (`gh pr checkout <num>` or `git fetch && git checkout <branch>`)

---

## 1. SECURITY (block-on-find)

- [ ] No hardcoded API keys / secrets / passwords / tokens
- [ ] No connection strings with credentials in source
- [ ] SQL queries use parameters (no f-string / `+` interpolation)
- [ ] User input sanitized before file paths / shell commands / URLs
- [ ] No `pickle.load()`, `yaml.load()` (use `safe_load`), `eval()` on user input
- [ ] PII not logged in plain text (emails, names, IDs, full request bodies)
- [ ] Auth checks on protected endpoints (`@require_auth` or equivalent)
- [ ] Secrets via env vars / Key Vault, NEVER in code or default fallbacks

---

## 2. CORRECTNESS

- [ ] Edge cases handled: empty, single-item, very large, Unicode, zero, negative, NaN
- [ ] Off-by-one errors checked (loops, slices, indices)
- [ ] Async code: no shared mutable state without locks
- [ ] Library APIs called correctly (sync vs async, types)
- [ ] Boolean logic: `and` vs `or`, negation, De Morgan
- [ ] Resources closed: file handles, connections, async tasks (use `with` / context managers)

---

## 3. ERROR HANDLING

- [ ] No bare `except:` or `except Exception: pass`
- [ ] Catches specific exception types, not generic `Exception`
- [ ] Errors logged with context (operation_id, params, stack)
- [ ] Errors re-raised after logging (not silently swallowed) where the layer should fail
- [ ] Retry on transient (429, 503, network), NOT on permanent (4xx)
- [ ] Timeouts on every network / I/O / lock operation
- [ ] Generic error messages don't hide root cause

---

## 4. TYPES & CONTRACTS

- [ ] Public APIs have type hints (Python: every parameter + return)
- [ ] No `# type: ignore` without an error code AND comment explaining why
- [ ] No `Any` in public API return types (without justification)
- [ ] No `dict[str, Any]` from external sources without Pydantic validation
- [ ] No mutable default arguments (`def f(x=[])`, `def f(x={})`)
- [ ] `Optional[T]` accessed only after None check (or via narrowing)

---

## 5. PERFORMANCE

- [ ] No N+1 queries (DB call inside loop over results)
- [ ] No O(n²) where O(n) was achievable
- [ ] No sync blocking call (`time.sleep`, `requests.get`) in async function
- [ ] User input has bounded iteration (no unbounded `for x in user_data`)
- [ ] Large queries paginated
- [ ] Repeated expensive computations cached
- [ ] No `df.collect()` / `cursor.fetchall()` on potentially-huge data
- [ ] LLM calls: prompt caching for stable system prompts; retry on 429/529; cost tracking

---

## 6. TESTING

- [ ] New code has tests
- [ ] Tests actually exercise the new behavior (not vacuously passing)
- [ ] Real-API tests gated behind `@pytest.mark.eval` or equivalent
- [ ] Stochastic output: tolerance bands, NOT `assert ==`
- [ ] No `time.sleep()` in tests (use fixtures / proper async)
- [ ] Mocks return realistic SDK-shaped objects (not raw dicts)
- [ ] Failure case tested (not just happy path)
- [ ] Tests don't depend on shared mutable state

---

## 7. OBSERVABILITY

- [ ] `logger` used, NOT `print()`
- [ ] Logs include operation_id / trace correlation
- [ ] Errors at `error` severity, warnings at `warning`, etc. (not all `info`)
- [ ] No full-request-body logging (PII + volume)
- [ ] OTel spans for new operations (if codebase is instrumented)
- [ ] Metrics emitted for things you'd want on a dashboard

---

## 8. MAINTAINABILITY

- [ ] Names communicate intent (no single-letter outside short loops)
- [ ] Boolean predicates read as such (`is_active`, `has_valid_token`)
- [ ] Functions do one thing (or one level of abstraction)
- [ ] Magic numbers / strings have named constants
- [ ] No duplicate logic that should be extracted (rule of three)
- [ ] Comments explain WHY, not WHAT
- [ ] Project conventions followed (formatter, linter, naming style)

---

## Final pass

- [ ] Have I read the full diff (not skimmed)?
- [ ] Have I left at least one positive comment? (PRs are people)
- [ ] Are my comments specific and actionable, not vague?
- [ ] Have I distinguished MUST FIX from NICE-TO-HAVE clearly?
- [ ] If I'd reject this PR, is the reason concrete enough to fix?

---

## Severity decision tree

```
Is it a security risk? → CRITICAL
Will it cause data loss / corruption? → CRITICAL
Will it break in production for real users? → WARN
Is it a code smell that will accumulate? → INFO
Is it a personal preference? → don't comment, or comment with "nit:"
```

## Comment phrasing

Good:
- "This will leak the API key in logs — replace with hash on line 42"
- "Edge case: what happens when `items` is empty? Test on line 17 doesn't cover this"
- "Suggestion: extract the validation block (lines 30-45) — it's used in 3 places"

Bad:
- "I don't like this"
- "This is wrong"
- "Refactor"
- "?"

Specific. Actionable. Reviewable.
