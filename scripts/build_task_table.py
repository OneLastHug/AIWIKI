#!/usr/bin/env python3
"""Stage B: build and persist the local documentation task table."""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from _common import (
    atomic_write_text,
    connect_state,
    emit_signal,
    ensure_run,
    init_state_db,
    normalize_rel_path,
    output_md_for,
    rel_key_for,
    render_progress_json_from_db,
    set_stage_status,
)

MAX_FILE_SIZE = 200_000
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "dist",
    "build",
    "target",
    ".next",
    "coverage",
    ".venv",
    "venv",
    "__pycache__",
    ".idea",
    ".vscode",
    ".turbo",
    ".vercel",
    ".cache",
    "tmp",
    "temp",
    "vendor",
    ".gradle",
}
SECRET_NAMES = {".env", ".env.local", ".npmrc", "id_rsa", "id_dsa", "id_ed25519", "credentials.json"}
SECRET_EXTS = {".pem", ".key", ".p12", ".pfx", ".crt", ".cer"}
CODE_EXTS = {
    ".py",
    ".js",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".kt",
    ".go",
    ".rs",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".rb",
    ".php",
    ".swift",
    ".scala",
    ".sh",
    ".bash",
    ".zsh",
    ".sql",
    ".vue",
    ".svelte",
    ".css",
    ".scss",
    ".less",
    ".html",
    ".htm",
    ".json",
    ".jsonc",
    ".yaml",
    ".yml",
    ".toml",
    ".xml",
    ".graphql",
    ".proto",
    ".prisma",
    ".mdx",
}
IMPORTANT_NAMES = {
    "README.md",
    "package.json",
    "pyproject.toml",
    "setup.py",
    "requirements.txt",
    "pom.xml",
    "build.gradle",
    "settings.gradle",
    "Cargo.toml",
    "go.mod",
    "Makefile",
    "CMakeLists.txt",
    "composer.json",
    "Gemfile",
    "pnpm-workspace.yaml",
    "turbo.json",
    "next.config.js",
    "next.config.mjs",
    "next.config.ts",
    "vite.config.ts",
    "Dockerfile",
}
KEYWORDS = [
    "main",
    "app",
    "server",
    "route",
    "router",
    "controller",
    "service",
    "store",
    "schema",
    "model",
    "config",
    "provider",
    "runtime",
    "database",
    "index",
]


@dataclass
class Task:
    priority: int
    priority_label: str
    kind: str
    rel_path: str
    abs_path: str
    output_md: str
    reason: str

    @property
    def rel_key(self) -> str:
        return rel_key_for(self.kind, self.rel_path)


def priority_base(label: str) -> int:
    return {"P0": 0, "P1": 1000, "P2": 2000}.get(label.upper(), 3000)


def item_path(item: Any) -> str:
    if isinstance(item, str):
        value = item
    elif isinstance(item, dict):
        value = item.get("path") or item.get("rel_path") or item.get("file") or item.get("directory") or ""
    else:
        value = ""
    try:
        return normalize_rel_path(str(value))
    except Exception:
        return ""


def item_priority(item: Any, default: str) -> str:
    if isinstance(item, dict):
        value = str(item.get("priority") or default).upper()
        if value in {"P0", "P1", "P2"}:
            return value
    return default


def load_critical(out: Path) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    path = out / "critical_paths.json"
    if not path.exists():
        return [], []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return [], []
    dirs: list[tuple[str, str]] = []
    files: list[tuple[str, str]] = []
    for item in data.get("critical_directories") or data.get("directories") or []:
        rel = item_path(item)
        if rel:
            dirs.append((rel, item_priority(item, "P0")))
    for item in data.get("critical_files") or data.get("files") or []:
        rel = item_path(item)
        if rel:
            files.append((rel, item_priority(item, "P0")))
    return dirs, files


def should_skip_file(path: Path) -> bool:
    name = path.name
    if name in SECRET_NAMES or path.suffix.lower() in SECRET_EXTS:
        return True
    try:
        if path.stat().st_size > MAX_FILE_SIZE:
            return True
    except OSError:
        return True
    if name in IMPORTANT_NAMES:
        return False
    if name.lower().startswith("readme") and path.suffix.lower() in {".md", ".mdx"}:
        return False
    return path.suffix.lower() not in CODE_EXTS


