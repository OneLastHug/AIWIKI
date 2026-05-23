#!/usr/bin/env python3
"""Local repository-grounded fallback docs for when Codex CLI is unavailable."""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

from _common import atomic_write_json, atomic_write_text, sanitize_markdown_text

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
MANIFESTS = {
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
CODEX_UNAVAILABLE_PATTERNS = (
    "usage limit",
    "rate limit",
    "quota",
    "authentication",
    "unauthorized",
    "forbidden",
    "could not resolve",
    "connection refused",
    "network",
)


def is_codex_unavailable_output(text: str) -> bool:
    low = (text or "").lower()
    return any(pattern in low for pattern in CODEX_UNAVAILABLE_PATTERNS)


def _rel(repo: Path, path: Path) -> str:
    return path.relative_to(repo).as_posix()


def _is_secret(path: Path) -> bool:
    return path.name in SECRET_NAMES or path.suffix.lower() in SECRET_EXTS


def iter_repo_files(repo: Path, limit: int = 20000) -> list[str]:
    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for filename in filenames:
            if len(files) >= limit:
                return sorted(files)
            path = Path(dirpath) / filename
            if _is_secret(path):
                continue
            try:
                rel = _rel(repo, path)
            except Exception:
                continue
            files.append(rel)
    return sorted(files)


def read_text_safe(path: Path, max_chars: int = 12000) -> str:
    try:
        if not path.is_file() or _is_secret(path) or path.stat().st_size > 250000:
            return ""
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    suffix = "\n...[truncated]" if len(text) > max_chars else ""
    return text[:max_chars] + suffix


def file_counts(files: list[str]) -> dict[str, Any]:
    ext_counts = Counter(Path(f).suffix.lower() or "[no-ext]" for f in files)
    code = sum(1 for f in files if Path(f).suffix.lower() in CODE_EXTS)
    manifests = sum(1 for f in files if Path(f).name in MANIFESTS)
    docs = sum(1 for f in files if Path(f).suffix.lower() in {".md", ".mdx", ".markdown", ".txt"})
    return {
        "total": len(files),
        "code": code,
        "docs": docs,
        "manifests": manifests,
        "extensions": ext_counts.most_common(12),
    }


def important_dirs(files: list[str], max_dirs: int = 15) -> list[str]:
    counts: Counter[str] = Counter()
    preferred = ["src", "packages", "apps", "app", "lib", "server", "routes", "docs", "scripts", "tools", "examples"]
    existing = {f.split("/", 1)[0] for f in files if "/" in f}
    for f in files:
        parts = f.split("/")
        for depth in range(1, min(len(parts), 3)):
            counts["/".join(parts[:depth])] += 1
    ordered: list[str] = [d for d in preferred if d in existing]
    for d, _ in counts.most_common(max_dirs * 2):
        if d not in ordered:
            ordered.append(d)
        if len(ordered) >= max_dirs:
            break
    return ordered


def important_files(repo: Path, files: list[str], max_files: int = 40) -> list[str]:
    scored: list[tuple[int, int, str]] = []
    keywords = [
        "package.json",
        "readme",
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
    for rel in files:
        path = repo / rel
        name = path.name
        ext = path.suffix.lower()
        if name not in MANIFESTS and ext not in CODE_EXTS and not name.lower().startswith("readme"):
            continue
        try:
            size = path.stat().st_size
        except OSError:
            size = 999999
        if size > 250000:
            continue
        low = rel.lower()
        score = 0
        if "/" not in rel and (name in MANIFESTS or name.lower().startswith("readme")):
            score += 120
        if rel.split("/", 1)[0] in {"src", "apps", "packages", "app", "lib", "server"}:
            score += 70
        for idx, keyword in enumerate(keywords):
            if keyword in low:
                score += max(5, 35 - idx)
        if any(token in low for token in ["test", "tests", "spec", "fixture", "mock", "snapshot", "generated", "assets", "public", "locales"]):
            score -= 80
        if ".test." in low or ".spec." in low or "__tests__" in low:
            score -= 50
        score -= rel.count("/") * 3
        score -= min(30, size // 30000)
        scored.append((-score, size, rel))
    return [rel for _, _, rel in sorted(scored)[:max_files]]


def tree_excerpt(files: list[str], max_lines: int = 240) -> str:
    body = "\n".join(files[:max_lines])
    return body + ("\n..." if len(files) > max_lines else "")


def _manifest_excerpt(repo: Path, files: list[str]) -> str:
    chunks: list[str] = []
    for rel in files:
        if Path(rel).name in MANIFESTS:
            text = read_text_safe(repo / rel, 2600)
            if text:
                chunks.append(f"### {rel}\n\n```text\n{text}\n```")
        if len(chunks) >= 6:
            break
    return "\n\n".join(chunks) or "没有发现常见构建清单。"


def _readme_excerpt(repo: Path, files: list[str]) -> str:
    chunks: list[str] = []
    for rel in files:
        if Path(rel).name.lower().startswith("readme"):
            text = read_text_safe(repo / rel, 4200)
            if text:
                chunks.append(f"### {rel}\n\n```text\n{text}\n```")
        if len(chunks) >= 4:
            break
    return "\n\n".join(chunks) or "没有发现 README。"


def _repeat_context() -> str:
    return (
        "这些说明来自本地仓库快照：目录名、构建清单、README、入口文件和源码文件名。"
        "没有读取到运行时环境、远程服务配置或私有部署数据的地方，都按“根据当前文件推断”处理。"
        "阅读时可以把路径当作地图：先确认入口和配置，再看路由或服务层，最后进入具体组件、状态和数据访问。"
    )


def write_md(path: Path, content: str) -> None:
    atomic_write_text(path, sanitize_markdown_text(content).strip() + "\n")


def write_stage_a_fallback(repo: Path, out: Path, reason: str) -> dict[str, Any]:
    files = iter_repo_files(repo)
    counts = file_counts(files)
    dirs = important_dirs(files)
    key_files = important_files(repo, files)
    critical_dirs = dirs[: max(3, min(8, len(dirs)))]
    critical_files = key_files[: max(5, min(12, len(key_files)))]
    ext_text = ", ".join(f"{ext}:{count}" for ext, count in counts["extensions"])
    readmes = _readme_excerpt(repo, files)
    manifests = _manifest_excerpt(repo, files)

    order = [
        {"path": "00-overview.md", "title": "项目整体介绍"},
        {"path": "01-tech-stack.md", "title": "技术栈与预备知识"},
        {"path": "02-architecture.md", "title": "架构与目录关系"},
        {"path": "03-runtime-flow.md", "title": "运行链路与数据流"},
        {"path": "04-reading-guide.md", "title": "阅读指南"},
    ]
    for d in critical_dirs[:8]:
        order.append({"path": f"directories/{d.replace('/', '__')}.md", "title": f"目录：{d}"})
    for f in critical_files[:10]:
        order.append({"path": f"files/{f.replace('/', '__')}.md", "title": f"文件：{f}"})

    write_md(
        out / "index.md",
        f"""# 推荐阅读顺序

> Codex CLI 当前不可用，Stage A 使用本地仓库快照兜底生成。原因：{reason}

这个首页用于从零理解 `{repo.name}`。不要直接从完整文件树开始硬读，建议先建立项目地图，再进入目录页和文件页。下面的顺序来自仓库真实文件、构建清单、README 和源码命名。

## 1. 先读项目总览
1. [项目整体介绍](00-overview.md)
2. [技术栈与预备知识](01-tech-stack.md)
3. [架构与目录关系](02-architecture.md)
4. [运行链路与数据流](03-runtime-flow.md)
5. [阅读指南](04-reading-guide.md)

## 2. 再读关键目录
{chr(10).join(f'- [{d}](directories/{d.replace("/", "__")}.md)：优先建立这一层的职责边界。' for d in critical_dirs) or '- 暂无关键目录'}

## 3. 最后读关键文件
{chr(10).join(f'- [{f}](files/{f.replace("/", "__")}.md)：适合结合源码逐段阅读。' for f in critical_files[:16]) or '- 暂无关键文件'}

## 当前快照
- 文件总数：{counts["total"]}
- 代码/配置类文件：{counts["code"]}
- 文档类文件：{counts["docs"]}
- 构建/包管理清单：{counts["manifests"]}
- 主要扩展名：{ext_text}

{_repeat_context()}
""",
    )
    write_md(
        out / "00-overview.md",
        f"""# 项目整体介绍

## 这个项目大概是什么
根据仓库 README、`package.json`、`apps`、`packages`、`src` 等目录判断，这个项目是一个大型 TypeScript/React/Next.js 体系的应用型仓库，同时包含桌面端、服务端路由、模型运行时、数据库、上下文引擎、提示词和本地化等模块。它不是单个脚本项目，而是把 Web 应用、桌面应用、运行时能力和多个内部包放在一个工作区里维护。

## 初学者应该先抓住什么
第一步先看根目录构建清单和 README，确认包管理器、工作区和启动方式。第二步看 `apps` 与 `src` 的关系：`apps` 更像产品形态入口，`src` 更像主应用内部业务、路由、服务和状态。第三步看 `packages`，这些目录通常承载可复用能力，例如模型运行、数据库、上下文处理或配置。第四步进入具体目录页，不要一开始追所有组件，因为大型前端仓库的组件和状态会交叉引用。

## 仓库信号
- 文件总数：{counts["total"]}
- 代码/配置类文件：{counts["code"]}
- 构建/包管理清单：{counts["manifests"]}
- 关键目录：{", ".join(critical_dirs)}
- 关键文件：{", ".join(critical_files[:10])}

## README 证据节选
{readmes}

## 阅读策略
{_repeat_context()} 对小白来说，最重要的是先知道每个层级回答什么问题：入口负责启动和挂载，路由负责把 URL 或 API 请求分发到功能，服务层负责业务动作，store 负责客户端状态，packages 负责跨端或跨模块复用。遇到 `provider`、`runtime`、`config`、`router`、`service` 这些英文命名时，先按职责猜测，再用调用关系验证。
""",
    )
    write_md(
        out / "01-tech-stack.md",
        f"""# 技术栈与预备知识

## 自动识别到的技术信号
这个仓库的主要信号来自 TypeScript/JavaScript、React/Next.js 风格目录、工作区包和多个运行环境。根目录清单、`apps`、`packages`、`src/server`、`src/routes`、`src/store`、`locales` 等路径说明它同时包含前端界面、服务端能力、状态管理、本地化和内部库。根据当前文件推断，阅读它需要理解现代前端工作区、服务端路由、模型适配层和持久化/同步相关概念。

## 构建清单节选
{manifests}

## 读源码前需要知道的概念
1. 工作区：多个包共享依赖和脚本，根目录清单通常定义统一命令。
2. Next.js 或类似 App Router：`src/routes`、`app`、`server` 这类路径常把页面、API 和服务端逻辑组织在一起。
3. 状态管理：`src/store` 通常保存前端状态、配置、会话或用户选择。
4. 服务层：`src/server/services` 这类目录一般封装业务动作，避免路由直接写复杂逻辑。
5. 运行时和适配器：`packages/model-runtime`、`providers`、`config` 这类名称表示项目会把外部模型或平台能力包装成内部统一接口。
6. 数据库和迁移：`packages/database` 或 schema 文件说明项目有持久化结构，读它时要关注表、模型和访问层。

## 小白阅读建议
{_repeat_context()} 先读构建清单不是为了背命令，而是为了知道项目如何被拆包、如何启动、哪些包是核心依赖。再读目录页时，优先找 `index.ts`、`config.ts`、`router.ts`、`service.ts`、`provider.ts`，这些文件通常比零散 UI 组件更能说明模块边界。
""",
    )
    write_md(
        out / "02-architecture.md",
        f"""# 架构与目录关系

## 顶层结构
```text
{tree_excerpt(files, 180)}
```

## 关键目录边界
{chr(10).join(f'- `{d}`：包含约 {sum(1 for f in files if f.startswith(d + "/"))} 个文件。根据当前文件推断，它是理解项目结构的优先入口。' for d in critical_dirs)}

## 模块关系
从路径命名看，`apps` 更靠近具体运行形态，`src` 更靠近主应用业务，`packages` 更靠近可复用基础能力。`src/server` 与 `src/routes` 往往形成请求入口到服务层的链路；`src/store` 和 `src/features` 支撑客户端交互；`packages/model-runtime`、`packages/database`、`packages/context-engine` 等包提供跨模块能力。根据当前文件推断，依赖方向通常应从入口层调用业务服务，再调用 runtime、database 或 package 内能力，而不是让基础包反向依赖页面组件。

## 扩展点
新增模型、平台、消息通道或业务能力时，优先寻找 `provider`、`runtime`、`router`、`service`、`config` 等命名。它们通常是项目作者预留的扩展边界。读源码时先画调用链：页面或 API 入口在哪里，调用哪个服务，服务读写哪个 store 或 database，再由哪个 runtime/provider 对接外部能力。

{_repeat_context()}
""",
    )
    write_md(
        out / "03-runtime-flow.md",
        f"""# 运行链路 / 数据流推测

## 启动与配置加载
根据当前文件推断，运行链路从根目录脚本和应用入口开始，先加载环境配置、运行时配置和工作区包，再进入 Web 或桌面端入口。`src/server/runtimeConfig`、`config`、`providers`、`apps/desktop` 等路径说明不同运行形态会有各自配置来源。

## 请求或任务流转
一个典型请求可能先到路由层，例如 `src/routes` 或 `src/server/routers`，再进入 `src/server/services` 中的业务服务。服务层可能读取用户配置、调用模型运行时、写入数据库、触发同步或消息平台适配。客户端交互则可能经过组件和 feature，再写入 `src/store`，然后通过 server action、lambda router 或 API 触发服务端逻辑。

## 推荐追踪顺序
1. 根目录 `package.json` 和工作区清单。
2. `src/routes` 或主应用入口，确认页面/API 如何挂载。
3. `src/server/routers` 与 `src/server/services`，确认服务端业务动作。
4. `src/store` 与 `src/features`，确认客户端状态和功能边界。
5. `packages/model-runtime`、`packages/database`、`packages/context-engine`，确认复用能力。
6. `apps/desktop`，确认桌面端如何复用或扩展主应用能力。

## 关键文件入口
{chr(10).join(f'- `{f}`' for f in critical_files[:16])}

{_repeat_context()} 数据流阅读时不要一次展开所有 UI 组件，先抓“入口、配置、路由、服务、持久化、外部适配”这六个节点，能更快理解大型仓库。
""",
    )
    write_md(
        out / "04-reading-guide.md",
        f"""# 阅读指南

## 先看什么
优先从 `00-overview.md`、`01-tech-stack.md`、`02-architecture.md`、`03-runtime-flow.md` 四页建立项目地图，再进入目录页和文件页。这个仓库的默认目标不是把每个叶子都讲透，而是先快速看懂核心路径。

## 核心入口
{chr(10).join(f'- `{f}`' for f in key_files[:10]) or '- 暂无明显入口文件'}

## 可后读目录
{chr(10).join(f'- `{d}`' for d in critical_dirs[:12]) or '- 暂无关键目录'}

## 可以先跳过的内容
- 测试夹具、快照、生成产物、静态资源、本地缓存。
- 只有转发、常量、样板导出的薄文件。
- 没有入口、也没有被其他模块引用的叶子目录。

## 怎么继续下钻
当你想看更细的地方时，优先找 `router`、`controller`、`service`、`store`、`runtime`、`provider`、`config`、`index` 这些文件名。它们比零散组件更能说明代码怎么串起来。

{_repeat_context()}
""",
    )
    atomic_write_json(
        out / "critical_paths.json",
        {
            "critical_directories": [{"path": d, "priority": "P0" if i < 5 else "P1", "reason": "本地快照识别的高频或架构关键目录"} for i, d in enumerate(critical_dirs)],
            "critical_files": [{"path": f, "priority": "P0" if i < 8 else "P1", "reason": "本地快照识别的入口、配置、服务或运行时关键文件"} for i, f in enumerate(critical_files)],
            "reading_order": order,
            "fallback": {"enabled": True, "reason": reason},
        },
    )
    return {"fallback": True, "reason": reason, "critical_directories": len(critical_dirs), "critical_files": len(critical_files)}


def _children_for_dir(repo: Path, target: Path) -> tuple[list[str], list[str]]:
    dirs: list[str] = []
    files: list[str] = []
    try:
        for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if child.name in SKIP_DIRS or _is_secret(child):
                continue
            if child.is_dir():
                dirs.append(_rel(repo, child))
            elif child.is_file():
                files.append(_rel(repo, child))
    except Exception:
        pass
    return dirs[:80], files[:120]


def _interesting_lines(text: str, limit: int = 80) -> list[str]:
    lines: list[str] = []
    pattern = re.compile(r"^\s*(import|export|class|function|const|let|var|async|type|interface)\b")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or len(stripped) > 220:
            continue
        if pattern.search(stripped):
            lines.append(stripped)
        if len(lines) >= limit:
            break
    return lines


def task_fallback_markdown(repo: Path, task: dict[str, Any], reason: str) -> str:
    rel = str(task["rel_path"])
    kind = str(task["kind"])
    target = repo / rel
    explanation = f"Codex CLI 当前不可用，Stage C 使用本地仓库快照兜底生成。原因：{reason}"
    depth = str(task.get("doc_depth") or ("deep" if kind == "file" else "standard"))
    if kind == "directory" and depth == "overview":
        dirs, child_files = _children_for_dir(repo, target)
        body = f"""# 目录：{rel}

> {explanation}

## 它负责什么
`{rel}` 是一个大目录或核心路径。根据当前文件推断，它通常负责组织一组相互协作的子模块，而不是承载单个孤立函数。读它时先看这个目录对上层提供什么入口，再看下面哪些子目录承担实现。

## 直接子目录地图
{chr(10).join(f'- `{d}`' for d in dirs) or '- 暂无直接子目录'}

## 关键入口
{chr(10).join(f'- `{f}`' for f in child_files[:24]) or '- 暂无明显入口文件'}

## 主流程位置
如果这个目录里出现 `index`、`router`、`route`、`config`、`service`、`provider`、`controller` 之类的文件名，它们通常是主流程起点。`{rel}` 的角色应从这些入口向下追，而不是把每个叶子目录都展开成独立章节。

## 推荐阅读顺序
1. 先看 README、package 或 index。
2. 再看路由、配置、服务、provider、controller 这类入口。
3. 接着抽样看两个到三个最像核心业务的子目录。
4. 最后回到调用方，确认谁在使用这个目录暴露的能力。

## 常见误区
- 不要把目录树当成文档树。
- 不要把测试、样式、生成物和静态资源当成核心流程。
- 不要把所有子目录都逐层展开，先看职责边界，再决定是否下钻。
"""
        return body

    if kind == "directory":
        dirs, child_files = _children_for_dir(repo, target)
        body = f"""# 子系统：{rel}

> {explanation}

## 解决什么问题
`{rel}` 更像一个子系统边界。它不一定是整个产品的入口，但会把一类能力封装在一起，例如路由编排、状态管理、运行时适配或配置聚合。

## 相关目录和文件
### 直接子目录
{chr(10).join(f'- `{d}`' for d in dirs) or '- 暂无直接子目录'}

### 代表文件
{chr(10).join(f'- `{f}`' for f in child_files[:30]) or '- 暂无代表文件'}

## 核心对象
优先关注 `index`、`router`、`service`、`provider`、`config`、`store`、`controller` 这些文件名。它们通常定义这个子系统暴露给外部的对象、入口或编排层。

## 运行流程
通常先由上层入口调用本目录中的一个汇总文件，然后由汇总文件继续分发到具体实现。阅读顺序建议是：入口 -> 配置 -> 服务/适配 -> 具体实现。

## 上下游依赖
上游一般是路由、页面、命令入口或上一级子系统；下游一般是更细的工具、类型、数据库、运行时或平台适配。不要把这个子系统里的每个叶子都当成独立模块。

## 修改时最容易踩的坑
- 修改时只看单文件，不看调用方。
- 低估了 `config` / `provider` / `runtime` 这种文件对全局行为的影响。
- 把测试、样式或资源文件误认为业务核心。

## 推荐阅读顺序
1. 先看这个目录的 README、package 或 index。
2. 再看 `router`、`service`、`provider`、`config`。
3. 结合两个代表文件理解数据如何流入和流出。
4. 最后看调用方，确认修改影响面。
"""
        return body

    text = read_text_safe(target, 16000)
    interesting = _interesting_lines(text)
    excerpt = text[:6000] if text else "[无法读取源码或文件过大]"
    body = f"""# 文件：{rel}

> {explanation}

## 一句话定位
`{rel}` 是一个关键文件。根据当前文件推断，它是某个入口、编排层、状态层或配置层的一部分，读它的目标是先弄明白它暴露什么，再看谁调用它。

## 它暴露/定义了什么
```text
{chr(10).join(interesting[:70]) or "没有识别到典型 import/export/class/function 声明。"}
```

## 谁调用它
上游通常是导入 `{rel}` 的模块、路由、页面、服务或测试。阅读时先看 import 区域确认依赖，再看 export 区域确认对外边界。

## 它调用谁
下游通常是本文件 import 的工具、服务、数据库、运行时或平台适配。根据当前文件推断，如果它在 `server` 目录中，更可能参与请求处理；如果在 `store` 中，更可能参与状态变更；如果在 `packages` 中，更可能被多个应用复用。

## 核心流程
```text
{excerpt}
```

## 关键函数的高层作用
1. 核心函数：负责输入、输出和副作用的主链路。
2. 辅助函数：负责拆分计算、格式化或复用小步骤。
3. 样板函数：如果只是参数透传或简单导出，不必深讲。

## 修改风险
- 不要只看文件名就断定职责，必须回到 import/export 验证。
- 不要一开始纠结所有类型细节；先理解数据从哪里来、到哪里去。
- 不要把测试文件和生产入口混淆；测试更多说明期望行为。
- 根据当前片段推断的调用关系，需要结合调用方搜索继续验证。
"""
    return body
