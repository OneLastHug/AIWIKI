#!/usr/bin/env python3
"""End-to-end AIWIKI documentation pipeline orchestrator."""
from __future__ import annotations

import argparse
import subprocess
import sys
import uuid
from pathlib import Path

from _common import (
    DEFAULT_TIMEOUT_SECONDS,
    MODEL,
    TASK_REASONING,
    atomic_write_text,
    clear_terminal_state,
    create_run,
    emit_signal,
    render_progress_json_from_db,
    set_stage_status,
    stage_failed,
    task_counts,
    update_run_status,
    write_terminal_state,
)


def run_child(out: Path, stage: str, cmd: list[str]) -> int:
    debug = out / "codex_debug"
    debug.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(cmd, text=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    atomic_write_text(debug / f"stage_{stage}_subprocess.txt", proc.stdout or "")
    return int(proc.returncode)


def finalize(out: Path, run_id: str, status: str, message: str, payload: dict) -> int:
    update_run_status(out, run_id, status, message)
    write_terminal_state(out, status if status in {"completed", "partial", "failed"} else "failed", {"message": message, **payload})
    signal_type = {
        "completed": "PIPELINE_COMPLETED",
        "partial": "PIPELINE_PARTIAL",
        "failed": "PIPELINE_FAILED",
    }.get(status, "PIPELINE_FAILED")
    emit_signal(out, run_id, signal_type, {"status": status, "message": message, **payload})
    render_progress_json_from_db(out, run_id)
    return 0 if status in {"completed", "partial"} else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the AIWIKI three-stage documentation pipeline.")
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--max-tasks", type=int, default=120)
    parser.add_argument("--skip-overview", action="store_true")
    args = parser.parse_args()

    repo = args.repo.resolve()
    out = args.out.resolve()
    scripts = Path(__file__).resolve().parent
    run_id = str(uuid.uuid4())
    out.mkdir(parents=True, exist_ok=True)
    clear_terminal_state(out)
    create_run(out, run_id, repo, model=MODEL, reasoning=TASK_REASONING, timeout_seconds=args.timeout)
    emit_signal(
        out,
        run_id,
        "PIPELINE_STARTED",
        {
            "repo": str(repo),
            "out": str(out),
            "concurrency": args.concurrency,
            "timeout_seconds": args.timeout,
            "max_tasks": args.max_tasks,
            "skip_overview": args.skip_overview,
        },
    )

    if args.skip_overview:
        set_stage_status(out, run_id, "A", "running", message="Stage A skipped by option")
        emit_signal(out, run_id, "STAGE_STARTED", {"stage": "A", "skipped": True})
        set_stage_status(out, run_id, "A", "skipped", message="Stage A skipped by option", payload={"skipped": True})
        emit_signal(out, run_id, "STAGE_COMPLETED", {"stage": "A", "skipped": True})
    else:
        code = run_child(
            out,
            "A",
            [
                sys.executable,
                str(scripts / "codex_overview.py"),
                "--repo",
                str(repo),
                "--out",
                str(out),
                "--run-id",
                run_id,
                "--timeout",
                str(args.timeout),
            ],
        )
        if code != 0:
            return finalize(out, run_id, "failed", "Stage A failed; pipeline stopped", {"stage": "A", "returncode": code})

    code = run_child(
        out,
        "B",
        [
            sys.executable,
            str(scripts / "build_task_table.py"),
            "--repo",
            str(repo),
            "--out",
            str(out),
            "--run-id",
            run_id,
            "--max-tasks",
            str(args.max_tasks),
        ],
    )
    if code != 0:
        return finalize(out, run_id, "failed", "Stage B failed; pipeline stopped", {"stage": "B", "returncode": code})

    code = run_child(
        out,
        "C",
        [
            sys.executable,
            str(scripts / "codex_parallel_pool.py"),
            "--repo",
            str(repo),
            "--out",
            str(out),
            "--run-id",
            run_id,
            "--concurrency",
            str(args.concurrency),
            "--timeout",
            str(args.timeout),
        ],
    )
    if code != 0:
        return finalize(out, run_id, "failed", "Stage C failed; pipeline stopped", {"stage": "C", "returncode": code})

    counts = task_counts(out, run_id)
    active_counts = {k: int(counts.get(k, 0)) for k in ("pending", "running", "done", "failed")}
    skipped = int(counts.get("skipped", 0))
    total = sum(active_counts.values())
    done = active_counts.get("done", 0)
    failed = active_counts.get("failed", 0)
    payload = {"counts": counts, "active_counts": active_counts, "skipped": skipped, "total": total, "done": done, "failed": failed}
    if stage_failed(out, run_id, "A") or stage_failed(out, run_id, "B") or stage_failed(out, run_id, "C"):
        return finalize(out, run_id, "failed", "A critical pipeline stage failed", payload)
    if failed:
        return finalize(out, run_id, "partial", "Pipeline completed with failed tasks", payload)
    if done == total:
        return finalize(out, run_id, "completed", "Pipeline completed successfully", payload)
    return finalize(out, run_id, "failed", "Pipeline ended with unfinished tasks", payload)


if __name__ == "__main__":
    sys.exit(main())
