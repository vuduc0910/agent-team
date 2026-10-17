import json
import os
import sqlite3
import sys
import tempfile
import time

TOKEN_KEYS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")


def db_path(event):
    root = os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd()
    d = os.path.join(root, ".team")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "agent-log.sqlite")


def read_transcript(path):
    if not path or not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if obj.get("type") == "assistant":
                out.append(obj)
    return out


def leader_summary(event):
    text = event.get("last_assistant_message")
    if text:
        return text
    for obj in reversed(read_transcript(event.get("transcript_path"))):
        content = (obj.get("message") or {}).get("content") or []
        texts = [b.get("text") for b in content if isinstance(b, dict) and b.get("type") == "text" and b.get("text")]
        if texts:
            return "\n".join(texts)
    return None


def usage_from_transcript(path):
    best = {}
    model = None
    for obj in read_transcript(path):
        m = obj.get("message") or {}
        u = m.get("usage") or {}
        key = m.get("id") or obj.get("requestId") or obj.get("uuid")
        model = m.get("model") or model
        cur = best.get(key)
        if cur is None or (u.get("output_tokens") or 0) > (cur.get("output_tokens") or 0):
            best[key] = u
    totals = {k: sum(int(u.get(k) or 0) for u in best.values()) for k in TOKEN_KEYS}
    return totals, model


def subagent_transcript(event):
    path = event.get("agent_transcript_path")
    if path:
        return path
    main = event.get("transcript_path") or ""
    sid = event.get("session_id") or ""
    return os.path.join(os.path.dirname(main), sid, "subagents", f"agent-{event.get('agent_id')}.jsonl")


def row_for(event):
    name = event.get("hook_event_name")
    ti = event.get("tool_input") or {}
    none = (None, 0, 0, 0, 0)
    if name == "Stop":
        t, model = usage_from_transcript(event.get("transcript_path"))
        return ("leader", "stop", None, leader_summary(event), None, None, model, *(t[k] for k in TOKEN_KEYS))
    if name == "SubagentStop":
        t, model = usage_from_transcript(subagent_transcript(event))
        return (event.get("agent_type"), "stop", None, event.get("last_assistant_message"), None, event.get("agent_id"), model, *(t[k] for k in TOKEN_KEYS))
    if name == "PreToolUse":
        return (ti.get("subagent_type"), "start", ti.get("prompt"), None, event.get("tool_use_id"), None, *none)
    resp = event.get("tool_response")
    if not isinstance(resp, str):
        resp = json.dumps(resp, ensure_ascii=False)
    return (ti.get("subagent_type"), ti.get("description"), ti.get("prompt"), resp, event.get("tool_use_id"), None, *none)


SCHEMA = [
    "create table if not exists runs(id integer primary key, ts text not null, session_id text, agent text, description text, prompt text, response text, tool_use_id text, agent_id text, model text, in_tokens integer, out_tokens integer, cache_read integer, cache_write integer)",
    "create view if not exists durations as select e.id, e.ts, e.agent, e.description, strftime('%s', e.ts) - strftime('%s', s.ts) as seconds from runs e join runs s on s.tool_use_id = e.tool_use_id and s.description = 'start' where e.description != 'start' and e.tool_use_id is not null",
    "create view if not exists member_tokens as select id, ts, session_id, agent, agent_id, model, in_tokens - coalesce(lag(in_tokens) over w, 0) as in_tokens, out_tokens - coalesce(lag(out_tokens) over w, 0) as out_tokens, cache_read - coalesce(lag(cache_read) over w, 0) as cache_read, cache_write - coalesce(lag(cache_write) over w, 0) as cache_write from runs where description = 'stop' and agent != 'leader' window w as (partition by session_id, agent_id order by id)",
    "create view if not exists leader_turns as select id, ts, session_id, model, in_tokens - coalesce(lag(in_tokens) over w, 0) as leader_in, out_tokens - coalesce(lag(out_tokens) over w, 0) as leader_out, cache_read - coalesce(lag(cache_read) over w, 0) as leader_cache_read, cache_write - coalesce(lag(cache_write) over w, 0) as leader_cache_write, coalesce(lag(id) over w, 0) as prev_id from runs where agent = 'leader' and description = 'stop' window w as (partition by session_id order by id)",
    "create view if not exists turn_tokens as select l.id, l.ts, l.session_id, l.model, l.leader_in, l.leader_out, l.leader_cache_read, l.leader_cache_write, (select count(*) from member_tokens m where m.session_id = l.session_id and m.id > l.prev_id and m.id < l.id) as member_runs, (select coalesce(sum(m.in_tokens + m.out_tokens + m.cache_write), 0) from member_tokens m where m.session_id = l.session_id and m.id > l.prev_id and m.id < l.id) as member_new, (select coalesce(sum(m.cache_read), 0) from member_tokens m where m.session_id = l.session_id and m.id > l.prev_id and m.id < l.id) as member_cache_read from leader_turns l",
]
MIGRATIONS = ["tool_use_id text", "agent_id text", "model text", "in_tokens integer", "out_tokens integer", "cache_read integer", "cache_write integer"]


