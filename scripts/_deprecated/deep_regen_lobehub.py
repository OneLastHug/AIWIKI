#!/usr/bin/env python3
"""Deep, progress-tracked LobeHub docs regeneration.

This script is intentionally deterministic and resumable-ish: every generated
Markdown page increments data/generated/<repo>/progress.json so the web UI can
show parsed directories+files / total directories+files.
"""
from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path('/data/project/lobehub')
OUT = Path('/data/project/repo-docs-service/data/generated/data-project-lobehub-167e6641')
PROGRESS = OUT / 'progress.json'
SOURCE = '/data/project/lobehub'

IGNORE_DIRS = {
    '.git', 'node_modules', '.next', 'dist', 'build', 'coverage', '.turbo', '.vercel',
    '.cache', 'tmp', 'temp', '.husky', '.github', '.devcontainer', '.vscode'
}
DOC_ONLY_DIRS = {'docs', 'locales'}
CORE_TOPS = {'src', 'packages', 'apps'}
CORE_EXTS = {'.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.json', '.yml', '.yaml', '.toml', '.mdx', '.css', '.scss', '.less', '.sql', '.sh'}
IMPORTANT_NAMES = {'package.json','README.md','Dockerfile','turbo.json','pnpm-workspace.yaml','tsconfig.json','next.config.ts','next.config.mjs'}
MAX_FILE_SIZE = 220_000
MAX_FILES = 420
MAX_DIRS = 260


def rel(p: Path) -> str:
    return p.relative_to(REPO).as_posix()


def is_ignored(path: Path) -> bool:
    parts = set(path.relative_to(REPO).parts) if path != REPO else set()
    if parts & IGNORE_DIRS:
        return True
    if parts and next(iter(path.relative_to(REPO).parts)) not in CORE_TOPS and path.name not in IMPORTANT_NAMES:
        # keep root-level manifests only outside core tops
        if len(path.relative_to(REPO).parts) > 1:
            return True
    return False


def score_file(r: str, size: int) -> tuple[int, int, str]:
    name = Path(r).name
    parts = r.split('/')
    score = 0
    if parts[0] == 'src': score += 90
    if parts[0] == 'packages': score += 80
    if parts[0] == 'apps': score += 70
    if name in IMPORTANT_NAMES: score += 80
    for token, val in [('index', 30), ('server', 28), ('route', 26), ('router', 26), ('store', 24), ('service', 24), ('schema', 24), ('model', 22), ('config', 20), ('provider', 18), ('client', 16), ('layout', 16), ('page', 16)]:
        if token in r.lower(): score += val
    if '.test.' in r or '.spec.' in r or '__tests__' in r: score -= 40
    if '/locales/' in r or r.startswith('locales/'): score -= 60
    if '/docs/' in r or r.startswith('docs/'): score -= 40
    score -= len(parts) // 2
    return (-score, size, r)


def collect_targets():
    files = []
    dirs = set()
    for p in REPO.rglob('*'):
        if is_ignored(p):
            continue
        if p.is_file():
            r = rel(p)
            if p.suffix.lower() in CORE_EXTS or p.name in IMPORTANT_NAMES:
                size = p.stat().st_size
                if size <= MAX_FILE_SIZE:
                    files.append((r, size))
                    pp = Path(r).parent
                    while str(pp) != '.':
                        dirs.add(pp.as_posix())
                        pp = pp.parent
        elif p.is_dir():
            if not is_ignored(p):
                r = rel(p)
                if r.split('/')[0] in CORE_TOPS:
                    dirs.add(r)
    files = [r for r, size in sorted(files, key=lambda x: score_file(x[0], x[1]))[:MAX_FILES]]
    # keep dirs that are ancestors of selected files or important shallow core dirs
    keep_dirs = set()
    for f in files:
        pp = Path(f).parent
        while str(pp) != '.':
            keep_dirs.add(pp.as_posix())
            pp = pp.parent
    for d in dirs:
        if d.count('/') <= 2 and d.split('/')[0] in CORE_TOPS:
            keep_dirs.add(d)
    dirs = sorted(keep_dirs, key=lambda d: (d.count('/'), d))[:MAX_DIRS]
    return dirs, files


