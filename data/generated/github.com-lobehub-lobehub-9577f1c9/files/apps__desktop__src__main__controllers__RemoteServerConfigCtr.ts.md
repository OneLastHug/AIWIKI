# 文件：apps/desktop/src/main/controllers/RemoteServerConfigCtr.ts

## 它负责什么

`RemoteServerConfigCtr.ts` 是桌面端 Electron main process 里的远程服务器配置控制器，默认导出 `RemoteServerConfigCtr` 类。它继承 `ControllerModule`，并通过：

```ts
static override readonly groupName = 'remoteServer';
```

把自己的 IPC 分组命名为 `remoteServer`。因此 renderer 侧可以通过类似 `ensureElectronIpc().remoteServer.getRemoteServerConfig()` 的方式调用它暴露的 `@IpcMethod()` 方法。

这个文件的职责不是单一的“配置读写”，而是围绕桌面端远程同步登录态的一整套 main 侧能力：

1. 管理 `dataSyncConfig`：读取、写入、清空远程同步配置。
2. 兼容旧配置：把历史的 `storageMode: 'local'` 迁移成现在的 `storageMode: 'cloud'`。
3. 管理 OIDC token：保存、读取、解密、清理 access token 和 refresh token。
4. 刷新 token：使用 refresh token 请求远端 `/oidc/token`，并保存新的 token。
5. 判断远程服务是否可用：区分官方云端 `cloud` 和自托管 `selfHost`。
6. 广播配置变化：通知所有窗口 `remoteServerConfigUpdated`。
7. 为订阅/商业功能 webview 注入 `Oidc-Auth` 请求头。

它处在 Electron main 侧，是 renderer 与本地安全存储、远端 OIDC、gateway 连接之间的中间层。

## 关键组成

### imports

文件开头的 import 可以分成几类理解：

```ts
import querystring from 'node:querystring';
import { URL } from 'node:url';
```

这两个 Node 内置模块用于构造 URL 和 `application/x-www-form-urlencoded` 请求体。token 刷新请求里会用 `querystring.stringify()` 生成 OIDC token endpoint 所需的表单格式。

```ts
import type { DataSyncConfig } from '@lobechat/electron-client-ipc';
```

`DataSyncConfig` 是 IPC 共享类型。根据仓库中的类型定义，它大致是：

```ts
export type StorageMode = 'cloud' | 'selfHost';

export interface DataSyncConfig {
  active?: boolean;
  remoteServerUrl?: string;
  storageMode: StorageMode;
}
```

也就是说，桌面端远程同步目前只支持官方云端和自托管两种模式。

```ts
import { safeStorage, session as electronSession } from 'electron';
```

`safeStorage` 用于加密保存 token；`electronSession` 用于获取 webview partition session，并注册请求拦截器。

```ts
import { OFFICIAL_CLOUD_SERVER } from '@/const/env';
import GatewayConnectionService from '@/services/gatewayConnectionSrv';
import { appendVercelCookie } from '@/utils/http-headers';
import { createLogger } from '@/utils/logger';
import { netFetch } from '@/utils/net-fetch';
```

这些是 main 侧基础设施：

- `OFFICIAL_CLOUD_SERVER`：官方云端服务地址。
- `GatewayConnectionService`：设备网关连接服务，token 清理时会断开 gateway。
- `appendVercelCookie`：给请求附加 Vercel 相关 cookie。
- `createLogger`：创建日志器。
- `netFetch`：基于 Electron 网络栈的 fetch，适合桌面端系统证书/代理场景。

```ts
import { ControllerModule, IpcMethod } from './index';
```

这是 desktop controller 的通用基类和 IPC 方法装饰器。被 `@IpcMethod()` 标记的方法会暴露给 renderer。

### 非重试错误分类

文件顶部定义了两组错误：

```ts
const NON_RETRYABLE_OIDC_ERRORS = [
  'invalid_grant',
  'invalid_client',
  'unauthorized_client',
  'access_denied',
  'invalid_scope',
];
```

这些是 OIDC 层面的不可重试错误。比如 `invalid_grant` 通常意味着 refresh token 已失效、过期或被撤销，继续重试没有意义。

