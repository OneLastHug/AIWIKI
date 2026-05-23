#!/usr/bin/env python3
"""Stage C: concurrent Codex task pool."""
from __future__ import annotations

import argparse
import asyncio
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from _common import (
    DEFAULT_TIMEOUT_SECONDS,
    MODEL,
    TASK_REASONING,
    atomic_write_text,
    connect_state,
    emit_signal,
    ensure_run,
    find_codex_bin,
    init_state_db,
    render_progress_json_from_db,
    safe_debug_name,
    sanitize_markdown_text,
    set_stage_status,
    strip_codex_output,
    task_counts,
    update_run_status,
    validate_markdown,
)
from local_fallback import is_codex_unavailable_output, task_fallback_markdown

DIRECTORY_OVERVIEW_HEADINGS = [
    "## 它负责什么",
    "## 直接子目录地图",
    "## 关键入口",
    "## 主流程位置",
    "## 推荐阅读顺序",
    "## 常见误区",
]
DIRECTORY_STANDARD_HEADINGS = [
    "## 解决什么问题",
    "## 相关目录和文件",
    "## 核心对象",
    "## 运行流程",
    "## 上下游依赖",
    "## 修改时最容易踩的坑",
    "## 推荐阅读顺序",
]
FILE_DEEP_HEADINGS = [
    "## 一句话定位",
    "## 它暴露/定义了什么",
    "## 谁调用它",
    "## 它调用谁",
    "## 核心流程",
    "## 关键函数的高层作用",
    "## 修改风险",
]

stop_event: asyncio.Event | None = None
signal_count = 0
worker_ids: list[str] = []
codex_unavailable_seen = False


def build_prompt(repo: Path, task: dict[str, Any]) -> str:
    rel = task["rel_path"]
    kind = task["kind"]
    depth = str(task.get("doc_depth") or ("deep" if kind == "file" else "standard"))
    kind_cn = "目录" if kind == "directory" else "文件"
    url_note = "不要输出真实网址；如必须提到链接、仓库地址或外部服务地址，请写成 `[URL已移除]`。"

    if kind == "directory" and depth == "overview":
        title = f"# 目录：{rel}"
        guidance = f"""- 只做地图式概览，不逐文件展开。
- 重点说明这个目录下面有什么子目录、关键入口和主流程位置。
- 文档控制在 1200-2200 中文字左右。
- 如果这里是大目录，只讲路径角色，不要把每个叶子都解释一遍。"""
        sections = DIRECTORY_OVERVIEW_HEADINGS
    elif kind == "directory":
        title = f"# 子系统：{rel}"
        guidance = f"""- 这是子系统级页面，不是文件清单。
- 重点解释这个目录负责什么、相关目录文件、核心对象和上下游依赖。
- 不要逐行解释源码，也不要把所有叶子目录都铺开。
- 文档控制在 900-1600 中文字左右。"""
        sections = DIRECTORY_STANDARD_HEADINGS
    else:
        title = f"# 文件：{rel}"
        guidance = f"""- 这是关键文件页，不要逐行解释。
- 只讲高层职责、谁调用它、它调用谁、核心流程和修改风险。
- 核心函数可以解释，辅助函数一句带过，样板函数不需要展开。
- 文档控制在 700-1300 中文字左右。"""
        sections = FILE_DEEP_HEADINGS

    section_text = "\n".join(sections)
    return f"""你是 AIWIKI 的源码学习文档作者。现在只处理一个任务，读取仓库上下文后输出这个目标的中文学习文档。

仓库根目录：{repo}
目标类型：{kind_cn}
目标相对路径：{rel}
目标绝对路径：{task["abs_path"]}
文档深度：{depth}

执行要求：
- 你可以读取目标路径和必要的邻近上下文，但不要修改仓库文件。
- 每个任务最多执行 6 个 shell 命令。
- {guidance}
- 中文为主，路径、函数名、类名、包名、命令保留英文。
- 如果证据不足，写“根据当前片段推断”，并说明依据。
- 不要把本地源码路径写成 Markdown 链接；不要输出 `[path](/data/project/...:1)`、`[path](path.ts:1)` 这类引用。源码引用只写反引号代码路径，例如 `src/app/(backend)/api/version/route.ts`。多个路径之间用中文顿号、逗号或分号隔开，路径前后保留正常文字间隔，避免粘连。
- {url_note}
- 最终只输出 Markdown 正文，不要输出命令执行过程，不要寒暄。

必须包含这些章节：
{title}
{section_text}
"""


