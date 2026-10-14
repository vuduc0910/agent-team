import json
import os
import sqlite3
import sys
import tempfile
import time


def db_path(row):
    d = os.path.join(row.get("cwd") or os.getcwd(), ".team")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "agent-log.sqlite")


def log(row, path):
    response = row.get("response")
    if response is not None and not isinstance(response, str):
        response = json.dumps(response, ensure_ascii=False)
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
        (
            time.strftime("%Y-%m-%dT%H:%M:%S"),
            row.get("session_id"),
            row.get("agent"),
            row.get("description"),
            row.get("prompt"),
            response,
            row.get("tool_use_id"),
        ),
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
    log({"session_id": "s1", "agent": "coder", "description": "start", "prompt": "p", "response": None, "tool_use_id": "c1"}, p)
    log({"session_id": "s1", "agent": "coder", "description": "d", "prompt": "p", "response": {"ok": True}, "tool_use_id": "c1"}, p)
    log({"session_id": "s1", "agent": "leader", "description": "idle", "prompt": None, "response": "Done."}, p)
    con = sqlite3.connect(p)
    rows = con.execute("select agent, description, prompt, response, tool_use_id from runs order by id").fetchall()
    assert rows == [("coder", "start", "p", None, "c1"), ("coder", "d", "p", '{"ok": true}', "c1"), ("leader", "idle", None, "Done.", None)], rows
    dur = con.execute("select agent, description, seconds from durations").fetchall()
    assert len(dur) == 1 and dur[0][0] == "coder" and dur[0][1] == "d" and dur[0][2] >= 0, dur
    print("selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
        sys.exit(0)
    try:
        row = json.load(sys.stdin)
        log(row, db_path(row))
    except Exception as e:
        print(f"log_agent: {e}", file=sys.stderr)
        sys.exit(1)
    sys.exit(0)
