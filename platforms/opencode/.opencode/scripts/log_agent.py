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
        "agent text, description text, prompt text, response text)"
    )
    con.execute(
        "insert into runs(ts, session_id, agent, description, prompt, response) values(?,?,?,?,?,?)",
        (
            time.strftime("%Y-%m-%dT%H:%M:%S"),
            row.get("session_id"),
            row.get("agent"),
            row.get("description"),
            row.get("prompt"),
            response,
        ),
    )
    con.commit()
    con.close()


def selftest():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "t.sqlite")
    log({"session_id": "s1", "agent": "coder", "description": "d", "prompt": "p", "response": {"ok": True}}, p)
    log({"session_id": "s1", "agent": "leader", "description": "idle", "prompt": None, "response": "Done."}, p)
    rows = sqlite3.connect(p).execute("select agent, description, prompt, response from runs order by id").fetchall()
    assert rows == [("coder", "d", "p", '{"ok": true}'), ("leader", "idle", None, "Done.")], rows
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
