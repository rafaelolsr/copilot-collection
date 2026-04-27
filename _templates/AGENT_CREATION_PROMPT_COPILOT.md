AGENT CREATION REQUEST  (GitHub Copilot CLI variant)
Fill the DECLARATION block. The CLI executes the rest.

This prompt produces a custom agent that conforms to the official
GitHub Copilot CLI custom-agents specification:
  https://docs.github.com/en/copilot/reference/custom-agents-configuration
  https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli

===================================================================


HARD ANTI-SUBSTITUTION CONTRACT  (read before generating anything)
===================================================================

This DECLARATION is for ONE specific domain — the value in
DOMAIN.primary. Every concept, pattern, and anti-pattern you
generate MUST be specific to that domain.

If you catch yourself about to write about a library, SDK, or
framework that is NOT explicitly named in DOMAIN.versions or
DOMAIN.sources — STOP. You are substituting generic training
content for the requested domain.

Specifically forbidden substitutions (unless explicitly named in
the DECLARATION):
  - Generic LLM SDK / vendor API patterns
  - tenacity / instructor / langchain / llama-index
  - Pydantic patterns disconnected from the domain
  - Generic "async Python LLM client" patterns
  - Generic "uv project setup" patterns

Before writing each file:
  1. Read the file name from CONCEPTS / PATTERNS / SPECS
  2. Confirm that name appears in the DECLARATION verbatim
  3. If unfamiliar with the topic → fetch docs from DOMAIN.sources
     URLs FIRST. Do not guess. Do not infer from related domains.
  4. If you cannot find authoritative content for a concept on the
     list → emit the file with a [NEEDS REVIEW: source unverified]
     stub and a confidence score of 0.50, but do NOT substitute
     content from a different domain.

You may only generate files whose names appear in the DECLARATION's
CONCEPTS, PATTERNS, or SPECS lists. No additions. No substitutions.

If you violate this contract, STOP, delete the offending file, and
re-read this section.

===================================================================


COPILOT CLI SPEC FACTS  (binding — do not deviate)
===================================================================

These facts come from the official GitHub Copilot CLI documentation.
The generator MUST follow them exactly:

FILE FORMAT
  - Custom agents use the file extension .agent.md (NOT .md)
  - Agent file body (after frontmatter) is capped at 30,000 characters

FILE LOCATIONS  (in priority order — user-level overrides repo-level)
  - User-level:  ~/.copilot/agents/[name].agent.md
  - Repo-level:  .github/agents/[name].agent.md
  - Choose repo-level by default unless DECLARATION specifies user-level

FRONTMATTER FIELDS  (only these are valid)
  Required:
    description    : string — required for auto-routing
  Optional:
    name           : string — display name (defaults to filename)
    target         : "vscode" | "github-copilot" — defaults to both
    tools          : YAML list of tool names — defaults to all
                     ["*"] = all enabled, [] = all disabled
    model          : string — model id; inherits default if unset
    disable-model-invocation : boolean — default false; if true,
                               agent runs only when explicitly invoked
    user-invocable : boolean — default true
    mcp-servers    : object — MCP server configs (CLI only,
                     not VS Code/IDE agents)
    metadata       : object — name/value strings (CLI only)
  RETIRED — do NOT use:
    infer          : replaced by disable-model-invocation

  Do NOT add any other frontmatter field. Copilot CLI ignores them.