def required_headings_for(task: dict[str, Any]) -> tuple[list[str], int]:
    kind = task["kind"]
    depth = str(task.get("doc_depth") or ("deep" if kind == "file" else "standard"))
    if kind == "directory" and depth == "overview":
        return DIRECTORY_OVERVIEW_HEADINGS, 1000
    if kind == "directory":
        return DIRECTORY_STANDARD_HEADINGS, 900
    return FILE_DEEP_HEADINGS, 700


def validate_task_markdown(task: dict[str, Any], text: str) -> tuple[bool, str]:
    headings, min_chars = required_headings_for(task)
    return validate_markdown(
        sanitize_markdown_text(text),
        min_chars=min_chars,
        required_headings=headings,
        must_contain=task["rel_path"],
    )


def register_worker(out: Path, run_id: str, worker_id: str) -> None:
    ts = time.time()
    with connect_state(out) as con:
        con.execute(
            """INSERT INTO workers(worker_id, run_id, status, current_task, pid, started_at, updated_at, stopped_at, last_error)
               VALUES(?,?,?,?,?,?,?,?,?)
               ON CONFLICT(worker_id) DO UPDATE SET
                 run_id=excluded.run_id,
                 status='running',
                 current_task=NULL,
                 pid=excluded.pid,
                 started_at=excluded.started_at,
                 updated_at=excluded.updated_at,
                 stopped_at=NULL,
                 last_error=NULL""",
            (worker_id, run_id, "running", None, os.getpid(), ts, ts, None, None),
        )
    worker_ids.append(worker_id)
    emit_signal(out, run_id, "WORKER_STARTED", {"worker_id": worker_id})


def stop_worker_row(out: Path, run_id: str, worker_id: str, error: str | None = None) -> None:
    ts = time.time()
    with connect_state(out) as con:
        con.execute(
            """UPDATE workers
               SET status='stopped', current_task=NULL, updated_at=?, stopped_at=?, last_error=?
               WHERE worker_id=?""",
            (ts, ts, error, worker_id),
        )
    emit_signal(out, run_id, "WORKER_STOPPED", {"worker_id": worker_id, "error": error})


def set_worker_current(out: Path, worker_id: str, rel_key: str | None) -> None:
    with connect_state(out) as con:
        con.execute(
            "UPDATE workers SET current_task=?, updated_at=? WHERE worker_id=?",
            (rel_key, time.time(), worker_id),
        )


def release_running_tasks(out: Path, run_id: str, reason: str) -> int:
    ts = time.time()
    with connect_state(out) as con:
        cur = con.execute(
            """UPDATE tasks
               SET status='pending', worker_id=NULL, started_at=NULL, updated_at=?, not_before=?, last_error=?
               WHERE run_id=? AND status='running'""",
            (ts, ts, reason, run_id),
        )
        count = cur.rowcount
        con.execute(
            """UPDATE workers SET status='stopped', current_task=NULL, updated_at=?, stopped_at=?, last_error=?
               WHERE run_id=? AND status='running'""",
            (ts, ts, reason, run_id),
        )
    return int(count or 0)


