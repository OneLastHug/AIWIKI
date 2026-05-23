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
class DirectoryMeta:
    rel_path: str
    abs_path: str
    direct_dirs: int
    direct_files: int
    has_readme: bool
    has_manifest: bool
    has_index: bool
    child_names: tuple[str, ...]


@dataclass
class Task:
    priority: int
    priority_label: str
    doc_depth: str
    kind: str
    rel_path: str
    abs_path: str
    output_md: str
    reason: str
    status: str
    parent_summary_only: bool

    @property
    def rel_key(self) -> str:
        return rel_key_for(self.kind, self.rel_path)


TOP_LEVEL_ROOTS = {"src", "app", "apps", "packages", "server", "routes", "lib", "docs"}
SELECTION_KEYWORDS = [
    "router",
    "route",
    "controller",
    "service",
    "store",
    "runtime",
    "provider",
    "config",
    "model",
    "schema",
    "domain",
    "infrastructure",
    "api",
    "auth",
    "task",
    "flow",
    "index",
    "main",
]
LOW_VALUE_KEYWORDS = [
    "test",
    "tests",
    "spec",
    "mocks",
    "mock",
    "fixture",
    "fixtures",
    "generated",
    "assets",
    "public",
    "locales",
    "snapshot",
    "snapshots",
    "coverage",
    "dist",
    "build",
    "vendor",
    "tmp",
    "temp",
]


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
        if value in {"A", "B", "C", "D", "P0", "P1", "P2"}:
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
            dirs.append((rel, item_priority(item, "A")))
    for item in data.get("critical_files") or data.get("files") or []:
        rel = item_path(item)
        if rel:
            files.append((rel, item_priority(item, "A")))
    return dirs, files


def is_secret_path(path: Path) -> bool:
    return path.name in SECRET_NAMES or path.suffix.lower() in SECRET_EXTS


def should_skip_file(path: Path) -> bool:
    name = path.name
    if is_secret_path(path):
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


def scan_directories(repo: Path) -> list[DirectoryMeta]:
    items: list[DirectoryMeta] = []
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        path = Path(dirpath)
        try:
            rel = normalize_rel_path(path.relative_to(repo).as_posix())
        except Exception:
            continue
        if not rel:
            continue
        visible_files = [name for name in filenames if not is_secret_path(path / name)]
        child_names = tuple(sorted({*dirnames, *visible_files}))
        items.append(
            DirectoryMeta(
                rel_path=rel,
                abs_path=str(path.resolve()),
                direct_dirs=len(dirnames),
                direct_files=len(visible_files),
                has_readme=any(name.lower().startswith("readme") for name in visible_files),
                has_manifest=any(name in IMPORTANT_NAMES for name in visible_files),
                has_index=any(name.lower().startswith("index.") for name in visible_files),
                child_names=child_names,
            )
        )
    return items


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


