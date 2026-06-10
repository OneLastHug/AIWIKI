# 目录：docs/prds/previews

## 它负责什么

`docs/prds/previews` 是 `docs/prds` 下的一个 PRD 文档分区，用来承载“预览类能力”或“preview 功能形态”的产品需求说明。从当前仓库片段看，它不是运行时代码目录，也不是某个前端页面、Electron 进程、IPC 模块或测试模块的实现位置，而是需求文档树的一部分。

这个目录目前很轻量：目标目录本身存在，但直接文件只看到 `docs/prds/previews/README.md`，没有发现更深层的功能子目录或成组的 PRD 文件。因此，它更像是一个预留的 PRD 分类入口，而不是已经展开的大型需求集合。根据当前片段推断，`previews` 的角色是和 `docs/prds/assistants`、`docs/prds/conversations`、`docs/prds/settings`、`docs/prds/teams`、`docs/prds/workspaces` 等并列的产品域分类，用于把“预览”相关的需求从会话、设置、团队、工作区等主线产品域中拆出来管理。

需要注意，这里的“previews”更可能指产品层面的预览、草案、实验性展示或功能预览需求，而不是构建产物里的 preview server，也不是 UI 组件库里的预览组件。当前片段没有足够证据证明它对应某个具体业务模块，所以阅读时应先把它当作 PRD 索引或占位目录看待。

## 直接子目录地图

当前 `docs/prds/previews` 下没有发现直接子目录。

已确认的直接内容是：

- `docs/prds/previews/README.md`：该目录的唯一可见入口文件。由于目录下没有其他 PRD 文件或子目录，它承担了该分区的说明、索引或占位职责。当前片段没有展示到有效 Markdown 标题，因此不能确认它是否已经写入完整需求内容；只能确定它是这个目录的关键入口。

从邻近结构看，`docs/prds` 是按产品域拆分的文档根目录，直接或近邻分区包括：

- `docs/prds/assistants`：助手相关 PRD。
- `docs/prds/conversations`：会话相关 PRD，下面继续按 `acp`、`aionrs`、`custom`、`gemini`、`remote`、`other` 等方向拆分。
- `docs/prds/settings`：设置相关 PRD，下面有 `about`、`display`、`llm_providers`、`skills`、`system` 等子域。
- `docs/prds/remote`：远程能力相关 PRD，下面有 `channels`、`webui` 等子域。
- `docs/prds/pet`、`docs/prds/teams`、`docs/prds/workspaces`：分别承载对应产品域的需求说明。

因此，`previews` 在地图上的位置是一个与主产品域并列的 PRD 分区，而不是嵌套在某个具体功能域里的附属说明。

## 关键入口

这个目录的关键入口只有 `docs/prds/previews/README.md`。

阅读或维护该目录时，应先从这个 README 开始，因为它是当前唯一的本地入口。如果后续新增预览相关需求，合理的组织方式通常是：先在 README 中说明该分区的边界、适用场景、当前需求列表和状态，再按功能主题拆出子目录或独立 Markdown 文件。但根据当前片段，尚未看到这些拆分已经发生。

如果要追踪它与整个 PRD 体系的关系，入口应上移到 `docs/prds`。`docs/prds` 下面的目录命名显示，仓库把需求文档按产品域组织，而非按实现层组织。也就是说，`docs/prds/previews` 的入口不是某个 `packages/desktop` 下的组件文件，而是 `docs/prds` 文档体系里的分类入口。

## 主流程位置

从当前片段看，`docs/prds/previews` 自身不包含可执行主流程。它没有发现页面入口、路由入口、服务入口、IPC 入口、构建脚本或测试入口；也没有看到多文件之间形成的需求流转链路。这个目录的“主流程”主要是文档阅读流程，而不是代码调用流程。

根据当前片段推断，它在仓库中的主流程位置可以理解为：

1. 产品需求被归入 `docs/prds`。
2. 如果需求属于预览能力或 preview 形态，就放入 `docs/prds/previews`。
3. 当前阶段通过 `docs/prds/previews/README.md` 作为唯一入口承载说明。
4. 真正的实现位置应再根据 README 或后续 PRD 内容，跳转到对应产品域的代码目录，例如桌面端 renderer、process、preload、common 配置、测试目录等。但当前目标目录没有提供足够证据指向具体实现路径。

换句话说，`docs/prds/previews` 是需求侧的主流程节点，不是实现侧的主流程节点。它负责帮助读者理解“预览相关需求在哪里登记、如何归类”，而不是告诉运行时代码如何执行。

## 推荐阅读顺序

建议按下面顺序阅读：

1. 先看 `docs/prds/previews/README.md`，确认这个分区是否已有说明、需求索引、状态标记或未来规划。当前目录只有这一个入口，不能跳过。
2. 再看 `docs/prds` 的同级目录结构，尤其是 `docs/prds/conversations`、`docs/prds/settings`、`docs/prds/remote`、`docs/prds/workspaces`。这些目录能帮助判断 `previews` 是独立产品域，还是未来会和会话、远程、设置等功能交叉。
3. 如果 README 中提到具体功能名称，再回到对应 PRD 分区寻找更完整需求。例如涉及会话预览，就优先看 `docs/prds/conversations`；涉及远程 Web UI 预览，就优先看 `docs/prds/remote/webui`；涉及设置页中的预览开关，就看 `docs/prds/settings` 相关子目录。
4. 最后再进入实现代码。不要一开始就从 `packages/desktop` 查代码，因为当前目录本身没有暴露实现锚点，直接跳代码容易把“preview”误匹配到无关的 UI 预览、构建预览或临时调试逻辑。

## 常见误区

第一个误区是把 `docs/prds/previews` 当成源码模块。它位于 `docs/prds` 下，当前只看到 README，职责是产品需求说明，不参与编译、运行或测试。

第二个误区是把它理解成前端页面预览目录。仓库里真正的 UI、进程和 IPC 实现通常会分布在 `packages/desktop/src/renderer`、`packages/desktop/src/process`、`packages/desktop/src/preload` 等位置；`docs/prds/previews` 不是这些实现目录的镜像。

第三个误区是认为它已经有完整的子系统结构。当前没有发现直接子目录，也没有看到成组 PRD 文件。根据当前片段，它更接近轻量入口或预留分类，不应过度推断它已经覆盖了完整 preview 功能族。

第四个误区是孤立阅读这个目录。因为它信息量很少，必须结合 `docs/prds` 的同级分区来理解：`previews` 是产品需求地图上的一个节点，和 `assistants`、`conversations`、`settings`、`remote` 等并列。只有当 README 或后续文件写明具体功能边界后，才能进一步映射到代码主流程。