def acquire_next_task(out: Path, run_id: str, worker_id: str, task_timeout: int) -> dict[str, Any] | None:
    now = time.time()
    stale_cutoff = now - max(task_timeout + 60, 120)
    recovered: list[dict[str, Any]] = []
    con = connect_state(out)
    con.isolation_level = None
    try:
        con.execute("BEGIN IMMEDIATE")
        stale_rows = con.execute(
            """SELECT rel_key, rel_path, attempts, max_attempts, worker_id FROM tasks
               WHERE run_id=? AND status='running' AND started_at IS NOT NULL AND started_at < ?""",
            (run_id, stale_cutoff),
        ).fetchall()
        for row in stale_rows:
            attempts = int(row["attempts"] or 0)
            max_attempts = int(row["max_attempts"] or 3)
            if attempts >= max_attempts:
                con.execute(
                    """UPDATE tasks
                       SET status='failed', worker_id=NULL, updated_at=?, completed_at=?, last_error=?
                       WHERE rel_key=?""",
                    (
                        now,
                        now,
                        f"stale running task recovered from {row['worker_id']} after max attempts",
                        row["rel_key"],
                    ),
                )
            else:
                con.execute(
                    """UPDATE tasks
                       SET status='pending', worker_id=NULL, started_at=NULL, updated_at=?, not_before=?, last_error=?
                       WHERE rel_key=?""",
                    (
                        now,
                        now,
                        f"stale running task recovered from {row['worker_id']}",
                        row["rel_key"],
                    ),
                )
            recovered.append({"rel_key": row["rel_key"], "rel_path": row["rel_path"], "previous_worker": row["worker_id"]})

        row = con.execute(
            """SELECT * FROM tasks
               WHERE run_id=? AND status='pending' AND (not_before IS NULL OR not_before <= ?)
               ORDER BY priority ASC, rel_path ASC
               LIMIT 1""",
            (run_id, now),
        ).fetchone()
        task = None
        if row:
            cur = con.execute(
                """UPDATE tasks
                   SET status='running', attempts=attempts+1, worker_id=?, started_at=?, updated_at=?
                   WHERE rel_key=? AND status='pending'""",
                (worker_id, now, now, row["rel_key"]),
            )
            if cur.rowcount == 1:
                task = con.execute("SELECT * FROM tasks WHERE rel_key=?", (row["rel_key"],)).fetchone()
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()

    for item in recovered:
        emit_signal(out, run_id, "WORKER_ZOMBIE_RECOVERED", item)
    if not task:
        return None
    return dict(task)


def has_unfinished_tasks(out: Path, run_id: str) -> bool:
    with connect_state(out) as con:
        row = con.execute(
            "SELECT COUNT(*) AS n FROM tasks WHERE run_id=? AND status IN ('pending','running')",
            (run_id,),
        ).fetchone()
    return bool(row and int(row["n"]) > 0)


def mark_success(out: Path, run_id: str, worker_id: str, task: dict[str, Any]) -> None:
    ts = time.time()
    with connect_state(out) as con:
        con.execute(
            """UPDATE tasks
               SET status='done', worker_id=NULL, updated_at=?, completed_at=?, not_before=NULL, last_error=NULL
               WHERE rel_key=?""",
            (ts, ts, task["rel_key"]),
        )
        con.execute(
            "UPDATE workers SET current_task=NULL, updated_at=? WHERE worker_id=?",
            (ts, worker_id),
        )
    emit_signal(out, run_id, "TASK_COMPLETED", {"worker_id": worker_id, "rel_key": task["rel_key"], "rel_path": task["rel_path"]})


def mark_failure(out: Path, run_id: str, worker_id: str, task: dict[str, Any], reason: str) -> None:
    ts = time.time()
    attempts = int(task.get("attempts") or 0)
    max_attempts = int(task.get("max_attempts") or 3)
    if attempts < max_attempts:
        backoff = min(30, 5 * attempts)
        status = "pending"
        not_before = ts + backoff
        completed_at = None
        signal_type = "TASK_RETRYING"
        payload = {
            "worker_id": worker_id,
            "rel_key": task["rel_key"],
            "rel_path": task["rel_path"],
            "attempt": attempts,
            "max_attempts": max_attempts,
            "backoff_seconds": backoff,
            "error": reason,
        }
    else:
        status = "failed"
        not_before = None
        completed_at = ts
        signal_type = "TASK_FAILED"
        payload = {
            "worker_id": worker_id,
            "rel_key": task["rel_key"],
            "rel_path": task["rel_path"],
            "attempt": attempts,
            "max_attempts": max_attempts,
            "error": reason,
        }
    with connect_state(out) as con:
        con.execute(
            """UPDATE tasks
               SET status=?, worker_id=NULL, updated_at=?, completed_at=?, not_before=?, last_error=?
               WHERE rel_key=?""",
            (status, ts, completed_at, not_before, reason, task["rel_key"]),
        )
        con.execute(
            "UPDATE workers SET current_task=NULL, updated_at=? WHERE worker_id=?",
            (ts, worker_id),
        )
    emit_signal(out, run_id, signal_type, payload)


