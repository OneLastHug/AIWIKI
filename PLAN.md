# Repo Learning Docs Service Implementation Plan

> **For Hermes:** Use Codex CLI to implement this plan. Keep the service scoped to code-learning documentation, not general document mirroring.

**Goal:** Build a local web service exposed through `docs.eitc.top` where the user can submit a GitHub/GitLab URL or allowed local repository path, then receive a generated multi-page beginner-friendly documentation site produced by Codex analysis.

**Architecture:** Python standard-library HTTP service for MVP, SQLite for jobs/repos, filesystem storage for cloned/imported repos and generated Markdown docs. Background worker processes jobs asynchronously and calls Codex via CLI to generate docs. Markdown is rendered to HTML dynamically. Large repos are chunked into overview, directory docs, and selected file docs rather than one giant page.

**Tech Stack:** Python 3, sqlite3, subprocess/git, codex CLI, standard-library http.server, markdown rendering fallback.

---

## Non-negotiable product rules

1. This is for learning code repositories.
2. Pure-document repositories must be filtered/rejected by default, especially collections dominated by `.md`, `.pdf`, `.doc`, `.docx`, `.ppt`, `.txt`, etc. The service should explain that such projects look like document/content repositories rather than code-learning targets.
3. A valid project should have meaningful code signals: source extensions, build manifests, package metadata, or executable entrypoints.
4. Generated homepage must be a recommended reading order, not a plain file list.
5. Generated docs must be segmented for large repos.
6. Do not expose secrets. Never render `.env`, private keys, or token files.
7. Local path submissions must be restricted to `/data/project`.

---

## Task 1: Create MVP file layout

**Objective:** Create a self-contained Python service under `/data/project/repo-docs-service`.

**Files:**
- Create: `server.py`
- Create: `README.md`
- Create: `data/.gitkeep`
- Create: `generated/.gitkeep`
- Create: `repos/.gitkeep`

**Requirements:**
- service port defaults to `18081`
- data root defaults to `/data/project/repo-docs-service/data`
- safe paths only

---

## Task 2: Add repository intake and filtering

**Objective:** Implement submission handling for GitHub/GitLab HTTPS URLs and local paths under `/data/project`.

**Routes:**
- `GET /` form and existing projects list
- `POST /submit` create job
- `GET /jobs/<job_id>` status page

**Filtering logic:**
- After clone/copy or for local path, scan up to a reasonable number of files.
- Reject if document assets dominate and code signals are too weak.
- Reject if no build manifest and code file count is too low.
- Count as document extensions: `.md`, `.markdown`, `.pdf`, `.doc`, `.docx`, `.ppt`, `.pptx`, `.txt`, `.rtf`, `.epub`.
- Count as code extensions: `.py`, `.js`, `.ts`, `.tsx`, `.jsx`, `.java`, `.kt`, `.go`, `.rs`, `.c`, `.cpp`, `.h`, `.hpp`, `.cs`, `.rb`, `.php`, `.swift`, `.scala`, `.sh`, `.sql`, `.vue`, `.svelte`.
- Count build manifests: `package.json`, `pyproject.toml`, `setup.py`, `requirements.txt`, `pom.xml`, `build.gradle`, `settings.gradle`, `Cargo.toml`, `go.mod`, `Makefile`, `CMakeLists.txt`, `composer.json`, `Gemfile`.

**Output:** rejected jobs must show a friendly reason.

---

## Task 3: Add background worker and status persistence

**Objective:** Jobs run asynchronously and persist status in SQLite.

**States:**
- queued
- importing
- filtering
- generating
- completed
- failed
- rejected

**Store:**
- `repos` table: repo_id, source, local_path, generated_path, created_at, status
- `jobs` table: job_id, repo_id, source, status, message, log, created_at, updated_at

---

## Task 4: Generate repository analysis inputs

**Objective:** Build a compact snapshot for Codex.

**Snapshot includes:**
- file tree excluding `.git`, `node_modules`, `dist`, `build`, `target`, `.next`, `coverage`, `.venv`, `__pycache__`
- language/file counts
- manifest file contents, truncated
- README/docs summaries where relevant
- selected source file snippets for top important files

---

## Task 5: Call Codex to generate segmented Markdown docs

**Objective:** Use Codex CLI to generate docs into `data/generated/<repo_id>/`.

**Command pattern:**
- Write prompt to a temp file.
- Run `codex exec --skip-git-repo-check --full-auto "$(cat prompt)"` inside service repo or target repo with PTY if needed.

**Prompt must require:**
- `index.md` as recommended reading order
- `00-overview.md`
- `01-tech-stack.md`
- `02-architecture.md`
- `03-runtime-flow.md`
- `directories/*.md`
- `files/*.md` for selected important files
- beginner-friendly explanations
- label uncertainty as inference
- do not claim facts not grounded in files

**Fallback:** If Codex fails, generate basic non-Codex docs from snapshot and mark warning.

---

## Task 6: Markdown rendering and doc routes

**Objective:** Render generated Markdown as HTML.

**Routes:**
- `GET /repos/<repo_id>/` renders `index.md`
- `GET /repos/<repo_id>/<path>` renders corresponding `.md`
- include sidebar from manifest / generated file list
- previous/next navigation based on reading order if possible

---

## Task 7: Verification

**Commands:**
- start server on `127.0.0.1:18081`
- submit `/data/project/lobehub`
- verify filter accepts it
- verify index/job page works
- verify generated docs render
- verify pure-doc synthetic repo is rejected

---
