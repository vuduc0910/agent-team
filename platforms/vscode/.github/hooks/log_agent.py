import json
import os
import sqlite3
import sys
import tempfile
import time


def db_path(event):
    root = event.get("cwd") or os.getcwd()
    d = os.path.join(root, ".team")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "agent-log.sqlite")


def as_text(value):
    if value is None or isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def row_for(event):
    name = event.get("hook_event_name")
    if name == "Stop":
        return ("leader", "stop", None, event.get("last_assistant_message") or event.get("transcript_path"))
    if name == "SubagentStop":
        return (event.get("agent_type"), event.get("agent_id"), None, None)
    tool = event.get("tool_name") or ""
    if tool.split("/")[-1] != "runSubagent":
        return None
    return (tool, event.get("tool_use_id"), as_text(event.get("tool_input")), as_text(event.get("tool_response")))


def log(event, path):
    row = row_for(event)
    if row is None:
        return
    agent, description, prompt, response = row
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
    p = os.path.join(tempfile.mkdtemp(), "t.sqlite")
    base = {"session_id": "s1", "timestamp": "2026-01-01T00:00:00Z", "cwd": "/repo"}
    log({**base, "hook_event_name": "PostToolUse", "tool_name": "execute/runInTerminal", "tool_input": {}, "tool_use_id": "x", "tool_response": "ignored"}, p)
    log({**base, "hook_event_name": "PostToolUse", "tool_name": "agent/runSubagent", "tool_input": {"prompt": "brief"}, "tool_use_id": "u1", "tool_response": {"ok": True}}, p)
    log({**base, "hook_event_name": "SubagentStop", "agent_id": "a1", "agent_type": "coder", "stop_hook_active": False}, p)
    log({**base, "hook_event_name": "Stop", "stop_hook_active": False, "transcript_path": "/t/1.json"}, p)
    log({**base, "hook_event_name": "Stop", "stop_hook_active": False, "last_assistant_message": "Done."}, p)
    rows = sqlite3.connect(p).execute("select agent, description, prompt, response from runs order by id").fetchall()
    assert rows == [
        ("agent/runSubagent", "u1", '{"prompt": "brief"}', '{"ok": true}'),
        ("coder", "a1", None, None),
        ("leader", "stop", None, "/t/1.json"),
        ("leader", "stop", None, "Done."),
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
