#!/usr/bin/env python3
"""Shared helpers for the AIWIKI documentation pipeline."""
from __future__ import annotations

import json
import os
import re
import shutil
import signal
import sqlite3
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

MODEL = "gpt-5.5"
OVERVIEW_REASONING = "high"
TASK_REASONING = "medium"
DEFAULT_TIMEOUT_SECONDS = 1800
STATE_FILES = {
    "completed": "pipeline.success",
    "partial": "pipeline.partial",
    "failed": "pipeline.failed",
}
MARKDOWN_URL_RE = re.compile(r"(?i)(?:https?://|git@github\.com:)[^\s<>()\[\]{}\"']+")


def utc_ts() -> float:
    return time.time()


def normalize_rel_path(value: str | Path) -> str:
    rel = str(value).replace("\\", "/").strip("/")
    parts = [p for p in rel.split("/") if p and p != "."]
    if any(p == ".." for p in parts):
        raise ValueError(f"unsafe relative path: {value}")
    return "/".join(parts)


def doc_name_for_rel(rel_path: str) -> str:
    rel_path = normalize_rel_path(rel_path)
    return rel_path.replace("/", "__") + ".md"


def output_md_for(kind: str, rel_path: str) -> str:
    rel_path = normalize_rel_path(rel_path)
    if kind == "directory":
        return f"directories/{doc_name_for_rel(rel_path)}"
    if kind == "file":
        return f"files/{doc_name_for_rel(rel_path)}"
    raise ValueError(f"unsupported task kind: {kind}")


def rel_key_for(kind: str, rel_path: str) -> str:
    return f"{kind}:{normalize_rel_path(rel_path)}"


def safe_debug_name(value: str, limit: int = 180) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")
    return (safe or "task")[:limit]


def state_db_path(out: Path) -> Path:
    return Path(out) / "state.sqlite3"