TOOL NAMES  (use these exact identifiers — NOT free-form names)
  Native tool aliases (case-insensitive):
    execute        : run shell commands  (alias: shell, Bash, powershell)
    read           : read files          (alias: Read, NotebookRead)
    edit           : edit/write files    (alias: Edit, MultiEdit, Write)
    search         : grep/glob           (alias: Grep, Glob)
    web            : URL/web search      (alias: WebSearch, WebFetch)
    todo           : task lists (VS Code only)
    agent          : invoke other agents (alias: custom-agent, Task)

  Out-of-the-box MCP servers (referenced as `server/tool` or `server/*`):
    github/*       : read-only GitHub tools (scoped to source repo)
    playwright/*   : browser automation (localhost only)

  Patterns:
    tools: ["*"]                           = all tools
    tools: []                              = no tools
    tools: ["read", "edit", "search"]      = specific native tools
    tools: ["github/*"]                    = all tools from a server
    tools: ["github/list_issues"]          = a specific MCP tool

KNOWLEDGE BASE
  Copilot CLI has NO native knowledge-base feature. The agent body
  is the only built-in instruction surface. We work around this by:
    1. Generating KB markdown files alongside the agent
    2. Telling the agent body (via instructions) to use the `read`
       tool to load those KB files on demand
    3. Using AGENTS.md ONLY for repo-wide custom instructions
       (NOT as an "agent registry" — that's not what AGENTS.md is)

AGENTS.md  (separate from custom agents — repo-wide instructions)
  - Lives at repo root or directories named in COPILOT_CUSTOM_INSTRUCTIONS_DIRS
  - Loaded for every Copilot session in the repo
  - We will append a small "Custom Agents" reference section to it
    (informational only — not a Copilot mechanism)

INVOCATION
  - Auto-inferred from description when prompt matches
  - Slash command in the CLI's interactive mode
  - Explicit: copilot --agent=[name] --prompt "..."

===================================================================


DECLARATION  (you fill this)
===================================================================

  AGENT
  -------------------------------------------------------------------
  name        →
                (lowercase-hyphenated; becomes filename:
                 .github/agents/[name].agent.md)
  role        →
                (one sentence; this is the seed for the description
                 frontmatter field)
  not_for     →
                (what it must never do — at least 3 lines;
                 these become the "Do NOT use for..." sentence in
                 the description)
  description →
                (optional override — if blank, generated from role +
                 not_for. Must include DOMAIN.display verbatim.)
  target      →
                (optional: "vscode" | "github-copilot" | both;
                 default = both)
  model       →
                (optional model id; "default" or omit to inherit)
  user_invocable →
                (true | false; default true)
  disable_model_invocation →
                (true | false; default false; set true if the agent
                 should run only when explicitly invoked)
  install_scope →
                (repo | user; default repo)

  tools       →
                (YAML list using EXACT Copilot CLI names from the
                 SPEC FACTS section above. Examples:
                   ["read", "edit", "search", "execute", "web"]
                   ["read", "search", "web", "github/*"]
                   ["*"]   for unrestricted
                   []      for no tools
                 Do NOT include "agent" unless this agent should
                 invoke other agents.)

  mcp_servers →
                (optional inline MCP server config — only if needed
                 beyond the built-in github/ and playwright/)

  DOMAIN
  -------------------------------------------------------------------
  primary   →  (DOMAIN_KEY — short, lowercase, hyphenated)
  display   →  (human-readable name)
  versions  →  (specific versions/products this agent reasons about
                — exhaustive; this is the allowlist for content)
  sources   →  (authoritative docs/specs/files — one per line)
                (URLs or local file paths; the agent FETCHES these
                 during generation to ground every concept/pattern)

  KB_DEPTH  →  minimal | standard | full

  CONCEPTS  →  one per line (skip if minimal)
                (each becomes knowledge/[primary]/concepts/[name].md)
                (every name MUST be domain-specific — if you can't
                 tell the domain from the name alone, rename it)

  PATTERNS  →  one per line (skip if minimal)
                (each becomes knowledge/[primary]/patterns/[name].md)

  SPECS     →  one per line (only if full)
                (machine-readable schemas/formats)

  SKILLS
  -------------------------------------------------------------------
  (one block per capability — these are NOT Copilot's "Agent Skills"
   feature; they are sections inside the agent body documenting what
   the agent can do)

    skill       → (verb_noun)
    trigger     → (phrase users say)
    does        → (concrete steps, including which knowledge files
                   to read via the `read` tool)
    output      → (file type / path / stdout)
    done_when   → (measurable completion criterion)
    fail_when   → (condition to FLAG instead of complete)
    test_case   → (input → expected output)

  ANTI_PATTERNS
  -------------------------------------------------------------------
  (one per line — each becomes a Wrong/Correct pair in
   knowledge/[primary]/anti-patterns.md)
  (every item MUST be specific to DOMAIN.primary)

  CONFIDENCE_THRESHOLD →
                (float 0.0-1.0, default 0.95)

  HANDOFF
  -------------------------------------------------------------------
  escalate_to →  (agent name or HUMAN)

===================================================================


GENERATION INSTRUCTIONS  (CLI executes in order)
===================================================================

Read each step fully before starting. Do not skip steps.
Re-read the HARD ANTI-SUBSTITUTION CONTRACT before each step.
Re-read the COPILOT CLI SPEC FACTS before STEP 1 and STEP 4.

Record today's date as VALIDATION_DATE (ISO 8601). Use it wherever
templates require {{VALIDATION_DATE}}.

Resolve the install path from DECLARATION.install_scope:
  - repo → AGENT_DIR = .github/agents/
  - user → AGENT_DIR = ~/.copilot/agents/
KB_DIR is always relative to repo root: knowledge/[primary]/

----------------------------------------------------------------
STEP 0 — DOMAIN GROUNDING  (mandatory before any file is written)
----------------------------------------------------------------

For each URL in DOMAIN.sources:
  - Fetch the page using the `web` tool
  - Extract canonical terminology, product names, current version
    numbers, primary capabilities
  - Save these facts to a working scratchpad

For each name in DOMAIN.versions:
  - Confirm it appears (or is consistent with) the fetched docs
  - If a version disagrees → use the fetched docs and lower
    confidence to 0.85 on affected files

If sources are unreachable:
  - Stop and report BLOCKED with the unreachable URLs
  - Do NOT proceed using training-data assumptions

This step is the gate. You may not generate concepts/patterns about
a domain you have not just read docs for.

----------------------------------------------------------------
STEP 1 — GENERATE [AGENT_DIR][name].agent.md
----------------------------------------------------------------

CRITICAL: extension is .agent.md (not .md). Body capped at 30,000
characters. Frontmatter fields limited to those listed in COPILOT
CLI SPEC FACTS — no custom fields.

  Frontmatter — emit only valid fields:

    ---
    name: [DECLARATION.name]
    description: |
      [3–5 sentences, see rules below]
    target: [DECLARATION.target — omit field if "both"]
    model: [DECLARATION.model — omit field if "default"]
    tools: [DECLARATION.tools as YAML list]
    user-invocable: [DECLARATION.user_invocable — omit if true]
    disable-model-invocation: [DECLARATION.disable_model_invocation
                               — omit if false]
    mcp-servers: [DECLARATION.mcp_servers — omit if none]
    ---

    Description rules:
      - Sentence 1: what the agent does — must include DOMAIN.display
      - Sentence 2: enumerate specific task types it handles
      - Sentence 3: trigger conditions ("Use when...")
      - Sentence 4: explicit exclusions ("Do NOT use for...")
      - Concrete trigger phrases users would type
      - Specific enough that auto-routing won't misfire
      - Keep description under 1,400 characters

  Body sections (MAX 30,000 CHARS — push detail to KB files):

      IDENTITY
        One paragraph: role, scope, what it never does. Include:
          "You do NOT inherit the calling conversation's history.
           Every invocation is a fresh context. The caller must
           pass task details, file paths, and constraints. Read
           files yourself with the read tool — do not assume they
           were already loaded."

      METADATA  (informational — Copilot ignores; for human readers)
        - kb_path:              knowledge/[primary]/
        - kb_index:             knowledge/[primary]/index.md
        - confidence_threshold: [CONFIDENCE_THRESHOLD]
        - last_validated:       [VALIDATION_DATE]
        - re_validate_after:    90 days
        - domain:               [DOMAIN.primary]

      KNOWLEDGE BASE PROTOCOL
        - On every invocation, use the `read` tool to load
          knowledge/[primary]/index.md FIRST
        - For each concept relevant to the task, `read` its file
          under knowledge/[primary]/concepts/
        - For each pattern to apply, `read` its file under
          knowledge/[primary]/patterns/
        - If KB content has last_validated older than 90 days OR
          confidence below threshold → use the `web` tool to fetch
          current state before proceeding
        - If KB has no entry → fetch from authoritative source,
          propose a new concept/pattern file, flag
          [NEEDS REVIEW: source unverified]

      EXECUTION RULES
        - read domain knowledge before acting
        - emit OUTPUT CONTRACT at end of every run
        - never commit, deploy, or call paid APIs without explicit
          confirmation
        - on confidence < threshold → status=FLAG, stop, escalate
        - preserve any [NEEDS REVIEW: ...] flags found
        - do not exceed scope defined in IDENTITY
        - when generating code, match patterns from
          knowledge/[primary]/patterns/ verbatim unless explicitly
          deviating (and document why)
        - if calling prompt is missing context → return
          status=BLOCKED with a specific request for what's missing

      SKILLS
        One block per skill from DECLARATION.SKILLS:
          - trigger phrase
          - action steps (with explicit `read` calls to KB files)
          - output path pattern
          - done_when criterion
          - fail_when criterion
          - test_case reference

      INVOCATION TEMPLATE  (for callers)
        When invoking [name], the caller MUST include:
          1. Task statement (one sentence)
          2. Target file paths (absolute paths)
          3. Constraints carried from prior context
          4. Expected output format
          5. Any [NEEDS REVIEW: ...] flags from prior turns

      ANTI_PATTERNS
        Full list from DECLARATION.ANTI_PATTERNS.
        Instruction: "Flag any of the following on sight. For each,
        `read` knowledge/[primary]/anti-patterns.md for the
        Wrong/Correct pair."

      OUTPUT CONTRACT
        Emit at the end of every run:
          status              → DONE | BLOCKED | FLAG
          confidence          → float 0.0-1.0
          confidence_rationale → why this level
          kb_files_consulted  → list of KB files read
          web_calls_made      → list of fetches
          findings[]
            type              → derive from domain
            severity          → CRITICAL | WARN | INFO
            target            → file:line or concept name
            message           → plain text
          artifacts[]         → file paths produced
          needs_review[]      → flagged items
          handoff_to          → [escalate_to] or HUMAN
          handoff_reason      → populated when status != DONE

  If body exceeds 30,000 chars: move SKILLS detail and ANTI_PATTERNS
  list into knowledge/[primary]/ and reference them with `read`
  instructions instead. Keep IDENTITY, METADATA, KNOWLEDGE BASE
  PROTOCOL, EXECUTION RULES, OUTPUT CONTRACT, and INVOCATION
  TEMPLATE in the body — those are core behavior.

----------------------------------------------------------------
STEP 2 — GENERATE knowledge/[primary]/
----------------------------------------------------------------

Use DOMAIN-SPECIFIC content sourced from STEP 0. No substitutions.

  ALL DEPTHS — required:

    knowledge/[primary]/index.md
      - Quick Navigation table linking every concept/pattern
      - Key Concepts table (2–5 rows)
      - Learning Path (Beginner / Intermediate / Advanced)
      - Stamp {{VALIDATION_DATE}}

    knowledge/[primary]/quick-reference.md
      - Decision Matrix (when to use what)
      - Common Pitfalls (Don't / Do table)
      - Sections matching DECLARATION.CONCEPTS

    knowledge/[primary]/_manifest.yaml
      - Lists every concept, pattern, spec with paths and confidence
      - Confidence default 0.95; lower if web validation conflicted
        with training data

    knowledge/[primary]/anti-patterns.md
      - One section per item in DECLARATION.ANTI_PATTERNS:
        - Wrong code/config block
        - Why it's wrong (1–2 sentences, domain-specific)
        - Correct alternative
        - Link to related concept/pattern

  KB_DEPTH = minimal — additionally:

    knowledge/[primary]/[primary].md
      - Single consolidated file (overview + key concepts +
        web-lookup fallback instructions)
      - Under 300 lines

  KB_DEPTH = standard OR full — additionally:

    knowledge/[primary]/concepts/[concept].md  per CONCEPTS
      - Purpose, confidence, validation date
      - Code example 10–30 lines (in DOMAIN's language/format)
      - Quick Reference table
      - Common Mistakes (Wrong / Correct pair)
      - Related links
      - Under 150 lines each

    knowledge/[primary]/patterns/[pattern].md  per PATTERNS
      - When to Use (3+ bullets)
      - Implementation (30–100 lines, production-ready)
      - Configuration table
      - Example Usage
      - See Also
      - Under 200 lines each

  KB_DEPTH = full — additionally:

    knowledge/[primary]/specs/[spec].yaml  per SPECS
    knowledge/[primary]/examples/inputs/
    knowledge/[primary]/examples/outputs/
    knowledge/[primary]/examples/tests/[skill].json  per skill

  WEB VALIDATION DURING GENERATION:
    For every knowledge file:
      - Fetch the relevant URL from DOMAIN.sources before writing
      - If fetched content disagrees with training → use fetched
        version, lower confidence to 0.85
      - If unreachable → write with confidence 0.90 plus
        [NEEDS REVIEW: web validation failed, verify against {{source}}]
      - Stamp {{VALIDATION_DATE}}

----------------------------------------------------------------
STEP 3 — APPEND TO AGENTS.md  (informational only)
----------------------------------------------------------------

AGENTS.md is Copilot's repo-wide custom-instructions file — NOT an
agent registry. We append a small reference section so humans
browsing the repo can find available custom agents.

  Open AGENTS.md at repo root (create if missing). Append (do not
  modify or remove existing content):

    ## Custom Agents

    Custom Copilot CLI agents in this repo. Invoke with
    `copilot --agent=[name]` or via slash command in interactive mode.

    | Agent | Domain | Use For | Do NOT Use For | KB |
    |-------|--------|---------|----------------|------|
    | [name] | [DOMAIN.display] | [use-when] | [do-not-use-when] | knowledge/[primary]/ |

    Last updated: {{VALIDATION_DATE}}

  If a row for [name] already exists, update it in place. Otherwise
  append a new row.

  Rules when writing to AGENTS.md:
    - never delete existing content
    - never modify sections marked [DECISION RECORD]
    - if outdated but unverifiable → insert [NEEDS REVIEW: ...]
    - produce a diff of every change
    - require explicit "confirmed" before writing

----------------------------------------------------------------
STEP 4 — SMOKE TEST
----------------------------------------------------------------

The agent is not done until tests pass.

  Test 1 — File structure
    REQUIRED:
      [AGENT_DIR][name].agent.md   (extension MUST be .agent.md)
      knowledge/[primary]/index.md
      knowledge/[primary]/quick-reference.md
      knowledge/[primary]/_manifest.yaml
      knowledge/[primary]/anti-patterns.md

    minimal:  + knowledge/[primary]/[primary].md
    standard: + concepts/*.md, patterns/*.md (one per declared name)
    full:     + specs/*.yaml, examples/tests/*.json

    Fail if any file is missing, empty, or has the wrong extension.

  Test 2 — Frontmatter validity (Copilot CLI spec)
    Read [AGENT_DIR][name].agent.md.
    - Frontmatter must be parseable YAML
    - description is present and under 1,400 chars
    - description is 3+ sentences and includes DOMAIN.display
    - Every frontmatter field is in this allowlist:
        name, description, target, tools, model,
        disable-model-invocation, user-invocable,
        mcp-servers, metadata
    - FAIL if any other field present (Copilot ignores them and
      they signal the generator drifted from the spec)
    - tools is a YAML list — not a string, not space-separated
    - Every tool name in `tools` is one of:
        execute, read, edit, search, web, todo, agent, *
        OR matches pattern "server/tool" or "server/*"
    - Body is under 30,000 characters
    - Body contains METADATA, KNOWLEDGE BASE PROTOCOL, EXECUTION
      RULES, OUTPUT CONTRACT, INVOCATION TEMPLATE sections

  Test 3 — Domain fidelity check  (CRITICAL — catches substitution)
    For every file in knowledge/[primary]/concepts/ and patterns/:
      - Confirm filename matches a name in DECLARATION.CONCEPTS or
        DECLARATION.PATTERNS verbatim. If a file exists that was
        NOT in the declaration → DELETE it and report violation.
      - grep file for forbidden tokens UNLESS they appear in
        DOMAIN.versions or DOMAIN.sources:
          "tenacity", "instructor", "langchain", "llama-index"
      - If forbidden tokens found → file is substituted content,
        DELETE and regenerate after re-fetching the source URL.

    For every name in DECLARATION.CONCEPTS and DECLARATION.PATTERNS:
      - Confirm the corresponding file exists.
      - If missing → generate it (after fetching source).

  Test 4 — Cross-reference check
    For each concepts/*.md and patterns/*.md:
      - grep for links to other knowledge/ files
      - confirm every linked file exists
    For every entry in _manifest.yaml:
      - confirm the file exists
      - confirm it has {{VALIDATION_DATE}} filled (no unfilled
        {{...}} placeholders remain)

  Test 5 — Anti-pattern coverage
    For each item in DECLARATION.ANTI_PATTERNS:
      - confirm it appears in anti-patterns.md
      - confirm Wrong + Correct code blocks both present
      - confirm example code is in the DOMAIN's language/syntax

  Test 6 — Routing accuracy
    Construct 3 prompts that SHOULD route to this agent.
    Construct 3 prompts that should NOT route to this agent.
    Verify description's "Use when..." matches the first set.
    Verify "Do NOT use for..." excludes the second set.

  Test 7 — Tool list validity
    Re-read DECLARATION.tools.
    For each entry, confirm it matches the Copilot CLI tool name
    spec (allowlist or server/tool pattern).
    If any free-form name (e.g. "read_file", "web_fetch",
    "run_shell") slipped through → FAIL and remap to the spec name:
      read_file  → read
      write_file → edit
      edit_file  → edit
      run_shell  → execute
      grep       → search
      glob       → search
      web_fetch  → web
      web_search → web

  Test 8 — Body size
    [AGENT_DIR][name].agent.md body (after frontmatter) is under
    30,000 characters. If over, move detail into knowledge/ files
    and reference via `read`.

----------------------------------------------------------------
STEP 5 — VALIDATION REPORT
----------------------------------------------------------------

After all tests pass:

  AGENT CREATION REPORT
  -------------------------------------------------------------------
  agent                → [name]
  install_path         → [AGENT_DIR][name].agent.md
  domain               → [DOMAIN.primary] / [DOMAIN.display]
  kb_depth             → [KB_DEPTH]
  validation_date      → [VALIDATION_DATE]
  files_created        → list every file written
  kb_coverage          → concepts: N/N | patterns: N/N | specs: N/N
  body_size_chars      → actual body length / 30,000
  web_validations      → list of URLs fetched during generation
  substitutions_caught → files deleted/regenerated due to Test 3
                         (should be zero on a clean run)
  tool_remappings      → free-form names corrected to spec names
                         (should be zero — declaration should use
                         spec names from the start)
  tests_passed         → Test 1..8 results
  tests_fixed          → tests that required iteration + what changed
  confidence_summary   → average confidence across knowledge files
  needs_review_items   → every [NEEDS REVIEW: ...] flag emitted
  routing_notes        → notes on description tuning
  known_gaps           → unvalidated sources, thin patterns,
                         unreachable URLs

  HOW TO USE THE AGENT
    Auto-routing:    just describe a task that matches the
                     description; Copilot may pick this agent.
    Slash command:   /agents in interactive mode → select [name]
    Explicit:        copilot --agent=[name] --prompt "..."

  recommended_next_steps →
    - verify knowledge files against latest [DOMAIN.versions] docs
    - test agent invocation with: copilot --agent=[name] --prompt
      "<a real task in the codebase>"
    - tighten routing description after first 5 real invocations
    - re-run web validation every 90 days
    - if substitutions_caught > 0: review the source URL for that
      concept and confirm it's reachable, then regenerate
    - if body_size_chars > 25,000: proactively move detail to
      knowledge/ before hitting the 30,000 hard cap

  Wait for human review before closing.
  Do not auto-commit. Do not delete generated files (except those
  caught by Test 3 substitution check).

===================================================================