```ts
const DETERMINISTIC_FAILURES = [
  'no refresh token available',
  'remote server is not active or configured',
  'missing tokens in refresh response',
];
```

这些是本地状态或确定性返回导致的问题，也不是靠重试能解决的。

`isNonRetryableError(error?: string)` 会把错误转小写，然后检查是否包含上述错误码或错误文本。这个判断被 `AuthCtr` 等上游调用，用来决定是否清 token、断开登录态、要求用户重新授权。

### 配置规范化：normalizeConfig

```ts
private normalizeConfig = (config: DataSyncConfig): DataSyncConfig => {
  if ((config.storageMode as string) !== 'local') return config;

  const nextConfig: DataSyncConfig = {
    ...config,
    remoteServerUrl: config.remoteServerUrl || OFFICIAL_CLOUD_SERVER,
    storageMode: 'cloud',
  };

  this.app.storeManager.set('dataSyncConfig', nextConfig);

  return nextConfig;
};
```

这个方法是兼容历史数据的关键。当前类型里 `storageMode` 只有 `'cloud' | 'selfHost'`，但旧版本可能存过 `'local'`。如果读到旧值，它会：

1. 把 `storageMode` 改成 `'cloud'`。
2. 如果没有 `remoteServerUrl`，补成 `OFFICIAL_CLOUD_SERVER`。
3. 立即写回 `storeManager`。
4. 返回规范化后的配置。

这里用了 `(config.storageMode as string)`，说明作者知道类型系统里已经没有 `'local'`，但运行时持久化数据可能仍然存在旧值。

### IPC 方法：getRemoteServerConfig

```ts
@IpcMethod()
async getRemoteServerConfig()
```

读取 `storeManager.get('dataSyncConfig')`，经过 `normalizeConfig()` 后返回。renderer 侧的 `remoteServerService.getRemoteServerConfig()` 最终会调到这里。

它是远程同步配置的主要读入口。Zustand store 里的 `useDataSyncConfig()` 使用 SWR 拉取这个 IPC 方法，并把返回值放到 `dataSyncConfig` 状态里。

### 配置可用性判断：isRemoteServerConfigured

```ts
async isRemoteServerConfigured(config?: DataSyncConfig): Promise<boolean>
```

这个方法没有 `@IpcMethod()`，主要给 main process 内部其他 controller/service 用。

判断逻辑是：

1. 如果没传 config，就调用 `getRemoteServerConfig()` 获取当前配置。
2. `active` 必须为真。
3. 如果是 `selfHost`，还必须有合法的 `remoteServerUrl`。
4. 如果是 `cloud`，不要求 `remoteServerUrl`，因为会使用 `OFFICIAL_CLOUD_SERVER`。

自托管 URL 校验由 `isValidSelfHostRemoteUrl()` 完成，只接受 `http:` 或 `https:`。

### IPC 方法：setRemoteServerConfig

```ts
@IpcMethod()
async setRemoteServerConfig(config: Partial<DataSyncConfig>)
```

这个方法用于更新远程同步配置。它会：

1. 读取旧配置 `prev`。
2. 合并 `{ ...prev, ...config }`。
3. 调用 `normalizeConfig()` 兼容旧值。
4. 写入 `storeManager.set('dataSyncConfig', merged)`。
5. 广播 `remoteServerConfigUpdated`。
6. 返回 `true`。

注意它接受的是 `Partial<DataSyncConfig>`，所以调用方可以只传 `{ active: false }` 或 `{ active: true }`。例如授权成功后，`AuthCtr` 会调用 `setRemoteServerConfig({ active: true })` 激活远程服务。

### IPC 方法：clearRemoteServerConfig

```ts
@IpcMethod()
async clearRemoteServerConfig()
```

这是断开远程同步时更彻底的清理入口。它会：

1. 把 `dataSyncConfig` 重置为 `{ active: false, storageMode: 'cloud' }`。
2. 调用 `clearTokens()` 删除 token。
3. 广播 `remoteServerConfigUpdated`。
4. 返回 `true`。

renderer 侧断开远程同步时，store action 明确使用 `clearRemoteServerConfig()`，而不是仅仅 `setRemoteServerConfig({ active: false })`，因为后者不会清除加密 token。

