# 目录：docs/prds/pet

## 它负责什么

`docs/prds/pet` 是桌面宠物功能的 PRD 文档槽位。按 `docs/prds` 的组织方式看，`assistants`、`previews`、`teams`、`workspaces` 等目录分别承载对应产品模块的需求说明；因此 `pet` 目录应当对应 Desktop Pet / 桌宠能力的产品需求文档。但当前片段中，`docs/prds/pet/README.md` 是空文件，目录内也没有其他文档，所以它现在更像一个预留入口，而不是已经成型的 PRD 集合。

根据当前片段推断，这个目录要描述的功能不是普通页面，而是 Electron 桌面端中的一个独立桌宠系统：它有单独的 renderer 页面、preload bridge、主进程窗口管理、设置页开关、尺寸配置、勿扰模式、工具调用确认气泡等能力。相关实现主要分布在 `packages/desktop/src` 下，而 `docs/prds/pet` 目前只是文档侧的归档位置。

换句话说，读这个目录时要先意识到：这里不是功能源码，也不是完整规格书；它是 “桌宠产品需求应该放在这里” 的目录。真正理解功能，需要把它和 `packages/desktop/src/index.ts`、`packages/desktop/src/process/pet`、`packages/desktop/src/renderer/pet`、`packages/desktop/src/preload/petPreload.ts`、`packages/desktop/src/preload/petHitPreload.ts`、`packages/desktop/src/preload/petConfirmPreload.ts`、`packages/desktop/src/renderer/pages/settings/PetSettings.tsx` 一起看。

## 直接子目录地图

当前 `docs/prds/pet` 没有直接子目录，只有一个空的 `README.md`。

在 `docs/prds` 这一层，`pet` 与其他产品需求目录并列，包括 `assistants`、`conversations`、`previews`、`remote`、`settings`、`teams`、`workspaces`。这说明 `pet` 在文档分类上被视为一个独立产品模块，而不是 `settings` 或 `conversations` 的附属说明。

目录地图可以概括为：

`docs/prds/pet`：桌宠 PRD 的预留目录。当前没有正文内容。

`docs/prds/pet/README.md`：预期的主说明入口，但当前为空。根据当前片段推断，后续如果补文档，应从这里描述桌宠的目标、开关、状态、交互、确认气泡、设置项和主进程生命周期。

## 关键入口

文档入口是 `docs/prds/pet/README.md`，但它目前没有内容，所以阅读时不能只停留在该文件。为了建立地图式理解，需要顺着功能入口看实现侧的几个关键位置。

构建入口在 `packages/desktop/electron.vite.config.ts`。这里配置了桌宠相关的 preload 入口：`petPreload`、`petHitPreload`、`petConfirmPreload`，也配置了 renderer 页面入口：`pet`、`pet-hit`、`pet-confirm`。这说明桌宠不是单一窗口，而是至少拆成展示层、命中/交互层、确认气泡层三类页面或窗口。

启动入口在 `packages/desktop/src/index.ts`。其中桌宠初始化逻辑会读取 `pet.enabled` 和 `pet.confirmEnabled`，然后动态导入 `./process/pet/petManager`，调用 `setPetConfirmEnabled` 和 `createPetWindow`。这条链路说明主窗口启动后，桌宠是延迟初始化的桌面端附属能力，不应阻塞主应用启动。

设置入口在 `packages/desktop/src/renderer/pages/settings/PetSettings.tsx`。这里读取和写入 `pet.enabled`、`pet.size`、`pet.dnd`、`pet.confirmEnabled`，并通过 `systemSettings` IPC provider 同步到主进程。用户能感知的桌宠配置，大概率都从这里进入。

IPC 声明入口在 `packages/desktop/src/common/adapter/ipcBridge.ts`，其中有 `getPetEnabled`、`setPetEnabled`、`getPetSize`、`setPetSize`、`getPetDnd`、`setPetDnd`、`getPetConfirmEnabled`、`setPetConfirmEnabled`。配置键类型和持久化字段则散落在 `packages/desktop/src/common/config/configKeys.ts`、`packages/desktop/src/common/config/storage.ts`、`packages/desktop/src/common/config/configMigration.ts`。

## 主流程位置

桌宠主流程可以按 “配置读取、窗口创建、渲染展示、交互命中、事件反馈、确认气泡” 来理解。

第一段是启动创建流程。`packages/desktop/src/index.ts` 在应用启动后的延迟阶段读取 `pet.enabled`。如果开关为 true，则读取 `pet.confirmEnabled`，再从 `packages/desktop/src/process/pet/petManager` 创建桌宠窗口。根据当前片段推断，`petManager` 是主进程中管理桌宠窗口生命周期、位置、尺寸、可见性和事件分发的核心模块，依据是 `index.ts` 对 `createPetWindow`、`destroyPetWindow`、`setPetConfirmEnabled` 的动态导入。