def connect(path):
    con = sqlite3.connect(path)
    con.execute(SCHEMA[0])
    for col in MIGRATIONS:
        try:
            con.execute(f"alter table runs add column {col}")
        except sqlite3.OperationalError:
            pass
    for stmt in SCHEMA[1:]:
        con.execute(stmt)
    return con


def fmt(n):
    n = int(n or 0)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1000:
        return f"{n / 1000:.1f}k"
    return str(n)


def turn_message(con, row_id):
    r = con.execute("select leader_in, leader_out, leader_cache_write, leader_cache_read, member_runs, member_new, member_cache_read from turn_tokens where id = ?", (row_id,)).fetchone()
    if not r:
        return None
    leader_new = r[0] + r[1] + r[2]
    return (f"agent-team tokens this turn: leader new {fmt(leader_new)} (in {fmt(r[0])}, out {fmt(r[1])}, cache write {fmt(r[2])}), cache read {fmt(r[3])}. "
            f"members: {r[4]} runs, new {fmt(r[5])}, cache read {fmt(r[6])}. total new {fmt(leader_new + r[5])}.")


def log(event, path):
    row = row_for(event)
    con = connect(path)
    cur = con.execute(
        "insert into runs(ts, session_id, agent, description, prompt, response, tool_use_id, agent_id, model, in_tokens, out_tokens, cache_read, cache_write) values(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (time.strftime("%Y-%m-%dT%H:%M:%S"), event.get("session_id"), *row),
    )
    con.commit()
    msg = turn_message(con, cur.lastrowid) if event.get("hook_event_name") == "Stop" else None
    con.close()
    return msg


def write_transcript(path, responses):
    with open(path, "w", encoding="utf-8") as f:
        for i, (mid, out, model) in enumerate(responses):
            for partial in (1, out):
                f.write(json.dumps({"type": "assistant", "message": {"id": mid, "model": model, "content": [{"type": "text", "text": f"m{i}"}],
                                    "usage": {"input_tokens": 10, "output_tokens": partial, "cache_read_input_tokens": 1000, "cache_creation_input_tokens": 200}}}) + "\n")


def selftest():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "t.sqlite")
    old = sqlite3.connect(p)
    old.execute("create table runs(id integer primary key, ts text not null, session_id text, agent text, description text, prompt text, response text)")
    old.commit()
    old.close()
    main = os.path.join(d, "s1.jsonl")
    os.makedirs(os.path.join(d, "s1", "subagents"))
    sub = os.path.join(d, "s1", "subagents", "agent-a1.jsonl")
    write_transcript(main, [("m1", 50, "claude-opus-5-5")])
    assert log({"session_id": "s1", "hook_event_name": "Stop", "transcript_path": main}, p).startswith("agent-team tokens")
    log({"session_id": "s1", "hook_event_name": "PreToolUse", "tool_use_id": "tu1", "tool_input": {"subagent_type": "coder", "description": "d", "prompt": "p"}}, p)
    log({"session_id": "s1", "hook_event_name": "PostToolUse", "tool_use_id": "tu1", "tool_input": {"subagent_type": "coder", "description": "d", "prompt": "p"}, "tool_response": {"ok": True}}, p)
    write_transcript(sub, [("a", 30, "claude-opus-5-5"), ("b", 40, "claude-opus-5-5")])
    log({"session_id": "s1", "hook_event_name": "SubagentStop", "transcript_path": main, "agent_id": "a1", "agent_type": "agent-team:coder", "last_assistant_message": "Changed: a.ts"}, p)
    write_transcript(main, [("m1", 50, "claude-opus-5-5"), ("m2", 70, "claude-opus-5-5")])
    msg = log({"session_id": "s1", "hook_event_name": "Stop", "transcript_path": main, "last_assistant_message": "Done."}, p)
    con = sqlite3.connect(p)
    rows = con.execute("select agent, description, in_tokens, out_tokens, cache_read, cache_write from runs order by id").fetchall()
    assert rows[0] == ("leader", "stop", 10, 50, 1000, 200), rows[0]
    assert rows[3] == ("agent-team:coder", "stop", 20, 70, 2000, 400), rows[3]
    assert rows[4] == ("leader", "stop", 20, 120, 2000, 400), rows[4]
    turn = con.execute("select leader_in, leader_out, leader_cache_read, leader_cache_write, member_runs, member_new, member_cache_read from turn_tokens order by id").fetchall()
    assert turn == [(10, 50, 1000, 200, 0, 0, 0), (10, 70, 1000, 200, 1, 490, 2000)], turn
    assert con.execute("select seconds from durations").fetchone()[0] >= 0
    assert msg == "agent-team tokens this turn: leader new 280 (in 10, out 70, cache write 200), cache read 1.0k. members: 1 runs, new 490, cache read 2.0k. total new 770.", msg
    print("selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
        sys.exit(0)
    try:
        event = json.load(sys.stdin)
        msg = log(event, db_path(event))
        if msg:
            print(json.dumps({"systemMessage": msg}))
    except Exception as e:
        print(f"log_agent: {e}", file=sys.stderr)
    sys.exit(0)