### token 内存与持久化字段

类里维护了几组私有字段：

```ts
private readonly encryptedTokensKey = 'encryptedTokens';

private encryptedAccessToken?: string;
private encryptedRefreshToken?: string;

private tokenExpiresAt?: number;
private lastRefreshAt?: number;

private refreshPromise: Promise<{ error?: string; success: boolean }> | null = null;
```

含义分别是：

- `encryptedTokensKey`：写入 electron-store 的 key。
- `encryptedAccessToken` / `encryptedRefreshToken`：内存中的加密 token，或者在 `safeStorage` 不可用时的明文 token。
- `tokenExpiresAt`：access token 过期时间，毫秒时间戳。
- `lastRefreshAt`：最近一次保存/刷新 token 的时间。
- `refreshPromise`：当前正在进行的刷新请求，用于合并并发刷新。

对应的 store 类型里也能看到：

```ts
encryptedTokens: {
  accessToken?: string;
  expiresAt?: number;
  lastRefreshAt?: number;
  refreshToken?: string;
};
```

### saveTokens

```ts
async saveTokens(accessToken: string, refreshToken: string, expiresIn?: number)
```

用于保存新 token，授权换 token 和 refresh token 成功后都会调用。

流程是：

1. 如果传了 `expiresIn`，计算 `tokenExpiresAt = Date.now() + expiresIn * 1000`。
2. 设置 `lastRefreshAt = Date.now()`。
3. 如果 `safeStorage.isEncryptionAvailable()` 为假，就直接把 token 存进内存和 store。
4. 如果 `safeStorage` 可用，则：
   - `safeStorage.encryptString(accessToken)`
   - 转成 base64 字符串保存。
   - refresh token 同样处理。
5. 写入 `this.app.storeManager.set('encryptedTokens', {...})`。

这里的命名是 `encryptedAccessToken`，但在 `safeStorage` 不可用时保存的是原始 token。代码也用日志提示了这个安全风险。

### getAccessToken / getRefreshToken

这两个方法结构几乎一样：

1. 如果内存里没有 token，先 `loadTokensFromStore()`。
2. 如果还是没有，返回 `null`。
3. 如果 `safeStorage` 不可用，直接返回保存的字符串。
4. 如果可用，将 base64 解码成 Buffer，再 `safeStorage.decryptString()`。
5. 解密失败则记录错误并返回 `null`。

`getAccessToken()` 被 gateway、webview 请求头注入、登录态检查等流程使用；`getRefreshToken()` 主要用于 `performTokenRefresh()`。

### clearTokens

```ts
async clearTokens()
```

清理 token 的动作包括：

1. 清空内存字段：
   - `encryptedAccessToken`
   - `encryptedRefreshToken`
   - `tokenExpiresAt`
2. 删除持久化 store 中的 `encryptedTokens`。
3. 获取 `GatewayConnectionService`，如果存在则调用 `disconnect()`。

所以 token 清理不仅影响远程同步登录态，也会断开依赖 token 的 gateway 连接。

### token 过期判断

```ts
getTokenExpiresAt(): number | undefined
```

返回当前 token 过期时间。

```ts
isTokenExpiringSoon(bufferTimeMs: number = 24 * 60 * 60 * 1000): boolean
```

判断 token 是否已经进入“快过期窗口”。默认 buffer 是 1 天。逻辑是：

```ts
const bufferTime = this.tokenExpiresAt - bufferTimeMs;
return Date.now() >= bufferTime;
```

如果没有 `tokenExpiresAt`，返回 `false`。也就是说，没有过期时间时不会主动判定为“快过期”。

### refreshAccessToken / performTokenRefresh

`refreshAccessToken()` 是公开的刷新入口：

```ts
async refreshAccessToken(): Promise<{ error?: string; success: boolean }>
```

它的一个重要设计是并发合并：

```ts
if (this.refreshPromise) {
  return this.refreshPromise;
}
```

如果已有刷新正在执行，后续调用直接复用同一个 promise，避免同时发多个 refresh 请求。

真正的刷新逻辑在 `performTokenRefresh()`：