def codex_command(repo: Path, prompt: str, candidate_path: Path) -> list[str]:
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    return [
        find_codex_bin(),
        "exec",
        "--skip-git-repo-check",
        "--cd",
        str(repo),
        "-m",
        MODEL,
        "-c",
        f'model_reasoning_effort="{TASK_REASONING}"',
        "-c",
        'sandbox_mode="read-only"',
        "-o",
        str(candidate_path),
        prompt,
    ]


async def run_codex_async(repo: Path, prompt: str, candidate_path: Path, timeout: int) -> tuple[int, str, bool]:
    proc = await asyncio.create_subprocess_exec(
        *codex_command(repo, prompt, candidate_path),
        cwd=str(repo),
        stdin=subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        start_new_session=True,
    )
    timed_out = False
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        timed_out = True
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=20)
        except asyncio.TimeoutError:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=20)
    raw = (stdout or b"").decode("utf-8", errors="replace")
    return int(proc.returncode or 0), raw, timed_out


async def run_one(repo: Path, out: Path, task: dict[str, Any], timeout: int) -> tuple[bool, str]:
    global codex_unavailable_seen
    local_fallback_disabled = os.environ.get("AIWIKI_DISABLE_LOCAL_FALLBACK", "").lower() in {"1", "true", "yes"}
    debug = out / "codex_debug"
    debug.mkdir(parents=True, exist_ok=True)
    safe = safe_debug_name(task["rel_key"])
    prompt_path = debug / f"last_prompt_{safe}.txt"
    raw_path = debug / f"last_raw_{safe}.txt"
    candidate_path = debug / f"last_md_{safe}.md"
    final_path = out / task["output_md"]
    try:
        candidate_path.unlink()
    except FileNotFoundError:
        pass

    prompt = build_prompt(repo, task)
    atomic_write_text(prompt_path, prompt)
    if not local_fallback_disabled and (
        codex_unavailable_seen or os.environ.get("AIWIKI_FORCE_LOCAL_FALLBACK", "").lower() in {"1", "true", "yes"}
    ):
        atomic_write_text(raw_path, "Codex skipped because local fallback is active.\n")
        candidate = task_fallback_markdown(repo, task, "Codex CLI unavailable; using local fallback for remaining tasks")
        atomic_write_text(candidate_path, candidate)
        ok, reason = validate_task_markdown(task, candidate)
        if not ok:
            return False, "local fallback validation failed: " + reason
        atomic_write_text(final_path, sanitize_markdown_text(candidate).strip() + "\n")
        return True, "local fallback"
    code, raw, timed_out = await run_codex_async(repo, prompt, candidate_path, timeout)
    atomic_write_text(raw_path, raw)
    if timed_out:
        return False, f"timeout after {timeout}s; process group killed"
    if code != 0:
        if not local_fallback_disabled and is_codex_unavailable_output(raw):
            codex_unavailable_seen = True
            reason_text = strip_codex_output(raw)[-500:] or "Codex CLI unavailable"
            candidate = task_fallback_markdown(repo, task, reason_text)
            atomic_write_text(candidate_path, candidate)
            ok, reason = validate_task_markdown(task, candidate)
            if not ok:
                return False, "local fallback validation failed: " + reason
            atomic_write_text(final_path, sanitize_markdown_text(candidate).strip() + "\n")
            return True, "local fallback after Codex unavailable"
        return False, f"codex exited with {code}: {strip_codex_output(raw)[-1000:]}"

    candidate = ""
    if candidate_path.exists() and candidate_path.stat().st_size > 0:
        candidate = candidate_path.read_text(encoding="utf-8", errors="replace").strip()
    if not candidate:
        candidate = strip_codex_output(raw)

    ok, reason = validate_task_markdown(task, candidate)
    if not ok:
        atomic_write_text(candidate_path, candidate)
        return False, "validation failed: " + reason
    atomic_write_text(final_path, sanitize_markdown_text(candidate).strip() + "\n")
    return True, "ok"


