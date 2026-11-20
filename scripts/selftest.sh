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
echo '{"tool_input":{"command":"vercel --prod"}}' | hook pre_bash_guard; echo "(deploy before phase 7 → deny)"
echo '{"tool_input":{"command":"npm run dev"}}' | hook pre_bash_guard; echo "(local dev → nothing)"
echo '{"tool_input":{"command":"npm install left-pad@1.3.0 --save"}}' | hook pre_bash_guard; echo
mkdir -p specs/40-technical; echo "| **DEP-01** | left-pad | MIT |" > specs/40-technical/dependencies.md
echo '{"tool_input":{"command":"npm install left-pad"}}' | hook pre_bash_guard; echo "(registered → nothing above)"
echo '{"stop_hook_active":false}' | hook stop_check; echo
echo '{"trigger":"auto"}' | hook pre_compact; S get log | tail -4

echo "== 5. resource budget + heavy-run wrapper"
S resources; S resources --workers 1 --slots 1
python3 "$P/scripts/bma_heavy.py" --label selftest -- 'echo "workers=$BMA_TEST_WORKERS"'
python3 "$P/scripts/bma_heavy.py" -- sleep 2 & sleep 0.5
python3 "$P/scripts/bma_heavy.py" -- echo "(ran after the first run released its slot)"; wait
python3 "$P/scripts/bma_heavy.py" -- false; echo "exit code passed through=$? (expect 1)"
echo '{"tool_input":{"command":"cd app && npm test"}}' | hook pre_bash_guard; echo "(unwrapped test run → deny)"
echo '{"tool_input":{"command":"npx jest --watch"}}' | hook pre_bash_guard; echo "(watch mode → deny)"
echo "{\"tool_input\":{\"command\":\"python3 $P/scripts/bma_heavy.py -- 'npm test'\"}}" | hook pre_bash_guard; echo "(wrapped → nothing)"
S set enforce_heavy false >/dev/null
echo '{"tool_input":{"command":"npm test"}}' | hook pre_bash_guard; echo "(enforcement off → nothing)"
S set enforce_heavy true >/dev/null

echo "== 6. spec lint hook + spec-id hook"
mkdir -p specs/20-features
printf -- '---\nid: F-001\ntitle: Bad\nstatus: draft\nmilestone: M-1\npriority: P0\n---\n- **R1** uses RULE-99\n- **AC1** Given x, when y, then z. (R1)\n' > specs/20-features/F-001-bad.md
echo "{\"tool_input\":{\"file_path\":\"$T/specs/20-features/F-001-bad.md\"}}" | hook post_edit_lint; echo "post_edit_lint exit=$?"
echo '{"prompt":"implement F-001 and see F-001.R1 in F-001-bad.md"}' | hook prompt_spec_ids; echo

echo "== 7. web UI: server, event hook, heavy-run events"
H() { printf '%s' "$1" | hook ui_events; }
H '{"hook_event_name":"SubagentStart","agent_id":"a1","agent_type":"build-my-app:feature-builder"}'
ls .build-my-app/tmp/ui/events.jsonl 2>/dev/null || echo "(UI off → no event log)"
python3 "$P/scripts/bma_ui.py" start --port 7399
python3 "$P/scripts/bma_ui.py" status
H '{"hook_event_name":"UserPromptSubmit","prompt":"build F-001"}'
H '{"hook_event_name":"PreToolUse","tool_name":"Agent","tool_input":{"subagent_type":"build-my-app:feature-builder","description":"Implement F-001"},"tool_use_id":"t1"}'
H '{"hook_event_name":"SubagentStart","agent_id":"a1","agent_type":"build-my-app:feature-builder"}'
H '{"hook_event_name":"PreToolUse","agent_id":"a1","agent_type":"build-my-app:feature-builder","tool_name":"Bash","tool_input":{"command":"python3 x/bma_heavy.py --label F-001 -- true"}}'
python3 "$P/scripts/bma_heavy.py" --label F-001 -- true
H '{"hook_event_name":"SubagentStop","agent_id":"a1","agent_type":"build-my-app:feature-builder","last_assistant_message":"F-001 done: 4 tests pass."}'
sleep 1
python3 - <<'PY'
import json, urllib.request, urllib.error
i = json.load(open(".build-my-app/tmp/ui/ui.json"))
base = f"http://127.0.0.1:{i['port']}"
d = json.load(urllib.request.urlopen(f"{base}/api/snapshot?token={i['token']}"))
print("phase:", d["state"]["current"], "| agents:", [(a["type"], a["status"], a["result"]) for a in d["agents"]])
print("feed:", [f["who"] for f in d["feed"]])
for name, url, headers in (("no token", f"{base}/api/snapshot", {}),
                           ("wrong host", f"{base}/api/snapshot?token={i['token']}", {"Host": "evil.test"})):
    try:
        urllib.request.urlopen(urllib.request.Request(url, headers=headers)); print(name, "→ 200 (BAD)")
    except urllib.error.HTTPError as e:
        print(name, "→", e.code)