1. 获取当前 `DataSyncConfig`。
2. 调用 `isRemoteServerConfigured(config)`，未启用或配置不完整则返回失败。
3. 调用 `getRefreshToken()`，没有 refresh token 则返回失败。
4. 通过 `getRemoteServerUrl(config)` 得到服务地址。
5. 构造 token endpoint：

   ```ts
   new URL('/oidc/token', remoteUrl)
   ```

6. 构造 form body：

   ```ts
   client_id=lobehub-desktop
   grant_type=refresh_token
   refresh_token=<refreshToken>
   ```

7. 设置 `Content-Type: application/x-www-form-urlencoded`。
8. 调用 `appendVercelCookie(headers)`。
9. 使用 `netFetch()` 发送 POST 请求。
10. 如果响应失败，尝试解析 JSON 错误并返回 `{ success: false, error }`。
11. 如果响应成功，要求必须有 `access_token` 和 `refresh_token`。
12. 调用 `saveTokens()` 保存新 token。
13. 返回 `{ success: true }`。

文件中的注释特别强调：这里不做自动重试。原因是 refresh token rotation 场景下，服务端收到 refresh 请求后旧 refresh token 可能立即被消费；如果客户端因为网络问题没收到响应又重发，可能触发 token reuse detection，导致整组授权被撤销。因此这里宁愿等待下一轮刷新，也不在同一次调用中盲目重试。

### afterAppReady

```ts
afterAppReady() {
  this.loadTokensFromStore();
}
```

controller 初始化后，从持久化 store 加载 token 到内存。它是 Electron controller 生命周期的一部分，由 controller 注册/应用启动流程调用。

### getRemoteServerUrl

```ts
async getRemoteServerUrl(config?: DataSyncConfig)
```

返回实际使用的远程服务地址：

- `storageMode === 'cloud'`：返回 `OFFICIAL_CLOUD_SERVER`。
- `storageMode === 'selfHost'`：返回 `dataConfig.remoteServerUrl`。

注意返回值在类型上可能是 `string | undefined`，因为自托管模式如果配置不完整，`remoteServerUrl` 可能不存在。不过正常调用前通常会经过 `isRemoteServerConfigured()`。

### setupSubscriptionWebviewSession

```ts
@IpcMethod()
async setupSubscriptionWebviewSession(params: { partition: string })
```

这个方法给订阅/商业功能使用的 webview session 注册请求拦截器。

流程是：

1. 从参数拿到 `partition`。
2. `electronSession.fromPartition(partition)` 获取对应 session。
3. 注册 `session.webRequest.onBeforeSendHeaders()`。
4. 只匹配：

   ```ts
   [URL已移除]
   ```

5. 每次请求前调用 `getAccessToken()`。
6. 如果有 token，给请求头加：

   ```ts
   Oidc-Auth: <accessToken>
   ```

7. 返回 `{ success: true }`。

renderer 侧 `SubscriptionIframeWrapper` 会调用 `remoteServerService.setupSubscriptionWebviewSession(PARTITION_ID)`，然后再渲染 webview。这样官方域名下的订阅页面可以拿到桌面端 OIDC 登录态。

## 上下游关系

### 向上暴露给 renderer 的 IPC

这个 controller 在 `apps/desktop/src/main/controllers/registry.ts` 中被注册：

```ts
RemoteServerConfigCtr,
```

因为它的 `groupName` 是 `remoteServer`，所以 renderer 侧通过 `ensureElectronIpc().remoteServer.*` 调用。对应封装在：

```text
src/services/electron/remoteServer.ts
```

主要方法映射是：

- `remoteServerService.getRemoteServerConfig()`
  - 调用 `remoteServer.getRemoteServerConfig()`
- `remoteServerService.setRemoteServerConfig(config)`
  - 调用 `remoteServer.setRemoteServerConfig(config)`
- `remoteServerService.clearRemoteServerConfig()`
  - 调用 `remoteServer.clearRemoteServerConfig()`
- `remoteServerService.setupSubscriptionWebviewSession(partition)`
  - 调用 `remoteServer.setupSubscriptionWebviewSession({ partition })`

renderer 的 Zustand action 位于：

```text
src/store/electron/actions/sync.ts
```

