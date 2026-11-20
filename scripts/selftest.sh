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
init = subprocess.run([sys.executable, f"{P}/scripts/bma_channel.py"], input='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}\n',
                      capture_output=True, text=True, env=dict(os.environ, BMA_CHANNEL="0")).stdout
caps = json.loads(init)["result"]["capabilities"]["experimental"]
print("capabilities are all objects (Claude Code rejects anything else):", all(isinstance(v, dict) for v in caps.values()))
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

echo "== 10. Claude's questions answered from the page (AskUserQuestion hook)"
python3 "$P/scripts/bma_ui.py" start --port 7399 >/dev/null
python3 - "$P" <<'PY'
import json, os, subprocess, sys, time, urllib.request, urllib.error
P = sys.argv[1]
i = json.load(open(".build-my-app/tmp/ui/ui.json")); base = f"http://127.0.0.1:{i['port']}"
def post(path, body):
    try:
        return urllib.request.urlopen(urllib.request.Request(base + path, data=json.dumps(body).encode(),
                                      headers={"Content-Type": "application/json", "X-Token": i["token"]})).status
    except urllib.error.HTTPError as e:
        return e.code
snap = lambda: json.load(urllib.request.urlopen(f"{base}/api/snapshot?token={i['token']}"))
Q = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "AskUserQuestion", "tool_input": {"questions": [
    {"question": "Which?", "header": "Pick", "options": [{"label": "A"}, {"label": "B"}], "multiSelect": False}]}})
