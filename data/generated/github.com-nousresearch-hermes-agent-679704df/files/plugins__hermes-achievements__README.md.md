# 文件：plugins/hermes-achievements/README.md

## 一句话定位

`plugins/hermes-achievements/README.md` 是内置 dashboard 插件 `hermes-achievements` 的说明入口：它面向用户和维护者解释这个成就系统插件做什么、如何安装/更新、暴露哪些 dashboard API、有哪些关键文件，以及如何做最小验证。它不是运行时代码，不参与插件扫描、路由挂载或成就计算本身。

## 它暴露/定义了什么

这个 README 主要定义的是“插件契约说明”，而不是 Python/JavaScript 接口。文档中明确了插件的产品定位：Hermes Dashboard 的成就系统会扫描本地 Hermes session history，根据真实 agent 行为解锁分层 badge。它还说明了三类成就状态：`Unlocked`、`Discovered`、`Secret`，以及常见等级序列 `Copper`、`Silver`、`Gold`、`Diamond`、`Olympian`。

从维护视角看，它暴露了几个重要事实：插件随 Hermes Agent vendored 到 `plugins/hermes-achievements/`；dashboard 启动时会自动注册为 tab；成就解锁状态存在用户本地 `state.json`；成就 ID 是状态键，不应随意重命名；性能路径已经改为 snapshot cache 与 incremental checkpoint scan。文档还列出 dashboard 插件包结构：`dashboard/manifest.json`、`dashboard/plugin_api.py`、`dashboard/dist/index.js`、`dashboard/dist/style.css`。

## 谁调用它

严格说，没有代码“调用”这个 README。Hermes dashboard 插件加载器读取的是 `plugins/hermes-achievements/dashboard/manifest.json`，后端路由挂载的是 `dashboard/plugin_api.py`，前端加载的是 `dashboard/dist/index.js` 和 `dashboard/dist/style.css`。README 只被人阅读，或者被文档站、仓库浏览器、开发者 onboarding 流程间接引用。

根据当前片段推断，真正的运行时调用链是：用户打开 `hermes dashboard` 后，`hermes_cli/web_server.py` 扫描用户插件目录和仓库内置 `plugins/*/dashboard/manifest.json`；发现 `hermes-achievements` 的 manifest 后，将其注册为 dashboard tab，并按 `api` 字段挂载 `plugin_api.py` 中的 `router`。README 中的“auto-registers as a dashboard tab”正是在描述这条运行时路径。

## 它调用谁

README 本身不调用任何模块。它描述的插件运行时会调用/依赖这些对象：

`dashboard/manifest.json` 提供 dashboard 插件元数据，包括 `name`、`label`、`tab.path`、`entry`、`css`、`api`。`dashboard/plugin_api.py` 暴露 FastAPI `APIRouter`，由 dashboard 后端挂载到 `/api/plugins/hermes-achievements/` 下。该后端读取 Hermes home 下的 session/state/snapshot/checkpoint 数据，主要通过 `get_hermes_home()` 定位用户本地状态目录。前端 `dashboard/dist/index.js` 调用 README 中列出的 API，例如 `GET /achievements`、`GET /scan-status`、`GET /recent-unlocks`、`GET /sessions/{session_id}/badges`、`POST /rescan`、`POST /reset-state`。

## 核心流程

整体流程可以理解为“插件发现 -> API 挂载 -> 扫描本地历史 -> 聚合指标 -> 评估成就 -> dashboard 展示”。

第一步，dashboard 启动时扫描 `dashboard/manifest.json`。manifest 声明此插件的 tab 路径是 `/achievements`，前端入口是 `dist/index.js`，样式是 `dist/style.css`，后端 API 是 `plugin_api.py`。这一步决定插件能否出现在 dashboard 里。

第二步，后端挂载 `plugin_api.py` 的 `router`。README 中列出的 API 都属于这个 router 的公开表面。用户进入 Achievements 页时，前端会请求 `/achievements` 获取成就快照，必要时请求 `/scan-status` 或触发 `/rescan`。