其中：

- `connectRemoteServer(values)` 会先写配置、再请求授权。
- `disconnectRemoteServer()` 会调用 `clearRemoteServerConfig()`，并重置用户数据 store。
- `useDataSyncConfig()` 使用 SWR 读取当前配置。

### 配置更新广播

`setRemoteServerConfig()` 和 `clearRemoteServerConfig()` 都会调用：

```ts
this.app.browserManager.broadcastToAllWindows('remoteServerConfigUpdated', undefined);
```

renderer 侧在：

```text
src/layout/GlobalProvider/SWRMutateInitializer.desktop.tsx
```

监听 `remoteServerConfigUpdated`，收到后触发 SWR 全局 revalidate。这样 main 侧配置变化可以反向推动 renderer 侧刷新状态。

事件类型定义在：

```text
packages/electron-client-ipc/src/events/remoteServer.ts
```

### AuthCtr 对它的依赖

`AuthCtr` 是授权流程的上游调用者，也是 token 刷新的重要协作者。它会通过：

```ts
this.app.getController(RemoteServerConfigCtr)
```

拿到当前 controller。

典型关系包括：

- 授权成功后调用 `saveTokens()` 保存 token。
- 授权成功后调用 `setRemoteServerConfig({ active: true })` 激活远程同步。
- 自动刷新 timer 中调用 `isTokenExpiringSoon()` 和 `refreshAccessToken()`。
- 刷新失败后调用 `isNonRetryableError()` 判断是否清 token。
- 非重试错误时调用 `clearTokens()` 和 `setRemoteServerConfig({ active: false })`。
- 启动或 app 激活时检查 token 是否需要主动刷新。

因此，`AuthCtr` 更像是“授权流程编排者”，而 `RemoteServerConfigCtr` 是“配置与 token 状态持有者”。

### GatewayConnectionCtr / GatewayConnectionService 对它的依赖

`GatewayConnectionCtr` 在 `afterAppReady()` 中把 token provider 和 token refresher 注入到 gateway service：

```ts
srv.setTokenProvider(() => this.remoteServerConfigCtr.getAccessToken());
srv.setTokenRefresher(() => this.remoteServerConfigCtr.refreshAccessToken());
```

这说明 gateway 连接需要 access token，并且遇到 token 问题时可以委托这里刷新。

`clearTokens()` 还会主动断开 `GatewayConnectionService`。所以远程登录态和 gateway 连接是绑定的：token 不存在时，gateway 不能继续保持连接。

### RemoteServerSyncCtr 等同步逻辑

仓库中还有：

```text
apps/desktop/src/main/controllers/RemoteServerSyncCtr.ts
```

它也引用 `RemoteServerConfigCtr`。根据当前片段推断，它应当负责具体数据同步请求，而本文件负责提供同步前所需的服务地址、配置状态和 token。依据是该文件名、引用关系，以及 `RemoteServerConfigCtr` 中暴露的 `getRemoteServerUrl()`、`getAccessToken()` 这类底层能力。

### Browser / BrowserManager 的关系

搜索结果显示：

```text
apps/desktop/src/main/core/browser/Browser.ts
apps/desktop/src/main/core/browser/BrowserManager.ts
```

也引用了 `RemoteServerConfigCtr`。根据当前片段推断，Browser 相关代码可能在创建窗口、协议处理或请求拦截时需要读取远程配置。依据是它们位于 Electron browser 管理层，并直接 `getController(RemoteServerConfigCtr)`。

### 订阅 webview 的关系

renderer 侧：

```text
src/business/client/BusinessSettingPages/SubscriptionIframeWrapper.tsx
```

会调用：

```ts
remoteServerService.setupSubscriptionWebviewSession(PARTITION_ID)
```

