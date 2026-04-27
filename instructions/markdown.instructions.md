---
name: markdown
description: |
  Coding standards for markdown content (docs, READMEs, ADRs, KB files).
  Auto-applied to .md files. Enforces clear structure, consistent
  punctuation, working links, semantic headings, and no markdown
  rendering pitfalls.
applyTo: "**/*.md,**/*.mdx"
---

# Markdown standards

When generating or modifying markdown in this project, follow these rules.

## Structure

- **One H1 per file** (`# Title`). Subsequent sections use H2 (`##`) and below.
- Heading hierarchy is strict — don't skip levels (no `##` then `####`).
- Front-matter when applicable: `---\n...\n---` at the top, no blank line between
  the closing `---` and the first content line.
- Files >300 lines: add a `## Table of Contents` near the top with anchor links.

## Headings

- Use **sentence case** (`## Configuration options`), not Title Case.
- Avoid trailing punctuation in headings (no `?` `.` `!`).
- Each heading describes the section's content — no clickbait, no marketing.

## Lists

- Use `-` for bullets, not `*` or `+` (consistency).
- `1.` for ordered lists; tooling auto-numbers.
- One blank line before and after the list.
- Nested lists: indent with 2 spaces.

## Links

- Inline: `[text](url)` — preferred for one-off references.
- Reference-style: `[text][ref]` + `[ref]: url` at file end — use when the same
  URL appears 3+ times.
- Internal cross-refs: relative paths (`../skills/simplify/SKILL.md`), not
  absolute URLs.
- NEVER `[Click here](url)` — link text describes the destination.
- Auto-link corruption: code blocks must NOT contain `](http://...)` patterns
  (a common formatting bug from chat editors). When you see them in code:
  remove the bracket-link wrapping, keep the original literal.

## Code blocks

- Always specify language for syntax highlighting:
  ````markdown
  ```python
  def hello(): ...
  ```
  ````
- Languages: `python`, `bash`, `yaml`, `json`, `typescript`, `dax`, `kusto`,
  `tmdl`, `bicep`, `csharp`, etc.
- Use `text` for non-code (logs, diagrams) — not the empty backticks.
- Inline code with single backticks: `` `variable_name` ``.
- For terminal sessions, prefix lines with `$ ` consistently.

## Emphasis

- **Bold** (`**text**`) for must-know information; sparingly.
- *Italic* (`*text*`) for emphasis or first introduction of a term.
- Never combine: don't `***both***`.
- Don't bold whole paragraphs — defeats the point.

## Tables

- Use markdown tables (not HTML) when the table fits the constraints.
- Align with explicit column markers: `|---|---|---|`.
- Left-align text columns, right-align numeric columns: `|---:|`.
- Tables with 4+ columns AND 5+ rows: consider HTML rendering or split.

## Images

- `![alt text](path)` — alt text is required for accessibility.
- Relative paths preferred (`assets/banner.png`), not absolute URLs.
- For dark/light theme awareness:
  ```markdown
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark.png" />
    <img src="assets/banner-light.png" alt="..." />
  </picture>
  ```

## Whitespace

- LF line endings (not CRLF). Enforce in `.gitattributes`:
  ```
  *.md text eol=lf
  ```
- No trailing whitespace.
- Single blank line between sections, never two.
- File ends with a single newline character.

## Front-matter

When using YAML front-matter (instructions, skills, workflows):

```yaml
---
name: kebab-case-name
description: |
  Multi-line description.
  Continues on the next line.
field: value
---
```

- Always quoted strings if they contain `:` or `#`.
- Lists: `- item` style or inline `[a, b, c]`.
- Block scalars (`|` or `>`) preferred for multi-line text.

## Anti-patterns to flag

| Pattern | Issue |
|---|---|
| `[Click here](url)` | Link text doesn't describe destination |
| `# Title` followed by `### Section` | Heading hierarchy skipped H2 |
| Code block without language | Loses syntax highlighting |
| Nested code fences `` ``` `` `` ``` `` | Markdown renders incorrectly; use 4+ backticks for outer fence |
| `<br>` | HTML in markdown; use blank line instead |
| Trailing whitespace at line end | Hard to spot, breaks diffs |
| `[link]( url)` (space after `(`) | Most parsers reject; some render literally |
| Tables with wildly different column widths | Hard to read; align or split |
| Heading + immediate text without blank line | Some parsers fail to render heading |

## Long-form content

For docs/specs/RFCs longer than ~500 lines:

- Mandatory ToC with anchor links
- Each major section gets a one-paragraph summary at the top
- Examples > prose where possible
- "Related" section at the end linking to siblings

## See also

- `instructions/agent-md.instructions.md` — for `.agent.md` files specifically
- `instructions/skill-md.instructions.md` — for `SKILL.md` files specifically