第三步，扫描逻辑读取本地 Hermes session history，把 tool calls、错误模式、文件编辑、web/browser 使用、模型/Provider 线索、skills/memory/plugin/cron 等行为转成统计指标。为了避免每次冷启动都全量扫描，当前实现引入 `scan_snapshot.json` 和 `scan_checkpoint.json`：snapshot 缓存完整结果，checkpoint 复用未变化 session 的分析结果。

第四步，成就定义中的 `threshold_metric` 或 `requirements` 与聚合指标比对，得到 `unlocked`、`discovered` 或隐藏状态。结果再和 `state.json` 中已有 unlock 状态合并，保证已解锁状态持久保存。最后 dashboard 前端把卡片、等级、进度、最近解锁和分享卡能力展示出来。

## 关键函数的高层作用

README 不定义函数，但它指向的核心实现集中在 `plugins/hermes-achievements/dashboard/plugin_api.py`。

`ACHIEVEMENTS` 是成就目录的核心数据源，定义每个 badge 的 `id`、`name`、`category`、`kind`、`threshold_metric`、`tiers` 或 `requirements`。修改它会直接改变 dashboard 展示和解锁规则。

`tiers()` 和 `req()` 是成就定义的轻量构造函数，用来减少重复结构；它们属于辅助函数，一句概括就是把阈值和条件包装成统一 dict。

`state_path()`、`snapshot_path()`、`checkpoint_path()` 负责把插件状态文件定位到 Hermes home 下的 `plugins/hermes-achievements/`。这保证 profile-aware 路径与普通用户安装路径一致。

`load_state()`、`save_state()` 管理已解锁状态；`load_snapshot()`、`save_snapshot()` 管理短期结果快照；`load_checkpoint()`、`save_checkpoint()` 管理按 session 复用的扫描检查点。它们共同支撑 README 中提到的“更快 warm loads”。

`analyze_messages()` 根据测试引用可知负责把单个 session 的消息内容分析成统计信号，例如错误、端口冲突、配置、文件、工具、模型等事件。`aggregate_stats()` 将多个 session 的统计合并为 lifetime 或 best-session 指标。`evaluate_tiered()` 处理分层阈值，`evaluate_requirements()` 处理多条件成就，`evaluate_definition()` 是对单个成就定义进行统一评估的入口。`display_achievement()` 则把内部评估结果整理成 dashboard 可消费的展示对象。

## 修改风险

最大风险是把 README 当成安装手册随意改，而忽略它同时记录了运行时契约。比如 API 列表、状态文件含义、成就 ID 稳定性、更新注意事项都和真实代码行为有关；如果文档和 `manifest.json`、`plugin_api.py` 不一致，会误导用户排障和插件维护。

第二个风险是成就 ID 和状态存储。README 已明确 `state.json` 使用 achievement ID 作为 unlock-state key，因此重命名 `ACHIEVEMENTS` 里的 `id` 会让已有用户看起来“丢失”历史解锁。新增成就通常安全，改阈值会影响进度展示，删除或重命名成就需要迁移策略。

第三个风险是性能说明。README 提到 snapshot cache 与 incremental checkpoint scan；如果后端扫描策略变化，必须同步更新这里，否则用户可能按旧流程理解 `/rescan`、warm load 和 checkpoint 行为。尤其是扫描本地 session history 的插件，冷启动时间、缓存 TTL、损坏 state 的容错都会影响 dashboard 首屏体验。

第四个风险是外部安装与 vendored 状态混杂。README 同时说明它已随 Hermes Agent 内置，又保留独立 clone/symlink 的开发安装方式。修改安装章节时要区分“普通 Hermes 用户无需安装”和“独立插件开发者可手动安装”，否则容易造成重复安装、旧版本覆盖或 dashboard 插件扫描路径混乱。

最后，README 中的截图、示例成就名、版本说明和测试命令都属于维护者信号。若 `dashboard/dist/index.js`、`dashboard/plugin_api.py` 或 `tests/test_achievement_engine.py` 的检查方式变化，`Development` 章节也要同步，否则贡献者会运行错误的验证命令。
