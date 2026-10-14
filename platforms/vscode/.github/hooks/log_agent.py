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
        return ("leader", "stop", None, event.get("last_assistant_message") or event.get("transcript_path"), None)
    if name == "SubagentStop":
        return (event.get("agent_type"), event.get("agent_id"), None, None, None)
    tool = event.get("tool_name") or ""
    if tool.split("/")[-1] != "runSubagent":
        return None
    if name == "PreToolUse":
        return (tool, "start", as_text(event.get("tool_input")), None, event.get("tool_use_id"))
    return (tool, "end", as_text(event.get("tool_input")), as_text(event.get("tool_response")), event.get("tool_use_id"))


def log(event, path):
    row = row_for(event)
    if row is None:
        return
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
        "select e.id, e.ts, e.agent, e.description, "
        "strftime('%s', e.ts) - strftime('%s', s.ts) as seconds "
        "from runs e join runs s on s.tool_use_id = e.tool_use_id and s.description = 'start' "
        "where e.description != 'start' and e.tool_use_id is not null"
    )
    con.execute(
        "insert into runs(ts, session_id, agent, description, prompt, response, tool_use_id) values(?,?,?,?,?,?,?)",
        (time.strftime("%Y-%m-%dT%H:%M:%S"), event.get("session_id"), *row),
    )
    con.commit()
    con.close()


def selftest():
    p = os.path.join(tempfile.mkdtemp(), "t.sqlite")
    old = sqlite3.connect(p)
    old.execute("create table runs(id integer primary key, ts text not null, session_id text, agent text, description text, prompt text, response text)")
    old.commit()
    old.close()
    base = {"session_id": "s1", "timestamp": "2026-01-01T00:00:00Z", "cwd": "/repo"}
    log({**base, "hook_event_name": "PreToolUse", "tool_name": "execute/runInTerminal", "tool_input": {}, "tool_use_id": "x"}, p)
    log({**base, "hook_event_name": "PostToolUse", "tool_name": "execute/runInTerminal", "tool_input": {}, "tool_use_id": "x", "tool_response": "ignored"}, p)
    log({**base, "hook_event_name": "PreToolUse", "tool_name": "agent/runSubagent", "tool_input": {"prompt": "brief"}, "tool_use_id": "u1"}, p)
    log({**base, "hook_event_name": "PostToolUse", "tool_name": "agent/runSubagent", "tool_input": {"prompt": "brief"}, "tool_use_id": "u1", "tool_response": {"ok": True}}, p)
    log({**base, "hook_event_name": "SubagentStop", "agent_id": "a1", "agent_type": "coder", "stop_hook_active": False}, p)
    log({**base, "hook_event_name": "Stop", "stop_hook_active": False, "transcript_path": "/t/1.json"}, p)
    log({**base, "hook_event_name": "Stop", "stop_hook_active": False, "last_assistant_message": "Done."}, p)
    con = sqlite3.connect(p)
    rows = con.execute("select agent, description, prompt, response, tool_use_id from runs order by id").fetchall()
    assert rows == [
        ("agent/runSubagent", "start", '{"prompt": "brief"}', None, "u1"),
        ("agent/runSubagent", "end", '{"prompt": "brief"}', '{"ok": true}', "u1"),
        ("coder", "a1", None, None, None),
        ("leader", "stop", None, "/t/1.json", None),
        ("leader", "stop", None, "Done.", None),
    ], rows
    dur = con.execute("select agent, description, seconds from durations").fetchall()
    assert len(dur) == 1 and dur[0][:2] == ("agent/runSubagent", "end") and dur[0][2] >= 0, dur
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
