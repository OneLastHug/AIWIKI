#!/usr/bin/env python3
"""Build a temporary absolute-path task table for LobeHub Codex documentation."""
from __future__ import annotations

import csv
import json
from pathlib import Path

REPO = Path('/data/project/lobehub').resolve()
OUT = Path('/data/project/repo-docs-service/data/generated/data-project-lobehub-167e6641').resolve()
MANIFEST_CSV = OUT / 'codex_task_table.csv'
MANIFEST_JSON = OUT / 'codex_task_table.json'

CORE_ROOTS = [
    REPO / 'src',
    REPO / 'packages',
    REPO / 'apps',
]
IGNORE_DIRS = {'.git','node_modules','.next','dist','build','coverage','.turbo','.vercel','.cache','tmp','temp','locales'}
CODE_EXTS = {'.ts','.tsx','.js','.jsx','.json','.yml','.yaml','.md','.mdx'}

PINNED = [
    ('directory','src'),
    ('directory','src/server'),
    ('directory','src/store'),
    ('directory','src/features'),
    ('directory','src/routes'),
    ('directory','packages'),
    ('directory','apps'),
    ('file','src/server/runtimeConfig/index.ts'),
    ('file','src/server/runtimeConfig/providers/index.ts'),
    ('file','src/server/routers/lambda/index.ts'),
    ('file','src/server/services/agentRuntime/index.ts'),
    ('file','src/store/serverConfig/index.ts'),
    ('directory','src/server/runtimeConfig'),
    ('directory','src/server/routers'),
    ('directory','src/server/services'),
    ('directory','packages/database/src'),
    ('directory','packages/model-runtime/src'),
]

KEYWORDS = ['runtimeConfig','lambda','agentRuntime','serverConfig','router','service','store','database','model-runtime','provider','config','index']

def skip(path: Path) -> bool:
    parts = set(path.relative_to(REPO).parts)
    return bool(parts & IGNORE_DIRS)

def md_name(rel: str) -> str:
    return rel.replace('/', '__') + '.md'

def output_path(kind: str, rel: str) -> Path:
    return OUT / ('directories' if kind == 'directory' else 'files') / md_name(rel)

def score(kind: str, rel: str) -> tuple:
    s = 0
    for i,k in enumerate(KEYWORDS):
        if k in rel:
            s -= (len(KEYWORDS)-i) * 10
    depth = rel.count('/')
    if kind == 'file':
        s -= 50
        if rel.endswith('/index.ts') or rel.endswith('/index.tsx') or rel.endswith('/index.js'):
            s -= 80
        if '.test.' in rel or '__tests__' in rel:
            s += 120
    else:
        s += depth * 5
    return (s, depth, rel)

def add(tasks, seen, kind, rel, priority, reason):
    abs_path = (REPO / rel).resolve()
    if not abs_path.exists():
        return
    key = (kind, rel)
    if key in seen:
        return
    seen.add(key)
    tasks.append({
        'priority': priority,
        'kind': kind,
        'rel_path': rel,
        'abs_path': str(abs_path),
        'output_md': str(output_path(kind, rel)),
        'reason': reason,
    })

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tasks=[]; seen=set(); pri=0
    for kind, rel in PINNED:
        pri += 10
        add(tasks, seen, kind, rel, pri, 'pinned-core')

    candidates=[]
    for root in CORE_ROOTS:
        if not root.exists():
            continue
        for p in root.rglob('*'):
            if skip(p):
                continue
            rel = p.relative_to(REPO).as_posix()
            if p.is_dir():
                # Keep meaningful dirs, avoid too many leaf test/component fragments.
                if rel.count('/') <= 4 and any(k in rel for k in KEYWORDS):
                    candidates.append(('directory', rel))
            elif p.is_file() and p.suffix in CODE_EXTS and p.stat().st_size <= 160_000:
                if any(k in rel for k in KEYWORDS) or rel.endswith(('/index.ts','/index.tsx','/package.json')):
                    candidates.append(('file', rel))
    candidates = sorted(candidates, key=lambda x: score(*x))
    for kind, rel in candidates:
        if len(tasks) >= 80:
            break
        pri += 10
        add(tasks, seen, kind, rel, pri, 'auto-core-ranked')

    with MANIFEST_CSV.open('w', newline='', encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=['priority','kind','rel_path','abs_path','output_md','reason'])
        w.writeheader(); w.writerows(tasks)
    MANIFEST_JSON.write_text(json.dumps({'repo': str(REPO), 'total': len(tasks), 'tasks': tasks}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'csv': str(MANIFEST_CSV), 'json': str(MANIFEST_JSON), 'total': len(tasks), 'first': tasks[:5]}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