然后再加载订阅页面。这个流程把桌面端登录态以 `Oidc-Auth` header 注入到 `[URL已移除] 请求中，用于官方域名下的订阅或商业功能页面识别用户。

## 运行/调用流程

### 读取远程配置流程

1. renderer 组件或 store 调用 `remoteServerService.getRemoteServerConfig()`。
2. service 通过 `ensureElectronIpc().remoteServer.getRemoteServerConfig()` 进入 Electron IPC。
3. main process 调用 `RemoteServerConfigCtr.getRemoteServerConfig()`。
4. 从 `this.app.storeManager.get('dataSyncConfig')` 读取配置。
5. 调用 `normalizeConfig()` 处理旧的 `local` 模式。
6. 返回 `DataSyncConfig`。
7. Zustand/SWR 把配置同步到 renderer 状态。

### 连接远程服务器流程

1. 用户在 UI 中选择 `cloud` 或 `selfHost`，填入配置。
2. renderer store 的 `connectRemoteServer(values)` 被调用。
3. 它先读取当前配置。
4. 如果配置有变化，调用 `setRemoteServerConfig({ ...values, active: false })`。
5. 接着调用 `requestAuthorization(values)`，这个方法实际在 `AuthCtr` 中。
6. `AuthCtr` 完成 OIDC/PKCE 授权流程后，拿到 `access_token` 和 `refresh_token`。
7. `AuthCtr` 调用 `RemoteServerConfigCtr.saveTokens()` 保存 token。
8. `AuthCtr` 调用 `RemoteServerConfigCtr.setRemoteServerConfig({ active: true })`。
9. `RemoteServerConfigCtr` 广播 `remoteServerConfigUpdated`。
10. renderer 监听广播并 revalidate SWR，UI 显示已连接。

### 断开远程服务器流程

1. renderer store 的 `disconnectRemoteServer()` 被调用。
2. 它调用 `remoteServerService.clearRemoteServerConfig()`。
3. IPC 进入 `RemoteServerConfigCtr.clearRemoteServerConfig()`。
4. `dataSyncConfig` 被重置为 `{ active: false, storageMode: 'cloud' }`。
5. 调用 `clearTokens()`：
   - 清内存 token。
   - 删除 store 中的 `encryptedTokens`。
   - 断开 `GatewayConnectionService`。
6. 广播 `remoteServerConfigUpdated`。
7. renderer 重置用户数据 stores 并刷新配置。

### access token 刷新流程

1. `AuthCtr` 的自动刷新 timer、app 激活逻辑，或 gateway service 调用 `refreshAccessToken()`。
2. `RemoteServerConfigCtr.refreshAccessToken()` 检查是否已有 `refreshPromise`。
3. 如果已有，直接复用，避免并发刷新。
4. 如果没有，执行 `performTokenRefresh()`。
5. `performTokenRefresh()` 检查远程服务配置是否 active 且可用。
6. 从本地安全存储读取并解密 refresh token。
7. 拼出远端 `/oidc/token` URL。
8. 发送 `grant_type=refresh_token` 请求。
9. 如果失败，返回错误但不直接清 token。
10. 如果成功，要求响应包含新的 `access_token` 和 `refresh_token`。
11. 调用 `saveTokens()` 保存新 token。
12. 返回 `{ success: true }`。
13. `AuthCtr` 根据返回结果广播 `tokenRefreshed`，或在不可重试错误时清 token 并要求重新授权。

### 订阅 webview 注入 token 流程

1. `SubscriptionIframeWrapper` 初始化时调用 `setupSubscriptionWebviewSession(PARTITION_ID)`。
2. IPC 进入 `RemoteServerConfigCtr.setupSubscriptionWebviewSession()`。
3. main process 通过 `electronSession.fromPartition(partition)` 找到 webview session。
4. 注册 `onBeforeSendHeaders`。
5. webview 访问 `[URL已移除] 时触发拦截器。
6. controller 调用 `getAccessToken()`。
7. 如果 token 存在，在请求头里加入 `Oidc-Auth`。
8. 请求继续发出，官方页面获得桌面端登录态。

## 小白阅读顺序

1. 先看 `DataSyncConfig` 类型  
   路径是 `packages/electron-client-ipc/src/types/dataSync.ts`。先理解配置只有三个字段：`active`、`storageMode`、`remoteServerUrl`。

2. 再看类声明和 `groupName`  
   重点理解 `RemoteServerConfigCtr extends ControllerModule` 和 `groupName = 'remoteServer'`。这决定了它是 Electron main process 的 IPC controller。

