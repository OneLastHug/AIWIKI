# 目录：docs/prds/remote/webui

## 它负责什么

`docs/prds/remote/webui` 是“设置页 → 远程连接 → WebUI”这组需求文档的入口目录，定位不是运行时代码，而是产品需求与实现核对说明。它把桌面端设置页里的 WebUI 服务管理能力整理成可验收的功能清单，覆盖服务启停、启动恢复、访问地址展示、远程访问控制、用户名与密码管理、QR 码登录、状态同步，以及扩展系统向 WebUI 注册路由和静态资源的能力。

从文档内容看，这个目录服务于两个读者：一类是想理解 WebUI 设置页用户行为的产品、测试或前端开发者；另一类是需要追踪实现链路的工程读者。`README.md` 给出功能索引和工作记录，`webui.md` 才是主体 PRD。主体文档按 `F-WEBUI-01` 到 `F-WEBUI-11` 拆分功能点，每个功能点通常包含用户故事、正常流程、异常情况和验收标准，后面还补充状态矩阵、IPC 通信链路、Toast 汇总和已知局限。

它所在的上级目录 `docs/prds/remote` 同时还有 `channels` 与 `webui` 两条线：`webui` 关注远程访问服务本身，`channels` 关注远程连接中的渠道配置。根据当前片段推断，这里的 WebUI PRD 是“远程连接”设置页面的一个子模块文档，而不是完整远程连接功能的唯一来源，依据是 `webui.md` 明确写到 Channels Tab 内容见相邻目录文档。

## 直接子目录地图

`docs/prds/remote/webui` 当前没有直接子目录，只有两份直接文件：

`docs/prds/remote/webui/README.md` 是索引页。它用表格列出主体文档 `webui.md`，并汇总 11 个 WebUI 功能点的编号、名称、状态和归属模块。这个文件适合先扫一遍，快速确认本目录讲的是哪些能力，以及这些能力是否已实现。

`docs/prds/remote/webui/webui.md` 是核心文档。它详细描述“设置 → 远程连接”页面中 WebUI Tab 的全部行为，并把用户可见流程与实现约束放在一起。这里不仅有前端 UI 流程，也有主进程 IPC、服务层、配置恢复、QR token、安全校验、扩展贡献注册等后端侧信息。

相邻但不属于本目录的 `docs/prds/remote/channels` 是 Channels Tab 的需求目录。阅读 WebUI 的页面结构章节时会遇到 WebUI / Channels 双 Tab 的描述，但 Channels 细节不在本目录展开。

## 关键入口

文档入口是 `docs/prds/remote/webui/README.md`。它承担目录导航和功能总览角色，最重要的信息是 `F-WEBUI-01` 到 `F-WEBUI-11` 的清单：服务启停、配置持久化、访问地址、远程访问、用户名、密码、QR 登录、页面结构、状态同步、扩展系统 WebUI 贡献等都在这里建立编号。

主体入口是 `docs/prds/remote/webui/webui.md`。阅读时可以把它当成 WebUI 设置页的地图：前半部分按功能拆用户流程，后半部分用附录补实现链路。尤其是“附录 B：IPC 通信链路”，把渲染进程、主进程桥接、服务层三个位置串起来，是从 PRD 跳到源码的关键索引。

对应源码的前端入口主要是 `packages/desktop/src/renderer/components/settings/SettingsModal/contents/WebuiModalContent.tsx`。PRD 多处描述的 Switch、访问地址、远程访问开关、用户名/密码弹窗、QR 码区域、Toast、状态加载和事件监听，都集中映射到这个组件。设置页路由和菜单入口还会经过 `packages/desktop/src/renderer/pages/settings/WebuiSettings.tsx`、`packages/desktop/src/renderer/components/settings/SettingsModal/index.tsx`、`packages/desktop/src/renderer/components/layout/Router.tsx`、`packages/desktop/src/renderer/pages/settings/components/SettingsSider.tsx`。

对应主进程和服务侧入口主要包括 `packages/desktop/src/process/bridge/webuiBridge.ts`、`packages/desktop/src/process/utils/webuiConfig.ts`，以及文档中提到的 `WebuiService`、`webuiQR`、`AuthService` 相关实现。根据当前片段推断，桥接层负责把 `webui.getStatus`、`webui.start`、`webui.stop`、`webui.changePassword`、`webui.changeUsername`、`webui.generateQRToken` 等调用转发到服务层；依据是 `webui.md` 的 IPC 通信链路附录和源码搜索结果共同指向这些名称。