PY
python3 "$P/scripts/bma_ui.py" stop
ls .build-my-app/tmp/ui/ui.json 2>/dev/null || echo "(ui.json removed → hooks idle again)"

echo "== 8. web chat: bridge (channel MCP server) ↔ page"
python3 "$P/scripts/bma_ui.py" start --port 7399 | tail -2
python3 - "$P" <<'PY'
import json, os, subprocess, sys, threading, time, urllib.request, urllib.error
P = sys.argv[1]
i = json.load(open(".build-my-app/tmp/ui/ui.json")); base = f"http://127.0.0.1:{i['port']}"
def post(text, **h):
    hdr = {"Content-Type": "application/json", "X-Token": i["token"], **h}
    try:
        return urllib.request.urlopen(urllib.request.Request(f"{base}/api/chat", data=json.dumps({"text": text}).encode(), headers=hdr)).status
    except urllib.error.HTTPError as e:
        return e.code
print("send with no chat session →", post("hi"), "(expect 409)")
off = subprocess.run([sys.executable, f"{P}/scripts/bma_channel.py"], input='{"jsonrpc":"2.0","id":1,"method":"tools/list"}\n',
                     capture_output=True, text=True, env=dict(os.environ, BMA_CHANNEL="0")).stdout
print("bridge without channels → tools:", json.loads(off)["result"]["tools"])
br = subprocess.Popen([sys.executable, f"{P}/scripts/bma_channel.py"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                      env=dict(os.environ, BMA_CHANNEL="1"))
out = []; threading.Thread(target=lambda: [out.append(json.loads(l)) for l in br.stdout], daemon=True).start()
br.stdin.write('{"jsonrpc":"2.0","id":"d","method":"server/discover"}\n{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25"}}\n'); br.stdin.flush()
time.sleep(1.5)
print("discover probe → error", out[0]["error"]["code"], "| channel capability:", "claude/channel" in out[1]["result"]["capabilities"]["experimental"])
print("wrong token →", post("x", **{"X-Token": "nope"}), "| foreign origin →", post("x", Origin="https://evil.test"))
print("send →", post("What's next?"))
time.sleep(1.2)
n = [m for m in out if m.get("method") == "notifications/claude/channel"]
print("pushed into the session:", n[0]["params"]["content"] if n else None)
snap = json.load(urllib.request.urlopen(f"{base}/api/snapshot?token={i['token']}"))
print("page:", snap["bridge"], [(f["who"], f.get("status")) for f in snap["feed"]])
br.stdin.close(); br.wait(5)
PY
python3 "$P/scripts/bma_ui.py" stop

echo "== 9. approvals from the page (permission relay)"
python3 "$P/scripts/bma_ui.py" start --port 7399 >/dev/null
python3 - "$P" <<'PY'
import json, os, subprocess, sys, threading, time, urllib.request, urllib.error
P = sys.argv[1]
i = json.load(open(".build-my-app/tmp/ui/ui.json")); base = f"http://127.0.0.1:{i['port']}"
def post(body):
    try:
        return urllib.request.urlopen(urllib.request.Request(f"{base}/api/permission", data=json.dumps(body).encode(),
                                      headers={"Content-Type": "application/json", "X-Token": i["token"]})).status
    except urllib.error.HTTPError as e:
        return e.code
br = subprocess.Popen([sys.executable, f"{P}/scripts/bma_channel.py"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                      env=dict(os.environ, BMA_CHANNEL="1"))
out = []; threading.Thread(target=lambda: [out.append(json.loads(l)) for l in br.stdout], daemon=True).start()
w = lambda m: (br.stdin.write(json.dumps(m) + "\n"), br.stdin.flush())
w({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}); time.sleep(1)
print("permission capability:", "claude/channel/permission" in out[0]["result"]["capabilities"]["experimental"])
for rid, cmd in (("abcde", "ls -la"), ("fghij", "git push -f origin main")):
    w({"jsonrpc": "2.0", "method": "notifications/claude/channel/permission_request",
       "params": {"request_id": rid, "tool_name": "Bash", "description": cmd, "input_preview": json.dumps({"command": cmd})}})
time.sleep(1.5)
print("allow normal →", post({"request_id": "abcde", "behavior": "allow"}), "(expect 200)")
print("allow hard stop →", post({"request_id": "fghij", "behavior": "allow"}), "(expect 409)")
open(f".build-my-app/tmp/ui/verdicts/{br.pid}.jsonl", "a").write('{"request_id": "fghij", "behavior": "allow"}\n')
time.sleep(1.2)
print("deny hard stop →", post({"request_id": "fghij", "behavior": "deny"}), "(expect 200)")
print("unknown id →", post({"request_id": "zzzzz", "behavior": "deny"}), "(expect 410)")
time.sleep(1.2)
print("verdicts sent (hard-stop allow written past the server must not appear):",
      [(m["params"]["request_id"], m["params"]["behavior"]) for m in out if m.get("method") == "notifications/claude/channel/permission"])
br.stdin.close(); br.wait(5)
PY
python3 "$P/scripts/bma_ui.py" stop
