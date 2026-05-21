#!/usr/bin/env python3
"""Serial Codex agent worker for LobeHub docs.

Approved strategy:
- Read a prebuilt task table containing absolute paths.
- One task = one fresh Codex exec session.
- The Codex agent reads context itself from the repo, guided by the absolute target path.
- After each task, the Codex process is closed. On timeout, kill its whole process group.
- Progress is cumulative real success count; a task counts only after validated Markdown is written.
"""
from __future__ import annotations

import csv
import json
import os
import re
import signal
import subprocess
import time
from pathlib import Path

REPO = Path('/data/project/lobehub').resolve()
OUT = Path('/data/project/repo-docs-service/data/generated/data-project-lobehub-167e6641').resolve()
TASK_TABLE = OUT / 'codex_task_table.csv'
ENHANCED = OUT / '.codex_enhanced.json'
PROGRESS = OUT / 'progress.json'
FAILURES = OUT / 'codex_failures.log'
DEBUG_DIR = OUT / 'codex_debug'
CODEX = '/root/.local/bin/codex'
MODEL = 'gpt-5.5'
REASONING = 'medium'
TIMEOUT = int(os.environ.get('LOBEHUB_CODEX_TIMEOUT', '600'))
MAX_TASKS = int(os.environ.get('LOBEHUB_CODEX_MAX_TARGETS', '80'))

