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

HOST = os.environ.get("RDS_HOST", "127.0.0.1")
PORT = int(os.environ.get("RDS_PORT", "18081"))
BASE = Path(os.environ.get("RDS_BASE") or (Path(__file__).resolve().parent / "data")).resolve()
DB = BASE / "service.sqlite3"
LOCAL_ROOT = Path("/data/project").resolve()

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


def important_dirs(files: list[str], max_dirs: int = 18) -> list[str]:
    counts: dict[str, int] = {}
    for f in files:
        parts = f.split("/")
        if len(parts) > 1:
            for i in range(1, min(len(parts), 3)):
                d = "/".join(parts[:i])
                counts[d] = counts.get(d, 0) + 1
    return [d for d, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:max_dirs]]


def important_code_files(root: Path, files: list[str], max_files: int = 30) -> list[str]:
    priority = []
    for f in files:
        p = root / f
        if p.suffix.lower() in CODE_EXTS or p.name in MANIFESTS or p.name.lower().startswith("readme"):
            score = 0
            low = f.lower()
            for token in ["main", "app", "server", "index", "router", "config", "service", "controller", "package.json", "pyproject", "go.mod"]:
                if token in low: score += 5
            try: size = p.stat().st_size
            except Exception: size = 999999
            if size < 250000:
                priority.append((-score, size, f))
    return [f for _, _, f in sorted(priority)[:max_files]]


def write_md(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def generate_fallback_docs(root: Path, gen: Path, source: str, scan: Scan, warning: str | None = None) -> list[str]:
    gen.mkdir(parents=True, exist_ok=True)
    dirs = important_dirs(scan.files)
    code_files = important_code_files(root, scan.files)
    order = ["index.md", "00-overview.md", "01-tech-stack.md", "02-architecture.md", "03-runtime-flow.md"]
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
        os.environ.get("RDS_PIPELINE_TIMEOUT", "600"),
        "--max-tasks",
        os.environ.get("RDS_PIPELINE_MAX_TASKS", "200"),
    ]
    if os.environ.get("RDS_PIPELINE_SKIP_OVERVIEW", "").lower() in {"1", "true", "yes"}:
        cmd.append("--skip-overview")
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
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


