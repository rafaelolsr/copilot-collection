<!-- Thanks for contributing! -->

## What this PR does

<!-- One sentence summary -->

## Type

- [ ] New agent
- [ ] Update existing agent
- [ ] New KB / KB update
- [ ] Plugin manifest
- [ ] Tooling / scripts
- [ ] Docs

## Checklist (for new/updated agents)

- [ ] `scripts/validate.sh` passes locally
- [ ] Frontmatter uses ONLY spec-allowed fields (`name`, `description`, `target`, `tools`, `model`, `disable-model-invocation`, `user-invocable`, `mcp-servers`, `metadata`)
- [ ] `description` is under 1,400 chars
- [ ] Body is under 30,000 chars
- [ ] No auto-link corruption (`grep '\](http' agents/<name>.agent.md` inside code blocks returns 0)
- [ ] Tool names are from the official allowlist (`read`, `edit`, `search`, `execute`, `web`, `todo`, `agent`, or `server/tool`)
- [ ] KB directory exists at `knowledge/<domain>/` with `index.md`, `quick-reference.md`, `_manifest.yaml`, `anti-patterns.md`
- [ ] Plugin manifest at `plugins/<name>/plugin.yaml` exists and references the agent + KB
- [ ] Sources for KB content are listed in the PR body (URLs that grounded the generation)

## KB sources

<!-- List the URLs you (or the generator) fetched to ground the KB content. -->

-
-
-

## Testing

<!-- How you verified the agent works. Sample invocations + outputs are great. -->