async def worker_loop(repo: Path, out: Path, run_id: str, worker_id: str, timeout: int) -> None:
    register_worker(out, run_id, worker_id)
    error: str | None = None
    try:
        while stop_event is None or not stop_event.is_set():
            task = acquire_next_task(out, run_id, worker_id, timeout)
            if not task:
                if not has_unfinished_tasks(out, run_id):
                    break
                await asyncio.sleep(1)
                continue
            set_worker_current(out, worker_id, task["rel_key"])
            emit_signal(
                out,
                run_id,
                "TASK_STARTED",
                {"worker_id": worker_id, "rel_key": task["rel_key"], "rel_path": task["rel_path"], "attempt": task["attempts"]},
            )
            try:
                ok, reason = await run_one(repo, out, task, timeout)
            except Exception as exc:
                ok, reason = False, f"exception: {type(exc).__name__}: {exc}"
            if ok:
                mark_success(out, run_id, worker_id, task)
            else:
                mark_failure(out, run_id, worker_id, task, reason)
            render_progress_json_from_db(out, run_id)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        stop_worker_row(out, run_id, worker_id, error)


def install_signal_handlers(loop: asyncio.AbstractEventLoop, out: Path, run_id: str) -> None:
    def handler(signum: int, _frame: Any) -> None:
        global signal_count
        signal_count += 1
        if signal_count == 1:
            if stop_event is not None:
                loop.call_soon_threadsafe(stop_event.set)
            emit_signal(out, run_id, "PIPELINE_SIGNAL", {"signal": signum, "action": "stop-after-current"})
        else:
            released = release_running_tasks(out, run_id, f"interrupted by signal {signum}")
            emit_signal(out, run_id, "PIPELINE_SIGNAL", {"signal": signum, "action": "forced-exit", "released": released})
            os._exit(130)

    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)


async def run_pool(repo: Path, out: Path, run_id: str, concurrency: int, timeout: int) -> int:
    global stop_event
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    install_signal_handlers(loop, out, run_id)
    tasks = [
        asyncio.create_task(worker_loop(repo, out, run_id, f"{run_id[:8]}-w{i + 1}", timeout))
        for i in range(max(1, concurrency))
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    errors = [r for r in results if isinstance(r, Exception)]
    if errors:
        raise RuntimeError("; ".join(str(e) for e in errors[:3]))
    if stop_event.is_set() and has_unfinished_tasks(out, run_id):
        return 130
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage C: run concurrent Codex task pool.")
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args()

    repo = args.repo.resolve()
    out = args.out.resolve()
    init_state_db(out)
    ensure_run(out, args.run_id, repo, timeout_seconds=args.timeout)
    set_stage_status(out, args.run_id, "C", "running", message="Stage C parallel pool running")
    emit_signal(
        out,
        args.run_id,
        "STAGE_STARTED",
        {"stage": "C", "concurrency": args.concurrency, "timeout_seconds": args.timeout},
    )
    try:
        code = asyncio.run(run_pool(repo, out, args.run_id, args.concurrency, args.timeout))
        counts = task_counts(out, args.run_id)
        payload = {"stage": "C", "counts": counts, "concurrency": args.concurrency}
        if code == 130:
            set_stage_status(out, args.run_id, "C", "failed", message="Stage C interrupted", payload=payload)
            emit_signal(out, args.run_id, "STAGE_FAILED", {**payload, "error": "interrupted"})
            update_run_status(out, args.run_id, "failed", "Stage C interrupted")
            render_progress_json_from_db(out, args.run_id)
            return 130
        set_stage_status(out, args.run_id, "C", "completed", message="Stage C completed", payload=payload)
        emit_signal(out, args.run_id, "STAGE_COMPLETED", payload)
        failed = counts.get("failed", 0)
        update_run_status(
            out,
            args.run_id,
            "partial" if failed else "completed",
            "Stage C completed with failed tasks" if failed else "Stage C completed",
        )
        render_progress_json_from_db(out, args.run_id)
        return 0
    except Exception as exc:
        payload = {"stage": "C", "error": str(exc)}
        set_stage_status(out, args.run_id, "C", "failed", message=str(exc), payload=payload)
        emit_signal(out, args.run_id, "STAGE_FAILED", payload)
        update_run_status(out, args.run_id, "failed", str(exc))
        render_progress_json_from_db(out, args.run_id)
        return 1


if __name__ == "__main__":
    sys.exit(main())
