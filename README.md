# Repo Learning Docs Service

本服务用于 `docs.eitc.top`：输入 GitHub/GitLab 仓库 URL 或 `/data/project` 下的本地代码仓库，生成适合小白学习的分段 Markdown/HTML 文档。

## 运行

```bash
cd /data/project/repo-docs-service
python3 server.py
```

默认监听：

```text
http://127.0.0.1:18081
```

Cloudflare Tunnel Public Hostname 的 origin 填：

```text
http://localhost:18081
```

## 功能

- 首页输入 GitHub/GitLab HTTPS URL 或本地路径。
- 只允许本地 `/data/project` 下的目录。
- 自动过滤纯文档/内容农场类项目：当 `.md/.pdf/.doc/.ppt/.txt` 等文档明显占主导且缺少代码/构建清单时拒绝。
- 后台任务生成文档，不阻塞网页。
- 文档按页面拆分：
  - `index.md` 推荐阅读顺序
  - `00-overview.md`
  - `01-tech-stack.md`
  - `02-architecture.md`
  - `03-runtime-flow.md`
  - `directories/*.md`
  - `files/*.md`
- 渲染为 HTML：`/repos/<repo_id>/...`

## 数据目录

```text
data/service.sqlite3
data/repos/<repo_id>/source
data/generated/<repo_id>/
```

## 安全限制

- 不接受任意域名 git URL，只接受 `https://github.com/...` 和 `https://gitlab.com/...`。
- 本地路径限制在 `/data/project`。
- 跳过 `.git,node_modules,dist,build,target,.next,coverage,.venv,__pycache__`。
- 跳过 `.env,id_rsa,*.pem,*.key` 等敏感文件。

## 注意

MVP 会先用本地快照生成可读文档；如果 Codex CLI 可用，会尝试增强文档。Codex 失败不会导致服务不可用。
