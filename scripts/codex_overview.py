#!/usr/bin/env python3
"""Stage A: ask Codex for project-level Chinese learning docs."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from _common import (
    DEFAULT_TIMEOUT_SECONDS,
    MODEL,
    OVERVIEW_REASONING,
    atomic_write_text,
    emit_signal,
    ensure_run,
    init_state_db,
    render_progress_json_from_db,
    run_codex_exec,
    set_stage_status,
    strip_codex_output,
    validate_markdown,
)
from local_fallback import is_codex_unavailable_output, write_stage_a_fallback

REQUIRED_MARKDOWN = [
    "index.md",
    "00-overview.md",
    "01-tech-stack.md",
    "02-architecture.md",
    "03-runtime-flow.md",
]
REQUIRED_JSON = "critical_paths.json"


def build_prompt(repo: Path, out: Path) -> str:
    return f"""你是 AIWIKI 的代码仓库中文学习文档作者。请直接读取仓库并在指定输出目录写入项目总览文档。

仓库根目录：{repo}
输出目录：{out}

你必须创建或覆盖这些文件：
- index.md
- 00-overview.md
- 01-tech-stack.md
- 02-architecture.md
- 03-runtime-flow.md
- critical_paths.json

写作要求：
- 面向刚接触该项目的中文读者，中文为主；代码名、路径、函数名、包名、命令保留英文。
- 只能基于仓库真实文件、README、包管理/构建配置、入口文件和源码结构；推断必须标注依据。
- 不要写营销文案，不要生成单个巨型文档，不要把命令执行过程写进正文。
- index.md 是推荐阅读顺序，必须链接上述总览页，并列出后续最值得看的目录/文件。
- 00-overview.md 说明项目解决的问题、核心能力、主要模块和适合初学者的切入点。
- 01-tech-stack.md 解释技术栈、运行环境、构建/包管理信号、读源码前需要知道的概念。
- 02-architecture.md 解释目录分层、模块边界、关键依赖方向和扩展点。
- 03-runtime-flow.md 解释启动、配置加载、请求/任务/数据流转、关键调用链。证据不足时写明“根据当前文件推断”。
- 每个总览 Markdown 至少 900 个非空白中文/符号字符；index.md 至少 350 个非空白字符。

critical_paths.json 必须是合法 JSON，格式如下：
{{
  "critical_directories": [
    {{"path": "src", "priority": "P0", "reason": "为什么优先读"}}
  ],
  "critical_files": [
    {{"path": "package.json", "priority": "P0", "reason": "为什么优先读"}}
  ],
  "reading_order": [
    {{"path": "00-overview.md", "title": "项目整体介绍"}}
  ]
}}