def directory_score(rel: str, meta: DirectoryMeta) -> int:
    parts = rel.split("/")
    low = rel.lower()
    score = 0
    if len(parts) == 1:
        score += 110
    if parts[0] in TOP_LEVEL_ROOTS:
        score += 85
    if any(token in low for token in SELECTION_KEYWORDS):
        score += 45
    if meta.has_manifest:
        score += 75
    if meta.has_readme:
        score += 55
    if meta.has_index:
        score += 25
    if meta.direct_dirs + meta.direct_files >= 8:
        score += min(30, meta.direct_dirs + meta.direct_files)
    if meta.direct_dirs >= 2 and meta.direct_files >= 2:
        score += 18
    if any(token in low for token in LOW_VALUE_KEYWORDS):
        score -= 85
    score -= min(32, max(0, len(parts) - 2) * 8)
    score -= min(24, len(rel) // 12)
    return score


def file_score(rel: str, size: int) -> int:
    parts = rel.split("/")
    name = parts[-1]
    low = rel.lower()
    score = 0
    if "/" not in rel and name in IMPORTANT_NAMES:
        score += 130
    if name.lower().startswith("readme"):
        score += 120
    if name.startswith("index."):
        score += 90
    if parts[0] in TOP_LEVEL_ROOTS:
        score += 55
    if any(token in low for token in SELECTION_KEYWORDS):
        score += 50
    if any(token in low for token in LOW_VALUE_KEYWORDS):
        score -= 90
    if ".test." in low or ".spec." in low or "__tests__" in low:
        score -= 70
    score -= min(40, len(parts) * 3)
    score -= min(48, size // 25_000)
    return score


def critical_bonus(rel: str, kind: str, critical_dirs: list[tuple[str, str]], critical_files: list[tuple[str, str]]) -> int:
    score = 0
    for idx, (path, label) in enumerate(critical_dirs):
        base = 180 - idx * 4
        if rel == path:
            score += base
        elif kind == "directory" and rel.startswith(path + "/"):
            score += max(20, base // 3)
    for idx, (path, label) in enumerate(critical_files):
        base = 220 - idx * 4
        if kind == "file" and rel == path:
            score += base
        elif kind == "directory" and path.startswith(rel + "/"):
            score += max(12, base // 4)
        elif kind == "directory" and rel + "/" in path:
            score += 0
    return score


def choose_doc_depth(kind: str, rel: str, meta: DirectoryMeta | None, score: int, selected: bool) -> str:
    if not selected:
        return "skip"
    if kind == "directory":
        if meta and (meta.has_manifest or meta.has_readme or meta.has_index or len(rel.split("/")) <= 2):
            return "overview"
        return "standard"
    return "deep"


def choose_priority_label(score: int, selected: bool) -> str:
    if not selected:
        return "C" if score >= 55 else "D"
    return "A" if score >= 150 else "B"


def choose_reason(kind: str, rel: str, meta: DirectoryMeta | None, score: int, selected: bool) -> str:
    low = rel.lower()
    if selected:
        if kind == "directory":
            if meta and meta.has_manifest:
                return "selected: contains build/manifest entry"
            if meta and meta.has_readme:
                return "selected: README / overview entry"
            if any(token in low for token in SELECTION_KEYWORDS):
                return "selected: core module boundary"
            return "selected: useful directory for architecture map"
        if any(token in low for token in ["route", "router", "controller"]):
            return "selected: request entry or controller"
        if any(token in low for token in ["service", "store", "runtime", "provider", "config"]):
            return "selected: service/runtime/config boundary"
        if rel.split("/")[-1].lower().startswith("readme"):
            return "selected: repository README entry"
        return "selected: high-value file for core path"
    if kind == "directory":
        if any(token in low for token in LOW_VALUE_KEYWORDS):
            return "skipped: low-value or generated subtree"
        return "skipped: covered by parent summary"
    if any(token in low for token in LOW_VALUE_KEYWORDS):
        return "skipped: low-value leaf file"
    return "skipped: below default budget"


def build_tasks(repo: Path, out: Path, max_tasks: int) -> tuple[list[Task], dict[str, int]]:
    critical_dirs, critical_files = load_critical(out)
    directories = scan_directories(repo)
    files = scan_files(repo)
    max_tasks = max(0, max_tasks)

    candidates: list[tuple[int, str, str, str, DirectoryMeta | None, int | None]] = []
    for meta in directories:
        score = directory_score(meta.rel_path, meta) + critical_bonus(meta.rel_path, "directory", critical_dirs, critical_files)
        candidates.append((score, "directory", meta.rel_path, meta.abs_path, meta, None))
    for rel, size in files:
        score = file_score(rel, size) + critical_bonus(rel, "file", critical_dirs, critical_files)
        candidates.append((score, "file", rel, str((repo / rel).resolve()), None, size))

    candidates.sort(key=lambda item: (-item[0], item[2], item[1]))
    selected_keys = {f"{kind}:{rel}" for _, kind, rel, _, _, _ in candidates[:max_tasks]}

    tasks: list[Task] = []
    for rank, (score, kind, rel, abs_path, meta, size) in enumerate(candidates):
        selected = f"{kind}:{rel}" in selected_keys
        priority_label = choose_priority_label(score, selected)
        doc_depth = choose_doc_depth(kind, rel, meta, score, selected)
        reason = choose_reason(kind, rel, meta, score, selected)
        if selected:
            status = "pending"
            parent_summary_only = False
        else:
            status = "skipped"
            parent_summary_only = True
        tasks.append(
            Task(
                priority=rank,
                priority_label=priority_label,
                doc_depth=doc_depth,
                kind=kind,
                rel_path=rel,
                abs_path=abs_path,
                output_md=output_md_for(kind, rel),
                reason=reason,
                status=status,
                parent_summary_only=parent_summary_only,
            )
        )

    counts = {
        "catalog_total": len(tasks),
        "selected_total": sum(1 for task in tasks if task.status == "pending"),
        "skipped_total": sum(1 for task in tasks if task.status == "skipped"),
    }
    tasks.sort(key=lambda t: (0 if t.status == "pending" else 1, t.priority, t.kind, t.rel_path))
    return tasks, counts


def write_csv(out: Path, tasks: list[Task]) -> None:
    fieldnames = [
        "rel_key",
        "priority",
        "priority_label",
        "doc_depth",
        "kind",
        "rel_path",
        "abs_path",
        "output_md",
        "parent_summary_only",
        "status",
        "reason",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for task in tasks:
        writer.writerow(
            {
                "rel_key": task.rel_key,
                "priority": task.priority,
                "priority_label": task.priority_label,
                "doc_depth": task.doc_depth,
                "kind": task.kind,
                "rel_path": task.rel_path,
                "abs_path": task.abs_path,
                "output_md": task.output_md,
                "parent_summary_only": int(task.parent_summary_only),
                "status": task.status,
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
                    completed_at, not_before, last_error, doc_depth, parent_summary_only
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(rel_key) DO UPDATE SET
                    run_id=excluded.run_id,
                    kind=excluded.kind,
                    rel_path=excluded.rel_path,
                    abs_path=excluded.abs_path,
                    output_md=excluded.output_md,
                    priority=excluded.priority,
                    reason=excluded.reason,
                    doc_depth=excluded.doc_depth,
                    parent_summary_only=excluded.parent_summary_only,
                    status=CASE WHEN tasks.status='done' THEN 'done' ELSE excluded.status END,
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
                    task.status,
                    0,
                    3,
                    None,
                    None,
                    ts,
                    None,
                    None,
                    None,
                    task.doc_depth,
                    1 if task.parent_summary_only else 0,
                ),
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage B: build local Codex task table.")
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--max-tasks", type=int, default=120)
    args = parser.parse_args()

    repo = args.repo.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    init_state_db(out)
    ensure_run(out, args.run_id, repo)
    set_stage_status(out, args.run_id, "B", "running", message="Stage B task table running")
    emit_signal(out, args.run_id, "STAGE_STARTED", {"stage": "B", "repo": str(repo), "out": str(out)})

    try:
        tasks, counts = build_tasks(repo, out, args.max_tasks)
        write_csv(out, tasks)
        persist_tasks(out, args.run_id, tasks)
        payload = {
            "stage": "B",
            "total": counts["selected_total"],
            "catalog_total": counts["catalog_total"],
            "selected_total": counts["selected_total"],
            "skipped_total": counts["skipped_total"],
            "budgeted": counts["selected_total"] < counts["catalog_total"],
            "truncated": False,
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
