import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time


def project_root(event):
    cwd = event.get("cwd") or os.getcwd()
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=cwd, capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return cwd


def db_path(event):
    d = os.path.join(project_root(event), ".team")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "agent-log.sqlite")


def as_text(value):
    if value is None or isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def row_for(event):
    name = event.get("hook_event_name")
    if name == "Stop":
        return ("leader", "stop", None, event.get("last_assistant_message"))
    if name == "SubagentStop":
        return (event.get("agent_type"), event.get("agent_id"), None, event.get("last_assistant_message"))
    return (event.get("tool_name"), event.get("tool_use_id"), as_text(event.get("tool_input")), as_text(event.get("tool_response")))


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
            "tool_name": "spawn_agent",
            "tool_use_id": "call_1",
            "tool_input": {"agent_type": "coder", "message": "brief"},
            "tool_response": {"ok": True},
        },
        p,
    )
    log(
        {
            "session_id": "s1",
            "hook_event_name": "SubagentStop",
            "agent_type": "coder",
            "agent_id": "a1",
            "last_assistant_message": "Changed: x.py",
        },
        p,
    )
    log({"session_id": "s1", "hook_event_name": "Stop", "last_assistant_message": "Done."}, p)
    rows = sqlite3.connect(p).execute("select agent, description, prompt, response from runs order by id").fetchall()
    assert rows == [
        ("spawn_agent", "call_1", '{"agent_type": "coder", "message": "brief"}', '{"ok": true}'),
        ("coder", "a1", None, "Changed: x.py"),
        ("leader", "stop", None, "Done."),
    ], rows
    assert project_root({"cwd": d}) == d
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
