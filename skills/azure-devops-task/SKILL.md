---
name: azure-devops-task
description: |
  Creates Azure DevOps Task work items from a request, plan, or implementation
  breakdown using Azure Boards best practices. Produces small sprint-scoped
  child tasks with title, description, estimates, activity, tags, links, and
  a task-level done checklist. Uses Azure DevOps MCP tools when available.

  Use when the user says: "Create a Task", "create an Azure DevOps task",
  "create tasks for this plan", "turn this plan into ADO tasks", "split this
  into Azure Boards tasks", or similar task-creation prompts.

  Do NOT use for: creating a feature spec, writing an implementation plan,
  generic TODO lists outside Azure DevOps, or pipeline/YAML work items.
license: MIT
---

# Azure DevOps Task

Creates Azure Boards `Task` work items that are ready for sprint execution.
The skill converts a user request or plan into small, verifiable, linked child
tasks and creates them through Azure DevOps MCP tools when those tools are
available.

## When to use

YES:
- The user asks to create one Azure DevOps Task.
- The user asks to create tasks from a plan, phase list, feature breakdown, or
  implementation notes.
- The user asks to split work into Azure Boards tasks under a PBI, User Story,
  Bug, or Feature.

NO:
- The user wants a plan but not Azure DevOps work items; use `make-plan`.
- The user wants requirements/specification; use `spec-driven`.
- The user wants pipeline configuration or Azure DevOps automation code; use
  the Azure DevOps specialist/instructions instead.

## Non-negotiable rule: parent PBI

Every task must have a known parent backlog item before creation.

If the PBI, User Story, Bug, or parent work item is unknown, STOP and ask:

```text
Which Azure DevOps PBI/User Story/Bug should these tasks be created under?
Please provide the work item ID or URL.
```

Do not create orphan tasks. Do not guess the parent from titles, branch names,
or local files.

## Workflow

### Step 1 - Extract the work

Identify whether the user wants:
1. A single task.
2. Multiple tasks from a plan or breakdown.
3. A draft payload only, not creation.

For a plan, map phases/steps into execution tasks. Prefer one task per coherent
deliverable, not one task per sentence. Split any task that is likely to exceed
one working day.

### Step 2 - Confirm required Azure DevOps context

Before creating anything, determine:
- Organization / collection.
- Project.
- Parent PBI/User Story/Bug/Feature work item ID or URL.
- Area Path.
- Iteration Path.
- Assignee, if known.

Use Azure DevOps MCP tools to fetch the parent work item when available. Inherit
Area Path and Iteration Path from the parent unless the user specifies
otherwise.

Ask the user only for missing required context. The parent work item is always
required. Area Path and Iteration Path can be inherited from the parent when
available.

### Step 3 - Decompose into task candidates

For each candidate task:
- Keep it small enough to complete within a day.
- Start the title with a verb.
- Make the scope concrete and testable.
- Put customer-facing acceptance criteria on the parent PBI, not on each task.
- Put implementation-specific completion checks in the task's `Done when`
  checklist.
- Link dependencies explicitly instead of hiding blockers in comments.

### Step 4 - Build each Task payload

Use this field mapping:

| Azure DevOps field | Value |
|---|---|
| `System.WorkItemType` | `Task` |
| `System.Title` | `<Verb> <specific deliverable> for <scope>` |
| `System.Parent` / relation | Parent PBI/User Story/Bug/Feature ID |
| `System.Description` | Description template below |
| `System.AreaPath` | Parent Area Path unless overridden |
| `System.IterationPath` | Parent Iteration Path unless overridden |
| `System.AssignedTo` | User-specified assignee, otherwise leave unassigned |
| `Microsoft.VSTS.Common.Activity` | Development, Testing, Design, Documentation, Review, or Deployment |
| `Microsoft.VSTS.Scheduling.OriginalEstimate` | Initial estimate in hours, when known |
| `Microsoft.VSTS.Scheduling.RemainingWork` | Same as original estimate at creation, when known |
| `System.Tags` | Standardized, comma-separated tags |

