#!/usr/bin/env bash
# Bootstrap a new agent skeleton (without running the generator).
# Use this when you know the agent's name + domain and want stubs in place
# before pasting the AGENT_CREATION_PROMPT into Copilot.
#
# Usage: scripts/new_agent.sh <agent-name> <domain> "<short description>"
# Example: scripts/new_agent.sh kql-specialist kql "KQL query builder for Azure Monitor"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ $# -lt 3 ]]; then
    cat <<EOF
Usage: $0 <agent-name> <domain> "<short description>"

  agent-name     lowercase-hyphenated; becomes filename
  domain         lowercase-hyphenated; becomes knowledge/<domain>/
  description    one-line summary for plugin manifest

Example:
  $0 kql-specialist kql "KQL query builder for Azure Monitor"
EOF
    exit 1
fi

NAME="$1"
DOMAIN="$2"
DESC="$3"

AGENT_FILE="$REPO_ROOT/agents/${NAME}.agent.md"
KB_DIR="$REPO_ROOT/knowledge/$DOMAIN"
PLUGIN_DIR="$REPO_ROOT/plugins/$NAME"

if [[ -e "$AGENT_FILE" ]]; then
    echo "ERROR: $AGENT_FILE already exists"
    exit 1
fi

# Stub agent file
cat > "$AGENT_FILE" <<EOF
---
name: $NAME
description: |
  $DESC

  [Replace this with a 3–5 sentence description following CONTRIBUTING.md.]

  Use when ...
  Do NOT use for ...
tools: ["read", "search", "web"]
---

# $NAME

[STUB — generate this agent body using \`_templates/AGENT_CREATION_PROMPT_COPILOT.md\`.]

## Metadata

- kb_path: \`knowledge/$DOMAIN/\`
- kb_index: \`knowledge/$DOMAIN/index.md\`
- confidence_threshold: 0.90
- last_validated: $(date +%Y-%m-%d)
- re_validate_after: 90 days
- domain: $DOMAIN
EOF

# Stub KB
mkdir -p "$KB_DIR/concepts" "$KB_DIR/patterns"
cat > "$KB_DIR/index.md" <<EOF
# $DOMAIN Knowledge Base

> Generated: $(date +%Y-%m-%d)
> Status: STUB

[Run the agent generator to populate.]
EOF
cat > "$KB_DIR/_manifest.yaml" <<EOF
domain: $DOMAIN
last_validated: $(date +%Y-%m-%d)
concepts: []
patterns: []
EOF
touch "$KB_DIR/quick-reference.md" "$KB_DIR/anti-patterns.md"

# Stub plugin manifest
mkdir -p "$PLUGIN_DIR"
cat > "$PLUGIN_DIR/plugin.yaml" <<EOF
name: $NAME
version: 0.1.0
description: |
  $DESC
author: datageek
license: MIT
homepage: https://github.com/datageek/copilot-collection
repository: https://github.com/datageek/copilot-collection
tags:
  - $DOMAIN
agent: ../../agents/${NAME}.agent.md
knowledge:
  - ../../knowledge/$DOMAIN/
EOF

echo "Created stubs:"
echo "  $AGENT_FILE"
echo "  $KB_DIR/"
echo "  $PLUGIN_DIR/plugin.yaml"
echo
echo "Next: open _templates/AGENT_CREATION_PROMPT_COPILOT.md, fill the"
echo "DECLARATION block for '$NAME', and run it in Copilot CLI to populate"
echo "the KB and finalize the agent body."
