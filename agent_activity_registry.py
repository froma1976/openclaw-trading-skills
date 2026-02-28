#!/usr/bin/env python3
import argparse
import sqlite3
from datetime import datetime
from pathlib import Path
import hashlib

DB_PATH = Path("C:/Users/Fernando/.openclaw/workspace/agent_activity_registry.db")


def now_iso():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def task_fingerprint(title: str, payload: str = "") -> str:
    base = f"{norm(title)}|{norm(payload)}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY,
          user_id TEXT UNIQUE NOT NULL,
          display_name TEXT,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tasks (
          id INTEGER PRIMARY KEY,
          task_id TEXT UNIQUE NOT NULL,
          title TEXT NOT NULL,
          details TEXT,
          assigned_by TEXT NOT NULL,
          assigned_to TEXT NOT NULL DEFAULT 'agent',
          status TEXT NOT NULL DEFAULT 'pending',
          fingerprint TEXT NOT NULL,
          source TEXT NOT NULL DEFAULT 'manual',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_fingerprint ON tasks(fingerprint);
        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);

        CREATE TABLE IF NOT EXISTS cron_tasks (
          id INTEGER PRIMARY KEY,
          name TEXT UNIQUE NOT NULL,
          cron_expr TEXT NOT NULL,
          task_ref TEXT,
          owner_user_id TEXT,
          active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS token_usage (
          id INTEGER PRIMARY KEY,
          model TEXT NOT NULL,
          session_key TEXT,
          tokens_in INTEGER NOT NULL DEFAULT 0,
          tokens_out INTEGER NOT NULL DEFAULT 0,
          recorded_at TEXT NOT NULL,
          recorded_by TEXT NOT NULL DEFAULT 'agent'
        );
        """
    )
    conn.commit()


def upsert_user(conn, user_id, display_name=None):
    conn.execute(
        """
        INSERT INTO users(user_id, display_name, created_at)
        VALUES(?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET display_name=COALESCE(excluded.display_name, users.display_name)
        """,
        (user_id, display_name, now_iso()),
    )


def add_task(conn, title, details, assigned_by, assigned_to="agent", source="manual"):
    fp = task_fingerprint(title, details or "")
    existing = conn.execute(
        "SELECT task_id, status FROM tasks WHERE fingerprint=? AND status IN ('pending','running')",
        (fp,),
    ).fetchone()
    if existing:
        return {"duplicate": True, "task_id": existing["task_id"], "status": existing["status"]}

    task_id = f"tsk_{hashlib.sha1((title + now_iso()).encode()).hexdigest()[:10]}"
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO tasks(task_id,title,details,assigned_by,assigned_to,status,fingerprint,source,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)
        """,
        (task_id, title, details, assigned_by, assigned_to, "pending", fp, source, ts, ts),
    )
    conn.commit()
    return {"duplicate": False, "task_id": task_id}


def set_task_status(conn, task_id, status):
    conn.execute(
        "UPDATE tasks SET status=?, updated_at=? WHERE task_id=?",
        (status, now_iso(), task_id),
    )
    conn.commit()


def add_cron(conn, name, expr, task_ref=None, owner=None):
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO cron_tasks(name, cron_expr, task_ref, owner_user_id, active, created_at, updated_at)
        VALUES(?,?,?,?,1,?,?)
        ON CONFLICT(name) DO UPDATE SET cron_expr=excluded.cron_expr, task_ref=excluded.task_ref, owner_user_id=excluded.owner_user_id, updated_at=excluded.updated_at
        """,
        (name, expr, task_ref, owner, ts, ts),
    )
    conn.commit()


def add_usage(conn, model, tokens_in, tokens_out, session_key=None, recorded_by="agent"):
    conn.execute(
        "INSERT INTO token_usage(model, session_key, tokens_in, tokens_out, recorded_at, recorded_by) VALUES(?,?,?,?,?,?)",
        (model, session_key, tokens_in, tokens_out, now_iso(), recorded_by),
    )
    conn.commit()


def summary(conn):
    t = conn.execute("SELECT status, COUNT(*) c FROM tasks GROUP BY status").fetchall()
    u = conn.execute("SELECT model, SUM(tokens_in) tin, SUM(tokens_out) tout FROM token_usage GROUP BY model ORDER BY (tin+tout) DESC").fetchall()
    c = conn.execute("SELECT name, cron_expr, active, owner_user_id FROM cron_tasks ORDER BY name").fetchall()
    return t, u, c


def main():
    p = argparse.ArgumentParser(description="Registro centralizado del agente")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init")

    s = sub.add_parser("add-user")
    s.add_argument("--user-id", required=True)
    s.add_argument("--name")

    s = sub.add_parser("add-task")
    s.add_argument("--title", required=True)
    s.add_argument("--details", default="")
    s.add_argument("--assigned-by", required=True)
    s.add_argument("--assigned-to", default="agent")
    s.add_argument("--source", default="manual")

    s = sub.add_parser("set-status")
    s.add_argument("--task-id", required=True)
    s.add_argument("--status", required=True, choices=["pending", "running", "done", "cancelled", "blocked"])

    s = sub.add_parser("add-cron")
    s.add_argument("--name", required=True)
    s.add_argument("--expr", required=True)
    s.add_argument("--task-ref")
    s.add_argument("--owner")

    s = sub.add_parser("add-usage")
    s.add_argument("--model", required=True)
    s.add_argument("--in", dest="tin", required=True, type=int)
    s.add_argument("--out", dest="tout", required=True, type=int)
    s.add_argument("--session")
    s.add_argument("--by", default="agent")

    sub.add_parser("summary")

    args = p.parse_args()
    conn = connect()

    if args.cmd == "init":
        init_db(conn)
        print(f"OK DB inicializada en {DB_PATH}")
    elif args.cmd == "add-user":
        init_db(conn)
        upsert_user(conn, args.user_id, args.name)
        conn.commit()
        print("OK usuario registrado")
    elif args.cmd == "add-task":
        init_db(conn)
        r = add_task(conn, args.title, args.details, args.assigned_by, args.assigned_to, args.source)
        if r["duplicate"]:
            print(f"DUPLICADA -> task_id existente: {r['task_id']} ({r['status']})")
        else:
            print(f"OK task creada: {r['task_id']}")
    elif args.cmd == "set-status":
        init_db(conn)
        set_task_status(conn, args.task_id, args.status)
        print("OK estado actualizado")
    elif args.cmd == "add-cron":
        init_db(conn)
        add_cron(conn, args.name, args.expr, args.task_ref, args.owner)
        print("OK cron registrada/actualizada")
    elif args.cmd == "add-usage":
        init_db(conn)
        add_usage(conn, args.model, args.tin, args.tout, args.session, args.by)
        print("OK consumo registrado")
    elif args.cmd == "summary":
        init_db(conn)
        t, u, c = summary(conn)
        print("\n== TAREAS ==")
        for r in t:
            print(f"- {r['status']}: {r['c']}")
        print("\n== TOKENS POR MODELO ==")
        for r in u:
            print(f"- {r['model']}: in={r['tin'] or 0}, out={r['tout'] or 0}")
        print("\n== CRON ==")
        for r in c:
            st = "activa" if r["active"] else "inactiva"
            print(f"- {r['name']} [{st}] {r['cron_expr']} owner={r['owner_user_id'] or '-'}")


if __name__ == "__main__":
    main()