critical_paths.json 至少包含 3 个 critical_directories、5 个 critical_files，reading_order 不能为空。
请把文件写到输出目录；最终 stdout 可以只简短说明完成情况。"""


def _paths_from(items: Any) -> list[str]:
    paths: list[str] = []
    if not isinstance(items, list):
        return paths
    for item in items:
        if isinstance(item, str):
            value = item
        elif isinstance(item, dict):
            value = str(item.get("path") or item.get("rel_path") or item.get("file") or item.get("directory") or "")
        else:
            value = ""
        value = value.strip().strip("/")
        if value:
            paths.append(value)
    return paths


def validate_stage_a(out: Path) -> tuple[bool, str, dict[str, Any]]:
    payload: dict[str, Any] = {"files": {}}
    for rel in REQUIRED_MARKDOWN:
        path = out / rel
        if not path.exists():
            return False, f"missing required file: {rel}", payload
        text = path.read_text(encoding="utf-8", errors="replace")
        min_chars = 350 if rel == "index.md" else 900
        ok, reason = validate_markdown(text, min_chars=min_chars)
        payload["files"][rel] = {"ok": ok, "reason": reason}
        if not ok:
            return False, f"{rel}: {reason}", payload

    cp_path = out / REQUIRED_JSON
    if not cp_path.exists():
        return False, f"missing required file: {REQUIRED_JSON}", payload
    try:
        data = json.loads(cp_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"critical_paths.json is not valid JSON: {exc}", payload
    dirs = _paths_from(data.get("critical_directories") or data.get("directories"))
    files = _paths_from(data.get("critical_files") or data.get("files"))
    reading = _paths_from(data.get("reading_order"))
    payload["critical_directories"] = len(dirs)
    payload["critical_files"] = len(files)
    payload["reading_order"] = len(reading)
    if len(dirs) < 3:
        return False, "critical_paths.json needs at least 3 critical directories", payload
    if len(files) < 5:
        return False, "critical_paths.json needs at least 5 critical files", payload
    if not reading:
        return False, "critical_paths.json reading_order must not be empty", payload
    return True, "ok", payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage A: generate project overview docs with Codex.")
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args()

    local_fallback_disabled = os.environ.get("AIWIKI_DISABLE_LOCAL_FALLBACK", "").lower() in {"1", "true", "yes"}
    repo = args.repo.resolve()
    out = args.out.resolve()
    debug = out / "codex_debug"
    out.mkdir(parents=True, exist_ok=True)
    debug.mkdir(parents=True, exist_ok=True)
    init_state_db(out)
    ensure_run(out, args.run_id, repo, reasoning=OVERVIEW_REASONING, timeout_seconds=args.timeout)
    set_stage_status(out, args.run_id, "A", "running", message="Stage A overview running")
    emit_signal(out, args.run_id, "STAGE_STARTED", {"stage": "A", "repo": str(repo), "out": str(out)})

    if not local_fallback_disabled and os.environ.get("AIWIKI_FORCE_LOCAL_FALLBACK", "").lower() in {"1", "true", "yes"}:
        fallback_payload = write_stage_a_fallback(repo, out, "AIWIKI_FORCE_LOCAL_FALLBACK enabled")
        ok, reason, payload = validate_stage_a(out)
        if not ok:
            payload = {"stage": "A", "error": f"local Stage A fallback validation failed: {reason}", **fallback_payload}
            set_stage_status(out, args.run_id, "A", "failed", message=payload["error"], payload=payload)
            emit_signal(out, args.run_id, "STAGE_FAILED", payload)
            render_progress_json_from_db(out, args.run_id)
            return 1
        payload.update(fallback_payload)
        set_stage_status(out, args.run_id, "A", "completed", message="Stage A overview completed with local fallback", payload=payload)
        emit_signal(out, args.run_id, "STAGE_COMPLETED", {"stage": "A", **payload})
        render_progress_json_from_db(out, args.run_id)
        return 0

    prompt = build_prompt(repo, out)
    atomic_write_text(debug / "stage_a_prompt.txt", prompt)
    try:
        code, raw, timed_out = run_codex_exec(
            repo=repo,
            prompt=prompt,
            timeout=args.timeout,
            model=MODEL,
            reasoning=OVERVIEW_REASONING,
            sandbox_mode="workspace-write",
            add_dirs=[out],
        )
        atomic_write_text(debug / "stage_a_raw.txt", raw)
        if timed_out:
            raise RuntimeError(f"Codex overview timed out after {args.timeout}s")
        if code != 0:
            if not local_fallback_disabled and is_codex_unavailable_output(raw):
                reason_text = strip_codex_output(raw)[-500:] or "Codex CLI unavailable"
                fallback_payload = write_stage_a_fallback(repo, out, reason_text)
                ok, reason, payload = validate_stage_a(out)
                if not ok:
                    raise RuntimeError(f"local Stage A fallback validation failed: {reason}")
                payload.update(fallback_payload)
                set_stage_status(out, args.run_id, "A", "completed", message="Stage A overview completed with local fallback", payload=payload)
                emit_signal(out, args.run_id, "STAGE_COMPLETED", {"stage": "A", **payload})
                render_progress_json_from_db(out, args.run_id)
                return 0
            tail = strip_codex_output(raw)[-1200:]
            raise RuntimeError(f"Codex overview exited with {code}: {tail}")
        ok, reason, payload = validate_stage_a(out)
        if not ok:
            raise RuntimeError(reason)
        set_stage_status(out, args.run_id, "A", "completed", message="Stage A overview completed", payload=payload)
        emit_signal(out, args.run_id, "STAGE_COMPLETED", {"stage": "A", **payload})
        render_progress_json_from_db(out, args.run_id)
        return 0
    except Exception as exc:
        payload = {"stage": "A", "error": str(exc)}
        set_stage_status(out, args.run_id, "A", "failed", message=str(exc), payload=payload)
        emit_signal(out, args.run_id, "STAGE_FAILED", payload)
        render_progress_json_from_db(out, args.run_id)
        return 1


if __name__ == "__main__":
    sys.exit(main())
