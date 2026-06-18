#!/usr/bin/env python3
"""Repo Learning Docs Service MVP.

A small local service for docs.eitc.top: submit a code repository URL/path,
filter out pure-document/content-farm repos, generate segmented beginner docs,
and render Markdown as HTML.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import queue
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.parse
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterable

from scripts._common import sanitize_markdown_text

HOST = os.environ.get("RDS_HOST", "127.0.0.1")
PORT = int(os.environ.get("RDS_PORT", "18081"))
BASE = Path(os.environ.get("RDS_BASE") or (Path(__file__).resolve().parent / "data")).resolve()
DB = BASE / "service.sqlite3"
LOCAL_ROOT = Path("/data/project").resolve()
ASSETS = (Path(__file__).resolve().parent / "assets").resolve()

SKIP_DIRS = {".git", "node_modules", "dist", "build", "target", ".next", "coverage", ".venv", "venv", "__pycache__", ".idea", ".vscode"}
SECRET_NAMES = {".env", ".env.local", ".npmrc", "id_rsa", "id_dsa", "id_ed25519", "credentials.json"}
SECRET_EXTS = {".pem", ".key", ".p12", ".pfx"}
DOC_EXTS = {".md", ".markdown", ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".txt", ".rtf", ".epub"}
CODE_EXTS = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".kt", ".go", ".rs", ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".swift", ".scala", ".sh", ".sql", ".vue", ".svelte", ".css", ".scss", ".html"}
MANIFESTS = {"package.json", "pyproject.toml", "setup.py", "requirements.txt", "pom.xml", "build.gradle", "settings.gradle", "Cargo.toml", "go.mod", "Makefile", "CMakeLists.txt", "composer.json", "Gemfile", "pnpm-lock.yaml", "bun.lock", "yarn.lock"}

job_q: queue.Queue[str] = queue.Queue()


def ensure_dirs() -> None:
    for p in [BASE, BASE / "repos", BASE / "generated", BASE / "tmp"]:
        p.mkdir(parents=True, exist_ok=True)


def db() -> sqlite3.Connection:
    ensure_dirs()
    con = sqlite3.connect(DB, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


def init_db() -> None:
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS repos(
            repo_id TEXT PRIMARY KEY, source TEXT, local_path TEXT, generated_path TEXT,
            status TEXT, created_at REAL, updated_at REAL)""")
        con.execute("""CREATE TABLE IF NOT EXISTS jobs(
            job_id TEXT PRIMARY KEY, repo_id TEXT, source TEXT, status TEXT, message TEXT,
            log TEXT, created_at REAL, updated_at REAL)""")


def now() -> float:
    return time.time()


def slugify(source: str) -> str:
    s = re.sub(r"^https?://", "", source.strip())
    s = re.sub(r"\.git$", "", s)
    s = re.sub(r"[^a-zA-Z0-9._/-]+", "-", s).strip("-/.")
    s = s.replace("/", "-") or "repo"
    h = hashlib.sha1(source.encode()).hexdigest()[:8]
    return f"{s[:70]}-{h}".lower()


def repo_card_context(source: str, repo_id: str, status: str) -> dict[str, str]:
    status_label = {
        "completed": "已完成",
        "queued": "排队中",
        "running": "生成中",
        "failed": "生成失败",
    }.get(status, status or "unknown")
    local = allowed_local(source)
    if local:
        return {
            "kicker": "Local Repo",
            "title": local.name or repo_id,
            "subtitle": str(local),
            "meta": "本地目录",
            "status_label": status_label,
            "status_class": f"status-{status or 'unknown'}",
            "type_class": "card-local",
        }
    parsed = urllib.parse.urlparse(source)
    host = (parsed.netloc or "").lower()
    parts = [seg for seg in parsed.path.split("/") if seg]
    owner = parts[0] if len(parts) > 0 else ""
    repo = parts[1] if len(parts) > 1 else repo_id.rsplit("-", 1)[0]
    repo = repo[:-4] if repo.endswith(".git") else repo
    if "github.com" in host:
        kicker = "GitHub"
        type_class = "card-github"
    elif "gitlab.com" in host:
        kicker = "GitLab"
        type_class = "card-gitlab"
    else:
        kicker = parsed.netloc or "Remote Repo"
        type_class = "card-remote"
    subtitle = f"{owner}/{repo}" if owner and repo else (parsed.netloc or source)
    meta = source
    return {
        "kicker": kicker,
        "title": repo or owner or repo_id,
        "subtitle": subtitle,
        "meta": meta,
        "status_label": status_label,
        "status_class": f"status-{status or 'unknown'}",
        "type_class": type_class,
    }


def repo_card_html(row: sqlite3.Row) -> str:
    ctx = repo_card_context(str(row["source"]), str(row["repo_id"]), str(row["status"] or ""))
    href = f"/repos/{row['repo_id']}/"
    repo_id_text = html.escape(str(row["repo_id"]))
    return (
        f"<li class='repo-card {ctx['status_class']} {ctx['type_class']}'>"
        f"<a class='repo-card-link' href='{href}'>"
        f"<div class='repo-card-top'><span class='repo-kicker'>{html.escape(ctx['kicker'])}</span>"
        f"<span class='repo-status'>{html.escape(ctx['status_label'])}</span></div>"
        f"<div class='repo-title'>{html.escape(ctx['title'])}</div>"
        f"<div class='repo-subtitle'>{html.escape(ctx['subtitle'])}</div>"
        f"<div class='repo-meta' title='{html.escape(ctx['meta'])}'>{html.escape(ctx['meta'])}</div>"
        f"<div class='repo-footer'><span class='repo-open'>打开学习文档</span></div>"
        f"<div class='repo-idline' title='{repo_id_text}'>{repo_id_text}</div>"
        f"</a></li>"
    )


def job_id_for(source: str) -> str:
    return hashlib.sha1(f"{source}-{time.time()}".encode()).hexdigest()[:16]


