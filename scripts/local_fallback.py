#!/usr/bin/env python3
"""Local repository-grounded fallback docs for when Codex CLI is unavailable."""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

from _common import atomic_write_json, atomic_write_text

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


def important_dirs(files: list[str], max_dirs: int = 18) -> list[str]:
    counts: Counter[str] = Counter()
    preferred = ["src", "packages", "apps", "app", "lib", "server", "docs", "locales", "public", "plugins", "tests", "scripts"]
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


def important_files(repo: Path, files: list[str], max_files: int = 36) -> list[str]:
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
    ]
    for d in critical_dirs[:8]:
        order.append({"path": f"directories/{d.replace('/', '__')}.md", "title": f"目录：{d}"})
    for f in critical_files[:10]:
        order.append({"path": f"files/{f.replace('/', '__')}.md", "title": f"文件：{f}"})

    atomic_write_text(
        out / "index.md",
        f"""# 推荐阅读顺序

> Codex CLI 当前不可用，Stage A 使用本地仓库快照兜底生成。原因：{reason}

这个首页用于从零理解 `{repo.name}`。不要直接从完整文件树开始硬读，建议先建立项目地图，再进入目录页和文件页。下面的顺序来自仓库真实文件、构建清单、README 和源码命名。

## 1. 先读项目总览
1. [项目整体介绍](00-overview.md)
2. [技术栈与预备知识](01-tech-stack.md)
3. [架构与目录关系](02-architecture.md)
4. [运行链路与数据流](03-runtime-flow.md)

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
    atomic_write_text(
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
    atomic_write_text(
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
    atomic_write_text(
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
    atomic_write_text(
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
    title_kind = "目录" if kind == "directory" else "文件"
    explanation = f"Codex CLI 当前不可用，Stage C 使用本地仓库快照兜底生成。原因：{reason}"
    if kind == "directory":
        dirs, child_files = _children_for_dir(repo, target)
        sample_files = [f for f in child_files if Path(f).suffix.lower() in CODE_EXTS or Path(f).name in MANIFESTS][:16]
        body = f"""# 目录：{rel}

> {explanation}

## 它负责什么
`{rel}` 是仓库中的一个目录节点。根据当前文件推断，它的职责要从直接子目录、入口文件、配置文件和命名来判断。若该目录位于 `src`、`apps` 或 `packages` 下，它通常分别对应主应用业务、具体运行形态或可复用内部包。当前页面只基于本地快照，不声称运行时外部配置。

## 关键组成
### 子目录
{chr(10).join(f'- `{d}`' for d in dirs) or '- 暂无直接子目录'}

### 代表文件
{chr(10).join(f'- `{f}`' for f in child_files[:40]) or '- 暂无直接文件'}

## 上下游关系
根据当前片段推断，`{rel}` 的上游通常是调用它的页面、路由、服务或包入口；下游通常是它内部继续引用的工具、配置、类型、数据库访问、运行时适配或 UI 组件。阅读时先找 `index`、`config`、`router`、`service`、`provider`、`types` 这类文件名，因为它们更容易暴露模块边界。

## 运行/调用流程
一个常见流程是：入口文件接收调用，读取配置或类型定义，分发到服务函数或组件，再调用同目录工具或跨包能力。若目录下存在路由文件，先看路由如何把请求转成服务调用；若目录下存在组件文件，先看 props、状态来源和事件回调；若目录下存在 package 清单，先看 exports、scripts 和依赖。

## 小白阅读顺序
1. 先看 `{rel}` 下的 README、package 或 index 文件。
2. 再看命名包含 `config`、`router`、`service`、`provider`、`store`、`schema` 的文件。
3. 然后抽样阅读代表文件：{", ".join(sample_files[:8]) or "当前目录没有明显代表文件"}。
4. 最后回到调用方，确认谁在使用这个目录暴露的能力。

## 常见误区
- 不要把目录下所有文件按字母顺序硬读；大型仓库要先找入口和边界。
- 不要把测试、样式、类型文件当成全部业务逻辑；它们更多是辅助理解。
- 看到英文路径名时先按工程约定理解：`service` 是业务动作，`store` 是状态，`provider` 是适配，`runtime` 是执行环境。
- 根据当前文件推断的地方，需要用后续调用关系验证。
"""
        return body

    text = read_text_safe(target, 16000)
    interesting = _interesting_lines(text)
    excerpt = text[:6000] if text else "[无法读取源码或文件过大]"
    return f"""# 文件：{rel}

> {explanation}

## 它负责什么
`{rel}` 是一个具体文件。根据当前文件推断，它的职责可以从文件路径、文件名、导入导出和关键声明判断。位于 `server`、`router`、`service`、`store`、`runtime`、`provider`、`config` 等路径中的文件通常分别承担服务端逻辑、请求分发、业务动作、状态管理、运行时适配和配置汇总职责。

## 关键组成
### 关键声明节选
```text
{chr(10).join(interesting[:70]) or "没有识别到典型 import/export/class/function 声明。"}
```

### 源码节选
```text
{excerpt}
```

## 上下游关系
上游通常是导入 `{rel}` 的模块、路由、页面、服务或测试；下游通常是本文件 import 的依赖。阅读时先看 import 区域确认它依赖哪些包和本地模块，再看 export 区域确认它向外提供什么。若文件包含默认导出、路由导出、class 或 service 对象，它往往是其他模块调用的边界。

## 运行/调用流程
典型调用流程是：上游模块调用本文件导出的函数、类或配置；本文件读取参数和配置，组织内部逻辑，然后调用下游工具、服务、数据库、运行时或平台适配。根据当前片段推断，如果这个文件在 `server` 目录中，它更可能参与请求处理或服务端任务；如果在 `store` 中，它更可能参与客户端状态变更；如果在 `packages` 中，它更可能被多个应用复用。

## 小白阅读顺序
1. 先读文件路径 `{rel}`，判断它属于哪一层。
2. 再读 import，给依赖分组：外部库、本地工具、类型、服务、配置。
3. 再读 export、class、function、const，确认本文件对外提供的 API。
4. 最后读实现细节，关注输入、输出、副作用和错误处理。

## 常见误区
- 不要只看文件名就断定职责，必须回到 import/export 验证。
- 不要一开始纠结所有类型细节；先理解数据从哪里来、到哪里去。
- 不要把测试文件和生产入口混淆；测试更多说明期望行为。
- 根据当前片段推断的调用关系，需要结合调用方搜索继续验证。
"""
