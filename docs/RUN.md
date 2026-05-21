# AIWIKI 运行手册

## 启动服务

```bash
cd /data/project/AIWIKI
python3 server.py
```

默认监听：

```text
[URL已移除]
```

默认数据目录是：

```text
/data/project/AIWIKI/data
```

如需覆盖数据目录：

```bash
RDS_BASE=/some/other/data python3 server.py
```

## 端到端运行管线

```bash
python3 scripts/run_pipeline.py \
  --repo /data/project/lobehub \
  --out /data/project/AIWIKI/data/generated/data-project-lobehub-167e6641 \
  --concurrency 5 \
  --timeout 1800 \
  --max-tasks 500
```

如果只想验证 Stage B/C，不调用总览模型：

```bash
python3 scripts/run_pipeline.py \
  --repo /data/project/lobehub \
  --out /data/project/AIWIKI/data/generated/data-project-lobehub-167e6641 \
  --skip-overview
```

## 分阶段运行

Stage A 生成项目总览与关键路径：

```bash
python3 scripts/codex_overview.py \
  --repo /data/project/lobehub \
  --out /data/project/AIWIKI/data/generated/data-project-lobehub-167e6641 \
  --run-id manual-a \
  --timeout 1800
```

Stage B 本地扫描并写入任务表：

```bash
python3 scripts/build_task_table.py \
  --repo /data/project/lobehub \
  --out /data/project/AIWIKI/data/generated/data-project-lobehub-167e6641 \
  --run-id manual-b \
  --max-tasks 500
```

Stage C 并发执行任务池：

```bash
python3 scripts/codex_parallel_pool.py \
  --repo /data/project/lobehub \
  --out /data/project/AIWIKI/data/generated/data-project-lobehub-167e6641 \
  --run-id manual-c \
  --concurrency 5 \
  --timeout 1800
```

通常应优先使用 `run_pipeline.py`，因为它会创建一致的 `run_id`、清理旧终态文件，并在结束时写入唯一终态文件。默认超时为 1800 秒，Stage A 和 Stage C 共用这一套超时；如需调整，只传一次 `--timeout`。

如果 Codex CLI 返回 usage limit、quota、鉴权或网络类错误，Stage A/C 会切到本地仓库快照兜底生成，并在 stage payload 与 Markdown 开头标明 fallback 原因；这保证管线状态、任务表、进度投影和终态文件仍然一致。需要做纯 Codex 验收时，可设置 `AIWIKI_DISABLE_LOCAL_FALLBACK=1`，此时 Codex 不可用会直接失败。

## 输出文件

每个生成目录包含这些运行时文件：

```text
index.md
00-overview.md
01-tech-stack.md
02-architecture.md
03-runtime-flow.md
critical_paths.json
codex_task_table.csv
state.sqlite3
progress.json
pipeline.success | pipeline.partial | pipeline.failed
directories/*.md
files/*.md
codex_debug/*
```

`pipeline.success`、`pipeline.partial`、`pipeline.failed` 三者在管线结束后只会保留一个：

- `pipeline.success`：总览、任务表、任务池全部完成，任务全为 `done`。
- `pipeline.partial`：关键阶段完成，但部分 Stage C 任务失败；成功文档仍可浏览，可重跑修复失败项。
- `pipeline.failed`：Stage A/B/C 关键阶段失败，或结束时仍有未完成任务。

## 状态与事件

`state.sqlite3` 是唯一运行时真相源，包含：

```text
pipeline_runs
stages
tasks
workers
signals
```

`progress.json` 是从 SQLite 聚合出来的投影，保留旧字段：

```text
status, done, total, percent, failed, current, updated_at,
unit, model, reasoning, timeout_seconds, last_success, last_error
```

并新增：

```text
run_id, stage, active_workers, task_breakdown
```

通过 HTTP 查看事件：

```bash
curl '[URL已移除]>/signals?since=0'
```

返回格式：

```json
{
  "signals": [
    {"id": 1, "type": "PIPELINE_STARTED", "payload": {}, "at": 1760000000.0}
  ]
}
```

轮询时把最后一个 `id` 作为下一次的 `since`。

## Codex CLI

管线默认查找 `CODEX_BIN`，其次使用 `PATH` 里的 `codex`。

```bash
CODEX_BIN=/root/.local/bin/codex python3 scripts/run_pipeline.py --repo <repo> --out <out>
```

Stage A 使用：

```text
model=gpt-5.5
reasoning=high
sandbox_mode=workspace-write
```

Stage C 使用：

```text
model=gpt-5.5
reasoning=medium
sandbox_mode=read-only
```

Stage C 每个任务会保留：

```text
codex_debug/last_prompt_<task>.txt
codex_debug/last_raw_<task>.txt
codex_debug/last_md_<task>.md
```

只有 `last_md` 通过 Markdown 校验后，才会原子写入 `directories/*.md` 或 `files/*.md`。
