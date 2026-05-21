# 目录：src/routes/(main)/settings/provider/features/ProviderConfig/OAuthDeviceFlowAuth

## 它负责什么

`OAuthDeviceFlowAuth` 是模型服务商设置页里专门处理 `authType === 'oauthDeviceFlow'` 的前端认证模块。它不负责普通 API Key 输入，而是负责 OAuth Device Flow，也就是“在当前页面显示用户码，用户去外部浏览器授权，前端轮询后端确认授权结果”的流程。

这个目录只有两个文件：

- `index.tsx`：React UI 组件，负责展示连接卡片、验证码、复制按钮、打开浏览器按钮、轮询提示、错误状态、已连接用户信息、断开连接确认框。
- `useOAuthDeviceFlow.ts`：业务 hook，负责申请 device code、启动轮询、处理过期/拒绝/成功/错误、清理定时器。

它的直接上层是 `ProviderConfig`。当某个 provider 的 `settings.authType` 是 `'oauthDeviceFlow'` 时，`ProviderConfig` 会渲染这个认证卡片，并且只有在 OAuth 已认证后才显示后续 provider 配置表单。

## 关键组成

### `OAuthDeviceFlowAuthProps`

`index.tsx` 导出默认组件 `OAuthDeviceFlowAuth`，props 包括：

- `providerId: string`：当前模型服务商 ID，例如根据当前片段可见后端对 `githubcopilot` 有特殊处理。
- `name: string`：服务商展示名，用于按钮文案和说明文案。
- `onAuthChange?: () => void`：认证状态变化后的回调，上层用它刷新 provider detail 和 runtime state。
- `title?: ReactNode`：卡片头部左侧内容，来自 `ProviderConfig` 的 provider 标题区域。
- `extra?: ReactNode`：卡片头部右侧内容，通常包括自定义 provider 更新入口和启用开关。

### UI 状态来源

组件同时使用两类状态：

- 后端认证状态：通过 `lambdaQuery.oauthDeviceFlow.getAuthStatus.useQuery({ providerId })` 获取，结果里有 `isAuthenticated`、`username`、`avatarUrl`。
- 当前前端认证流程状态：通过 `useOAuthDeviceFlow({ providerId, onSuccess })` 获取，结果里有 `state`、`deviceCodeInfo`、`error`、`startAuth`、`cancelAuth`。

这两个状态不要混为一谈。`isAuthenticated` 表示“后端 keyVaults 中是否已有 OAuth token”；`state` 表示“这一次前端 device flow 正进行到哪一步”。

### `useOAuthDeviceFlow`

`useOAuthDeviceFlow.ts` 定义了两个核心类型：

```ts
type AuthState = 'idle' | 'requesting' | 'pending_user_auth' | 'polling' | 'success' | 'error';
type PollStatus = 'pending' | 'success' | 'expired' | 'denied' | 'slow_down';
```

hook 内部维护：

- `state`：当前认证阶段。
- `deviceCodeInfo`：后端返回的 `deviceCode`、`userCode`、`verificationUri`、`expiresIn`、`interval`。
- `error`：错误码，如 `codeExpired`、`denied`、`authError`。
- `pollingRef`：轮询 `setInterval` 的引用。
- `expiryRef`：过期 `setTimeout` 的引用。
- `deviceCodeRef`：当前 device code，用来避免旧流程的延迟回调误启动轮询。

它调用的 tRPC mutation 有两个：

- `lambdaQuery.oauthDeviceFlow.initiateDeviceCode.useMutation()`：向后端申请 device code。
- `lambdaQuery.oauthDeviceFlow.pollAuthStatus.useMutation()`：按 device code 轮询授权状态。

### 样式与组件依赖

`index.tsx` 使用 `createStaticStyles` 和 `cssVar` 定义静态样式，符合仓库偏好的零运行时 CSS-in-JS 风格。UI 主要来自：

- `@lobehub/ui`：`CopyButton`、`Flexbox`、`Icon`
- `antd`：`App`、`Avatar`、`Button`、`Typography`
- `@lobehub/icons`：`ProviderIcon`
- `lucide-react`：`ExternalLinkIcon`、`Loader2Icon`、`LogOutIcon`、`UnplugIcon`
- `@ant-design/icons`：`CheckCircleFilled`

文案通过 `useTranslation('modelProvider')` 读取，key 集中在 `providerModels.config.oauth.*` 这一组。

## 上下游关系

### 上游：`ProviderConfig`

上游文件是：

`src/routes/(main)/settings/provider/features/ProviderConfig/index.tsx`

其中通过：