def scan_files(repo: Path) -> list[tuple[str, int]]:
    files: list[tuple[str, int]] = []
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for filename in filenames:
            path = Path(dirpath) / filename
            if should_skip_file(path):
                continue
            try:
                rel = normalize_rel_path(path.relative_to(repo).as_posix())
                size = path.stat().st_size
            except Exception:
                continue
            files.append((rel, size))
    return files


def auto_file_priority(rel: str, size: int) -> int:
    parts = rel.split("/")
    name = parts[-1]
    score = 0
    if len(parts) == 1 and name in IMPORTANT_NAMES:
        score += 100
    if parts[0] in {"src", "app", "apps", "packages", "lib", "server"}:
        score += 80
    low = rel.lower()
    for i, token in enumerate(KEYWORDS):
        if token in low:
            score += max(4, 30 - i)
    if name.startswith("index."):
        score += 25
    if ".test." in rel or ".spec." in rel or "__tests__" in rel:
        score -= 60
    score -= min(40, rel.count("/") * 4)
    score -= min(40, size // 25_000)
    return 5000 - score


def make_task(repo: Path, kind: str, rel_path: str, priority: int, label: str, reason: str) -> Task | None:
    rel_path = normalize_rel_path(rel_path)
    abs_path = (repo / rel_path).resolve()
    if not abs_path.exists():
        return None
    if kind == "directory" and not abs_path.is_dir():
        return None
    if kind == "file" and not abs_path.is_file():
        return None
    return Task(
        priority=priority,
        priority_label=label,
        kind=kind,
        rel_path=rel_path,
        abs_path=str(abs_path),
        output_md=output_md_for(kind, rel_path),
        reason=reason,
    )


def add_or_raise(tasks: dict[str, Task], task: Task | None) -> None:
    if not task:
        return
    old = tasks.get(task.rel_key)
    if old is None or task.priority < old.priority:
        tasks[task.rel_key] = task


def parent_dirs(rel_path: str) -> list[str]:
    parts = normalize_rel_path(rel_path).split("/")[:-1]
    parents: list[str] = []
    for i in range(1, len(parts) + 1):
        parents.append("/".join(parts[:i]))
    return parents


def choose_tasks(repo: Path, out: Path, max_tasks: int) -> tuple[list[Task], int]:
    critical_dirs, critical_files = load_critical(out)
    selected: dict[str, Task] = {}
    all_candidates: set[str] = set()
    max_tasks = max(0, max_tasks)

    def select_bundle(bundle: list[Task]) -> bool:
        for task in bundle:
            all_candidates.add(task.rel_key)
        needed = [t for t in bundle if t.rel_key not in selected]
        if len(selected) + len(needed) > max_tasks:
            return False
        for task in needed:
            selected[task.rel_key] = task
        return True

    for idx, (rel, label) in enumerate(critical_dirs):
        task = make_task(repo, "directory", rel, priority_base(label) + idx, label, f"critical-from-overview:{label}")
        select_bundle([task] if task else [])

    for idx, (rel, label) in enumerate(critical_files):
        base = priority_base(label) + 100 + idx
        bundle: list[Task] = []
        for depth, parent in enumerate(parent_dirs(rel)):
            parent_task = make_task(repo, "directory", parent, base - 20 + depth, label, f"parent-of-critical:{rel}")
            if parent_task:
                bundle.append(parent_task)
        file_task = make_task(repo, "file", rel, base, label, f"critical-from-overview:{label}")
        if file_task:
            bundle.append(file_task)
        select_bundle(bundle)

    candidates: list[Task] = []
    for rel, size in scan_files(repo):
        priority = auto_file_priority(rel, size)
        task = make_task(repo, "file", rel, priority, "P2", "auto-local-scan")
        if task:
            candidates.append(task)
    candidates.sort(key=lambda t: (t.priority, t.rel_path))

    for file_task in candidates:
        bundle = []
        for depth, parent in enumerate(parent_dirs(file_task.rel_path)):
            parent_task = make_task(
                repo,
                "directory",
                parent,
                max(0, file_task.priority - 30 + depth),
                file_task.priority_label,
                f"parent-of-file:{file_task.rel_path}",
            )
            if parent_task:
                bundle.append(parent_task)
        bundle.append(file_task)
        if not select_bundle(bundle):
            continue

    tasks = sorted(selected.values(), key=lambda t: (t.priority, 0 if t.kind == "directory" else 1, t.rel_path))
    dropped = len(all_candidates - set(selected))
    return tasks, dropped


def write_csv(out: Path, tasks: list[Task]) -> None:
    fieldnames = ["rel_key", "priority", "priority_label", "kind", "rel_path", "abs_path", "output_md", "reason"]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for task in tasks:
        writer.writerow(
            {
                "rel_key": task.rel_key,
                "priority": task.priority,
                "priority_label": task.priority_label,
                "kind": task.kind,
                "rel_path": task.rel_path,
                "abs_path": task.abs_path,
                "output_md": task.output_md,
                "reason": task.reason,
            }
        )
    atomic_write_text(out / "codex_task_table.csv", buf.getvalue())


def persist_tasks(out: Path, run_id: str, tasks: list[Task]) -> None:
    ts = time.time()
    with connect_state(out) as con:
        for task in tasks:
            con.execute(
                """INSERT INTO tasks(
                    rel_key, run_id, kind, rel_path, abs_path, output_md, priority, reason,
                    status, attempts, max_attempts, worker_id, started_at, updated_at,
                    completed_at, not_before, last_error
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(rel_key) DO UPDATE SET
                    run_id=excluded.run_id,
                    kind=excluded.kind,
                    rel_path=excluded.rel_path,
                    abs_path=excluded.abs_path,
                    output_md=excluded.output_md,
                    priority=excluded.priority,
                    reason=excluded.reason,
                    status=CASE WHEN tasks.status='done' THEN 'done' ELSE 'pending' END,
                    attempts=CASE WHEN tasks.status='done' THEN tasks.attempts ELSE 0 END,
                    max_attempts=excluded.max_attempts,
                    worker_id=NULL,
                    started_at=NULL,
                    updated_at=excluded.updated_at,
                    completed_at=CASE WHEN tasks.status='done' THEN tasks.completed_at ELSE NULL END,
                    not_before=NULL,
                    last_error=CASE WHEN tasks.status='done' THEN tasks.last_error ELSE NULL END""",
                (
                    task.rel_key,
                    run_id,
                    task.kind,
                    task.rel_path,
                    task.abs_path,
                    task.output_md,
                    task.priority,
                    task.reason,
                    "pending",
                    0,
                    3,
                    None,
                    None,
                    ts,
                    None,
                    None,
                    None,
                ),
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage B: build local Codex task table.")
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--max-tasks", type=int, default=500)
    args = parser.parse_args()

    repo = args.repo.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    init_state_db(out)
    ensure_run(out, args.run_id, repo)
    set_stage_status(out, args.run_id, "B", "running", message="Stage B task table running")
    emit_signal(out, args.run_id, "STAGE_STARTED", {"stage": "B", "repo": str(repo), "out": str(out)})

    try:
        tasks, dropped = choose_tasks(repo, out, args.max_tasks)
        write_csv(out, tasks)
        persist_tasks(out, args.run_id, tasks)
        payload = {
            "stage": "B",
            "total": len(tasks),
            "truncated": dropped > 0,
            "dropped": dropped,
            "max_tasks": args.max_tasks,
            "csv": str(out / "codex_task_table.csv"),
        }
        set_stage_status(out, args.run_id, "B", "completed", message="Stage B task table completed", payload=payload)
        emit_signal(out, args.run_id, "STAGE_COMPLETED", payload)
        render_progress_json_from_db(out, args.run_id)
        return 0
    except Exception as exc:
        payload = {"stage": "B", "error": str(exc)}
        set_stage_status(out, args.run_id, "B", "failed", message=str(exc), payload=payload)
        emit_signal(out, args.run_id, "STAGE_FAILED", payload)
        render_progress_json_from_db(out, args.run_id)
        return 1


if __name__ == "__main__":
    sys.exit(main())
