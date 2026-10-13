import json
import os
import sqlite3
import sys
import tempfile
import time


def db_path(event):
    root = os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd()
    d = os.path.join(root, ".team")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "agent-log.sqlite")


def leader_summary(event):
    text = event.get("last_assistant_message")
    if text:
        return text
    path = event.get("transcript_path")
    if not path or not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    for line in reversed(lines):
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if obj.get("type") != "assistant":
            continue
        content = (obj.get("message") or {}).get("content") or []
        texts = [b.get("text") for b in content if isinstance(b, dict) and b.get("type") == "text" and b.get("text")]
        if texts:
            return "\n".join(texts)
    return None


def row_for(event):
    if event.get("hook_event_name") == "Stop":
        return ("leader", "stop", None, leader_summary(event))
    ti = event.get("tool_input") or {}
    resp = event.get("tool_response")
    if not isinstance(resp, str):
        resp = json.dumps(resp, ensure_ascii=False)
    return (ti.get("subagent_type"), ti.get("description"), ti.get("prompt"), resp)


def log(event, path):
    agent, description, prompt, response = row_for(event)
    con = sqlite3.connect(path)
    con.execute(
        "create table if not exists runs("
        "id integer primary key, ts text not null, session_id text, "
        "agent text, description text, prompt text, response text)"
    )
    con.execute(
        "insert into runs(ts, session_id, agent, description, prompt, response) values(?,?,?,?,?,?)",
        (time.strftime("%Y-%m-%dT%H:%M:%S"), event.get("session_id"), agent, description, prompt, response),
    )
    con.commit()
    con.close()


def selftest():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "t.sqlite")
    log(
        {
            "session_id": "s1",
            "hook_event_name": "PostToolUse",
            "tool_input": {"subagent_type": "coder", "description": "d", "prompt": "p"},
            "tool_response": {"ok": True},
        },
        p,
    )
    t = os.path.join(d, "t.jsonl")
    with open(t, "w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "user", "message": {"content": "hi"}}) + "\n")
        f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash"}]}}) + "\n")
        f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Done."}, {"type": "text", "text": "Bye."}]}}) + "\n")
    log({"session_id": "s1", "hook_event_name": "Stop", "transcript_path": t}, p)
    log({"session_id": "s1", "hook_event_name": "Stop", "last_assistant_message": "Direct."}, p)
    rows = sqlite3.connect(p).execute("select agent, description, response from runs order by id").fetchall()
    assert rows == [
        ("coder", "d", '{"ok": true}'),
        ("leader", "stop", "Done.\nBye."),
        ("leader", "stop", "Direct."),
    ], rows
    print("selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
        sys.exit(0)
    try:
        event = json.load(sys.stdin)
        log(event, db_path(event))
    except Exception as e:
        print(f"log_agent: {e}", file=sys.stderr)
    sys.exit(0)
