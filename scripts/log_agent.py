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
    name = event.get("hook_event_name")
    ti = event.get("tool_input") or {}
    if name == "Stop":
        return ("leader", "stop", None, leader_summary(event), None)
    if name == "PreToolUse":
        return (ti.get("subagent_type"), "start", ti.get("prompt"), None, event.get("tool_use_id"))
    resp = event.get("tool_response")
    if not isinstance(resp, str):
        resp = json.dumps(resp, ensure_ascii=False)
    return (ti.get("subagent_type"), ti.get("description"), ti.get("prompt"), resp, event.get("tool_use_id"))


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
        "select e.id, e.ts, e.agent, e.description, "
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
    log({"session_id": "s1", "hook_event_name": "PreToolUse", "tool_use_id": "tu1",
         "tool_input": {"subagent_type": "coder", "description": "d", "prompt": "p"}}, p)
    log({"session_id": "s1", "hook_event_name": "PostToolUse", "tool_use_id": "tu1",
         "tool_input": {"subagent_type": "coder", "description": "d", "prompt": "p"}, "tool_response": {"ok": True}}, p)
    t = os.path.join(d, "t.jsonl")
    with open(t, "w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Done."}]}}) + "\n")
    log({"session_id": "s1", "hook_event_name": "Stop", "transcript_path": t}, p)
    con = sqlite3.connect(p)
    rows = con.execute("select agent, description, response, tool_use_id from runs order by id").fetchall()
    assert rows == [("coder", "start", None, "tu1"), ("coder", "d", '{"ok": true}', "tu1"), ("leader", "stop", "Done.", None)], rows
    dur = con.execute("select agent, description, seconds from durations").fetchall()
    assert len(dur) == 1 and dur[0][0] == "coder" and dur[0][1] == "d" and dur[0][2] >= 0, dur
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