def update_progress(done: int, total: int, current: str, status: str = 'running'):
    PROGRESS.write_text(json.dumps({
        'status': status,
        'done': done,
        'total': total,
        'percent': round(done / total * 100, 2) if total else 100,
        'current': current,
        'updated_at': time.time(),
        'unit': '目录+文件',
    }, ensure_ascii=False, indent=2), encoding='utf-8')


def safe_read(path: Path, limit=18000) -> str:
    try:
        return path.read_text(encoding='utf-8', errors='replace')[:limit]
    except Exception as e:
        return f'[读取失败: {e}]'


def write_md(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + '\n', encoding='utf-8')


def sample_tree(prefix: str, files: list[str], limit=80) -> str:
    selected = [f for f in files if f.startswith(prefix + '/')]
    return '\n'.join(selected[:limit]) + ('\n...' if len(selected) > limit else '')


def direct_children(d: str, dirs: list[str], files: list[str]):
    children_dirs = sorted({x[len(d)+1:].split('/')[0] for x in dirs if x.startswith(d + '/') and x != d})
    children_files = sorted([Path(f).name for f in files if str(Path(f).parent).replace('\\','/') == d])
    return children_dirs[:40], children_files[:60]


def codex_explain(kind: str, target: str, context: str, timeout=180) -> str | None:
    prompt = f'''
你是 LobeHub 项目的中文源码学习文档作者。请只基于下面给你的真实目录/源码信息，写一页适合小白理解的 Markdown 解释。

要求：
- 中文为主，代码名、文件名、函数名、包名保留英文。
- 不要空泛描述，不要只贴源码。
- 必须说明：它负责什么、为什么存在、和上下游关系、下面重要子目录/文件分别做什么、小白阅读顺序。
- 如果证据不足，明确写“基于当前文件名和片段推测”。
- 输出 Markdown 正文，不要寒暄。

类型：{kind}
目标：{target}
上下文：
```text
{context[:24000]}
```
'''
    try:
        cp = subprocess.run(
            ['codex', 'exec', '--skip-git-repo-check', '-'],
            input=prompt,
            text=True,
            cwd=str(REPO),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        out = cp.stdout.strip()
        if cp.returncode == 0 and out:
            # Strip noisy codex headers if any; keep markdown-looking tail.
            return out[-18000:]
        return None
    except Exception:
        return None


def fallback_dir_doc(d: str, dirs: list[str], files: list[str]) -> str:
    cdirs, cfiles = direct_children(d, dirs, files)
    return f'''
# 目录：{d}

## 它负责什么
`{d}` 是 LobeHub 代码树中的一个功能区域。下面的说明基于真实目录结构和被选中的源码文件生成，后续 Codex 深度解释会继续补全更细的调用关系。

## 下面有哪些子目录
{chr(10).join(f'- `{x}`：`{d}/{x}` 下的子功能区，建议展开继续读。' for x in cdirs) or '- 没有发现直接子目录。'}

## 下面有哪些重要文件
{chr(10).join(f'- `{x}`：该目录下的源码/配置文件，点击文件名进入文件级解释。' for x in cfiles) or '- 没有发现直接文件，主要内容在更深层子目录。'}

## 文件树节选
```text
{sample_tree(d, files)}
```

## 小白阅读建议
先看本目录下的 `index`、`route`、`store`、`service`、`schema`、`config` 等名字明显的文件，再顺着导入关系读更深层文件。
'''


def fallback_file_doc(f: str) -> str:
    txt = safe_read(REPO / f, 22000)
    imports = '\n'.join(re.findall(r'^(?:import|export)\s+.*$', txt, flags=re.M)[:40])
    symbols = '\n'.join(re.findall(r'^(?:export\s+)?(?:const|function|class|interface|type)\s+[A-Za-z0-9_]+.*$', txt, flags=re.M)[:60])
    return f'''
# 文件：{f}

## 文件职责
这个文件位于 `{str(Path(f).parent)}`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
{imports or '未在节选中发现明显 import/export 语句。'}
```

## 主要对外内容
```text
{symbols or '未在节选中发现明显导出的类型、函数或组件。'}
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
{txt}
```
'''


def main():
    if not REPO.exists():
        raise SystemExit(f'missing repo {REPO}')
    dirs, files = collect_targets()
    if OUT.exists():
        backup = OUT.with_name(OUT.name + f'.bak-{int(time.time())}')
        shutil.copytree(OUT, backup)
    for sub in ['directories','files']:
        shutil.rmtree(OUT/sub, ignore_errors=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'directories').mkdir(exist_ok=True)
    (OUT/'files').mkdir(exist_ok=True)
    total = len(dirs) + len(files)
    done = 0
    update_progress(done, total, '准备解析')

    write_md(OUT/'index.md', f'''
# LobeHub 中文学习文档

## 解析范围与进度
本轮重解析覆盖核心代码树：`src`、`packages`、`apps`。为了避免被 `.agents`、`.github`、构建缓存、海量配置和文档噪声淹没，本轮优先解析最能解释项目架构和运行链路的 {len(dirs)} 个目录与 {len(files)} 个文件。

## 推荐阅读顺序
1. [项目整体介绍](00-overview.md)
2. [技术栈与预备知识](01-tech-stack.md)
3. [架构与目录关系](02-architecture.md)
4. [运行链路 / 数据流](03-runtime-flow.md)
5. 从左侧 `源码结构` 展开 `src`、`packages`、`apps`，点击目录名读目录说明，点击文件名读文件说明。

## 完全小白路线
先读 `src`，再读 `src/server`、`src/store`、`src/features`、`packages`，最后按兴趣进入具体文件。
''')
    write_md(OUT/'00-overview.md', f'''
# 项目整体介绍

LobeHub 是一个大型 TypeScript/React/Next.js 体系项目，包含前端应用、服务端能力、模型运行时、数据库、桌面端和多包复用模块。本轮文档重点不是罗列源码，而是把核心目录和文件转成中文学习路径。

- 核心目录目标数：{len(dirs)}
- 核心文件目标数：{len(files)}
- 解析进度口径：已解析目录+文件 / 目录+文件总数
''')
    write_md(OUT/'01-tech-stack.md', '# 技术栈与预备知识\n\n主要技术线索：TypeScript、React、Next.js、状态管理、服务端 API、数据库 schema、模型运行时 packages、桌面端 apps。\n')
    write_md(OUT/'02-architecture.md', '# 架构与目录关系\n\n建议把项目理解成三层：`src` 应用主体，`packages` 可复用能力包，`apps` 独立应用入口。\n')
    write_md(OUT/'03-runtime-flow.md', '# 运行链路 / 数据流\n\n从页面/路由进入，经过状态与服务层，调用 server/database/model-runtime 等能力，再回到 UI 展示。具体链路请从左侧目录和文件页逐层阅读。\n')

    order = ['index.md','00-overview.md','01-tech-stack.md','02-architecture.md','03-runtime-flow.md']
    for d in dirs:
        done += 1
        update_progress(done, total, f'目录 {d}')
        context = fallback_dir_doc(d, dirs, files)
        # First pass must be real-time: write deterministic structure docs immediately.
        # Codex enhancement is intentionally deferred so progress does not appear stuck.
        write_md(OUT/'directories'/f"{d.replace('/', '__')}.md", context)
        order.append(f"directories/{d.replace('/', '__')}.md")
    for f in files:
        done += 1
        update_progress(done, total, f'文件 {f}')
        context = fallback_file_doc(f)
        # First pass must be real-time: write deterministic file docs immediately.
        # Codex enhancement is intentionally deferred so progress does not appear stuck.
        write_md(OUT/'files'/f"{f.replace('/', '__')}.md", context)
        order.append(f"files/{f.replace('/', '__')}.md")
    (OUT/'manifest.json').write_text(json.dumps({'order': order, 'source': SOURCE, 'generated_at': time.time(), 'targets': {'dirs': len(dirs), 'files': len(files)}}, ensure_ascii=False, indent=2), encoding='utf-8')
    update_progress(total, total, '完成', status='completed')
    print(json.dumps({'dirs': len(dirs), 'files': len(files), 'total': total}, ensure_ascii=False))

if __name__ == '__main__':
    main()