DEBUG_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def save_json(path: Path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def load_tasks():
    with TASK_TABLE.open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def enhanced_set():
    return set(load_json(ENHANCED, {'enhanced': []}).get('enhanced', []))


def failed_count():
    if not FAILURES.exists():
        return 0
    text = FAILURES.read_text(encoding='utf-8', errors='replace')
    return text.count('===== ')


def rel_key(task):
    return task['output_md'].replace(str(OUT) + '/', '')


def update_progress(status: str, current: str, tasks_total: int, last_error: str | None = None, current_started_at: float | None = None, last_success: str | None = None):
    done = len(enhanced_set())
    now = time.time()
    obj = {
        'status': status,
        'done': done,
        'total': tasks_total,
        'percent': round(done / tasks_total * 100, 2) if tasks_total else 0,
        'failed': failed_count(),
        'current': current,
        'updated_at': now,
        'unit': 'Codex独立Agent解析页',
        'note': '任务来自 codex_task_table.csv；每个目录/文件单独启动 Codex agent，完成/失败后关闭进程；成功写回才计数。',
        'model': MODEL,
        'reasoning': REASONING,
        'timeout_seconds': TIMEOUT,
    }
    if current_started_at:
        obj['current_started_at'] = current_started_at
        obj['current_elapsed_seconds'] = round(now - current_started_at, 1)
    if last_success:
        obj['last_success'] = last_success
    if last_error:
        obj['last_error'] = last_error
    save_json(PROGRESS, obj)


def log_failure(task, reason: str, output: str):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    with FAILURES.open('a', encoding='utf-8') as f:
        f.write(f"\n===== {ts} =====\n")
        f.write(f"kind: {task['kind']}\n")
        f.write(f"target: {task['rel_path']}\n")
        f.write(f"abs_path: {task['abs_path']}\n")
        f.write(f"reason: {reason}\n")
        f.write(f"output_len: {len(output)}\n")
        f.write('--- output head ---\n')
        f.write(output[:3000])
        f.write('\n--- output tail ---\n')
        f.write(output[-3000:])
        f.write('\n')


def sanitize(name: str) -> str:
    return re.sub(r'[^A-Za-z0-9_.-]+', '_', name)[:160]


def build_prompt(task) -> str:
    rel = task['rel_path']
    kind_cn = '目录' if task['kind'] == 'directory' else '文件'
    title = f"# {kind_cn}：{rel}"
    return f"""你是“万用文档”的源码学习文档作者。现在只处理任务表中的一个目标。请启动全新的理解过程，自己在仓库里读取必要上下文，然后输出这个目标的中文学习文档。

仓库根目录：{REPO}
目标类型：{kind_cn}
目标相对路径：{rel}
目标绝对路径：{task['abs_path']}
输出 Markdown 文件路径：{task['output_md']}

上下文读取要求：
- 你必须自己查看目标路径及其邻近上下文，不要只根据路径名猜。
- 每个任务最多执行 6 个 shell 命令。
- 文件任务：优先完整阅读目标文件；再查看同目录 index/types/provider/service/config；必要时查 1-2 个调用方。
- 目录任务：先列出直接子目录/文件；再查看 README/package/index/router/config 等入口；必要时抽样 1-2 个代表文件。

大目录规则（重要）：
- 如果目标是 `src`、`packages`、`apps`、`src/server`、`src/routes`、`src/features`、`src/store` 等超大目录，只做地图式概览。
- 超大目录不要深挖每个文件；只解释当前目录总体职责、直接下属目录/文件角色、初学者先读哪些入口。
- 超大目录文档控制在 1200-2200 中文字左右。
- 具体文件或小目录才做 import/export、调用方、核心逻辑的深入解释。

最终输出要求：
- 最终只输出 Markdown 正文，不要输出你执行命令的过程，不要说“我将查看”。
- 中文为主，路径、函数名、类名、包名、命令保留英文。
- 面向小白，但必须具体到真实源码内容。
- 不要复用旧草稿模板，不要写“后续会补全”，不要只罗列文件名。
- 如果证据不足，写“根据当前片段推断”，并说明依据。

必须包含这些章节：
{title}
## 它负责什么
## 关键组成
## 上下游关系
## 运行/调用流程
## 小白阅读顺序
## 常见误区
"""


def strip_codex_output(text: str) -> str:
    # Prefer content after the final assistant marker if CLI logs are present.
    if '\ncodex\n' in text:
        parts = text.split('\ncodex\n')
        text = parts[-1]
    text = re.sub(r'\ntokens used\n[\s\S]*$', '', text).strip()
    return text.strip()


def validate_markdown(task, md: str) -> tuple[bool, str]:
    if len(md) < 800:
        return False, f'too short: {len(md)} chars'
    rel = task['rel_path']
    if rel not in md:
        return False, f'missing target rel path {rel}'
    required = ['## 它负责什么', '## 关键组成', '## 上下游关系', '## 小白阅读顺序']
    missing = [h for h in required if h not in md]
    if missing:
        return False, 'missing headings: ' + ', '.join(missing)
    banned = ['后续会补全', '下面的说明基于真实目录结构', '只可参考']
    if any(b in md for b in banned):
        return False, 'contains banned draft/template phrase'
    return True, 'ok'


def run_one(task, tasks_total: int) -> bool:
    current = f"{task['kind']} {task['rel_path']}"
    started_at = time.time()
    update_progress('codex-agent-running', f'正在解析：{current}', tasks_total, current_started_at=started_at)
    prompt = build_prompt(task)
    safe = sanitize(task['kind'] + '_' + task['rel_path'])
    raw_out = DEBUG_DIR / f'last_raw_{safe}.txt'
    md_out = DEBUG_DIR / f'last_md_{safe}.md'
    prompt_file = DEBUG_DIR / f'last_prompt_{safe}.txt'
    prompt_file.write_text(prompt, encoding='utf-8')
    cmd = [
        CODEX, 'exec', '--skip-git-repo-check', '--cd', str(REPO),
        '-m', MODEL,
        '-c', f'model_reasoning_effort="{REASONING}"',
        '-c', 'model_reasoning_summary="auto"',
        '-o', str(md_out),
        prompt,
    ]
    output = ''
    proc = None
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(REPO),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            preexec_fn=os.setsid,
        )
        try:
            output, _ = proc.communicate(timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                output, _ = proc.communicate(timeout=20)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                output, _ = proc.communicate(timeout=20)
            raw_out.write_text(output or '', encoding='utf-8', errors='replace')
            reason = f'timeout after {TIMEOUT}s; process group killed'
            log_failure(task, reason, output or '')
            update_progress('codex-agent-running', f'失败未计数，继续下一项：{current}', tasks_total, reason, current_started_at=started_at)
            return False
    except Exception as e:
        if proc and proc.poll() is None:
            try: os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError: pass
        reason = f'exception: {type(e).__name__}: {e}'
        log_failure(task, reason, output or '')
        update_progress('codex-agent-running', f'异常未计数，继续下一项：{current}', tasks_total, reason, current_started_at=started_at)
        return False

    raw_out.write_text(output or '', encoding='utf-8', errors='replace')
    if proc.returncode != 0:
        reason = f'nonzero returncode {proc.returncode}'
        log_failure(task, reason, output or '')
        update_progress('codex-agent-running', f'失败未计数，继续下一项：{current}', tasks_total, reason, current_started_at=started_at)
        return False

    md = ''
    if md_out.exists() and md_out.stat().st_size > 0:
        md = md_out.read_text(encoding='utf-8', errors='replace').strip()
    if not md:
        md = strip_codex_output(output or '')
    ok, reason = validate_markdown(task, md)
    if not ok:
        log_failure(task, 'validation failed: ' + reason, output or md)
        update_progress('codex-agent-running', f'校验失败未计数：{current}', tasks_total, reason, current_started_at=started_at)
        return False

    out_path = Path(task['output_md'])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md + "\n\n---\n\n> 本页已由独立 Codex agent 使用 gpt-5.5 medium 读取 LobeHub 真实源码后增强。\n", encoding='utf-8')
    state = load_json(ENHANCED, {'enhanced': []})
    done = set(state.get('enhanced', []))
    done.add(rel_key(task))
    state['enhanced'] = sorted(done)
    state['updated_at'] = time.time()
    save_json(ENHANCED, state)
    update_progress('codex-agent-running', f'已完成：{current}，准备下一项', tasks_total, last_success=current)
    return True


def main():
    tasks = load_tasks()
    tasks_total = len(tasks)
    done = enhanced_set()
    pending = [t for t in tasks if rel_key(t) not in done]
    selected = pending[:MAX_TASKS]
    update_progress('codex-agent-running', f'开始串行解析，本批 {len(selected)} 项', tasks_total)
    ok_count = 0
    for task in selected:
        if run_one(task, tasks_total):
            ok_count += 1
        # Ensure each task's process is gone before next one.
        time.sleep(1)
    final_status = 'completed' if len(enhanced_set()) >= tasks_total else 'partial'
    update_progress(final_status, f'本轮结束：成功 {ok_count} 项，累计 {len(enhanced_set())}/{tasks_total}', tasks_total)
    print(json.dumps({'round_success': ok_count, 'cumulative_done': len(enhanced_set()), 'total': tasks_total, 'status': final_status}, ensure_ascii=False))

if __name__ == '__main__':
    main()