## 主流程位置

第一条主流程是 WebUI 服务启停。用户在设置页打开 WebUI 开关后，前端通过 WebUI IPC 调用启动服务，成功后更新运行态、显示访问地址，并把 `webui.desktop.enabled` 持久化；关闭时则隐藏访问地址和 QR 区域，并异步停止服务。这个流程的前端主位置在 `WebuiModalContent.tsx`，主进程桥接位置在 `webuiBridge.ts`，自动恢复和配置来源位置在 `webuiConfig.ts`，应用启动恢复入口可从 `packages/desktop/src/index.ts` 中的 `restoreDesktopWebUIFromPreferences` 继续追。

第二条主流程是远程访问控制。用户切换“允许远程访问”后，如果服务正在运行，需要停止后重新启动，因为监听地址要在本地访问与局域网访问之间切换；如果服务未运行，则只保存偏好，等下次启动生效。PRD 明确指出访问地址会随远程访问状态变化，远程访问开启时才出现 QR 登录区域。

第三条主流程是认证管理。用户名管理提供查看、复制和修改；密码管理提供初始密码展示与后续重设；修改用户名或密码后，已有 token 通过 JWT secret 轮转被动失效。这里需要注意，密码修改不要求当前密码，安全假设依赖 Electron 本地环境。前端表单与错误提示在 `WebuiModalContent.tsx`，后端校验落在文档所称的 `AuthService` 一侧。

第四条主流程是 QR 码登录。当前置条件满足“WebUI 运行中且允许远程访问”时，前端生成二维码登录链接，后端生成一次性、短有效期 token；扫码后通过 `/qr-login` 入口验证并登录。PRD 还说明 QR token 存在内存 `Map` 中，进程重启即失效。

第五条主流程是扩展贡献。扩展可以在 `manifest.contributes.webui` 中声明 API 路由或静态资源，由 `resolveWebuiContributions` 做命名空间、保留路径、路径遍历和冲突检查后注册到 WebUI 服务。这个功能不属于设置页 UI 的日常用户流程，但属于 WebUI 服务能力边界。

## 推荐阅读顺序

1. 先读 `docs/prds/remote/webui/README.md`，建立 11 个功能点的全局索引，确认本目录只讲 WebUI Tab，不展开 Channels。
2. 再读 `docs/prds/remote/webui/webui.md` 开头说明和 `F-WEBUI-09`，先理解页面结构、桌面端与非桌面端差异、WebUI / Channels 双 Tab 关系。
3. 接着读 `F-WEBUI-01` 到 `F-WEBUI-04`，掌握服务启停、持久化恢复、访问地址、远程访问切换这些基础流程。
4. 然后读 `F-WEBUI-05` 到 `F-WEBUI-08`，集中理解登录凭据和 QR 登录。
5. 最后读 `F-WEBUI-10`、`F-WEBUI-11` 和附录。附录 B 适合与源码一起看，附录 D 适合测试和评审时优先关注。

## 常见误区

第一个误区是把本目录当成源码目录。它实际是 PRD 文档目录，真正的渲染进程实现、IPC bridge 和服务实现分布在 `packages/desktop/src/renderer`、`packages/desktop/src/process` 等位置。

第二个误区是认为 WebUI 和 Channels 是同一功能。页面上它们同属“远程连接”，但 WebUI 管的是浏览器访问服务、认证和 QR 登录；Channels 管的是消息渠道或远程连接渠道配置。WebUI PRD 只在页面结构中提到 Channels，细节应去 `docs/prds/remote/channels`。

第三个误区是认为“允许远程访问”只是前端显示开关。PRD 明确说明运行中切换需要重启 WebUI 服务，因为监听地址会变化；这会带来短暂不可用，也会影响访问地址和 QR 区域显示。

第四个误区是认为启动成功、停止成功 Toast 与真实服务状态完全强一致。文档列出已知局限：启动 IPC 超时后 UI 可能乐观显示运行中，停止操作也是 fire-and-forget，Toast 出现时服务器可能仍在停止过程中。

第五个误区是把 QR 登录当成长期凭据。QR token 是短期、一次性、内存态 token，进程重启会失效，重复扫码或过期扫码都会失败。

第六个误区是忽略桌面端与非桌面端差异。PRD 指出 WebUI 服务管理区域仅在 Electron 桌面端渲染；非桌面端通过浏览器访问时不提供同样的 WebUI 服务管理入口，而是直接显示 Channels 配置内容。
