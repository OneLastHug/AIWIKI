# 目录：docs/prds/remote/channels

## 它负责什么

这个目录承载的是「设置页 → 远程连接」里 **Channels Tab** 的产品需求文档与索引。根据当前片段推断，它不是实现代码目录，而是围绕 IM 渠道接入的 PRD 集合，重点描述渠道卡片、启停、连接测试、配对授权、Agent 选择、默认模型选择，以及扩展渠道接入规则。

目录内最核心的是 `channels.md`，它把 Telegram、Lark、DingTalk、WeChat、WeCom 五个内置渠道，以及扩展渠道的交互流程拆成 F-WEBUI-12 到 F-WEBUI-21 的功能点。`README.md` 则更像索引页，用来概览文档结构和功能点状态。

## 直接子目录地图

`docs/prds/remote/channels` 下直接可见的子目录主要是各渠道名的占位目录：

- `dingtalk`
- `exwechat`
- `lark`
- `telegram`
- `tg`
- `wechat`

这些目录目前都只看到 `.gitkeep`，没有展开出的内容。结合 `channels.md` 的描述，它们更像是为后续按渠道拆分文档或素材预留的容器，而不是现阶段已经填满的知识库。

同级还有两个关键文件：

- `README.md`：渠道 PRD 索引
- `channels.md`：Channels Tab 的主说明文档

## 关键入口

真正的阅读入口是 `README.md`，它先告诉你这个目录是什么，再把你导向 `channels.md`。如果要直接进入细节，应以 `channels.md` 为主。

此外，`channels.md` 里明确提到相关联的 WebUI 文档在 `../webui/webui.md`。所以这个目录虽然是 Channels 主题，但它并不孤立，和同级的 `remote/webui` 目录是配套关系。

如果你是在找“实现入口”，文档里给出的关键入口是附录 A 的 IPC 通信链路，核心对象包括 `ChannelModalContent.tsx`、`channel.getPluginStatus.invoke()`、`channel.enablePlugin.invoke()`、`channel.pairingRequested.on()`、`acpConversation.getAvailableAgents.invoke()`、`ConfigStorage.get/set()` 等。根据当前片段推断，这些名字不是本目录文件，而是文档指向的实现坐标。

## 主流程位置

主流程都集中在 `channels.md` 正文的 F-WEBUI-12 到 F-WEBUI-21：

1. `F-WEBUI-12` 定义 Channels 页面总览、卡片结构、默认折叠与状态展示。
2. `F-WEBUI-13` 到 `F-WEBUI-17` 分别覆盖 Telegram、Lark、DingTalk、WeChat、WeCom 的接入方式。
3. `F-WEBUI-18` 负责每个渠道的 Agent 选择。
4. `F-WEBUI-19` 负责默认模型选择。
5. `F-WEBUI-20` 负责配对与授权的通用安全流程。
6. `F-WEBUI-21` 负责扩展渠道支持。

如果只看流程主线，可以把它理解成：先加载渠道状态，再展开单个渠道配置，然后完成连接测试或扫码登录，接着进入配对授权，最后再补上 Agent 和模型设置。附录 A 里把这些流程对应的 IPC 调用也列出来了，适合顺着读。

## 推荐阅读顺序

建议按这个顺序看：

1. `README.md`
2. `channels.md` 的开头说明
3. `F-WEBUI-12`，先建立页面结构认知
4. `F-WEBUI-13` 到 `F-WEBUI-17`，按渠道理解各自接入方式
5. `F-WEBUI-18` 到 `F-WEBUI-20`，看通用配置和授权流程
6. `F-WEBUI-21`，理解扩展渠道机制
7. 附录 A、B、C，用来把流程、通知和已知局限串起来

如果你还想对齐 WebUI 侧的整体设定页文档，再去看同级 `remote/webui/webui.md`，这样能把 Channels 和 WebUI 两个 Tab 的边界区分清楚。

## 常见误区

最容易弄混的一点，是把这个目录当成实现目录。实际上它主要是 PRD 和索引，真正的代码入口不在这里，而是在文档附录引用的 `ChannelModalContent.tsx` 和相关 IPC 处理链路里。

第二个误区，是忽略 `README.md` 的索引角色，直接跳进 `channels.md`。这样虽然也能读，但容易丢失功能点总览和状态标记，尤其是它把 F-WEBUI-12 到 F-WEBUI-21 的覆盖范围先总览了一遍。

第三个误区，是把这些子目录当成已经完成的细分专题。根据当前片段推断，它们目前只是占位目录，因为可见内容只有 `.gitkeep`。

第四个误区，是把 `tg` 和 `telegram` 视为两个完全不同的产品主题。仅凭当前片段看，更稳妥的理解是它们属于同一渠道域里的命名兼容或历史保留项，不能直接从目录名推导出独立语义。