def md_inline(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", lambda m: f'<a href="{html.escape(m.group(2))}">{m.group(1)}</a>', s)
    return s


def render_md(text: str) -> str:
    out=[]; code=[]; in_code=False; list_type=None; quote=[]
    def close_list():
        nonlocal list_type
        if list_type:
            out.append(f"</{list_type}>"); list_type=None
    def close_quote():
        nonlocal quote
        if quote:
            close_list(); out.append("<blockquote>" + "\n".join(f"<p>{md_inline(q)}</p>" for q in quote) + "</blockquote>"); quote=[]
    def open_list(kind):
        nonlocal list_type
        close_quote()
        if list_type != kind:
            close_list(); out.append(f"<{kind}>"); list_type=kind
    for line in text.splitlines():
        if line.strip().startswith("```"):
            close_quote(); close_list()
            if not in_code:
                in_code=True; code=[]
            else:
                out.append("<pre><code>"+html.escape("\n".join(code))+"</code></pre>"); in_code=False
            continue
        if in_code: code.append(line); continue
        if not line.strip(): close_quote(); close_list(); continue
        m=re.match(r"^>\s?(.*)$", line)
        if m:
            quote.append(m.group(1)); continue
        close_quote()
        m=re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            close_list(); n=len(m.group(1)); out.append(f"<h{n}>{md_inline(m.group(2))}</h{n}>"); continue
        m=re.match(r"^\s*[-*]\s+(.*)$", line)
        if m:
            open_list('ul'); out.append("<li>"+md_inline(m.group(1))+"</li>"); continue
        m=re.match(r"^\s*\d+[.)]\s+(.*)$", line)
        if m:
            open_list('ol'); out.append("<li>"+md_inline(m.group(1))+"</li>"); continue
        close_list(); out.append("<p>"+md_inline(line)+"</p>")
    close_quote(); close_list()
    if in_code: out.append("<pre><code>"+html.escape("\n".join(code))+"</code></pre>")
    return "\n".join(out)


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
        return "<div class='right-card progress-card'><div class='right-label'>DOC STATUS</div><strong>v0.1</strong><div class='progress'><span></span></div><small>生成文档可读性优化中</small></div>"
    done = int(pr.get('done') or 0)
    total = int(pr.get('total') or 0)
    percent = float(pr.get('percent') or (done / total * 100 if total else 0))
    status = html.escape(str(pr.get('status') or 'running'))
    current = html.escape(str(pr.get('current') or ''))
    unit = html.escape(str(pr.get('unit') or '目录+文件'))
    return f"<div class='right-card progress-card'><div class='right-label'>解析进度</div><strong>{percent:.1f}%</strong><div class='progress'><span style='width:{max(0,min(100,percent)):.1f}%'></span></div><small>{done} / {total} {unit}<br>状态：{status}<br>{current}</small></div>"

def page(title: str, body: str, sidebar: str = "", repo_id: str | None = None) -> bytes:
    has_sidebar = bool(sidebar.strip())
    escaped_title = html.escape(title)
    sidebar_panel = (
        "<div class='sidebar-panel'>"
        "<div class='side-kicker'>欢迎使用 REPO DOCS</div>"
        "<h2 class='sidebar-title'><a href='/'>文档</a></h2>"
        f"{sidebar}"
        "</div>"
    ) if has_sidebar else ""
    mobile_nav = (
        "<details class='mobile-nav'>"
        "<summary><span>文档目录</span><span class='chevron'>⌄</span></summary>"
        f"<div class='mobile-nav-body'>{sidebar_panel}</div>"
        "</details>"
    ) if has_sidebar else ""
    aside = f"<aside class='sidebar'>{sidebar_panel}</aside>" if has_sidebar else ""
    rightbar = (
        "<aside class='rightbar'>"
        + progress_card_html(repo_id) +
        "<div class='right-card'><div class='right-label'>页面目录</div><div id='page-toc' class='page-toc'><span class='muted'>加载中…</span></div></div><div class='right-card'><div class='right-label'>阅读建议</div><p>先看首页路线，再读架构与目录，再进入文件级讲解。展开状态会自动记住。</p></div>"
        "<div class='right-card'><div class='right-label'>过滤规则</div><p>纯 MD / PDF / Office 文档仓库会被拒绝，只保留代码学习项目。</p></div>"
        "</aside>"
    ) if has_sidebar else ""
    layout_class = "layout has-sidebar" if has_sidebar else "layout no-sidebar"
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#0b0f12"><title>{escaped_title}</title>
<style>
:root{{--bg:#090b0e;--top:#0d1116;--panel:#0f141a;--panel-2:#141a20;--card:#0c1015;--text:#f3f6f8;--text-2:#c8d0d7;--muted:#89939d;--border:rgba(255,255,255,.08);--border-2:rgba(255,255,255,.13);--accent:#c5f74f;--accent-2:#8ee65f;--link:#58a6ff;--code-bg:#11161d;--quote:#1b222a;--header-h:58px;--sidebar-w:320px;--right-w:248px;color-scheme:dark}}
:root[data-theme='light']{{--bg:#fff;--top:#fff;--panel:#fafafa;--panel-2:#f5f5f5;--card:#fff;--text:#101214;--text-2:#343a40;--muted:#6b7280;--border:rgba(0,0,0,.08);--border-2:rgba(0,0,0,.13);--accent:#93d500;--accent-2:#13c985;--link:#0969da;--code-bg:#f6f8fa;--quote:#f5fff0;color-scheme:light}}
*{{box-sizing:border-box}}html{{font-size:16px;scroll-padding-top:calc(var(--header-h) + 18px)}}body{{margin:0;background:var(--bg);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,'Noto Sans SC','PingFang SC','Microsoft YaHei',sans-serif;line-height:1.7;overflow-x:hidden;-webkit-font-smoothing:antialiased}}a{{color:inherit;text-decoration:none;overflow-wrap:anywhere}}a:hover{{color:var(--accent)}}img,table{{max-width:100%}}p,li,.muted,.repo-id,.repo-link,summary,small{{overflow-wrap:anywhere;word-break:break-word}}::selection{{background:rgba(197,247,79,.32)}}
.adbar{{height:32px;display:flex;align-items:center;justify-content:center;padding:0 16px;background:#111820;color:#d6dde3;border-bottom:1px solid var(--border);font-size:13px}}:root[data-theme='light'] .adbar{{background:#f7f9fb;color:#4b5563}}.adbar b{{color:var(--accent);font-weight:650}}
.topbar{{position:sticky;top:0;z-index:60;height:var(--header-h);display:grid;grid-template-columns:auto minmax(120px,520px) auto;align-items:center;gap:18px;padding:0 22px;background:rgba(13,17,22,.9);backdrop-filter:blur(16px);border-bottom:1px solid var(--border)}}:root[data-theme='light'] .topbar{{background:rgba(255,255,255,.9)}}.brand{{display:flex;align-items:center;gap:12px;min-width:0}}.brand-mark{{position:relative;width:30px;height:24px;display:inline-block}}.brand-mark:before,.brand-mark:after{{content:'';position:absolute;width:20px;height:7px;border-radius:99px;background:var(--accent);transform:skewX(-22deg)}}.brand-mark:before{{left:0;top:2px}}.brand-mark:after{{right:0;bottom:2px}}.brand strong{{font-size:18px;font-weight:740;letter-spacing:-.04em}}.brand span{{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:13px}}.brand span span{{padding-left:10px;border-left:1px solid var(--border)}}.search{{height:36px;border:1px solid var(--border);background:var(--panel);border-radius:10px;display:flex;align-items:center;gap:10px;color:var(--muted);padding:0 10px 0 12px;font-size:14px}}.search input{{flex:1;border:0;background:transparent;color:var(--text);font:inherit;min-width:80px;outline:0;padding:0}}.search input::placeholder{{color:var(--muted)}}.search kbd{{margin-left:auto;border:1px solid var(--border-2);border-radius:6px;padding:1px 6px;color:var(--muted);font:12px ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--bg)}}.top-actions{{display:flex;gap:9px;align-items:center;justify-content:flex-end}}.top-pill,.theme-toggle{{height:36px;display:inline-flex;align-items:center;justify-content:center;border:1px solid var(--border);border-radius:10px;padding:0 12px;font-size:13px;font-weight:570;background:var(--panel);color:var(--text-2);cursor:pointer}}.top-pill.primary{{background:var(--accent);color:#101400;border-color:transparent}}.theme-toggle{{width:38px;padding:0;font-size:17px}}.theme-toggle .sun{{display:none}}:root[data-theme='light'] .theme-toggle .sun{{display:inline}}:root[data-theme='light'] .theme-toggle .moon{{display:none}}
.layout{{display:grid;min-height:calc(100vh - var(--header-h) - 32px)}}.layout.has-sidebar{{grid-template-columns:var(--sidebar-w) minmax(0,1fr) var(--right-w)}}.layout.no-sidebar{{grid-template-columns:minmax(0,1fr)}}.sidebar{{position:sticky;top:var(--header-h);height:calc(100vh - var(--header-h));overflow:auto;background:var(--bg);border-right:1px solid var(--border);padding:24px 18px 34px;resize:horizontal;min-width:240px;max-width:620px;width:var(--sidebar-w);scrollbar-gutter:stable}}.sidebar-panel{{display:grid;gap:12px}}.side-kicker,.right-label{{font:700 11px/1.35 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}}.sidebar-title{{margin:0 0 8px;font-size:16px;line-height:1.25;letter-spacing:-.02em}}.repo-id{{display:inline-flex;width:fit-content;max-width:100%;padding:5px 9px;border:1px solid color-mix(in srgb,var(--accent) 45%,transparent);border-radius:8px;background:color-mix(in srgb,var(--accent) 12%,transparent);color:var(--accent);font-size:12px;font-weight:650}}
.repo-nav{{display:block}}.nav-section{{margin-bottom:18px;padding-bottom:14px;border-bottom:1px solid var(--border)}}.nav-section:last-child{{border-bottom:0;margin-bottom:0;padding-bottom:0}}.nav-section-title{{display:flex;align-items:center;gap:8px;margin:0 0 10px;color:var(--muted);font-size:12px;font-weight:700;letter-spacing:.04em;text-transform:uppercase}}.overview-link{{display:block;padding:8px 10px;border-radius:8px;color:var(--text-2);font-size:13px;line-height:1.45}}.overview-link:hover{{background:var(--panel);color:var(--text);text-decoration:none}}.repo-tree{{display:grid;gap:4px}}.tree-node,.tree-leaf{{display:block;min-width:0}}.tree-node>summary,.tree-leaf{{display:flex;align-items:center;gap:8px;padding:7px 9px;border-radius:8px;color:var(--text-2);font-size:13px;line-height:1.45}}.tree-node>summary{{cursor:pointer;list-style:none;user-select:none}}.tree-node>summary::-webkit-details-marker{{display:none}}.tree-summary:focus,.tree-summary:focus-visible,.tree-toggle:focus,.tree-toggle:focus-visible,.tree-toggle:active,.tree-dir-link:focus,.tree-dir-link:focus-visible{{outline:none!important;box-shadow:none!important;background:transparent!important}}.tree-toggle{{flex:0 0 auto;width:18px;height:18px;padding:0;border:0;appearance:none;-webkit-appearance:none;border-radius:0;background:transparent!important;color:var(--muted);cursor:pointer;font:700 12px/1 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;display:inline-flex;align-items:center;justify-content:center;outline:none!important;box-shadow:none!important;-webkit-tap-highlight-color:transparent}}.tree-node[open] .tree-toggle{{transform:rotate(90deg)}}.tree-dir-link{{flex:1 1 auto;min-width:0;color:inherit}}.tree-node>summary:hover,.tree-leaf:hover,.overview-link:hover{{background:var(--panel);color:var(--text);text-decoration:none}}.is-active{{background:transparent!important;color:var(--accent)!important;border-color:transparent!important;box-shadow:none!important;font-weight:700}}.tree-children{{display:grid;gap:3px;margin-left:13px;padding-left:10px;border-left:1px solid var(--border)}}.tree-label{{display:block;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}.tree-missing{{opacity:.7}}
main{{min-width:0;padding:34px 38px 74px;background:var(--bg)}}.content-wrap{{width:min(100%,860px);margin:0 auto}}.card{{min-width:0;background:transparent;border:0;border-radius:0;padding:0;box-shadow:none}}.layout.no-sidebar main{{padding-top:58px}}.layout.no-sidebar .content-wrap{{width:min(100%,980px)}}.layout.no-sidebar .card{{padding:0}}
.card h1{{font-size:clamp(2.45rem,4.8vw,4.7rem);line-height:1.02;letter-spacing:-.065em;margin:0 0 18px;color:var(--text);font-weight:780}}.layout.has-sidebar .card h1{{font-size:clamp(2.25rem,4vw,4.15rem)}}.card h2{{font-size:clamp(1.45rem,2vw,2rem);line-height:1.18;letter-spacing:-.035em;margin:2.15em 0 .72em;color:var(--text);font-weight:740}}.card h3{{font-size:clamp(1.14rem,1.35vw,1.36rem);line-height:1.28;letter-spacing:-.02em;margin:1.75em 0 .55em;font-weight:700}}.card h4,.card h5,.card h6{{margin:1.35em 0 .45em;line-height:1.3}}.card p{{margin:0 0 1.05em;color:var(--text-2);font-size:16px}}.card ul,.card ol{{padding-left:1.35rem;margin:0 0 1.15em;color:var(--text-2)}}.card li{{margin:.36em 0;padding-left:.08em}}.card strong{{font-weight:760;color:var(--text)}}.card a{{color:var(--link);text-decoration:none}}.card a:hover{{color:var(--accent);text-decoration:underline;text-underline-offset:3px}}.muted{{color:var(--muted)!important}}small{{color:var(--muted);font-size:13px}}
.card blockquote{{margin:1.35em 0;padding:14px 18px;border-left:3px solid color-mix(in srgb,var(--text) 45%,transparent);background:var(--quote);border-radius:0 12px 12px 0;color:var(--text-2)}}pre{{max-width:100%;overflow-x:auto;overflow-y:hidden;background:var(--code-bg);border:1px solid var(--border);padding:16px 18px;border-radius:12px;margin:1.25em 0;color:var(--text)}}pre code{{display:block;min-width:max-content;background:none;border:0;padding:0;border-radius:0;white-space:pre;font:13px/1.68 ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,'Liberation Mono','Courier New',monospace;color:var(--text-2)}}code{{background:var(--code-bg);border:1px solid var(--border);padding:.13em .38em;border-radius:6px;font:0.9em/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:var(--text);overflow-wrap:anywhere}}
.source-form{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:30px 0 34px;padding:7px;border:1px solid var(--border);border-radius:12px;background:var(--panel);max-width:820px}}input{{flex:1 1 360px;min-width:0;border:0;outline:0;background:transparent;color:var(--text);font:inherit;padding:11px 13px}}input::placeholder{{color:var(--muted)}}button{{flex:0 0 auto;border:0;border-radius:9px;background:var(--accent);color:#111700;font:750 14px/1.4 inherit;padding:11px 17px;cursor:pointer}}button:hover{{filter:brightness(.95)}}button:focus,input:focus,.theme-toggle:focus{{outline:2px solid color-mix(in srgb,var(--accent) 50%,transparent);outline-offset:2px}}
.card > ul:first-of-type,.repo-list{{display:grid;gap:10px;list-style:none;padding:0;margin:16px 0}}.card > ul:first-of-type li,.repo-card{{border:1px solid var(--border);border-radius:12px;padding:14px 16px;background:var(--panel)}}.repo-card:hover{{border-color:var(--border-2)}}
.rightbar{{position:sticky;top:var(--header-h);height:calc(100vh - var(--header-h));overflow:auto;border-left:1px solid var(--border);padding:24px 18px;background:var(--bg)}}.right-card{{border:1px solid var(--border);border-radius:12px;background:var(--panel);padding:14px;margin-bottom:14px;color:var(--text-2)}}.right-card p{{font-size:13px;line-height:1.55;margin:.55em 0 0;color:var(--muted)}}.page-toc{{display:grid;gap:6px}}.toc-link{{display:block;padding:6px 8px;border-radius:8px;color:var(--text-2);font-size:12px;line-height:1.35;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}.toc-link:hover{{background:var(--panel);color:var(--text)}}.toc-lv-h1{{padding-left:0}}.toc-lv-h2{{padding-left:10px}}.toc-lv-h3{{padding-left:18px}}.progress-card strong{{display:block;margin:8px 0;font-size:22px}}.progress{{height:8px;background:var(--panel-2);border-radius:99px;overflow:hidden;margin:8px 0}}.progress span{{display:block;width:78%;height:100%;background:linear-gradient(90deg,var(--accent),var(--accent-2));border-radius:inherit}}
.mobile-nav{{display:none;position:sticky;top:var(--header-h);z-index:45;padding:10px 12px;background:var(--bg);border-bottom:1px solid var(--border)}}.mobile-nav summary{{display:flex;align-items:center;justify-content:space-between;list-style:none;cursor:pointer;padding:10px 12px;border-radius:10px;border:1px solid var(--border);background:var(--panel);font-weight:700}}.mobile-nav summary::-webkit-details-marker{{display:none}}.mobile-nav[open] .chevron{{transform:rotate(180deg)}}.chevron{{transition:transform .16s ease;color:var(--muted)}}.mobile-nav-body{{margin-top:10px;max-height:68vh;overflow:auto;background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:14px}}
@media(max-width:1180px){{.layout.has-sidebar{{grid-template-columns:var(--sidebar-w) minmax(0,1fr)}}.rightbar{{display:none}}.topbar{{grid-template-columns:auto minmax(120px,1fr) auto}}}}
@media(max-width:860px){{:root{{--header-h:56px}}.adbar{{display:none}}.topbar{{grid-template-columns:auto auto;padding:0 14px}}.search{{display:none}}.brand span span{{display:none}}.top-actions .top-pill{{display:none}}.mobile-nav{{display:block}}.layout.has-sidebar{{grid-template-columns:minmax(0,1fr)}}.sidebar{{display:none}}main{{padding:22px 16px 48px}}.content-wrap{{width:100%}}.card h1{{font-size:2.45rem;letter-spacing:-.055em}}.card h2{{font-size:1.55rem;margin-top:1.8em}}.card h3{{font-size:1.2rem}}.card p,.card li{{font-size:15.5px}}.source-form{{display:grid;border-radius:12px;padding:9px;margin:24px 0}}input{{width:100%;flex:auto;padding:11px}}button{{width:100%;padding:12px 16px}}pre{{border-radius:10px;padding:13px 14px}}}}
</style><script>
(function(){{try{{var t=localStorage.getItem('repo-docs-theme')||'dark';document.documentElement.dataset.theme=t;}}catch(e){{document.documentElement.dataset.theme='dark';}}}})();
function toggleTheme(){{var r=document.documentElement;var n=r.dataset.theme==='light'?'dark':'light';r.dataset.theme=n;try{{localStorage.setItem('repo-docs-theme',n)}}catch(e){{}}}}
(function(){{
  function syncSidebarWidth(){{
    var sidebar=document.querySelector('.sidebar');
    if(!sidebar) return;
    var root=document.documentElement;
    var apply=function(){{ root.style.setProperty('--sidebar-w', sidebar.offsetWidth+'px'); try{{localStorage.setItem('repo-docs-sidebar-w', sidebar.offsetWidth)}}catch(e){{}} }};
    var saved=null;
    try{{saved=parseInt(localStorage.getItem('repo-docs-sidebar-w')||'',10);}}catch(e){{}}
    if(saved && saved>240){{ sidebar.style.width=saved+'px'; root.style.setProperty('--sidebar-w', saved+'px'); }}
    apply();
    if('ResizeObserver' in window){{ new ResizeObserver(apply).observe(sidebar); }}
    window.addEventListener('resize', apply);
  }}
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
    var hs=[].slice.call(document.querySelectorAll('.card h1,.card h2,.card h3'));
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
<body><div class="adbar">Repo Docs - <b>中文代码学习文档</b>：从推荐阅读顺序开始，不再硬啃源码</div><header class="topbar"><a class="brand" href="/"><span class="brand-mark" aria-hidden="true"></span><span><strong>repo docs</strong><span>文档</span></span></a><div class="search"><input id="nav-search" type="search" placeholder="搜索目录 / 文件 / 函数" aria-label="搜索目录文件函数"><kbd>⌘ K</kbd></div><nav class="top-actions"><a class="top-pill primary" href="/">Ask AI</a><button class="theme-toggle" type="button" onclick="toggleTheme()" aria-label="切换暗黑/正常模式"><span class="moon">☾</span><span class="sun">☀</span></button></nav></header>{mobile_nav}<div class="{layout_class}">{aside}<main><div class="content-wrap"><article class="card">{body}</article></div></main>{rightbar}</div></body></html>""".encode()


OVERVIEW_DOCS = [
    ("index.md", "推荐阅读顺序"),
    ("00-overview.md", "项目整体介绍"),
    ("01-tech-stack.md", "技术栈与预备知识"),
    ("02-architecture.md", "架构与目录关系"),
    ("03-runtime-flow.md", "运行链路 / 数据流"),
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
        return f"<a class='tree-leaf tree-{kind} depth-{indent}' href='{doc_href(repo_id, doc)}' title='{title}'><span class='tree-label'>{display_html}</span></a>"
    return f"<span class='tree-leaf tree-missing depth-{indent}' title='{title}'><span class='tree-label'>{display_html}</span></span>"


def repo_sidebar(repo_id: str, gen: Path) -> str:
    files = sorted(str(p.relative_to(gen)).replace(os.sep,"/") for p in gen.rglob("*.md")) if gen.exists() else []
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
    orphan_html = f"<section class='nav-section'><div class='nav-section-title'>其他文档</div>{''.join(orphan_items)}</section>" if orphan_items else ""

    overview_html = "".join(overview_items) or "<p class='muted'>暂无总览文档</p>"
    return (
        f"<p class='repo-id muted' title='{html.escape(repo_id)}'>{html.escape(repo_id)}</p>"
        "<nav class='repo-nav structured-nav' aria-label='文档目录'>"
        f"<section class='nav-section'><div class='nav-section-title'>项目总览</div>{overview_html}</section>"
        f"<section class='nav-section'><div class='nav-section-title'>源码结构</div><div class='repo-tree'>{tree_html}</div></section>"
        f"{orphan_html}"
        "</nav>"
    )


class Handler(BaseHTTPRequestHandler):
    def send_html(self, title, body, code=200, sidebar=""):
        data=page(title,body,sidebar, getattr(self, "_current_repo_id", None)); self.send_response(code); self.send_header("Content-Type","text/html; charset=utf-8"); self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data)
    def send_json(self, obj, code=200):
        data=json.dumps(obj, ensure_ascii=False).encode("utf-8"); self.send_response(code); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data)
    def redirect(self, loc):
        self.send_response(303); self.send_header("Location",loc); self.end_headers()
    def do_GET(self):
        u=urllib.parse.urlparse(self.path); path=urllib.parse.unquote(u.path)
        if path=="/":
            with db() as con: repos=con.execute("SELECT * FROM repos ORDER BY updated_at DESC LIMIT 50").fetchall()
            repo_html="".join(f"<li class='repo-card'><a href='/repos/{r['repo_id']}/'><strong>{html.escape(r['repo_id'])}</strong></a> <span class='repo-id'>{html.escape(r['status'])}</span><br><small>{html.escape(r['source'])}</small></li>" for r in repos) or "<li class='repo-card'><span class='muted'>还没有生成过项目文档。</span></li>"
            self.send_html("Repo Docs", f"<p class='side-kicker'>Code Learning Docs</p><h1>万用文档</h1><p class='muted'>输入 GitHub/GitLab HTTPS URL 或 /data/project 下本地仓库，系统会过滤纯 MD/PDF/Office/TXT 文档仓库，只为真正的代码项目生成分段讲解。</p><form class='source-form' method='post' action='/submit'><input name='source' aria-label='仓库地址或本地路径' placeholder='https://github.com/org/repo 或 /data/project/lobehub'><button type='submit'>生成文档</button></form><h2>已有项目</h2><ul class='repo-list'>{repo_html}</ul>") ; return
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