def connect_state(out: Path) -> sqlite3.Connection:
    Path(out).mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(state_db_path(Path(out)), timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")
    return con


def init_state_db(out: Path) -> None:
    with connect_state(out) as con:
        con.execute(
            """CREATE TABLE IF NOT EXISTS pipeline_runs(
                run_id TEXT PRIMARY KEY,
                repo TEXT,
                out TEXT,
                status TEXT,
                model TEXT,
                reasoning TEXT,
                timeout_seconds INTEGER,
                started_at REAL,
                updated_at REAL,
                completed_at REAL,
                message TEXT
            )"""
        )
        con.execute(
            """CREATE TABLE IF NOT EXISTS stages(
                run_id TEXT,
                stage TEXT,
                status TEXT,
                started_at REAL,
                completed_at REAL,
                message TEXT,
                payload TEXT,
                PRIMARY KEY(run_id, stage)
            )"""
        )
        con.execute(
            """CREATE TABLE IF NOT EXISTS tasks(
                rel_key TEXT PRIMARY KEY,
                run_id TEXT,
                kind TEXT,
                rel_path TEXT,
                abs_path TEXT,
                output_md TEXT,
                priority INTEGER,
                reason TEXT,
                status TEXT,
                attempts INTEGER DEFAULT 0,
                max_attempts INTEGER DEFAULT 3,
                worker_id TEXT,
                started_at REAL,
                updated_at REAL,
                completed_at REAL,
                not_before REAL,
                last_error TEXT
            )"""
        )
        con.execute(
            """CREATE TABLE IF NOT EXISTS workers(
                worker_id TEXT PRIMARY KEY,
                run_id TEXT,
                status TEXT,
                current_task TEXT,
                pid INTEGER,
                started_at REAL,
                updated_at REAL,
                stopped_at REAL,
                last_error TEXT
            )"""
        )
        con.execute(
            """CREATE TABLE IF NOT EXISTS signals(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                type TEXT,
                payload TEXT,
                at REAL
            )"""
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status_priority ON tasks(status, priority)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_tasks_run_status ON tasks(run_id, status)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_signals_run_id ON signals(run_id, id)")
        task_columns = {row["name"] for row in con.execute("PRAGMA table_info(tasks)").fetchall()}
        if "doc_depth" not in task_columns:
            con.execute("ALTER TABLE tasks ADD COLUMN doc_depth TEXT DEFAULT 'deep'")
        if "parent_summary_only" not in task_columns:
            con.execute("ALTER TABLE tasks ADD COLUMN parent_summary_only INTEGER DEFAULT 0")


def atomic_write_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    finally:
        try:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        except OSError:
            pass


def atomic_write_json(path: Path, obj: Any) -> None:
    atomic_write_text(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def sanitize_markdown_text(text: str) -> str:
    if not text:
        return text
    return MARKDOWN_URL_RE.sub("[URL已移除]", text)


def sanitize_markdown_tree(root: Path, *, exclude_dirs: tuple[str, ...] = ("codex_debug",)) -> None:
    root = Path(root)
    if not root.exists():
        return
    for path in root.rglob("*.md"):
        if any(part in exclude_dirs for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        sanitized = sanitize_markdown_text(text)
        if sanitized != text:
            atomic_write_text(path, sanitized)


def clear_terminal_state(out: Path) -> None:
    for name in STATE_FILES.values():
        try:
            (Path(out) / name).unlink()
        except FileNotFoundError:
            pass


def write_terminal_state(out: Path, status: str, payload: dict[str, Any] | None = None) -> None:
    if status not in STATE_FILES:
        raise ValueError(f"unsupported terminal status: {status}")
    clear_terminal_state(out)
    data = {"status": status, "at": utc_ts(), "payload": payload or {}}
    atomic_write_json(Path(out) / STATE_FILES[status], data)


def create_run(
    out: Path,
    run_id: str,
    repo: Path,
    *,
    model: str = MODEL,
    reasoning: str = TASK_REASONING,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> None:
    init_state_db(out)
    ts = utc_ts()
    with connect_state(out) as con:
        con.execute(
            """INSERT OR REPLACE INTO pipeline_runs(
                run_id, repo, out, status, model, reasoning, timeout_seconds,
                started_at, updated_at, completed_at, message
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (run_id, str(repo), str(out), "running", model, reasoning, timeout_seconds, ts, ts, None, ""),
        )
    render_progress_json_from_db(out, run_id)


def ensure_run(
    out: Path,
    run_id: str,
    repo: Path | None = None,
    *,
    model: str = MODEL,
    reasoning: str = TASK_REASONING,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> None:
    init_state_db(out)
    ts = utc_ts()
    repo_text = str(repo) if repo is not None else ""
    with connect_state(out) as con:
        row = con.execute("SELECT run_id FROM pipeline_runs WHERE run_id=?", (run_id,)).fetchone()
        if row:
            con.execute(
                """UPDATE pipeline_runs
                   SET repo=COALESCE(NULLIF(?, ''), repo),
                       out=?,
                       model=?,
                       reasoning=?,
                       timeout_seconds=?,
                       updated_at=?
                   WHERE run_id=?""",
                (repo_text, str(out), model, reasoning, timeout_seconds, ts, run_id),
            )
        else:
            con.execute(
                """INSERT INTO pipeline_runs(
                    run_id, repo, out, status, model, reasoning, timeout_seconds,
                    started_at, updated_at, completed_at, message
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (run_id, repo_text, str(out), "running", model, reasoning, timeout_seconds, ts, ts, None, ""),
            )
    render_progress_json_from_db(out, run_id)


def update_run_status(out: Path, run_id: str, status: str, message: str = "") -> None:
    ts = utc_ts()
    completed = ts if status in {"completed", "partial", "failed"} else None
    with connect_state(out) as con:
        con.execute(
            """UPDATE pipeline_runs
               SET status=?, message=?, updated_at=?, completed_at=COALESCE(?, completed_at)
               WHERE run_id=?""",
            (status, message, ts, completed, run_id),
        )
    render_progress_json_from_db(out, run_id)


def set_stage_status(
    out: Path,
    run_id: str,
    stage: str,
    status: str,
    *,
    message: str = "",
    payload: dict[str, Any] | None = None,
) -> None:
    ts = utc_ts()
    with connect_state(out) as con:
        row = con.execute(
            "SELECT started_at FROM stages WHERE run_id=? AND stage=?",
            (run_id, stage),
        ).fetchone()
        started = row["started_at"] if row else ts
        completed = ts if status in {"completed", "failed", "skipped"} else None
        con.execute(
            """INSERT INTO stages(run_id, stage, status, started_at, completed_at, message, payload)
               VALUES(?,?,?,?,?,?,?)
               ON CONFLICT(run_id, stage) DO UPDATE SET
                 status=excluded.status,
                 started_at=COALESCE(stages.started_at, excluded.started_at),
                 completed_at=excluded.completed_at,
                 message=excluded.message,
                 payload=excluded.payload""",
            (run_id, stage, status, started, completed, message, json.dumps(payload or {}, ensure_ascii=False)),
        )
    render_progress_json_from_db(out, run_id)


def emit_signal(out: Path, run_id: str, signal_type: str, payload: dict[str, Any] | None = None) -> int:
    init_state_db(out)
    ts = utc_ts()
    with connect_state(out) as con:
        cur = con.execute(
            "INSERT INTO signals(run_id, type, payload, at) VALUES(?,?,?,?)",
            (run_id, signal_type, json.dumps(payload or {}, ensure_ascii=False), ts),
        )
        signal_id = int(cur.lastrowid)
    return signal_id


def _latest_signal(con: sqlite3.Connection, run_id: str) -> sqlite3.Row | None:
    return con.execute(
        "SELECT * FROM signals WHERE run_id=? ORDER BY id DESC LIMIT 1",
        (run_id,),
    ).fetchone()


def render_progress_json_from_db(out: Path, run_id: str) -> dict[str, Any]:
    out = Path(out)
    init_state_db(out)
    with connect_state(out) as con:
        run = con.execute("SELECT * FROM pipeline_runs WHERE run_id=?", (run_id,)).fetchone()
        stage_row = con.execute(
            """SELECT * FROM stages WHERE run_id=?
               ORDER BY CASE status WHEN 'running' THEN 0 ELSE 1 END, started_at DESC
               LIMIT 1""",
            (run_id,),
        ).fetchone()
        rows = con.execute(
            "SELECT status, COUNT(*) AS n FROM tasks WHERE run_id=? GROUP BY status",
            (run_id,),
        ).fetchall()
        breakdown = {str(r["status"]): int(r["n"]) for r in rows}
        skipped = breakdown.get("skipped", 0)
        active_breakdown = {k: int(breakdown.get(k, 0)) for k in ("pending", "running", "done", "failed")}
        total = sum(active_breakdown.values())
        done = active_breakdown.get("done", 0)
        failed = active_breakdown.get("failed", 0)
        active_rows = con.execute(
            """SELECT worker_id, current_task, updated_at FROM workers
               WHERE run_id=? AND status='running'
               ORDER BY worker_id""",
            (run_id,),
        ).fetchall()
        last_success = con.execute(
            """SELECT rel_path FROM tasks
               WHERE run_id=? AND status='done'
               ORDER BY completed_at DESC LIMIT 1""",
            (run_id,),
        ).fetchone()
        last_error = con.execute(
            """SELECT last_error FROM tasks
               WHERE run_id=? AND last_error IS NOT NULL AND last_error <> ''
               ORDER BY updated_at DESC LIMIT 1""",
            (run_id,),
        ).fetchone()
        current_task = con.execute(
            """SELECT rel_path FROM tasks
               WHERE run_id=? AND status='running'
               ORDER BY started_at DESC LIMIT 1""",
            (run_id,),
        ).fetchone()
        sig = _latest_signal(con, run_id)

    run_status = run["status"] if run else "running"
    stage = stage_row["stage"] if stage_row else ""
    current = current_task["rel_path"] if current_task else ""
    if not current and sig:
        current = f"{sig['type']}"
    progress = {
        "status": run_status,
        "done": done,
        "total": total,
        "percent": round(done / total * 100, 2) if total else 0,
        "failed": failed,
        "skipped": skipped,
        "core_done": done,
        "core_total": total,
        "current": current,
        "updated_at": utc_ts(),
        "unit": "核心文档",
        "coverage": "认知地图生成",
        "model": run["model"] if run else MODEL,
        "reasoning": run["reasoning"] if run else TASK_REASONING,
        "timeout_seconds": int(run["timeout_seconds"]) if run and run["timeout_seconds"] is not None else DEFAULT_TIMEOUT_SECONDS,
        "last_success": last_success["rel_path"] if last_success else None,
        "last_error": last_error["last_error"] if last_error else None,
        "run_id": run_id,
        "stage": stage,
        "active_workers": [
            {"worker_id": r["worker_id"], "current_task": r["current_task"], "updated_at": r["updated_at"]}
            for r in active_rows
        ],
        "task_breakdown": {**breakdown, **active_breakdown},
    }
    atomic_write_json(out / "progress.json", progress)
    return progress


def markdown_non_ws_len(text: str) -> int:
    return len(re.sub(r"\s+", "", text or ""))


def validate_markdown(
    text: str,
    *,
    min_chars: int,
    required_headings: list[str] | tuple[str, ...] = (),
    must_contain: str | None = None,
) -> tuple[bool, str]:
    stripped = (text or "").strip()
    if not stripped:
        return False, "empty markdown"
    size = markdown_non_ws_len(stripped)
    if size < min_chars:
        return False, f"too short: {size} non-whitespace chars < {min_chars}"
    if not re.search(r"^#\s+", stripped, flags=re.M):
        return False, "missing top-level heading"
    if must_contain and must_contain not in stripped:
        return False, f"missing target path: {must_contain}"
    missing = [h for h in required_headings if h not in stripped]
    if missing:
        return False, "missing headings: " + ", ".join(missing)
    banned = ["后续会补全", "只可参考", "我将查看", "我会查看"]
    for phrase in banned:
        if phrase in stripped:
            return False, f"contains banned phrase: {phrase}"
    return True, "ok"


def strip_codex_output(text: str) -> str:
    text = (text or "").strip()
    if "\ncodex\n" in text:
        text = text.split("\ncodex\n")[-1]
    text = re.sub(r"\ntokens used\n[\s\S]*$", "", text).strip()
    return text


def find_codex_bin() -> str:
    env = os.environ.get("CODEX_BIN")
    if env:
        return env
    found = shutil.which("codex")
    if found:
        return found
    raise FileNotFoundError("codex CLI not found; set CODEX_BIN or install codex")


def run_process_group(
    cmd: list[str],
    *,
    cwd: Path,
    timeout: int,
    input_text: str | None = None,
) -> tuple[int, str, bool]:
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    timed_out = False
    try:
        output, _ = proc.communicate(input=input_text, timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            output, _ = proc.communicate(timeout=20)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            output, _ = proc.communicate(timeout=20)
    return int(proc.returncode or 0), output or "", timed_out


def run_codex_exec(
    *,
    repo: Path,
    prompt: str,
    timeout: int,
    model: str = MODEL,
    reasoning: str = TASK_REASONING,
    sandbox_mode: str = "read-only",
    output_path: Path | None = None,
    add_dirs: list[Path] | None = None,
) -> tuple[int, str, bool]:
    cmd = [
        find_codex_bin(),
        "exec",
        "--skip-git-repo-check",
        "--cd",
        str(repo),
        "-m",
        model,
        "-c",
        f'model_reasoning_effort="{reasoning}"',
        "-c",
        f'sandbox_mode="{sandbox_mode}"',
    ]
    for extra in add_dirs or []:
        cmd.extend(["--add-dir", str(extra)])
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cmd.extend(["-o", str(output_path)])
    cmd.append(prompt)
    return run_process_group(cmd, cwd=repo, timeout=timeout)


def task_counts(out: Path, run_id: str) -> dict[str, int]:
    with connect_state(out) as con:
        rows = con.execute(
            "SELECT status, COUNT(*) AS n FROM tasks WHERE run_id=? GROUP BY status",
            (run_id,),
        ).fetchall()
    return {str(r["status"]): int(r["n"]) for r in rows}


def stage_failed(out: Path, run_id: str, stage: str) -> bool:
    with connect_state(out) as con:
        row = con.execute(
            "SELECT status FROM stages WHERE run_id=? AND stage=?",
            (run_id, stage),
        ).fetchone()
    return bool(row and row["status"] == "failed")
