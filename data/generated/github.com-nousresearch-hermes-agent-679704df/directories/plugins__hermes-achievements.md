# 目录：plugins/hermes-achievements

## 它负责什么

`plugins/hermes-achievements` 是 Hermes Dashboard 的内置成就插件，用本地 Hermes 会话历史生成类似“成就徽章”的可视化页面。它不参与核心 agent 推理链路，也不是一个通用工具集；它主要读取 `hermes_state.SessionDB` 中的 session、message、model 等历史数据，统计工具调用、错误模式、文件编辑、Web/浏览器使用、模型/Provider 使用、技能/记忆/插件相关活动等指标，然后把这些指标映射到一组成就定义。

这个目录的核心职责可以分成三层：第一层是 Dashboard 插件注册，通过 `dashboard/manifest.json` 告诉 dashboard 增加一个 Achievements tab；第二层是后端 API，通过 `dashboard/plugin_api.py` 暴露 FastAPI router；第三层是前端展示，通过 `dashboard/dist/index.js` 和 `dashboard/dist/style.css` 渲染成就面板。成就状态本身不是写在仓库里，而是通过 `get_hermes_home()` 落到用户本地 Hermes home 下的插件状态文件中，例如 `state.json`、`scan_snapshot.json`、`scan_checkpoint.json`。

## 直接子目录地图

`dashboard/` 是插件运行时主体目录，包含 Dashboard 插件声明、后端 API 和前端构建产物。`dashboard/manifest.json` 描述插件名称、tab 位置、入口 JS/CSS、后端 API 文件；`dashboard/plugin_api.py` 是所有成就扫描、评估、缓存、路由的核心实现；`dashboard/dist/` 存放已构建好的前端资源。

`docs/` 是设计和实现说明目录，包含性能规格、实现计划等文档。`docs/assets/` 放成就页面截图或展示用图片，服务于 README 和文档说明，不是运行主流程的必要代码。

`tests/` 是插件后端逻辑测试目录，目前重点测试 `dashboard/plugin_api.py` 中的成就引擎函数，例如 session 分析、分层成就评估、secret 状态、模型/Provider 聚合、目录中已移除成就的回归断言等。

根目录下的 `README.md` 是用户和开发者入口说明，概述插件用途、API、更新方式和检查命令；`LICENSE` 是许可证文件。

## 关键入口

最重要的入口是 `dashboard/manifest.json`。Dashboard 插件系统根据这个 manifest 识别插件：`name` 是 `hermes-achievements`，tab 路径是 `/achievements`，前端入口是 `dist/index.js`，样式是 `dist/style.css`，后端 API 是 `plugin_api.py`。因此，想理解“这个目录如何被 dashboard 看见”，先看 manifest。

运行时后端入口是 `dashboard/plugin_api.py` 顶部定义的 `router = APIRouter()`。文件末尾用 `@router.get` 和 `@router.post` 注册 API：`/achievements`、`/scan-status`、`/recent-unlocks`、`/sessions/{session_id}/badges`、`/rescan`、`/reset-state`。这些路由会被 Hermes Dashboard 挂载到插件 API 前缀下。

成就目录本身由 `ACHIEVEMENTS` 常量定义。每个成就包含 `id`、`name`、`description`、`category`、`kind`、`icon`，以及 `threshold_metric` 加 `tiers`，或 `requirements`。分层成就通过 `tiers()` 生成 Copper、Silver、Gold、Diamond、Olympian 阈值；多条件成就通过 `req()` 声明多个指标门槛。

## 主流程位置

主流程从前端请求 `/achievements` 开始，对应 `achievements()`。它调用 `evaluate_all()` 获取当前成就 payload。`evaluate_all()` 是缓存和扫描调度中心：如果内存缓存仍新鲜就直接返回；如果有磁盘 snapshot，会先加载旧结果并在后台刷新；如果首次运行没有 snapshot，会启动后台扫描并返回 pending 结构；如果是 `/rescan`，则以 `force=True` 同步扫描。