第二段是渲染流程。`packages/desktop/src/renderer/pet/pet.html` 内部加载 `../pet-states/idle.svg`，并执行 `packages/desktop/src/renderer/pet/petRenderer.ts`。这说明桌宠的视觉状态很可能由一组 SVG 状态资源驱动，默认状态是 `idle.svg`。`petPreload.ts` 暴露 `petAPI`，接收 `pet:state-changed`、`pet:eye-move`、`pet:resize` 等事件，说明主进程会推送状态变化、眼睛移动和尺寸变化给渲染端。

第三段是交互命中流程。`packages/desktop/src/preload/petHitPreload.ts` 暴露 `petHitAPI`，把拖拽开始、拖拽结束、点击、右键菜单、鼠标穿透设置等动作发送给主进程。`packages/desktop/src/renderer/pet/petHitRenderer.ts` 是命中层 renderer，负责把用户点击、拖拽、右键等原始交互整理成 IPC 消息。

第四段是工具调用确认流程。`packages/desktop/src/preload/petConfirmPreload.ts` 暴露 `petConfirmAPI`，监听 `pet:confirm-add`、`pet:confirm-update`、`pet:confirm-remove`、`pet:confirm-theme`，并通过 `pet:confirm-respond` 回传用户选择。根据当前片段推断，桌宠可作为工具调用权限确认的气泡入口；该能力由 `pet.confirmEnabled` 控制。

第五段是 Agent 或运行事件反馈。`packages/desktop/src/common/adapter/main.ts` 中有 `setPetNotifyHook` 和 `petNotifyHook`，注释显示会在 hook 存在时通知 pet。结合 `pet.dnd` 字段说明，桌宠可能会根据 AI 事件进入不同状态，而勿扰模式会让它保持 idle 或忽略事件。

## 推荐阅读顺序

建议先读 `docs/prds/pet/README.md`，确认当前文档为空，避免误以为需求细节已经写在这里。

第二步读 `packages/desktop/electron.vite.config.ts` 中的 `pet`、`pet-hit`、`pet-confirm` 和三个 preload 配置，先建立桌宠由多个 Electron 入口组成的结构感。

第三步读 `packages/desktop/src/index.ts` 中桌宠初始化和销毁相关代码，理解桌宠什么时候被创建、由哪个主进程模块接管。

第四步读 `packages/desktop/src/renderer/pages/settings/PetSettings.tsx`，把用户可操作的配置项列出来：启用、大小、勿扰、确认气泡。

第五步读 `packages/desktop/src/common/adapter/ipcBridge.ts`、`packages/desktop/src/common/config/configKeys.ts`、`packages/desktop/src/common/config/storage.ts`，确认这些设置如何跨 renderer / main 同步与持久化。

第六步读 `packages/desktop/src/renderer/pet` 和 `packages/desktop/src/preload` 下的 pet 相关文件，理解展示窗口、命中窗口、确认窗口分别负责什么。最后再进入 `packages/desktop/src/process/pet`，看主进程如何把这些窗口和事件串起来。

## 常见误区

第一个误区是把 `docs/prds/pet` 当成完整 PRD。当前目录只有空 `README.md`，没有需求正文；它只能作为文档入口定位，不能作为功能事实的唯一依据。

第二个误区是以为桌宠只是设置页里的一个开关。实际从入口配置看，它涉及 Electron 多窗口、多 preload、主进程生命周期、renderer 状态资源和 IPC 通信，复杂度高于普通设置项。

第三个误区是把 `pet`、`pet-hit`、`pet-confirm` 混为一个页面。根据配置和 preload 命名推断，三者职责不同：`pet` 负责视觉展示，`pet-hit` 负责鼠标命中与拖拽点击，`pet-confirm` 负责确认气泡。阅读或改动时要分清窗口边界。

第四个误区是只看 renderer，不看主进程。桌宠窗口创建、销毁、鼠标穿透、拖拽、上下文菜单、确认气泡开关等都需要主进程参与；核心流程应从 `packages/desktop/src/index.ts` 和 `packages/desktop/src/process/pet` 入手。

第五个误区是忽略配置键的默认值和迁移。`pet.enabled`、`pet.size`、`pet.dnd`、`pet.confirmEnabled` 同时出现在设置页、本地配置类型、存储结构和迁移配置中。若后续补 PRD 或实现变更，需要同步考虑默认行为、历史配置兼容和 i18n 文案。
