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
        return ("leader", "stop", None, event.get("last_assistant_message"), None)
    if name == "SubagentStop":
        return (event.get("agent_type"), event.get("agent_id"), None, event.get("last_assistant_message"), None)
    if name == "PreToolUse":
        return (event.get("tool_name"), "start", as_text(event.get("tool_input")), None, event.get("tool_use_id"))
    return (event.get("tool_name"), "end", as_text(event.get("tool_input")), as_text(event.get("tool_response")), event.get("tool_use_id"))


def log(event, path):
    agent, description, prompt, response, tool_use_id = row_for(event)
    con = sqlite3.connect(path)
    con.execute(
        "create table if not exists runs("
        "id integer primary key, ts text not null, session_id text, "
        "agent text, description text, prompt text, response text, tool_use_id text)"
    )
    try:
        con.execute("alter table runs add column tool_use_id text")
    except sqlite3.OperationalError:
        pass
    con.execute(
        "create view if not exists durations as "
        "select e.id, e.ts, e.agent, e.description, e.tool_use_id, "
        "strftime('%s', e.ts) - strftime('%s', s.ts) as seconds "
        "from runs e join runs s on s.tool_use_id = e.tool_use_id and s.description = 'start' "
        "where e.description != 'start' and e.tool_use_id is not null"
    )
    con.execute(
        "insert into runs(ts, session_id, agent, description, prompt, response, tool_use_id) values(?,?,?,?,?,?,?)",
        (time.strftime("%Y-%m-%dT%H:%M:%S"), event.get("session_id"), agent, description, prompt, response, tool_use_id),
    )
    con.commit()
    con.close()


def selftest():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "t.sqlite")
    old = sqlite3.connect(p)
    old.execute("create table runs(id integer primary key, ts text not null, session_id text, agent text, description text, prompt text, response text)")
    old.commit()
    old.close()
    spawn = {
        "session_id": "s1",
        "tool_name": "spawn_agent",
        "tool_use_id": "call_1",
        "tool_input": {"agent_type": "coder", "message": "brief"},
    }
    log({**spawn, "hook_event_name": "PreToolUse"}, p)
    log({**spawn, "hook_event_name": "PostToolUse", "tool_response": {"ok": True}}, p)
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
    con = sqlite3.connect(p)
    rows = con.execute("select agent, description, prompt, response, tool_use_id from runs order by id").fetchall()
    assert rows == [
        ("spawn_agent", "start", '{"agent_type": "coder", "message": "brief"}', None, "call_1"),
        ("spawn_agent", "end", '{"agent_type": "coder", "message": "brief"}', '{"ok": true}', "call_1"),
        ("coder", "a1", None, "Changed: x.py", None),
        ("leader", "stop", None, "Done.", None),
    ], rows
    dur = con.execute("select agent, description, tool_use_id, seconds from durations").fetchall()
    assert len(dur) == 1 and dur[0][:3] == ("spawn_agent", "end", "call_1") and dur[0][3] >= 0, dur
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