3. 读配置方法  
   先看 `getRemoteServerConfig()`、`setRemoteServerConfig()`、`clearRemoteServerConfig()`。这三者是最容易理解的入口：读、写、清空。

4. 读 `normalizeConfig()`  
   理解为什么代码里会处理类型系统已经不存在的 `'local'`。这是桌面应用常见问题：持久化数据可能来自旧版本。

5. 读 token 保存和读取  
   按顺序看 `saveTokens()`、`getAccessToken()`、`getRefreshToken()`、`loadTokensFromStore()`。重点理解内存缓存、electron-store、`safeStorage` 三者之间的关系。

6. 读 token 刷新  
   再看 `refreshAccessToken()` 和 `performTokenRefresh()`。这里要注意并发合并和“不自动重试”的设计原因。

7. 读清理逻辑  
   看 `clearTokens()`，理解为什么清 token 会顺带断开 gateway。

8. 最后看 webview session  
   看 `setupSubscriptionWebviewSession()`，理解它和普通配置读写不同，它是在 Electron session 层注册请求头注入。

9. 对照 renderer service  
   看 `src/services/electron/remoteServer.ts`，你会看到 renderer 调 main 的薄封装。

10. 对照 store action  
   看 `src/store/electron/actions/sync.ts`，理解 UI 里的“连接/断开远程同步”如何落到这个 controller。

## 常见误区

1. 误以为它只管“远程服务器地址”  
   实际上它还管理 OIDC token、token 刷新、配置变更广播、gateway 断开、webview 请求头注入。它是桌面端远程登录态的核心状态控制器。

2. 误以为 `setRemoteServerConfig({ active: false })` 等于登出  
   不等于。`setRemoteServerConfig()` 只更新配置，不会清 token。真正断开远程同步应该走 `clearRemoteServerConfig()`，因为它会调用 `clearTokens()`。

3. 误以为 `storageMode: 'cloud'` 必须有 `remoteServerUrl`  
   不需要。`cloud` 模式下会使用 `OFFICIAL_CLOUD_SERVER`。只有 `selfHost` 模式才要求 `remoteServerUrl` 合法。

4. 误以为 `safeStorage` 永远可用  
   代码明确处理了 `safeStorage.isEncryptionAvailable()` 为假的情况。此时 token 会以未加密形式保存到原字段中，因此日志会提示风险。

5. 误以为 `encryptedAccessToken` 一定是密文  
   不一定。如果 `safeStorage` 不可用，这个字段保存的是原始 access token。字段名表达的是理想状态，不代表所有平台运行时都加密。

6. 误以为 token 刷新失败会立刻清空登录态  
   不一定。`AuthCtr` 会调用 `isNonRetryableError()` 判断错误类型。只有 `invalid_grant`、缺 refresh token、配置无效等不可重试错误才会清 token。临时网络错误会保留 token，等待后续刷新。

7. 误以为 refresh token 请求应该自动重试  
   这个文件特意不做重试。因为 refresh token rotation 下，旧 refresh token 可能被服务端消费；重发同一个 refresh token 可能触发复用检测，反而导致授权整体失效。

8. 误以为 `refreshAccessToken()` 可以并发发多个请求  
   不会。它用 `refreshPromise` 合并并发调用。刷新进行中，后续调用拿到的是同一个 promise。

9. 误以为 `remoteServerConfigUpdated` 只通知当前窗口  
   不是。它通过 `browserManager.broadcastToAllWindows()` 广播到所有窗口。renderer 侧收到后会触发 SWR revalidate。

10. 误以为 `setupSubscriptionWebviewSession()` 会给所有请求加 token  
   不会。它只匹配 `[URL已移除] partition 对应的 Electron session 生效。自托管 URL 不在这个匹配规则内。

11. 误以为 `getRemoteServerUrl()` 总能返回字符串  
   `cloud` 模式一定返回官方地址；`selfHost` 模式依赖 `remoteServerUrl`。正常业务调用前应先通过 `isRemoteServerConfigured()` 校验。

12. 误以为 `afterAppReady()` 会刷新 token  
   不会。这里的 `afterAppReady()` 只从 store 加载 token 到内存。自动刷新逻辑主要在 `AuthCtr` 中编排。