```ts
const isOAuthProvider = authType === 'oauthDeviceFlow';
```

判断当前 provider 是否使用 OAuth Device Flow。若是，则渲染：

```tsx
<OAuthDeviceFlowAuth
  extra={headerExtra}
  name={name || id}
  providerId={id}
  title={headerTitle}
  onAuthChange={handleOAuthChange}
/>
```

同时，`ProviderConfig` 会查询 OAuth 状态：

```ts
lambdaQuery.oauthDeviceFlow.getAuthStatus.useQuery(
  { providerId: id },
  { enabled: isOAuthProvider, refetchOnWindowFocus: true },
)
```

并用：

```ts
const shouldShowForm = !isOAuthProvider || isOAuthAuthenticated;
```

控制表单是否显示。也就是说，OAuth provider 未登录时，用户只看到 OAuth 连接卡片；登录成功后，才看到普通 provider 配置表单，例如 endpoint、responses api、checker 等配置项。

`handleOAuthChange` 会调用：

- `useAiInfraStore.getState().refreshAiProviderDetail()`
- `useAiInfraStore.getState().refreshAiProviderRuntimeState()`

这说明 OAuth token 保存后，上层需要刷新 provider 配置和运行态。

### 下游：tRPC `oauthDeviceFlow` router

前端调用的是：

`lambdaQuery.oauthDeviceFlow.*`

对应后端文件：

`src/server/routers/lambda/oauthDeviceFlow.ts`

相关接口包括：

- `getAuthStatus`：读取 provider 的 `keyVaults`，判断是否存在 `oauthAccessToken`。
- `initiateDeviceCode`：根据 provider 的 `settings.oauthDeviceFlow` 配置，申请 device code。
- `pollAuthStatus`：轮询授权结果；成功后把 OAuth token 写入 provider config 的 `keyVaults`。
- `revokeAuth`：清空 `keyVaults` 中的 OAuth token、GitHub 用户名、头像、bearer token 等字段。

根据当前片段推断，OAuth Device Flow 当前重点服务于 GitHub Copilot，因为后端对 `providerId === 'githubcopilot'` 且 `service instanceof GithubCopilotOAuthService` 做了专门分支，并保存 `githubUsername`、`githubAvatarUrl`、`bearerToken` 等字段。依据是 `oauthDeviceFlow.ts` 中的特殊分支，以及搜索结果中 `packages/model-bank/src/modelProviders/githubCopilot.ts` 配置了 `authType: 'oauthDeviceFlow'`。

## 运行/调用流程

1. 用户进入 provider 设置页，`ProviderConfig` 读取 provider 的 `settings.authType`。
2. 如果 `authType !== 'oauthDeviceFlow'`，走普通 API Key 表单逻辑；如果是 OAuth provider，则先渲染 `OAuthDeviceFlowAuth`。
3. `OAuthDeviceFlowAuth` 调用 `getAuthStatus` 查询后端是否已认证。
4. 若已认证，卡片显示头像、用户名、“已连接”状态和断开连接按钮。
5. 若未认证，卡片显示连接按钮。
6. 用户点击连接按钮后，`handleStartAuth` 设置 `isAuthenticating = true`，并调用 hook 的 `startAuth()`。
7. `startAuth()` 先把状态设为 `requesting`，然后调用 `initiateDeviceCode`。
8. 后端返回 `userCode`、`deviceCode`、`verificationUri`、`interval`、`expiresIn`。
9. 前端显示 `userCode`，提供复制按钮和打开浏览器按钮。
10. hook 设置过期定时器：超过 `expiresIn` 后进入 `error`，错误码为 `codeExpired`。
11. hook 延迟 2 秒后启动轮询，调用 `pollAuthStatus`。
12. 如果轮询返回 `pending`，继续等下一次。
13. 如果返回 `slow_down`，前端把轮询间隔增加 5 秒。
14. 如果返回 `expired` 或 `denied`，清理定时器并显示错误。
15. 如果返回 `success`，清理定时器，设置 `state = 'success'`，调用 `onSuccess`。
16. `onSuccess` 在组件里会 invalidate `getAuthStatus`，再通知上层 `onAuthChange`。
17. 上层刷新 provider detail 和 runtime state。
18. `getAuthStatus` 刷新后，如果后端已保存 token，`isAuthenticated` 变为 `true`。
19. `ProviderConfig` 因 `isOAuthAuthenticated` 为真，开始显示后续 provider 配置表单。

断开连接流程更短：