hook = lambda: subprocess.Popen([sys.executable, f"{P}/hooks/ask_web.py"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
ev = lambda d: subprocess.run([sys.executable, f"{P}/hooks/ui_events.py"], input=json.dumps(d), text=True)
open_q = lambda: [q for q in snap()["questions"] if q["state"] == "open"]
term_q = lambda: [q for q in snap()["questions"] if q["state"] == "terminal"]
Qt = json.dumps({**json.loads(Q), "tool_use_id": "tu-1"})
h = hook(); out = h.communicate(Qt, timeout=10)[0]; time.sleep(1.2)
print("page not on screen → stays in the terminal:", out == "", "| page shows it read-only:", [q["questions"][0]["question"] for q in term_q()])
print("  answer from the page →", post("/api/answer", {"qid": term_q()[0]["qid"], "answers": {"Which?": "A"}}), "(expect 410)")
ev({"hook_event_name": "PostToolUse", "tool_name": "AskUserQuestion", "tool_use_id": "tu-1", "tool_input": {}}); time.sleep(1.2)
print("  answered in the terminal → card closes:", term_q() == [])
h = hook(); h.communicate(Q, timeout=10); time.sleep(1.2)
ev({"hook_event_name": "PreToolUse", "tool_name": "Read", "tool_input": {"file_path": "README.md"}}); time.sleep(1.2)
print("  dismissed in the terminal, Claude moves on → card closes:", term_q() == [])
post("/api/presence", {"visible": True})
h = hook(); h.stdin.write(Q); h.stdin.close(); time.sleep(1.5)
qid = open_q()[0]["qid"]
print("incomplete answer →", post("/api/answer", {"qid": qid, "answers": {}}), "(expect 400)")
print("answer →", post("/api/answer", {"qid": qid, "answers": {"Which?": "B"}}))
o = json.loads(h.stdout.read())["hookSpecificOutput"]
print("hook allows with answers:", o["permissionDecision"], o["updatedInput"]["answers"])
h = hook(); h.stdin.write(Q); h.stdin.close(); time.sleep(1.5)
qid = open_q()[0]["qid"]
print("move to terminal →", post("/api/answer", {"qid": qid, "terminal": True}), "| hook output empty:", h.stdout.read() == "")
time.sleep(1.2)
print("  still shown, read-only:", [q["qid"] for q in term_q()] == [qid])
print("answer after it moved →", post("/api/answer", {"qid": qid, "answers": {"Which?": "A"}}), "(expect 410)")
if True:   # no page pings: the open live connection alone keeps "the page is open" fresh
    with urllib.request.urlopen(f"{base}/events?token={i['token']}", timeout=15) as es:
        es.readline(); time.sleep(11.5)
        pr = json.load(open(".build-my-app/tmp/ui/presence.json"))
print("server keeps presence fresh while a page is connected:", time.time() - pr["seen"] < 12)
PY
python3 "$P/scripts/bma_ui.py" stop

echo "== 11. previews: open the app from the page"
python3 "$P/scripts/bma_ui.py" start --port 7399 >/dev/null
python3 - "$P" <<'PY'
import base64, json, os, socket, subprocess, sys, time, urllib.request, urllib.error
P = sys.argv[1]
i = json.load(open(".build-my-app/tmp/ui/ui.json")); base = f"http://127.0.0.1:{i['port']}"
pv = lambda *a: subprocess.run([sys.executable, f"{P}/scripts/bma_preview.py", *a], capture_output=True, text=True)
def post(body):
    try:
        r = urllib.request.urlopen(urllib.request.Request(f"{base}/api/preview", data=json.dumps(body).encode(),
                                   headers={"Content-Type": "application/json", "X-Token": i["token"]}))
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:60]
def get(path):
    try:
        return urllib.request.urlopen(base + path).status
    except urllib.error.HTTPError as e:
        return e.code
snap = lambda: json.load(urllib.request.urlopen(f"{base}/api/snapshot?token={i['token']}"))
for kind, target in (("web", "https://example.com"), ("web", "file:///etc/passwd"), ("ios", "x; rm -rf ~"), ("android", "com.example.app && reboot")):
    r = pv("add", "--kind", kind, "--target", target)
    print(f"reject {kind} {target!r}:", r.returncode != 0)
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
open("shot.png", "wb").write(png)
r = pv("add", "--kind", "web", "--target", f"http://localhost:{port}/", "--label", "Dev build", "--cmd", "python3 -m http.server", "--pid", str(srv.pid), "--screenshot", "shot.png")
print("add web preview:", r.stdout.strip())
time.sleep(1.5)
p = snap()["previews"][0]
print("page sees it:", p["label"], p["state"], "| screenshot:", bool(p["shot"]))
print("feed note:", [f["text"][:40] for f in snap()["feed"] if f.get("kind") == "preview"])
print("open (web) →", post({"id": p["id"], "action": "open"}))
print("screenshot →", get(f"/api/preview-shot?token={i['token']}&id={p['id']}"), "| without token →", get(f"/api/preview-shot?id={p['id']}"),
      "| unknown id →", get(f"/api/preview-shot?token={i['token']}&id=../../state"))
print("bad action →", post({"id": p["id"], "action": "rm"})[0], "| unknown preview →", post({"id": "nope", "action": "open"})[0])
PY
python3 "$P/scripts/bma_ui.py" stop
sleep 1
python3 "$P/scripts/bma_preview.py" list
python3 "$P/scripts/bma_preview.py" remove --all
rm -f shot.png

echo "== 12. agent reports: outcome for the hand-off at the front desk"
python3 "$P/scripts/bma_ui.py" start --port 7399 >/dev/null
python3 - "$P" <<'PY'
import importlib.util, json, os, subprocess, sys, time, urllib.request
P = sys.argv[1]
spec = importlib.util.spec_from_file_location("ue", f"{P}/hooks/ui_events.py"); ue = importlib.util.module_from_spec(spec); spec.loader.exec_module(ue)
cases = [("F-003 is green: 14 tests pass, 0 failed.", "pass"), ("Found 3 issues in the diff.", "fixes"),
         ("Tests still fail after 3 attempts.", "blocked"), ("Inject a fixed clock.", None),
         ("All good, mostly.\n**Status:** fixes", "fixes"), ("## Report\nStatus: blocked\nNeed the API key.", "blocked")]
print("outcomes:", sum(ue.outcome(t) == w for t, w in cases), "/", len(cases))
print("summary skips heading and status:", repr(ue.summary("## Report\nStatus: blocked\nNeed the API key.")))
hook = lambda d: subprocess.run([sys.executable, f"{P}/hooks/ui_events.py"], input=json.dumps({**d, "cwd": os.getcwd()}), text=True, env={**os.environ, "CLAUDE_PROJECT_DIR": os.getcwd()})
for aid, msg in (("r1", "Review done; 2 findings in StreakEngine.\nStatus: fixes"), ("r2", "")):
    hook({"hook_event_name": "SubagentStart", "agent_id": aid, "agent_type": "build-my-app:code-reviewer"})
    hook({"hook_event_name": "SubagentStop", "agent_id": aid, "agent_type": "build-my-app:code-reviewer", "last_assistant_message": msg})
time.sleep(1.5)
i = json.load(open(".build-my-app/tmp/ui/ui.json"))
snap = json.load(urllib.request.urlopen(f"http://127.0.0.1:{i['port']}/api/snapshot?token={i['token']}"))
ag = {a["id"]: a for a in snap["agents"]}
print("r1:", ag["r1"]["status"], ag["r1"]["outcome"], ag["r1"]["reported"], repr(ag["r1"]["result"]))
print("r2 (no report):", ag["r2"]["status"], ag["r2"]["outcome"], ag["r2"]["reported"])
print("feed badge:", [f.get("outcome") for f in snap["feed"] if f.get("agent") == "r1"])
PY
python3 "$P/scripts/bma_ui.py" stop
