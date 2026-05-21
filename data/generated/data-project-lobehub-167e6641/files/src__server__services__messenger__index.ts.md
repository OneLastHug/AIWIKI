# 文件：src/server/services/messenger/index.ts

## 文件职责
这个文件位于 `src/server/services/messenger`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
export type { ConsumedLinkTokenMarker, LinkTokenPayload } from './linkTokenStore';
export {
export { getMessengerRouter, MessengerRouter } from './MessengerRouter';
export { messengerPlatformRegistry } from './platforms';
export { MessengerDiscordBinder } from './platforms/discord';
export { MessengerSlackBinder } from './platforms/slack';
export { MessengerTelegramBinder } from './platforms/telegram';
export type { MessengerPlatformBinder } from './types';
```

## 主要对外内容
```text
未在节选中发现明显导出的类型、函数或组件。
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
export type { ConsumedLinkTokenMarker, LinkTokenPayload } from './linkTokenStore';
export {
  consumeLinkToken,
  issueLinkToken,
  peekConsumedLinkToken,
  peekLinkToken,
} from './linkTokenStore';
export { getMessengerRouter, MessengerRouter } from './MessengerRouter';
export { messengerPlatformRegistry } from './platforms';
export { MessengerDiscordBinder } from './platforms/discord';
export { MessengerSlackBinder } from './platforms/slack';
export { MessengerTelegramBinder } from './platforms/telegram';
export type { MessengerPlatformBinder } from './types';

```