1. 用户点击断开连接按钮。
2. 组件用 `App.useApp().modal.confirm()` 弹出确认框。
3. 确认后调用 `revokeAuth.mutateAsync({ providerId })`。
4. 后端清空 OAuth 相关 keyVaults。
5. 前端 invalidate `getAuthStatus`，调用 `onAuthChange`，上层刷新 provider 状态。
6. 卡片回到未连接状态，OAuth provider 的配置表单也会被隐藏。

## 小白阅读顺序

1. 先读 `ProviderConfig/index.tsx` 中和 OAuth 有关的几段：
   - `const isOAuthProvider = authType === 'oauthDeviceFlow'`
   - `getAuthStatus.useQuery(...)`
   - `handleOAuthChange`
   - `shouldShowForm`
   - `<OAuthDeviceFlowAuth ... />`

   这样能先理解“为什么这个目录会被调用”。

2. 再读 `OAuthDeviceFlowAuth/index.tsx` 的 props 和顶部 query/mutation：
   - `OAuthDeviceFlowAuthProps`
   - `getAuthStatus.useQuery`
   - `revokeAuth.useMutation`
   - `handleSuccess`
   - `useOAuthDeviceFlow(...)`

   这一步看清楚组件的输入、后端查询和回调关系。

3. 接着读 `renderContent()`：
   - 已认证状态：显示头像、用户名、断开连接。
   - 认证中状态：显示 loading、验证码、打开浏览器、轮询提示、取消。
   - 错误状态：显示错误和重试。
   - 默认状态：显示连接按钮。

   这是 UI 行为最直观的部分。

4. 然后读 `useOAuthDeviceFlow.ts`：
   - 先看 `AuthState` 和 `PollStatus`
   - 再看 `startAuth`
   - 再看 `startPolling`
   - 最后看 `cancelAuth` 和 `useEffect` cleanup

   hook 是这个目录真正的流程核心。

5. 最后读 `src/server/routers/lambda/oauthDeviceFlow.ts`：
   - `initiateDeviceCode` 对应前端申请验证码。
   - `pollAuthStatus` 对应前端轮询。
   - `getAuthStatus` 对应前端判断是否已连接。
   - `revokeAuth` 对应断开连接。

   读完后，前端卡片和后端 token 保存逻辑就能串起来。

## 常见误区

1. 不要把 `isAuthenticating` 和 hook 的 `state` 当成同一个状态。  
   `isAuthenticating` 是组件层面的“当前是否显示认证流程 UI”；`state` 是 hook 层面的 OAuth 流程阶段。已登录但用户又点了重新认证时，组件会用 `isAuthenticated && !isAuthenticating` 避免误显示旧的已连接状态。

2. 不要以为 `userCode` 就是 token。  
   `userCode` 只是给用户在外部页面输入的短码；真正的 token 是后端在 `pollAuthStatus` 成功后保存到 `keyVaults` 里的 `oauthAccessToken`、`bearerToken` 等字段。

3. 不要跳过定时器清理。  
   `useOAuthDeviceFlow` 里有 `pollingRef` 和 `expiryRef`，在成功、失败、取消、卸载时都要清理。否则会出现页面已离开但仍在轮询的问题。

4. 不要认为前端直接拿到 OAuth token。  
   当前实现里前端只拿 device code 状态和认证状态，token 保存发生在后端 router 中，并通过 `AiProviderModel.updateConfig` 写入加密的 keyVaults。

5. 不要只刷新 `getAuthStatus` 就认为所有 provider 状态都同步了。  
   `OAuthDeviceFlowAuth` 自己会 invalidate `getAuthStatus`，但上层 `ProviderConfig` 还通过 `onAuthChange` 刷新 provider detail 和 runtime state。两者解决的问题不同：前者更新卡片认证状态，后者更新 provider 配置和运行态。

6. 不要忽略 `slow_down`。  
   OAuth Device Flow 的服务端可能要求客户端降低轮询频率。hook 在收到 `slow_down` 后会把轮询间隔增加 5 秒，这是协议层面的节流处理，不是普通错误。

7. 不要在 OAuth provider 未认证时期待看到完整配置表单。  
   `ProviderConfig` 明确用 `shouldShowForm = !isOAuthProvider || isOAuthAuthenticated` 控制表单显示。OAuth provider 没连上前，用户主要操作入口就是这个认证卡片。

8. 不要误解 `verificationUri` 的打开方式。  
   前端用 `window.open(deviceCodeInfo.verificationUri, '_blank')` 打开外部授权页面，同时也把链接作为文本链接展示出来。用户还需要把页面里的 `userCode` 输入到外部授权页面，流程才会继续。