扫描逻辑集中在 `scan_sessions()`。它导入 `hermes_state.SessionDB`，调用 `list_sessions_rich()` 获取 session 元数据，再对每个 session 调用 `get_messages()` 读取消息。为了避免大历史库每次全量重算，它使用 `scan_checkpoint.json`，用 `session_fingerprint()` 比较 session 的 `last_active`、`started_at`、`model`、标题等指纹，未变化的 session 复用旧统计，变化的 session 才重新分析。

单个 session 的指标提取在 `analyze_messages()`。这个函数从 message 的 `tool_calls`、`tool_name`、文本内容中识别工具名称、错误文本、端口冲突、安装失败、日志读取、Git 活动、配置文件活动、模型关键词等，并返回一组 session 级统计。

跨 session 聚合在 `aggregate_stats()`。它计算 lifetime 总数、单 session 最大值、distinct model/provider 数、周末/深夜 session 数等。之后 `evaluate_definition()` 根据成就定义类型分发到 `evaluate_tiered()`、`evaluate_requirements()` 或兼容性的 `evaluate_boolean()`。最终 `_compute_from_scan()` 把所有 `ACHIEVEMENTS` 评估成展示对象，并在非 partial scan 时写入 unlock 状态。

后台刷新流程在 `_start_background_scan()` 和 `_run_scan_and_update_cache()`。长扫描会发布 partial snapshot，让 dashboard 不必等完整扫描结束才显示进度；最终结果会写入 `scan_snapshot.json`，状态信息由 `/scan-status` 返回。

## 推荐阅读顺序

建议先读 `README.md`，建立插件用途、API 列表和运行方式的整体印象。第二步读 `dashboard/manifest.json`，确认插件如何注册到 Dashboard，以及前端和后端入口文件分别是什么。

第三步读 `dashboard/plugin_api.py` 的结构，不必一开始逐行看完整成就列表。可以先定位这些函数：`evaluate_all()`、`scan_sessions()`、`analyze_messages()`、`aggregate_stats()`、`evaluate_definition()`、`_compute_from_scan()`，这几处串起来就是完整后端主链路。然后再回头看 `ACHIEVEMENTS`，理解每个成就只是对聚合指标的声明式配置。

第四步读 `tests/test_achievement_engine.py`。测试覆盖了最核心的行为边界：工具调用如何计数、tier 如何取最高满足层级、secret 成就如何隐藏、多条件成就如何要求全部满足、模型/Provider 如何聚合、本地/open-weight 模型如何判断、配置活动如何避免误报。它比前端构建产物更适合作为学习后端逻辑的入口。

如果需要了解 UI，只能从 `dashboard/dist/index.js`、`dashboard/dist/style.css` 看构建后的实现。根据当前片段推断，这里没有保留前端源码目录，`dist` 更像随插件发布的打包产物，因此阅读价值低于 manifest、API 和测试。

## 常见误区

不要把这个目录理解成 Hermes 的核心成就系统框架。它是一个 Dashboard 插件，主入口由插件 manifest 和 dashboard 挂载机制驱动，核心 agent 运行不依赖它。

不要以为成就状态保存在仓库目录中。`state_path()`、`snapshot_path()`、`checkpoint_path()` 都基于 `get_hermes_home()`，实际状态位于用户 Hermes home 的 `plugins/hermes-achievements` 下。仓库里的 `plugins/hermes-achievements` 只是插件代码和静态资源。

不要把 `/achievements` 请求理解为每次都全量扫描。`evaluate_all()` 有内存缓存、磁盘 snapshot、后台扫描和 checkpoint 复用。手动 `/rescan` 才会走同步强制刷新路径。

不要忽略 secret/discovered/unlocked 三种状态。`display_achievement()` 会在 secret 状态隐藏真实名称和描述；有进度但未达阈值时通常是 discovered；满足阈值后才写入 unlock 状态。

不要把 `dashboard/dist/` 当成主要开发源。当前目录片段只显示打包后的 JS/CSS，没有源码工程结构；学习主流程应以后端 API 和测试为主。

不要随意改成就 `id`。README 明确说明成就 ID 是本地 unlock state 的键，重命名会影响已有用户状态。新增或调整成就时，应同步考虑测试、阈值、状态兼容性和 snapshot/checkpoint 行为。
