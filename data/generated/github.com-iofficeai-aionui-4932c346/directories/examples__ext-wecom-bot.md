# 目录：examples/ext-wecom-bot

## 它负责什么

`examples/ext-wecom-bot` 是一个面向 AionUI 的企业微信 Bot 扩展示例，目标不是提供完整业务，而是验证“外部渠道接入 + 加密回调 + 流式响应”这条链路是否能跑通。根据当前片段推断，它更像一个参考实现和联调样板：一方面展示如何把企业微信回调接入统一消息管道，另一方面展示 WebUI 侧如何暴露 webhook 和静态资源。

这个目录的核心价值有三点。第一，演示 WeCom Bot 模式的回调校验与加密消息处理。第二，演示消息进入后如何转成 AionUI 的统一入站消息，再交给后续处理。第三，演示当 stream 上下文不可用时，如何用 `response_url` 做一次性的兜底回复。

## 直接子目录地图

这个目录下面的直接子目录只有四个，职责边界比较清楚：

- `assets`：静态资源目录，主要放图标和展示文件。
- `channels`：渠道插件实现目录，主业务逻辑基本都在这里，尤其是企业微信消息的接入、状态管理和消息桥接。
- `webui`：WebUI 侧路由入口目录，主要承接 webhook 请求。
- `dist`：发布态镜像目录。根据 `README.md` 和目录结构判断，这里是面向扩展加载器的 dist-first 入口集合，内容与源码目录对应，用于运行时加载。

从结构上看，`channels` 和 `webui` 是两条主线，`assets` 是配套资源，`dist` 则是运行时消费的镜像层。`dist` 里也有 `assets`、`channels`、`webui`，说明它不是单独的一套逻辑，而是对上面三类入口的打包结果或发布副本。

## 关键入口

最关键的入口是 `aion-extension.json`。它定义了这个扩展的名字、图标、渠道插件和 WebUI 路由，是整个目录的注册中心。这里能看到两个最重要的挂载点：

- `channels/ext-wecom-bot-channel.js`：渠道插件入口。
- `webui/webhook.js`：Webhook API 入口。

如果只看主流程，真正需要优先读的是 `channels/ext-wecom-bot-channel.js`、`channels/state.js` 和 `webui/webhook.js`。前者负责插件生命周期、消息编解码和对外发送；后两者负责流状态、重复事件去重、`response_url` 记录以及 HTTP 请求处理。

`README.md` 也算关键入口，但它更像使用说明，不是运行时入口。它能帮助你快速确认这个例子的运行方式和 Webhook 地址格式。

## 主流程位置

主流程基本分成“注册”和“处理”两段。

第一段是扩展注册。`aion-extension.json` 把 `ext-wecom-bot` 作为一个 channel plugin 暴露出去，并把 `/ext-wecom-bot/webhook` 绑定到 `webui/webhook.js`。这说明这个例子同时包含“渠道插件”和“WebUI API”两类能力。

第二段是消息处理。`webui/webhook.js` 接收企业微信回调后，先做签名校验，再解密 payload。它对两类请求分支处理：

- `GET`：用于回调验证，解密 `echostr` 后直接返回明文。
- `POST`：用于消息事件处理，先解密 body，再判断是不是 `stream` 刷新请求。

如果是 `stream` 类型，它会从 `channels/state.js` 取当前流状态并回包；如果是普通入站消息，它会创建新的 stream，立即返回 stream 响应，然后异步调用插件的 `handleInboundMessage()` 继续处理。这一段是整个目录最核心的运行链路。

第三段在 `channels/ext-wecom-bot-channel.js`。这里实现了插件对象本身：签名校验、AES 解密、`msgtype=stream` 的加密回包、统一消息封装、以及 `sendMessage()` 的回写逻辑。`sendMessage()` 先尝试向最近的 stream 写回内容，如果没有可用 stream，就消费一次性的 `response_url` 作为兜底。

状态层在 `channels/state.js`。这里维护了三个关键存储：stream 存储、事件去重表、`response_url` 存储。也就是说，真正把“接收、回包、续流、过期清理”串起来的是这层状态文件。

## 推荐阅读顺序

1. 先看 `README.md`，快速确认这个例子的目标、启动方式和 webhook 地址。
2. 再看 `aion-extension.json`，建立“扩展如何被宿主识别”的全局视图。
3. 然后读 `webui/webhook.js`，把 HTTP 层的入口和分支流程看清楚。
4. 接着读 `channels/ext-wecom-bot-channel.js`，理解插件生命周期、消息转换和 stream 回包。
5. 最后读 `channels/state.js`，补齐状态管理、去重和过期清理这三块基础设施。

## 常见误区

- 把 `dist` 当成完全独立的代码树。根据当前片段推断，它更像发布态镜像，和源码目录是一一对应关系，主要用于运行时加载。
- 只盯着 `channels` 而忽略 `webui/webhook.js`。这个例子的入口其实在 Webhook 层，`channels` 负责的是插件逻辑，不是 HTTP 接入本身。
- 误以为 `GET` 和 `POST` 是同一条处理链。实际上 `GET` 只做回调验证，`POST` 才是消息接收与流式响应主路径。
- 忽略 `response_url` 的单次使用语义。`channels/state.js` 明确把它设计成一次性兜底，不适合当成长期可复用地址。
- 把 `state.js` 视为辅助文件。实际上它保存了 stream、去重和回调兜底三个关键状态，没有它主流程就无法闭环。
