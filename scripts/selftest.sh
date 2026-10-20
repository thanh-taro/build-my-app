#!/usr/bin/env bash
# Self-test: exercises the state CLI, every hook, and the project template in a scratch dir.
# Usage: scripts/selftest.sh [scratch-dir]
set -u
P="$(cd "$(dirname "$0")/.." && pwd)"
T="${1:-$(mktemp -d)}"; rm -rf "$T"; mkdir -p "$T"; cd "$T"
export CLAUDE_PROJECT_DIR="$T"
S() { python3 "$P/scripts/bma_state.py" "$@"; }
hook() { python3 "$P/hooks/$1.py"; }

echo "== 1. hooks outside a bma project (expect nothing)"
echo '{"prompt":"F-001","tool_input":{"command":"git push --force"}}' | hook session_start
echo '{"tool_input":{"command":"git push --force"}}' | hook pre_bash_guard
echo '{}' | hook stop_check
echo "(end)"

echo "== 2. init + template + lint on empty spec tree"
S init
cp -R "$P/templates/project/tools" ./tools; cp -R "$P/templates/project/specs" ./specs
python3 tools/spec_lint.py; echo "lint exit=$?"

echo "== 3. state machine"
S next
S phase product-spec in_progress; echo "(expected refusal above) exit=$?"
S phase setup in_progress --step "profiling"
S decide add "Which platform first?" --options "iOS|Web" --recommend iOS --kind product
S next
S decide answer D-001 iOS
S phase setup gate; S next
S gate setup pass --note ok; S next
S phase product-spec in_progress
S loop start spec-review --max 2; S loop next spec-review; S loop next spec-review; echo "loop limit exit=$?"
S status

echo "== 4. hooks inside the project"
echo '{"source":"startup"}' | hook session_start; echo
echo "{\"tool_input\":{\"file_path\":\"$T/.build-my-app/state.json\"}}" | hook pre_edit_guard; echo
printf '// GENERATED FROM specs/30-experience/tokens.json\nlet x = 1\n' > gen.swift
echo "{\"tool_input\":{\"file_path\":\"$T/gen.swift\"}}" | hook pre_edit_guard; echo
echo '{"tool_input":{"command":"rm -rf ~"}}' | hook pre_bash_guard; echo
echo '{"tool_input":{"command":"git push --force origin main"}}' | hook pre_bash_guard; echo
echo '{"tool_input":{"command":"npm install left-pad@1.3.0 --save"}}' | hook pre_bash_guard; echo
mkdir -p specs/40-technical; echo "| **DEP-01** | left-pad | MIT |" > specs/40-technical/dependencies.md
echo '{"tool_input":{"command":"npm install left-pad"}}' | hook pre_bash_guard; echo "(registered → nothing above)"
echo '{"stop_hook_active":false}' | hook stop_check; echo
echo '{"trigger":"auto"}' | hook pre_compact; S get log | tail -4

echo "== 5. spec lint hook + spec-id hook"
mkdir -p specs/20-features
printf -- '---\nid: F-001\ntitle: Bad\nstatus: draft\nmilestone: M-1\npriority: P0\n---\n- **R1** uses RULE-99\n- **AC1** Given x, when y, then z. (R1)\n' > specs/20-features/F-001-bad.md
echo "{\"tool_input\":{\"file_path\":\"$T/specs/20-features/F-001-bad.md\"}}" | hook post_edit_lint; echo "post_edit_lint exit=$?"
echo '{"prompt":"implement F-001 and see F-001.R1 in F-001-bad.md"}' | hook prompt_spec_ids; echo