def update_job(job_id: str, status: str | None = None, message: str | None = None, append: str | None = None) -> None:
    with db() as con:
        row = con.execute("SELECT log FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        log = row["log"] if row else ""
        if append:
            log += f"[{time.strftime('%H:%M:%S')}] {append}\n"
        sets, vals = ["updated_at=?"], [now()]
        if status is not None:
            sets.append("status=?"); vals.append(status)
        if message is not None:
            sets.append("message=?"); vals.append(message)
        sets.append("log=?"); vals.append(log)
        vals.append(job_id)
        con.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE job_id=?", vals)


def is_remote(src: str) -> bool:
    return bool(re.match(r"^https://(github\.com|gitlab\.com)/[\w.\-]+/[\w.\-]+/?(\.git)?$", src.strip()))


def allowed_local(src: str) -> Path | None:
    try:
        p = Path(src).expanduser().resolve()
        p.relative_to(LOCAL_ROOT)
        return p if p.exists() and p.is_dir() else None
    except Exception:
        return None


def safe_walk(root: Path, limit: int = 20000) -> Iterable[Path]:
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if count >= limit:
                return
            p = Path(dirpath) / name
            if name in SECRET_NAMES or p.suffix.lower() in SECRET_EXTS:
                continue
            count += 1
            yield p


def rel(root: Path, p: Path) -> str:
    return str(p.relative_to(root)).replace(os.sep, "/")


@dataclass
class Scan:
    total: int = 0
    docs: int = 0
    code: int = 0
    manifests: int = 0
    by_ext: dict[str, int] = None
    files: list[str] = None

    def __post_init__(self):
        self.by_ext = self.by_ext or {}
        self.files = self.files or []


def scan_repo(root: Path) -> Scan:
    s = Scan()
    for p in safe_walk(root):
        r = rel(root, p)
        ext = p.suffix.lower()
        s.total += 1
        s.files.append(r)
        s.by_ext[ext or "[no-ext]"] = s.by_ext.get(ext or "[no-ext]", 0) + 1
        if ext in DOC_EXTS:
            s.docs += 1
        if ext in CODE_EXTS:
            s.code += 1
        if p.name in MANIFESTS:
            s.manifests += 1
    return s


def filter_reason(s: Scan) -> str | None:
    if s.total == 0:
        return "仓库里没有可分析文件。"
    doc_ratio = s.docs / max(s.total, 1)
    if s.code < 5 and s.manifests == 0:
        return f"代码信号太弱：只发现 {s.code} 个代码文件、{s.manifests} 个构建/包管理清单。这个项目更像文档集合，不适合代码学习文档生成。"
    if doc_ratio > 0.70 and s.code < 20 and s.manifests == 0:
        return f"文档类文件占比过高（约 {doc_ratio:.0%}），且缺少足够代码/构建清单，疑似纯文档、宣传或内容农场项目，已按你的规则过滤。"
    if s.docs >= 50 and s.code < max(10, s.docs // 5) and s.manifests == 0:
        return "文档/PDF/Office/TXT 文件明显多于代码文件，且没有识别到工程构建清单，已过滤。"
    return None


def import_source(source: str, repo_id: str) -> Path:
    if is_remote(source):
        dest = BASE / "repos" / repo_id / "source"
        if (dest / ".git").exists():
            check = subprocess.run(
                ["git", "-C", str(dest), "rev-parse", "--is-inside-work-tree"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            if check.returncode == 0 and check.stdout.strip() == "true":
                return dest
        if dest.exists():
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--depth", "1", source, str(dest)], check=True, text=True, capture_output=True, timeout=300)
        return dest
    p = allowed_local(source)
    if p:
        return p
    raise ValueError("只接受 GitHub/GitLab HTTPS 仓库 URL，或 /data/project 下存在的本地目录。")


def read_text_safe(p: Path, max_chars: int = 12000) -> str:
    try:
        txt = p.read_text(encoding="utf-8", errors="replace")
        return txt[:max_chars] + ("\n...[truncated]" if len(txt) > max_chars else "")
    except Exception as e:
        return f"[无法读取: {e}]"


def tree_lines(files: list[str], max_lines: int = 350) -> str:
    return "\n".join(files[:max_lines]) + ("\n..." if len(files) > max_lines else "")


def important_dirs(files: list[str], max_dirs: int = 15) -> list[str]:
    counts: dict[str, int] = {}
    preferred = ["src", "packages", "apps", "app", "lib", "server", "routes", "docs", "scripts", "tools", "examples"]
    existing = {f.split("/", 1)[0] for f in files if "/" in f}
    for f in files:
        parts = f.split("/")
        if len(parts) > 1:
            for i in range(1, min(len(parts), 3)):
                d = "/".join(parts[:i])
                counts[d] = counts.get(d, 0) + 1
    ordered = [d for d in preferred if d in existing]
    for d, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        if d not in ordered:
            ordered.append(d)
        if len(ordered) >= max_dirs:
            break
    return ordered[:max_dirs]


def important_code_files(root: Path, files: list[str], max_files: int = 40) -> list[str]:
    priority = []
    for f in files:
        p = root / f
        if p.suffix.lower() in CODE_EXTS or p.name in MANIFESTS or p.name.lower().startswith("readme"):
            score = 0
            low = f.lower()
            for token in ["main", "app", "server", "index", "router", "route", "config", "service", "controller", "provider", "runtime", "model", "schema", "domain", "task", "flow", "package.json", "pyproject", "go.mod"]:
                if token in low: score += 5
            if any(token in low for token in ["test", "tests", "spec", "fixture", "mock", "snapshot", "generated", "locales", "public"]):
                score -= 20
            try: size = p.stat().st_size
            except Exception: size = 999999
            if size < 250000:
                priority.append((-score, size, f))
    return [f for _, _, f in sorted(priority)[:max_files]]


def write_md(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(sanitize_markdown_text(content).strip() + "\n", encoding="utf-8")


def generate_fallback_docs(root: Path, gen: Path, source: str, scan: Scan, warning: str | None = None) -> list[str]:
    gen.mkdir(parents=True, exist_ok=True)
    dirs = important_dirs(scan.files)
    code_files = important_code_files(root, scan.files)
    order = ["index.md", "00-overview.md", "01-tech-stack.md", "02-architecture.md", "03-runtime-flow.md", "04-reading-guide.md"]
    order += [f"directories/{d.replace('/', '__')}.md" for d in dirs]
    order += [f"files/{f.replace('/', '__')}.md" for f in code_files]

    top_ext = ", ".join(f"{k}:{v}" for k, v in sorted(scan.by_ext.items(), key=lambda kv: -kv[1])[:12])
    warn = f"\n> ⚠️ {warning}\n" if warning else ""
    write_md(gen / "index.md", f"""
# 推荐阅读顺序
{warn}
这是为代码学习生成的项目文档首页。建议不要从文件列表硬啃，而按下面顺序读。

## 1. 先建立全局地图
1. [项目整体介绍](00-overview.md)
2. [技术栈与预备知识](01-tech-stack.md)
3. [架构与目录关系](02-architecture.md)
4. [运行链路/数据流推测](03-runtime-flow.md)
5. [阅读指南](04-reading-guide.md)

## 2. 再读重要目录
{chr(10).join(f'- [{d}](directories/{d.replace("/", "__")}.md)' for d in dirs) or '- 暂无可拆分目录'}

## 3. 最后读关键文件
{chr(10).join(f'- [{f}](files/{f.replace("/", "__")}.md)' for f in code_files) or '- 暂无可读代码文件'}

## 项目概况快照
- 来源：`{source}`
- 文件总数：{scan.total}
- 代码文件：{scan.code}
- 文档类文件：{scan.docs}
- 构建/包管理清单：{scan.manifests}
- 主要文件类型：{top_ext}
""")
    readmes = [f for f in scan.files if Path(f).name.lower().startswith("readme")][:5]
    readme_text = "\n\n".join(f"## {r}\n\n" + read_text_safe(root / r, 6000) for r in readmes)
    write_md(gen / "00-overview.md", f"""
# 项目整体介绍

## 这个项目大概是什么
本页基于仓库结构、README、构建清单和代码文件分布自动生成。它优先帮助小白建立“这个项目在解决什么问题、我应该从哪里开始看”的直觉。

## 仓库目录节选
```text
{tree_lines(scan.files)}
```

## 项目自带说明节选
{readme_text or '没有发现项目自带说明。'}
""")
    manifests = [f for f in scan.files if Path(f).name in MANIFESTS][:20]
    manifest_text = "\n\n".join(f"## {m}\n```text\n{read_text_safe(root/m, 4000)}\n```" for m in manifests)
    write_md(gen / "01-tech-stack.md", f"""
# 技术栈与预备知识

## 自动识别到的工程信号
- 构建/包管理清单数量：{scan.manifests}
- 主要文件类型：{top_ext}

## 对小白的建议
先根据下面的清单判断项目属于前端、后端、桌面端、命令行工具、基础库还是混合仓库。遇到不熟悉的技术栈时，先读官方入门概念，再回来看目录级说明。

{manifest_text or '没有发现常见构建清单。'}
""")
    write_md(gen / "02-architecture.md", f"""
# 架构与目录关系

## 重要目录
{chr(10).join(f'- `{d}`：包含约 {sum(1 for f in scan.files if f.startswith(d + "/"))} 个文件。建议先读对应目录页。' for d in dirs)}

## 代码学习方法
1. 先找入口：`main` / `app` / `server` / `index` / 路由配置。这些英文通常是代码里的固定命名。
2. 再找核心模型：`types`（类型）、`models`（数据模型）、`schema`（结构定义）、`database`（数据库）。
3. 再找业务服务：`service`（业务服务）、`controller`（请求控制器）、`router`（路由）、`store`（状态存储）。
4. 最后看测试：测试通常说明作者希望代码如何被使用。
""")
    write_md(gen / "03-runtime-flow.md", f"""
# 运行链路 / 数据流推测

> 这是基于文件命名和工程结构的初步推测。更准确的解释需要进一步 Codex 深度分析具体入口文件。

## 推荐追踪顺序
1. 启动/入口文件。
2. 配置加载。
3. 路由或命令分发。
4. 服务层/状态管理。
5. 数据访问或外部 API。
6. 测试验证。

## 可能值得优先看的入口/关键文件
{chr(10).join(f'- `{f}`' for f in code_files[:15])}
""")
    write_md(gen / "04-reading-guide.md", f"""
# 阅读指南

## 先看什么
优先从 `00-overview.md`、`01-tech-stack.md`、`02-architecture.md`、`03-runtime-flow.md` 建立项目地图，再进入目录页和文件页。这个仓库的默认目标不是把每个叶子都讲透，而是先快速看懂核心路径。

## 核心入口
{chr(10).join(f'- `{f}`' for f in code_files[:10]) or '- 暂无明显入口文件'}

## 可后读目录
{chr(10).join(f'- `{d}`' for d in dirs[:12]) or '- 暂无关键目录'}

## 可以先跳过的内容
- 测试夹具、快照、生成产物、静态资源、本地缓存。
- 只有转发、常量、样板导出的薄文件。
- 没有入口、也没有被其他模块引用的叶子目录。

## 怎么继续下钻
当你想看更细的地方时，优先找 `router`、`controller`、`service`、`store`、`runtime`、`provider`、`config`、`index` 这些文件名。它们比零散组件更能说明代码怎么串起来。
""")
    for d in dirs:
        files = [f for f in scan.files if f.startswith(d + "/")][:200]
        write_md(gen / "directories" / f"{d.replace('/', '__')}.md", f"""
# 目录：{d}

## 它可能负责什么
这个目录包含 {len(files)} 个被抽样展示的文件。请从文件命名、子目录和关键源码入手理解它在项目中的职责。

## 文件列表节选
```text
{tree_lines(files, 220)}
```

## 小白阅读建议
- 先看项目说明、`index` 入口、路由、业务服务、类型/结构定义等文件。英文文件名只是代码命名，不要求先理解英文语义。
- 暂时跳过构建产物、测试快照和重复样板。
- 如果这里是业务目录，优先找“谁调用它”和“它调用谁”。
""")
    for f in code_files:
        p = root / f
        txt = read_text_safe(p, 14000)
        write_md(gen / "files" / f"{f.replace('/', '__')}.md", f"""
# 文件：{f}

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
{txt}
```
""")
    (gen / "manifest.json").write_text(json.dumps({"order": order, "source": source, "generated_at": now()}, ensure_ascii=False, indent=2), encoding="utf-8")
    return order


def pipeline_terminal(gen: Path) -> tuple[str | None, str]:
    for status, name in [("completed", "pipeline.success"), ("partial", "pipeline.partial"), ("failed", "pipeline.failed")]:
        path = gen / name
        if path.exists():
            try:
                return status, path.read_text(encoding="utf-8", errors="replace")[-2000:]
            except Exception:
                return status, ""
    return None, ""


def run_pipeline(root: Path, gen: Path) -> tuple[int, str]:
    script = Path(__file__).resolve().parent / "scripts" / "run_pipeline.py"
    cmd = [
        sys.executable,
        str(script),
        "--repo",
        str(root),
        "--out",
        str(gen),
        "--concurrency",
        os.environ.get("RDS_PIPELINE_CONCURRENCY", "5"),
        "--timeout",
        os.environ.get("RDS_PIPELINE_TIMEOUT", "1800"),
        "--max-tasks",
        os.environ.get("RDS_PIPELINE_MAX_TASKS", "120"),
    ]
    if os.environ.get("RDS_PIPELINE_SKIP_OVERVIEW", "").lower() in {"1", "true", "yes"}:
        cmd.append("--skip-overview")
    proc = subprocess.run(cmd, text=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return int(proc.returncode), proc.stdout or ""


def worker() -> None:
    while True:
        job_id = job_q.get()
        try:
            with db() as con:
                job = con.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if not job: continue
            source = job["source"]; repo_id = job["repo_id"]
            update_job(job_id, "importing", "正在导入仓库", "开始导入仓库")
            root = import_source(source, repo_id)
            update_job(job_id, "filtering", "正在过滤纯文档/内容农场项目", f"源码路径: {root}")
            s = scan_repo(root)
            reason = filter_reason(s)
            if reason:
                update_job(job_id, "rejected", reason, reason)
                with db() as con: con.execute("UPDATE repos SET status=?, updated_at=? WHERE repo_id=?", ("rejected", now(), repo_id))
                continue
            gen = BASE / "generated" / repo_id
            update_job(job_id, "generating", "正在生成分段 Markdown 文档", f"扫描完成 total={s.total} code={s.code} docs={s.docs} manifests={s.manifests}")
            order = generate_fallback_docs(root, gen, source, s)
            with db() as con:
                con.execute("UPDATE repos SET local_path=?, generated_path=?, status=?, updated_at=? WHERE repo_id=?", (str(root), str(gen), "generating", now(), repo_id))
            update_job(job_id, append=f"基础文档已写入 {gen}，开始三阶段 Codex 管线")
            code, output = run_pipeline(root, gen)
            if output:
                update_job(job_id, append=output[-4000:])
            terminal, terminal_text = pipeline_terminal(gen)
            if terminal == "completed":
                update_job(job_id, "completed", f"生成完成，共 {len(order)} 个基础入口，Codex 管线已完成", "完成")
                repo_status = "completed"
            elif terminal == "partial":
                update_job(job_id, "completed", "生成完成，部分任务失败，可重跑；成功文档仍可浏览", terminal_text or "部分任务失败")
                repo_status = "completed"
            else:
                msg = "三阶段管线失败，已保留基础文档。"
                if terminal_text:
                    msg += terminal_text[-1000:]
                elif code != 0:
                    msg += f" pipeline returncode={code}"
                update_job(job_id, "failed", msg, msg)
                repo_status = "failed"
            with db() as con:
                con.execute("UPDATE repos SET local_path=?, generated_path=?, status=?, updated_at=? WHERE repo_id=?", (str(root), str(gen), repo_status, now(), repo_id))
        except Exception as e:
            update_job(job_id, "failed", str(e), f"失败: {e}")
        finally:
            job_q.task_done()


def _render_inline_text(text: str) -> str:
    text = html.escape(text)
    return re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)


def _find_balanced(text: str, start: int, opener: str, closer: str) -> int:
    depth = 0
    i = start
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _is_local_source_href(href: str) -> bool:
    href = (href or "").strip()
    if not href:
        return True
    if href.startswith(("#", "/repos/")):
        return False
    if re.match(r"^[a-z][a-z0-9+.-]*://", href, flags=re.I):
        return False
    return True


def md_inline(s: str) -> str:
    out: list[str] = []
    buf: list[str] = []

    def flush_text() -> None:
        if buf:
            out.append(_render_inline_text("".join(buf)))
            buf.clear()

    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "`":
            end = s.find("`", i + 1)
            if end != -1:
                flush_text()
                out.append("<code>" + html.escape(s[i + 1:end]) + "</code>")
                i = end + 1
                continue
        if ch == "[":
            label_end = _find_balanced(s, i, "[", "]")
            if label_end != -1 and label_end + 1 < len(s) and s[label_end + 1] == "(":
                href_end = _find_balanced(s, label_end + 1, "(", ")")
                if href_end != -1:
                    flush_text()
                    label = s[i + 1:label_end]
                    href = s[label_end + 2:href_end].strip()
                    if _is_local_source_href(href):
                        out.append("<code>" + html.escape(label) + "</code>")
                    else:
                        out.append(f'<a href="{html.escape(href, quote=True)}">{_render_inline_text(label)}</a>')
                    i = href_end + 1
                    continue
        buf.append(ch)
        i += 1
    flush_text()
    return "".join(out)


_CODE_KEYWORDS = {
    # python
    "def", "class", "return", "if", "elif", "else", "for", "while", "import", "from", "as",
    "in", "is", "not", "and", "or", "None", "True", "False", "async", "await", "lambda",
    "with", "try", "except", "finally", "raise", "yield", "global", "nonlocal", "pass",
    "break", "continue", "assert", "del", "self", "cls", "print", "nonlocal",
    # js / ts
    "const", "let", "var", "function", "new", "typeof", "instanceof", "null", "undefined",
    "export", "default", "of", "switch", "case", "do", "void", "this", "super", "extends",
    "static", "get", "set", "interface", "type", "enum", "implements", "readonly", "public",
    "private", "protected", "namespace", "declare", "abstract", "as",
    # go / rust / c / java-ish
    "func", "go", "defer", "range", "make", "chan", "select", "map", "package", "fallthrough",
    "pub", "fn", "let", "mut", "use", "impl", "trait", "struct", "mod", "crate", "move", "ref",
    "match", "where", "unsafe", "extern", "Self", "int", "float", "double", "char", "void",
    "long", "short", "unsigned", "signed", "sizeof", "struct", "union", "const",
    # shell / misc
    "echo", "set", "local", "then", "fi", "done", "esac",
}

_NUM_RE = re.compile(r"(?:0[xX][0-9a-fA-F]+|0[bB][01]+|\d[\d_]*\.?\d*(?:[eE][+-]?\d+)?)")


def highlight_code(raw: str, lang: str = "") -> str:
    """Tokenize raw source into colored spans (visual only). Output is HTML-escaped."""
    out: list[str] = []
    i, n = 0, len(raw)
    while i < n:
        ch = raw[i]
        nxt = raw[i + 1] if i + 1 < n else ""
        # block comment /* */
        if ch == "/" and nxt == "*":
            end = raw.find("*/", i + 2)
            end = (end + 2) if end != -1 else n
            out.append('<span class="tok-com">' + html.escape(raw[i:end]) + "</span>")
            i = end
            continue
        # line comment # or //
        if ch == "#" or (ch == "/" and nxt == "/"):
            end = raw.find("\n", i)
            end = end if end != -1 else n
            out.append('<span class="tok-com">' + html.escape(raw[i:end]) + "</span>")
            i = end
            continue
        # strings: " ' `
        if ch in ("\"", "'", "`"):
            j = i + 1
            while j < n:
                if raw[j] == "\\":
                    j += 2
                    continue
                j += 1
                if j - 1 < n and raw[j - 1] == ch:
                    break
            out.append('<span class="tok-str">' + html.escape(raw[i:j]) + "</span>")
            i = j
            continue
        # numbers
        if ch.isdigit() or (ch == "." and nxt.isdigit()):
            m = _NUM_RE.match(raw, i)
            if m:
                out.append('<span class="tok-num">' + html.escape(m.group(0)) + "</span>")
                i = m.end()
                continue
        # identifiers / keywords / calls
        if ch.isalpha() or ch == "_" or ch == "$":
            j = i + 1
            while j < n and (raw[j].isalnum() or raw[j] in "_$"):
                j += 1
            word = raw[i:j]
            esc = html.escape(word)
            if word in _CODE_KEYWORDS:
                out.append('<span class="tok-kw">' + esc + "</span>")
            elif j < n and raw[j] == "(":
                out.append('<span class="tok-fn">' + esc + "</span>")
            else:
                out.append(esc)
            i = j
            continue
        # decorators / preprocessor @...
        if ch == "@" and nxt.isalpha():
            j = i + 1
            while j < n and (raw[j].isalnum() or raw[j] == "_"):
                j += 1
            out.append('<span class="tok-dec">' + html.escape(raw[i:j]) + "</span>")
            i = j
            continue
        out.append(html.escape(ch))
        i += 1
    return "".join(out)


def render_md(text: str) -> str:
    out=[]; code=[]; in_code=False; code_lang=""; code_in_list=False; list_type=None; quote=[]; para=[]; last_li_open=False; pending_list_blank=False

    def flush_para():
        nonlocal para
        if para:
            raw = " ".join(p.strip() for p in para)
            cls = " class='lead-code'" if raw.lstrip().startswith("`") else ""
            out.append("<p" + cls + ">" + md_inline(raw) + "</p>")
            para=[]

    def close_list():
        nonlocal list_type, last_li_open, pending_list_blank
        if last_li_open:
            out.append("</li>"); last_li_open=False
        if list_type:
            out.append(f"</{list_type}>"); list_type=None
        pending_list_blank=False

    def close_quote():
        nonlocal quote
        if quote:
            flush_para(); close_list()
            parts=[]; block=[]
            for q in quote:
                if q.strip():
                    block.append(q.strip())
                elif block:
                    parts.append("<p>" + md_inline(" ".join(block)) + "</p>"); block=[]
            if block:
                parts.append("<p>" + md_inline(" ".join(block)) + "</p>")
            out.append("<blockquote>" + "\n".join(parts) + "</blockquote>"); quote=[]

    def open_list(kind, start=None):
        nonlocal list_type
        close_quote(); flush_para()
        if list_type != kind:
            close_list()
            attr=f" start='{int(start)}'" if kind == "ol" and start else ""
            out.append(f"<{kind}{attr}>"); list_type=kind

    def add_list_item(kind, depth, content, start=None):
        nonlocal last_li_open, pending_list_blank
        open_list(kind, start)
        if last_li_open:
            out.append("</li>")
        out.append(f"<li class='depth-{depth}'>"+content)
        last_li_open=True; pending_list_blank=False

    def render_table(rows):
        def split_row(row):
            row=row.strip().strip("|")
            return [md_inline(cell.strip()) for cell in row.split("|")]
        head=split_row(rows[0])
        body=[split_row(r) for r in rows[2:]]
        th="".join(f"<th>{cell}</th>" for cell in head)
        trs=["<thead><tr>"+th+"</tr></thead>"]
        if body:
            trs.append("<tbody>" + "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in body) + "</tbody>")
        out.append("<div class='table-wrap'><table>" + "".join(trs) + "</table></div>")

    lines=text.splitlines()
    i=0
    while i < len(lines):
        line=lines[i]
        stripped=line.strip()
        if stripped.startswith("```"):
            close_quote(); flush_para()
            if not in_code:
                code_in_list=bool(list_type and last_li_open and (line[:1].isspace() or pending_list_blank))
                if not code_in_list:
                    close_list()
                in_code=True; code=[]; code_lang=stripped[3:].strip().split()[0] if stripped[3:].strip() else ""
            else:
                out.append(_code_block("\n".join(code), code_lang))
                in_code=False; code_lang=""; code_in_list=False; pending_list_blank=False
            i+=1; continue
        if in_code:
            code.append(line[3:] if code_in_list and line.startswith("   ") else line); i+=1; continue
        if not stripped:
            close_quote(); flush_para()
            if list_type and last_li_open:
                pending_list_blank=True; i+=1; continue
            close_list(); i+=1; continue
        if re.match(r"^[-*_]\s*[-*_]\s*[-*_][\s*_=-]*$", stripped):
            close_quote(); flush_para(); close_list(); out.append("<hr>"); i+=1; continue
        if stripped.startswith("|") and i+1 < len(lines) and re.match(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$", lines[i+1]):
            close_quote(); flush_para(); close_list()
            rows=[line, lines[i+1]]; i+=2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i]); i+=1
            render_table(rows); continue
        m=re.match(r"^>\s?(.*)$", line)
        if m:
            flush_para(); close_list(); quote.append(m.group(1)); i+=1; continue
        close_quote()
        m=re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            flush_para(); close_list(); n=len(m.group(1)); heading=m.group(2).strip()
            title_parts=re.match(r"^(文件|目录)[:：]\s*(.+)$", heading)
            if n == 1 and title_parts:
                kind=html.escape(title_parts.group(1))
                path_text=html.escape(title_parts.group(2))
                out.append(f"<h1 class='doc-title'><span class='doc-title-kind'>{kind}</span><span class='doc-title-path'>{path_text}</span></h1>")
            else:
                out.append(f"<h{n}>{md_inline(heading)}</h{n}>")
            i+=1; continue
        if list_type and pending_list_blank and re.match(r"^\s{2,}\S", line):
            out.append("<p>" + md_inline(line.strip()) + "</p>"); pending_list_blank=False; i+=1; continue
        m=re.match(r"^(\s*)[-*]\s+(.*)$", line)
        if m:
            depth=min(5, len(m.group(1).replace("\t", "    ")) // 2)
            item=m.group(2)
            task=re.match(r"^\[( |x|X)\]\s+(.*)$", item)
            if task:
                checked=" checked" if task.group(1).lower()=="x" else ""
                item=f"<input type='checkbox' disabled{checked}> " + md_inline(task.group(2))
            else:
                item=md_inline(item)
            add_list_item('ul', depth, item); i+=1; continue
        m=re.match(r"^(\s*)(\d+)[.)]\s+(.*)$", line)
        if m:
            depth=min(5, len(m.group(1).replace("\t", "    ")) // 2)
            add_list_item('ol', depth, md_inline(m.group(3)), int(m.group(2))); i+=1; continue
        if list_type and last_li_open and (not pending_list_blank or line[:1].isspace()):
            out.append("<p>" + md_inline(line.strip()) + "</p>"); i+=1; continue
        if list_type and pending_list_blank:
            close_list()
        para.append(line); i+=1
    close_quote(); flush_para(); close_list()
    if in_code: out.append(_code_block("\n".join(code), code_lang))
    return "\n".join(out)


def _code_block(code: str, lang: str = "") -> str:
    lang = (lang or "").strip()
    lang_esc = html.escape(lang)
    name = html.escape(lang or "code")
    body = highlight_code(code, lang)
    return (
        f'<figure class="code-block" data-lang="{lang_esc}">'
        f'<div class="code-head"><span class="dot d-r"></span><span class="dot d-y"></span>'
        f'<span class="dot d-g"></span><span class="code-name">{name}</span>'
        f'<button class="code-copy" type="button" onclick="copyCode(this)" aria-label="复制代码">复制</button></div>'
        f'<pre><code class="language-{lang_esc or "text"}">{body}</code></pre>'
        f'</figure>'
    )


def shorten_sidebar_label(path: str, max_len: int = 52) -> str:
    if len(path) <= max_len:
        return path
    parts = path.split("/")
    if len(parts) > 2:
        candidate = f"{parts[0]}/.../{parts[-1]}"
        if len(candidate) <= max_len:
            return candidate
        path = candidate
    keep = max_len - 3
    head = max(14, keep // 2)
    tail = max(10, keep - head)
    if head + tail > keep:
        tail = keep - head
    return f"{path[:head]}...{path[-tail:]}"



def load_repo_progress(repo_id: str | None) -> dict | None:
    if not repo_id:
        return None
    progress_path = BASE / "generated" / repo_id / "progress.json"
    if not progress_path.exists():
        return None
    try:
        return json.loads(progress_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def progress_card_html(repo_id: str | None) -> str:
    pr = load_repo_progress(repo_id)
    if not pr:
        return "<div class='progress-card'><div class='progress-label'>认知地图</div><strong>准备中</strong><div class='progress'><span></span></div><small>正在生成项目级阅读地图</small></div>"
    done = int(pr.get('core_done') or pr.get('done') or 0)
    total = int(pr.get('core_total') or pr.get('total') or 0)
    skipped = int(pr.get('skipped') or 0)
    percent = float(pr.get('percent') or (done / total * 100 if total else 0))
    status = html.escape(str(pr.get('status') or 'running'))
    current = html.escape(str(pr.get('current') or ''))
    unit = html.escape(str(pr.get('unit') or '核心文档'))
    skipped_text = f"<br>已跳过：{skipped} 个低价值节点" if skipped else ""
    coverage = html.escape(str(pr.get('coverage') or '认知地图生成'))
    return f"<div class='progress-card'><div class='progress-label'>{coverage}</div><strong>{done} / {total}</strong><div class='progress'><span style='width:{max(0,min(100,percent)):.1f}%'></span></div><small>{unit} 完成率 {percent:.1f}%{skipped_text}<br>状态：{status}<br>{current}</small></div>"

def page(title: str, body: str, sidebar: str = "", repo_id: str | None = None) -> bytes:
    has_sidebar = bool(sidebar.strip())
    escaped_title = html.escape(title)
    progress = progress_card_html(repo_id) if has_sidebar else ""
    sidebar_panel = (
        "<div class='sidebar-panel'>"
        "<a class='sidebar-home' href='/'>‹ 返回首页</a>"
        f"{progress}"
        "<div class='sidebar-search'><input id='nav-search' type='search' placeholder='搜索目录 / 文件 / 函数' aria-label='搜索文档'></div>"
        f"{sidebar}"
        "</div>"
    ) if has_sidebar else ""
    mobile_nav = (
        "<details class='mobile-nav' id='mobile-nav'>"
        "<summary><span class='m-nav-icon' aria-hidden='true'>☰</span><span>文档目录</span><span class='chevron'>⌄</span></summary>"
        f"<div class='mobile-nav-body'>{sidebar_panel}</div>"
        "</details>"
    ) if has_sidebar else ""
    aside = f"<aside class='sidebar' id='doc-sidebar'><div class='sidebar-inner'>{sidebar_panel}</div></aside>" if has_sidebar else ""
    rightbar = (
        "<aside class='toc-rail' aria-label='本页目录'>"
        "<div class='rail-card'><div class='rail-label'>本页目录</div>"
        "<div id='page-toc' class='page-toc'><span class='muted'>加载中…</span></div></div>"
        "</aside>"
    ) if has_sidebar else ""
    layout_class = "doc-layout has-toc" if has_sidebar else "home-layout"
    if has_sidebar:
        main_inner = "<main class='main'><div class='doc-main'><article class='prose'>" + body + "</article></div></main>"
    elif body.lstrip().startswith("<div class='home-page'"):
        main_inner = "<main class='main'><div class='home-wrap'>" + body + "</div></main>"
    else:
        main_inner = "<main class='main'><div class='doc-main'><article class='prose'>" + body + "</article></div></main>"
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#ffffff"><title>{escaped_title}</title>
<style>
@import url('/assets/fonts/noto-sans-sc-400.css');
@import url('/assets/fonts/noto-sans-sc-700.css');
:root{{--bg:#ffffff;--bg-soft:#fafafa;--hover:#f4f4f5;--card:#ffffff;--text:#18181b;--text-2:#3f3f46;--muted:#71717a;--muted-2:#a1a1aa;--border:#e4e4e7;--border-strong:#d4d4d8;--primary:#18181b;--primary-fg:#ffffff;--link:#2563eb;--link-hover:#1d4ed8;--code-bg:#0a0a0a;--code-border:#27272a;--code-text:#e4e4e7;--code-muted:#71717a;--blue:#3b82f6;--emerald:#10b981;--purple:#a855f7;--amber:#f59e0b;--red:#ef4444;--header-h:56px;--sidebar-w:264px;--rail-w:220px;color-scheme:light}}
:root[data-theme='dark']{{--bg:#09090b;--bg-soft:#18181b;--hover:#27272a;--card:#0a0a0a;--text:#fafafa;--text-2:#d4d4d8;--muted:#a1a1aa;--muted-2:#71717a;--border:#27272a;--border-strong:#3f3f46;--primary:#fafafa;--primary-fg:#18181b;--link:#60a5fa;--link-hover:#93c5fd;--code-bg:#000000;--code-border:#27272a;--code-text:#e4e4e7;--code-muted:#71717a;color-scheme:dark}}
*{{box-sizing:border-box}}html{{font-size:16px;scroll-padding-top:calc(var(--header-h) + 20px);-webkit-text-size-adjust:100%}}body{{margin:0;background:var(--bg);color:var(--text);font-family:'Noto Sans SC',-apple-system,BlinkMacSystemFont,'Segoe UI','Helvetica Neue',Arial,'PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;line-height:1.6;overflow-x:hidden;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}}a{{color:inherit;text-decoration:none;overflow-wrap:anywhere}}a:hover{{color:var(--text)}}img{{max-width:100%}}p,li,small,summary{{overflow-wrap:anywhere;word-break:break-word}}::selection{{background:color-mix(in srgb,var(--blue) 22%,transparent)}}.muted{{color:var(--muted)!important}}small{{color:var(--muted);font-size:.8rem}}
.header{{position:sticky;top:0;z-index:50;background:color-mix(in srgb,var(--bg) 80%,transparent);backdrop-filter:saturate(180%) blur(10px);-webkit-backdrop-filter:saturate(180%) blur(10px);border-bottom:1px solid var(--border)}}.header-in{{max-width:80rem;margin:0 auto;height:var(--header-h);display:flex;align-items:center;gap:.75rem;padding:0 1rem}}.brand{{display:flex;align-items:center;gap:.6rem;font-weight:700;font-size:1.02rem;color:var(--text);white-space:nowrap}}.brand:hover{{color:var(--text)}}.brand-mark{{width:26px;height:26px;border-radius:8px;background:linear-gradient(135deg,var(--blue),var(--purple));display:inline-grid;place-items:center;color:#fff;flex:0 0 auto}}.header-spacer{{flex:1 1 auto}}.icon-btn{{width:36px;height:36px;border:1px solid var(--border);border-radius:9px;background:var(--card);color:var(--muted);display:inline-flex;align-items:center;justify-content:center;cursor:pointer;font-size:15px;line-height:1}}.icon-btn:hover{{color:var(--text);background:var(--hover);border-color:var(--border-strong)}}.theme-toggle .moon{{display:none}}:root[data-theme='dark'] .theme-toggle .moon{{display:inline}}:root[data-theme='dark'] .theme-toggle .sun{{display:none}}.btn-primary{{height:36px;padding:0 14px;border-radius:9px;background:var(--primary);color:var(--primary-fg);font-weight:600;font-size:.85rem;border:0;cursor:pointer;display:inline-flex;align-items:center;gap:6px;white-space:nowrap;text-decoration:none}}.btn-primary:hover{{opacity:.88;color:var(--primary-fg)}}
.layout{{max-width:80rem;margin:0 auto;padding:0 1rem}}@media(min-width:640px){{.layout{{padding:0 1.5rem}}}}.doc-layout{{display:grid;grid-template-columns:var(--sidebar-w) minmax(0,1fr);gap:2.5rem;padding:2rem 0 4rem;align-items:start}}.home-layout{{padding:0}}.main{{min-width:0}}.doc-main{{max-width:48rem;margin:0 auto}}.sidebar{{position:sticky;top:calc(var(--header-h) + 1.25rem);align-self:start;max-height:calc(100vh - var(--header-h) - 2.5rem);overflow:auto;padding:0 1rem 2rem 0;scrollbar-width:thin}}.sidebar-panel{{display:flex;flex-direction:column;gap:1rem}}.sidebar-home{{font-size:.78rem;font-weight:600;color:var(--muted);padding:2px 0}}.sidebar-home:hover{{color:var(--text)}}.sidebar-search input{{width:100%;border:1px solid var(--border);background:var(--bg-soft);border-radius:8px;padding:7px 11px;font:inherit;font-size:.8rem;color:var(--text);outline:0}}.sidebar-search input:focus{{border-color:var(--border-strong)}}.sidebar-search input::placeholder{{color:var(--muted)}}
.progress-card{{border:1px solid var(--border);border-radius:10px;background:var(--bg-soft);padding:12px 13px}}.progress-label{{font-size:.68rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:var(--muted)}}.progress-card strong{{display:block;font-size:1.1rem;margin:6px 0 4px;color:var(--text)}}.progress{{height:6px;background:var(--hover);border-radius:99px;overflow:hidden;margin:6px 0}}.progress span{{display:block;height:100%;background:linear-gradient(90deg,var(--blue),var(--emerald));border-radius:inherit}}.progress-card small{{font-size:.7rem;color:var(--muted);line-height:1.55;display:block}}.repo-id{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.7rem;color:var(--muted-2);padding:2px 0;word-break:break-all}}
.repo-nav{{display:flex;flex-direction:column;gap:1.25rem}}.nav-section{{display:flex;flex-direction:column}}.nav-section-title{{display:flex;align-items:center;gap:7px;font-size:.68rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);margin:0 0 8px;padding:0 8px}}.nav-section-title::before{{content:'';width:8px;height:8px;border-radius:50%;background:var(--dot,var(--muted-2));flex:0 0 auto}}.nav-section--blue{{--dot:var(--blue)}}.nav-section--emerald{{--dot:var(--emerald)}}.nav-section--purple{{--dot:var(--purple)}}.nav-section--amber{{--dot:var(--amber)}}.nav-section--red{{--dot:var(--red)}}.overview-link{{display:block;padding:7px 10px;border-radius:7px;font-size:.85rem;color:var(--text-2);line-height:1.4;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}.overview-link:hover{{background:var(--hover);color:var(--text)}}.repo-tree{{display:flex;flex-direction:column;gap:1px}}.tree-node,.tree-leaf{{display:block;min-width:0}}.tree-node>summary,.tree-leaf{{display:flex;align-items:center;gap:5px;padding:6px 10px;border-radius:7px;font-size:.85rem;color:var(--text-2);line-height:1.4}}.tree-node>summary{{cursor:pointer;list-style:none;user-select:none}}.tree-node>summary::-webkit-details-marker{{display:none}}.tree-toggle,.tree-toggle-spacer{{flex:0 0 auto;width:16px;height:16px;padding:0;border:0;background:transparent;color:var(--muted);cursor:pointer;font:700 11px/1 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;display:inline-flex;align-items:center;justify-content:center}}.tree-toggle-spacer{{visibility:hidden;cursor:default}}.tree-node[open] .tree-toggle{{transform:rotate(90deg)}}.tree-dir-link{{flex:1;min-width:0;color:inherit}}.tree-node>summary:hover,.tree-leaf:hover{{background:var(--hover);color:var(--text)}}.is-active{{background:var(--hover)!important;color:var(--text)!important;font-weight:600}}.tree-children{{display:flex;flex-direction:column;gap:1px;margin-left:9px;padding-left:10px;border-left:1px solid var(--border)}}.tree-label{{display:block;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}.tree-missing{{opacity:.55}}
.prose{{color:var(--text-2);font-size:16px;line-height:1.8}}.prose>*:first-child{{margin-top:0}}.prose h1{{font-size:1.875rem;font-weight:700;line-height:1.3;margin:0 0 1.5rem;color:var(--text);letter-spacing:-.01em;overflow-wrap:anywhere}}.prose h2{{font-size:1.375rem;font-weight:600;line-height:1.4;margin:2.5rem 0 1rem;color:var(--text);padding-bottom:.5rem;border-bottom:1px solid var(--border);overflow-wrap:anywhere}}.prose h3{{font-size:1.125rem;font-weight:600;line-height:1.45;margin:2rem 0 .75rem;color:var(--text);overflow-wrap:anywhere}}.prose h4,.prose h5,.prose h6{{font-size:1rem;font-weight:600;line-height:1.5;margin:1.5rem 0 .5rem;color:var(--text)}}.prose p{{margin:0 0 1.1rem}}.prose ul,.prose ol{{margin:0 0 1.1rem;padding-left:1.5rem}}.prose li{{margin:.4rem 0}}.prose li::marker{{color:var(--muted)}}.prose li.depth-1{{margin-left:1rem}}.prose li.depth-2{{margin-left:2rem}}.prose li.depth-3{{margin-left:3rem}}.prose li.depth-4,.prose li.depth-5{{margin-left:4rem}}.prose li input[type='checkbox']{{margin-right:.5rem;vertical-align:-1px}}.prose strong{{font-weight:650;color:var(--text)}}.prose a{{color:var(--link);text-decoration:underline;text-decoration-color:color-mix(in srgb,var(--link) 32%,transparent);text-underline-offset:2px}}.prose a:hover{{color:var(--link-hover)}}.prose hr{{border:0;border-top:1px solid var(--border);margin:2.5rem 0}}.prose img{{border-radius:10px;border:1px solid var(--border)}}.prose h1.doc-title{{font-size:inherit;line-height:1.25;margin-bottom:2rem}}.doc-title-kind{{display:inline-flex;align-items:center;margin:0 0 12px;padding:3px 10px;border-radius:999px;background:color-mix(in srgb,var(--blue) 12%,transparent);color:var(--blue);font-size:.78rem;font-weight:600;line-height:1.4}}:root[data-theme='dark'] .doc-title-kind{{color:#93c5fd}}.doc-title-path{{display:block;color:var(--text);font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;font-size:1.6rem;font-weight:600;line-height:1.3;overflow-wrap:anywhere;word-break:break-word}}
.prose blockquote{{margin:1.5rem 0;padding:.85rem 1.1rem;border-left:3px solid var(--blue);background:var(--bg-soft);border-radius:0 10px 10px 0;color:var(--text-2)}}.prose blockquote p{{margin:0}}.prose blockquote p+p{{margin-top:.6rem}}.prose code{{background:var(--hover);color:var(--text);padding:.15em .4em;border-radius:6px;font:.875em ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace;border:1px solid var(--border);overflow-wrap:anywhere;-webkit-box-decoration-break:clone;box-decoration-break:clone}}.prose pre{{background:var(--bg-soft);border:1px solid var(--border);border-radius:10px;padding:14px 16px;overflow:auto;margin:1.25rem 0;font:13px/1.65 ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;color:var(--text-2)}}.prose pre code{{display:block;min-width:max-content;background:none;border:0;padding:0;color:inherit;font-size:inherit;border-radius:0}}.table-wrap{{max-width:100%;overflow:auto;margin:1.5rem 0;border:1px solid var(--border);border-radius:10px}}table{{width:100%;border-collapse:collapse;background:var(--card)}}th,td{{padding:10px 13px;border-bottom:1px solid var(--border);font-size:.9rem;line-height:1.55;text-align:left;vertical-align:top}}tr:last-child td{{border-bottom:0}}th{{background:var(--bg-soft);color:var(--text);font-weight:600}}
.code-block{{margin:1.5rem 0;border:1px solid var(--code-border);border-radius:12px;overflow:hidden;background:var(--code-bg)}}.code-head{{display:flex;align-items:center;gap:6px;padding:10px 14px;border-bottom:1px solid var(--code-border);background:rgba(255,255,255,.025)}}.dot{{width:11px;height:11px;border-radius:50%;display:inline-block;flex:0 0 auto}}.d-r{{background:#ff5f57}}.d-y{{background:#febc2e}}.d-g{{background:#28c840}}.code-name{{margin-left:8px;color:var(--code-muted);font:12px/1 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}}.code-copy{{margin-left:auto;border:0;background:transparent;color:var(--code-muted);font:600 12px/1 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;cursor:pointer;padding:5px 9px;border-radius:6px}}.code-copy:hover{{color:var(--code-text);background:rgba(255,255,255,.07)}}.code-block pre{{margin:0;background:transparent!important;border:0!important;border-radius:0!important;padding:16px;overflow:auto}}.code-block code{{display:block;min-width:max-content;background:none;border:0;padding:0;color:var(--code-text);font:13px/1.7 ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,'Liberation Mono','Courier New',monospace;white-space:pre}}.tok-kw{{color:#c084fc}}.tok-str{{color:#86efac}}.tok-com{{color:#71717a;font-style:italic}}.tok-num{{color:#fcd34d}}.tok-fn{{color:#60a5fa}}.tok-dec{{color:#f472b6}}
.home-wrap{{max-width:80rem;margin:0 auto;padding:3rem 0 5rem}}.home-page{{display:flex;flex-direction:column}}.home-hero{{text-align:center;padding:1.5rem 0 2rem}}.home-kicker{{margin:0 0 12px;color:var(--blue);font-size:.78rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase}}:root[data-theme='dark'] .home-kicker{{color:#60a5fa}}.home-title{{margin:0;font-size:clamp(2.1rem,5vw,3.25rem);line-height:1.1;letter-spacing:-.03em;font-weight:800;color:var(--text)}}.home-subtitle{{max-width:42rem;margin:1.1rem auto 0;color:var(--muted);font-size:1.0625rem;line-height:1.7}}.source-form{{display:flex;gap:8px;max-width:40rem;margin:2rem auto 0;padding:7px;background:var(--card);border:1px solid var(--border);border-radius:14px;box-shadow:0 1px 3px rgba(0,0,0,.05),0 8px 24px rgba(0,0,0,.04)}}.source-form input{{flex:1 1 auto;min-width:0;border:0;outline:0;background:transparent;color:var(--text);font:inherit;padding:12px 14px}}.source-form input::placeholder{{color:var(--muted)}}.source-form button{{flex:0 0 auto;border:0;border-radius:10px;background:var(--primary);color:var(--primary-fg);font:600 .9rem/1.4 inherit;padding:12px 18px;cursor:pointer;white-space:nowrap}}.source-form button:hover{{opacity:.88}}.home-library{{margin-top:3.5rem}}.home-section-head{{margin-bottom:1.25rem}}.home-section-kicker{{margin:0;color:var(--muted);font-size:.72rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase}}.home-section-title{{margin:.25rem 0 0;font-size:1.5rem;font-weight:700;color:var(--text)}}.repo-list{{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:1rem;list-style:none;margin:0;padding:0}}.repo-card{{margin:0;border:1px solid var(--border);border-radius:14px;background:var(--card);overflow:hidden;transition:border-color .15s ease,transform .15s ease,box-shadow .15s ease}}.repo-card:hover{{border-color:var(--border-strong);transform:translateY(-2px);box-shadow:0 10px 28px rgba(0,0,0,.07)}}.repo-card-link{{display:flex;flex-direction:column;gap:9px;padding:18px;height:100%;color:inherit}}.repo-card-top{{display:flex;align-items:center;justify-content:space-between;gap:8px}}.repo-kicker{{display:inline-flex;align-items:center;padding:3px 9px;border-radius:999px;font-size:.68rem;font-weight:600;letter-spacing:.02em;background:var(--hover);color:var(--muted)}}.card-github .repo-kicker{{background:color-mix(in srgb,var(--blue) 12%,transparent);color:var(--blue)}}.card-gitlab .repo-kicker,.card-remote .repo-kicker{{background:color-mix(in srgb,var(--amber) 14%,transparent);color:var(--amber)}}.card-local .repo-kicker{{background:color-mix(in srgb,var(--emerald) 12%,transparent);color:var(--emerald)}}.repo-status{{display:inline-flex;align-items:center;padding:3px 9px;border-radius:999px;font-size:.68rem;font-weight:600;background:var(--hover);color:var(--muted)}}.status-completed .repo-status{{background:color-mix(in srgb,var(--emerald) 14%,transparent);color:var(--emerald)}}.status-running .repo-status{{background:color-mix(in srgb,var(--blue) 14%,transparent);color:var(--blue)}}.status-queued .repo-status{{background:color-mix(in srgb,var(--amber) 14%,transparent);color:var(--amber)}}.status-failed .repo-status{{background:color-mix(in srgb,var(--red) 14%,transparent);color:var(--red)}}.repo-title{{font-size:1.125rem;line-height:1.3;font-weight:700;color:var(--text);overflow-wrap:anywhere;word-break:break-word}}.repo-subtitle{{color:var(--text-2);font-size:.85rem;font-weight:500;line-height:1.5;overflow-wrap:anywhere;word-break:break-word}}.repo-meta{{color:var(--muted);font-size:.74rem;line-height:1.5;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}.repo-footer{{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:auto;padding-top:11px;border-top:1px solid var(--border)}}.repo-open{{color:var(--text);font-size:.8rem;font-weight:600}}.repo-card:hover .repo-open{{color:var(--blue)}}.repo-idline{{color:var(--muted-2);font-size:.68rem;line-height:1.5;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;overflow-wrap:anywhere;word-break:break-all}}
.toc-rail{{display:none}}.rail-card{{display:flex;flex-direction:column;gap:8px;position:sticky;top:calc(var(--header-h) + 1.25rem)}}.rail-label{{font-size:.68rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:var(--muted)}}.page-toc{{display:flex;flex-direction:column;gap:1px}}.toc-link{{display:block;padding:5px 10px;border-radius:6px;font-size:.78rem;color:var(--muted);line-height:1.4;border-left:2px solid transparent;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}.toc-link:hover{{color:var(--text);background:var(--hover)}}.toc-lv-h2{{padding-left:22px}}.toc-lv-h3{{padding-left:34px}}@media(min-width:1280px){{.doc-layout.has-toc{{grid-template-columns:var(--sidebar-w) minmax(0,1fr) var(--rail-w);gap:2.5rem}}.toc-rail{{display:block}}}}
.mobile-nav{{display:none;position:sticky;top:var(--header-h);z-index:30;background:var(--bg);border-bottom:1px solid var(--border);padding:10px 1rem}}.mobile-nav summary{{display:flex;align-items:center;gap:8px;list-style:none;cursor:pointer;padding:10px 12px;border-radius:9px;border:1px solid var(--border);background:var(--card);font-weight:600;font-size:.9rem;color:var(--text)}}.mobile-nav summary::-webkit-details-marker{{display:none}}.mobile-nav .chevron{{margin-left:auto;transition:transform .15s ease;color:var(--muted)}}.mobile-nav[open] .chevron{{transform:rotate(180deg)}}.m-nav-icon{{font-size:1rem}}.mobile-nav-body{{margin-top:10px;max-height:70vh;overflow:auto;background:var(--card);border:1px solid var(--border);border-radius:10px;padding:14px}}
@media(max-width:1023px){{.doc-layout{{grid-template-columns:minmax(0,1fr);gap:0;padding:1.25rem 0 3rem}}.sidebar{{display:none}}.mobile-nav{{display:block}}.doc-main{{max-width:100%}}}}
@media(max-width:900px){{.home-wrap{{padding:2rem 0 4rem}}.home-title{{font-size:2rem}}.home-subtitle{{font-size:1rem}}.source-form{{flex-direction:column;border-radius:14px}}.source-form button{{width:100%}}.repo-list{{grid-template-columns:1fr}}.prose h1{{font-size:1.6rem}}.prose h2{{font-size:1.2rem}}}}
</style><script>
(function(){{try{{var t=localStorage.getItem('repo-docs-theme')||'light';document.documentElement.dataset.theme=t;}}catch(e){{document.documentElement.dataset.theme='light';}}}})();
function toggleTheme(){{var r=document.documentElement;var n=r.dataset.theme==='light'?'dark':'light';r.dataset.theme=n;try{{localStorage.setItem('repo-docs-theme',n)}}catch(e){{}}}}
function copyCode(btn){{var pre=btn.closest('.code-block')&&btn.closest('.code-block').querySelector('pre');if(!pre)return;var txt=pre.innerText;var done=function(){{var o=btn.textContent;btn.textContent='已复制';setTimeout(function(){{btn.textContent=o}},1500)}};try{{navigator.clipboard.writeText(txt).then(done,function(){{}})}}catch(e){{}}}}
(function(){{
  function syncSidebarWidth(){{}}
  function makeSearch(){{
    var input=document.getElementById('nav-search');
    if(!input) return;
    var items=[].slice.call(document.querySelectorAll('.overview-link,.tree-dir-link,.tree-leaf'));
    var sections=[].slice.call(document.querySelectorAll('.nav-section'));
    input.addEventListener('input', function(){{
      var q=input.value.trim().toLowerCase();
      items.forEach(function(el){{
        var t=(el.getAttribute('title')||el.textContent||'').toLowerCase();
        var show=!q||t.indexOf(q)>=0;
        el.style.display=show?'':'none';
      }});
      sections.forEach(function(sec){{
        var has=[].slice.call(sec.querySelectorAll('.overview-link,.tree-dir-link,.tree-leaf')).some(function(el){{ return el.style.display!== 'none'; }});
        sec.style.display=has?'':'none';
      }});
    }});
  }}
  function restoreDetails(){{
    var openSet={{}};
    try{{openSet=JSON.parse(localStorage.getItem('repo-docs-open')||'{{}}')||{{}};}}catch(e){{}}
    document.querySelectorAll('.tree-node').forEach(function(d){{
      var summary=d.querySelector('.tree-summary');
      var toggle=d.querySelector('.tree-toggle');
      var link=d.querySelector('.tree-dir-link');
      if(!summary) return;
      var k=summary.getAttribute('title')||summary.textContent.trim();
      if(openSet[k]) d.open=true;
      d.addEventListener('toggle', function(){{
        var key=summary.getAttribute('title')||summary.textContent.trim();
        openSet[key]=d.open;
        try{{localStorage.setItem('repo-docs-open', JSON.stringify(openSet));}}catch(e){{}}
      }});
      if(toggle){{
        toggle.addEventListener('click', function(e){{
          e.preventDefault();
          e.stopPropagation();
          d.open=!d.open;
        }});
      }}
      if(link){{
        link.addEventListener('click', function(e){{
          var href=d.getAttribute('data-doc');
          if(!href) e.preventDefault();
        }});
      }}
    }});
  }}
  function highlightCurrent(){{
    var p=location.pathname.replace(/\\/$/,'');
    var best=null;
    document.querySelectorAll('.overview-link,.tree-dir-link,.tree-leaf').forEach(function(el){{
      el.classList.remove('is-active');
      var href=el.getAttribute('href');
      if(!href || href==='#') return;
      var a=document.createElement('a'); a.href=href;
      var hp=(a.pathname||'').replace(/\\/$/,'');
      if(hp===p && (!best || (href.length > (best.getAttribute('href')||'').length))) best=el;
    }});
    if(best){{
      best.classList.add('is-active');
      var parent=best.closest('.tree-node');
      while(parent){{ parent.open=true; parent=parent.parentElement ? parent.parentElement.closest('.tree-node') : null; }}
    }}
  }}

  function buildPageToc(){{
    var toc=document.getElementById('page-toc');
    if(!toc) return;
    var hs=[].slice.call(document.querySelectorAll('.prose h1,.prose h2,.prose h3'));
    if(!hs.length){{ toc.innerHTML='<span class="muted">本页暂无目录</span>'; return; }}
    toc.innerHTML=hs.map(function(h,i){{
      if(!h.id) h.id='sec-'+i;
      var text=h.textContent||'';
      return '<a class="toc-link toc-lv-'+h.tagName.toLowerCase()+'" href="#'+h.id+'" title="'+text.replace(/"/g,'&quot;')+'">'+text+'</a>';
    }}).join('');
  }}
  function init(){{ syncSidebarWidth(); makeSearch(); restoreDetails(); highlightCurrent(); buildPageToc(); }}
  if(document.readyState==='loading'){{ document.addEventListener('DOMContentLoaded', init); }} else {{ init(); }}
}})();
</script></head>
<body><header class="header"><div class="header-in"><a class="brand" href="/"><span class="brand-mark" aria-hidden="true"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="8 6 2 12 8 18"></polyline><polyline points="16 6 22 12 16 18"></polyline></svg></span><span class="brand-name">Repo Docs</span></a><div class="header-spacer"></div><button class="icon-btn theme-toggle" type="button" onclick="toggleTheme()" aria-label="切换深色/浅色模式"><span class="moon">☾</span><span class="sun">☀</span></button><a class="btn-primary header-cta" href="/">生成文档</a></div></header>{mobile_nav}<div class="layout"><div class="{layout_class}">{aside}{main_inner}{rightbar}</div></div></body></html>""".encode()


OVERVIEW_DOCS = [
    ("index.md", "推荐阅读顺序"),
    ("00-overview.md", "项目整体介绍"),
    ("01-tech-stack.md", "技术栈与预备知识"),
    ("02-architecture.md", "架构与目录关系"),
    ("03-runtime-flow.md", "运行链路 / 数据流"),
    ("04-reading-guide.md", "阅读指南"),
]

IMPORTANT_ORDER = {
    "src": 0, "apps": 1, "packages": 2, "package.json": 3, "README.md": 4,
    "index.ts": 5, "index.tsx": 5, "index.js": 5, "main.ts": 6, "main.tsx": 6,
    "app.ts": 7, "app.tsx": 7, "server.ts": 8, "router.ts": 9, "routes": 10,
}


def doc_href(repo_id: str, md_rel: str) -> str:
    target = md_rel[:-3] if md_rel.endswith(".md") else md_rel
    return f"/repos/{repo_id}/{urllib.parse.quote(target)}"


def natural_key(name: str):
    return (IMPORTANT_ORDER.get(name, 100), [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)])


def ensure_tree_path(root: dict, parts: list[str]) -> dict:
    node = root
    for part in parts:
        node = node.setdefault("children", {}).setdefault(part, {"kind": "dir", "children": {}})
    return node


def decode_doc_path(prefix: str, rel: str) -> str:
    stem = rel[len(prefix):-3]
    return stem.replace("__", "/")


def add_dir_doc(tree: dict, source_path: str, md_rel: str) -> None:
    parts = [x for x in source_path.split("/") if x]
    if not parts:
        return
    node = ensure_tree_path(tree, parts)
    node["kind"] = "dir"
    node["doc"] = md_rel
    node["source_path"] = source_path


def add_file_doc(tree: dict, source_path: str, md_rel: str) -> None:
    parts = [x for x in source_path.split("/") if x]
    if not parts:
        return
    parent = ensure_tree_path(tree, parts[:-1]) if len(parts) > 1 else tree
    node = parent.setdefault("children", {}).setdefault(parts[-1], {"kind": "file", "children": {}})
    node["kind"] = "file"
    node["doc"] = md_rel
    node["source_path"] = source_path


def add_function_doc(tree: dict, source_path: str, func_name: str, md_rel: str) -> None:
    parts = [x for x in source_path.split("/") if x]
    if not parts:
        return
    parent = ensure_tree_path(tree, parts[:-1]) if len(parts) > 1 else tree
    file_node = parent.setdefault("children", {}).setdefault(parts[-1], {"kind": "file", "children": {}})
    file_node["kind"] = "file"
    file_node.setdefault("children", {})[func_name] = {"kind": "function", "doc": md_rel, "source_path": f"{source_path}::{func_name}", "children": {}}


def tree_item_html(repo_id: str, name: str, node: dict, depth: int = 0) -> str:
    kind = node.get("kind", "dir")
    children = node.get("children", {})
    source_path = node.get("source_path") or name
    title = html.escape(source_path)
    display = name if kind != 'dir' else name
    display_html = html.escape(display)
    doc = node.get("doc")
    indent = min(depth, 8)
    if kind == "function" and not display.endswith(")"):
        display_html = html.escape(display + "()")
    if children:
        child_html = "".join(
            tree_item_html(repo_id, child_name, child_node, depth + 1)
            for child_name, child_node in sorted(children.items(), key=lambda kv: (0 if kv[1].get("kind") == "dir" else 1, natural_key(kv[0])))
        )
        doc_href_attr = doc_href(repo_id, doc) if doc else ""
        open_attr = " open" if depth <= 0 else ""
        return f"<details class='tree-node tree-{kind} depth-{indent}' data-doc='{doc_href_attr}'{open_attr}><summary class='tree-summary' title='{title}'><button class='tree-toggle' type='button' aria-label='展开或折叠'>▸</button><a class='tree-dir-link tree-label' href='{doc_href_attr or '#'}' title='{title}'>{display_html}</a></summary><div class='tree-children'>{child_html}</div></details>"
    if doc:
        return f"<a class='tree-leaf tree-{kind} depth-{indent}' href='{doc_href(repo_id, doc)}' title='{title}'><span class='tree-toggle-spacer' aria-hidden='true'></span><span class='tree-label'>{display_html}</span></a>"
    return f"<span class='tree-leaf tree-missing depth-{indent}' title='{title}'><span class='tree-toggle-spacer' aria-hidden='true'></span><span class='tree-label'>{display_html}</span></span>"


def repo_sidebar(repo_id: str, gen: Path) -> str:
    files = sorted(
        rel
        for p in gen.rglob("*.md")
        for rel in [str(p.relative_to(gen)).replace(os.sep, "/")]
        if not rel.startswith("codex_debug/")
    ) if gen.exists() else []
    file_set = set(files)
    consumed: set[str] = set()

    overview_items = []
    for rel, label in OVERVIEW_DOCS:
        if rel in file_set:
            consumed.add(rel)
            overview_items.append(f"<a class='overview-link' href='{doc_href(repo_id, rel)}' title='{html.escape(rel)}'>{html.escape(label)}</a>")

    tree = {"children": {}}
    for rel in files:
        if rel in consumed:
            continue
        if rel.startswith("directories/") and rel.endswith(".md"):
            source_path = decode_doc_path("directories/", rel)
            add_dir_doc(tree, source_path, rel)
            consumed.add(rel)
        elif rel.startswith("files/") and rel.endswith(".md"):
            source_path = decode_doc_path("files/", rel)
            add_file_doc(tree, source_path, rel)
            consumed.add(rel)
        elif rel.startswith("functions/") and rel.endswith(".md"):
            raw = decode_doc_path("functions/", rel)
            if "::" in raw:
                source_path, func_name = raw.split("::", 1)
            elif "__" in rel[len("functions/"):-3]:
                # Best-effort fallback for generated names like functions/path__func.md.
                stem = rel[len("functions/"):-3]
                left, func_name = stem.rsplit("__", 1)
                source_path = left.replace("__", "/")
            else:
                source_path, func_name = raw, Path(raw).stem
            add_function_doc(tree, source_path, func_name, rel)
            consumed.add(rel)

    tree_html = "".join(
        tree_item_html(repo_id, name, node, 0)
        for name, node in sorted(tree.get("children", {}).items(), key=lambda kv: (0 if kv[1].get("kind") == "dir" else 1, natural_key(kv[0])))
    ) or "<p class='muted'>暂无源码结构文档</p>"

    orphan_items = []
    for rel in files:
        if rel not in consumed:
            label = Path(rel).stem
            orphan_items.append(f"<a class='overview-link' href='{doc_href(repo_id, rel)}' title='{html.escape(rel)}'>{html.escape(label)}</a>")
    orphan_html = f"<section class='nav-section nav-section--amber'><div class='nav-section-title'>其他文档</div>{''.join(orphan_items)}</section>" if orphan_items else ""

    overview_html = "".join(overview_items) or "<p class='muted'>暂无总览文档</p>"
    return (
        f"<p class='repo-id' title='{html.escape(repo_id)}'>{html.escape(repo_id)}</p>"
        "<nav class='repo-nav structured-nav' aria-label='文档目录'>"
        f"<section class='nav-section nav-section--blue'><div class='nav-section-title'>项目总览</div>{overview_html}</section>"
        f"<section class='nav-section nav-section--emerald'><div class='nav-section-title'>源码结构</div><div class='repo-tree'>{tree_html}</div></section>"
        f"{orphan_html}"
        "</nav>"
    )


class Handler(BaseHTTPRequestHandler):
    def send_html(self, title, body, code=200, sidebar=""):
        data=page(title,body,sidebar, getattr(self, "_current_repo_id", None)); self.send_response(code); self.send_header("Content-Type","text/html; charset=utf-8"); self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data)
    def send_json(self, obj, code=200):
        data=json.dumps(obj, ensure_ascii=False).encode("utf-8"); self.send_response(code); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data)
    def send_asset(self, path: str):
        rel = path[len("/assets/"):]
        target = (ASSETS / rel).resolve()
        if not str(target).startswith(str(ASSETS) + os.sep) or not target.exists() or not target.is_file():
            self.send_html("404","<h1>Not found</h1>",404); return
        content_types = {".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf", ".css": "text/css; charset=utf-8"}
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_types.get(target.suffix.lower(), "application/octet-stream"))
        self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    def redirect(self, loc):
        self.send_response(303); self.send_header("Location",loc); self.end_headers()
    def do_GET(self):
        u=urllib.parse.urlparse(self.path); path=urllib.parse.unquote(u.path)
        if path.startswith("/assets/"):
            self.send_asset(path); return
        if path=="/":
            with db() as con: repos=con.execute("SELECT * FROM repos ORDER BY updated_at DESC LIMIT 50").fetchall()
            repo_html="".join(repo_card_html(r) for r in repos) or "<li class='repo-card'><span class='muted'>还没有生成过项目文档。</span></li>"
            self.send_html("Repo Docs", f"<div class='home-page'><section class='home-hero'><p class='home-kicker'>AIWIKI</p><h1 class='home-title'>代码学习文档库</h1><p class='home-subtitle'>导入 GitHub/GitLab 仓库或 `/data/project` 下本地项目，生成结构化中文代码文档。</p><form class='source-form' method='post' action='/submit'><input name='source' aria-label='仓库地址或本地路径' placeholder='https://github.com/org/repo 或 /data/project/lobehub'><button type='submit'>生成学习文档</button></form></section><section class='home-library'><div class='home-section-head'><p class='home-section-kicker'>Project Library</p><div class='home-section-title'>已有项目</div></div><ul class='repo-list repo-grid'>{repo_html}</ul></section></div>") ; return
        if path.startswith("/jobs/"):
            jid=path.split("/",2)[2]
            with db() as con: j=con.execute("SELECT * FROM jobs WHERE job_id=?",(jid,)).fetchone()
            if not j: self.send_html("404","<h1>Job not found</h1>",404); return
            link=f"<p><a href='/repos/{j['repo_id']}/'>打开文档</a></p>" if j['status']=="completed" else "<script>setTimeout(()=>location.reload(),3000)</script>"
            self.send_html("Job", f"<h1>任务 {html.escape(jid)}</h1><p>状态：<b>{html.escape(j['status'])}</b></p><p>{html.escape(j['message'] or '')}</p>{link}<pre>{html.escape(j['log'] or '')}</pre>"); return
        if path.startswith("/repos/"):
            parts=path.strip("/").split("/",2); repo_id=parts[1]; sub=parts[2] if len(parts)>2 else ""
            gen=BASE/"generated"/repo_id
            if sub.rstrip("/") == "signals":
                qs=urllib.parse.parse_qs(u.query)
                try:
                    since=int(qs.get("since",["0"])[0] or 0)
                except ValueError:
                    since=0
                state=gen/"state.sqlite3"
                if not state.exists():
                    self.send_json({"signals":[]}); return
                signals=[]
                try:
                    con=sqlite3.connect(state, timeout=30); con.row_factory=sqlite3.Row
                    rows=con.execute("SELECT id,type,payload,at FROM signals WHERE id>? ORDER BY id LIMIT 200",(since,)).fetchall()
                    con.close()
                    for row in rows:
                        try:
                            payload=json.loads(row["payload"] or "{}")
                        except Exception:
                            payload=row["payload"]
                        signals.append({"id":row["id"],"type":row["type"],"payload":payload,"at":row["at"]})
                except Exception as e:
                    self.send_json({"signals":[],"error":str(e)},500); return
                self.send_json({"signals":signals}); return
            md = gen/(sub + ("" if sub.endswith(".md") else ".md")) if sub else gen/"index.md"
            self._current_repo_id = repo_id
            if not md.exists(): self.send_html("404","<h1>文档不存在</h1>",404,repo_sidebar(repo_id,gen)); return
            self.send_html(md.name, render_md(md.read_text(encoding="utf-8",errors="replace")), sidebar=repo_sidebar(repo_id,gen)); return
        self.send_html("404","<h1>Not found</h1>",404)
    def do_POST(self):
        if self.path!="/submit": self.send_html("404","<h1>Not found</h1>",404); return
        length=int(self.headers.get("content-length","0")); data=self.rfile.read(length).decode(); source=urllib.parse.parse_qs(data).get("source",[""])[0].strip()
        if not (is_remote(source) or allowed_local(source)):
            self.send_html("输入无效","<h1>输入无效</h1><p>只接受 GitHub/GitLab HTTPS URL，或 /data/project 下存在的本地目录。</p>",400); return
        rid=slugify(source); jid=job_id_for(source); t=now()
        with db() as con:
            con.execute("INSERT OR REPLACE INTO repos(repo_id,source,local_path,generated_path,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",(rid,source,"",str(BASE/"generated"/rid),"queued",t,t))
            con.execute("INSERT INTO jobs(job_id,repo_id,source,status,message,log,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",(jid,rid,source,"queued","已排队","",t,t))
        job_q.put(jid); self.redirect(f"/jobs/{jid}")
    def log_message(self, fmt, *args): print("%s - %s"%(self.address_string(), fmt%args), flush=True)


def main():
    ensure_dirs(); init_db(); threading.Thread(target=worker,daemon=True).start()
    srv=ThreadingHTTPServer((HOST,PORT),Handler)
    print(f"Repo docs service on http://{HOST}:{PORT}", flush=True)
    srv.serve_forever()

if __name__ == "__main__": main()