Recommended defaults:
- Activity: infer from the task; otherwise `Development`.
- Estimate: use the user's estimate when provided; otherwise omit rather than
  inventing precision.
- Tags: include only useful standardized tags such as `backend`, `frontend`,
  `api`, `testing`, `documentation`, `security`, or `infra`.

### Step 5 - Create through MCP

When Azure DevOps MCP tools are available:
1. Fetch the parent work item to verify it exists.
2. Read its title, state, Area Path, and Iteration Path.
3. Check existing child tasks when practical to avoid obvious duplicates.
4. Create each Task with a parent-child relation.
5. Return the created work item IDs and URLs.

If MCP tools are unavailable, credentials are missing, or the project cannot be
resolved, do not pretend creation succeeded. Output the ready-to-create payloads
and state exactly what is missing.

### Step 6 - Report the result

After creation, summarize the created tasks in a table. Include blockers or
skipped items separately.

## Description template

Use this exact shape for `System.Description` unless the project has a stronger
local convention:

```markdown
## Context

<Why this task exists and which parent work item it supports.>

## Scope

<What must be changed, produced, reviewed, or tested.>

## Done when

- [ ] <Specific verifiable outcome 1>
- [ ] <Specific verifiable outcome 2>
- [ ] Tests, review, documentation, or release notes updated if applicable
- [ ] Pull request, commit, or evidence linked if applicable

## Out of scope

<What this task should not cover.>

## References

- Parent work item: #<id>
- Related plan/spec/design: <link or "none">
- Dependency/blocker: #<id or "none">
```

## Output format

When tasks are created:

```markdown
Created <N> Azure DevOps Task(s) under <ParentType> #<id>.

| ID | Title | Activity | Estimate | URL |
|---|---|---:|---:|---|
| <id> | <title> | <activity> | <hours or -> | <url> |
```

When creation is blocked:

```markdown
I cannot create the Azure DevOps Task(s) yet because <missing context>.

Please provide:
- Parent PBI/User Story/Bug ID or URL
- <other missing required context>
```

When outputting a draft payload:

```markdown
Draft Azure DevOps Task payloads for parent #<id>:

## Task 1 - <title>

Fields:
- Area Path: <value>
- Iteration Path: <value>
- Activity: <value>
- Original Estimate: <value or omitted>
- Remaining Work: <value or omitted>
- Tags: <value or omitted>

Description:
<description template filled in>
```

## Anti-patterns

Avoid:
1. Creating orphan tasks without a parent PBI/User Story/Bug/Feature.
2. Creating huge tasks such as "Implement the feature"; split them.
3. Duplicating the parent acceptance criteria into every task.
4. Inventing estimates when no estimate basis exists.
5. Using comments as dependency tracking instead of Azure DevOps links.
6. Creating tasks with vague titles such as "Fix stuff" or "Update code".
7. Claiming MCP creation succeeded when only a draft payload was produced.

## Configuration

Users can include these parameters in the prompt:

| Parameter | Default | Effect |
|---|---|---|
| `parent` / `pbi` | required | Parent work item ID or URL |
| `project` | MCP/project context | Azure DevOps project |
| `area` | parent Area Path | Overrides inherited Area Path |
| `iteration` | parent Iteration Path | Overrides inherited Iteration Path |
| `assignee` | unassigned | Sets `System.AssignedTo` |
| `estimate_unit` | hours | Unit for Original Estimate and Remaining Work |
| `mode` | create | Use `draft` to output payloads without creating |
| `max_task_size` | 1 day | Split work larger than this |

## See also

- `make-plan` skill - create the implementation plan before generating tasks.
- `spec-driven` skill - capture feature requirements before planning.
- `azure-devops-specialist` agent - deeper Azure DevOps automation and API work.
