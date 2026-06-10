# 文件：next/src/hooks/useAuth.ts

## 一句话定位

`next/src/hooks/useAuth.ts` 是前端认证状态的轻量封装 hook：它把 `next-auth/react` 的 `useSession`、`signIn`、`signOut` 和 Next.js 路由跳转组合起来，为页面和组件提供统一的登录态、登录/退出方法，以及受保护页面的自动拦截逻辑。

## 它暴露/定义了什么

该文件主要暴露一个导出函数 `useAuth(options?: UseAuthOptions): Auth`。

它内部定义了几个类型：

`Provider` 表示允许的第三方登录来源，当前类型上列出 `"google"`、`"github"`、`"discord"`。不过当前实现里的 `handleSignIn` 没有把 provider 参数继续传给 `next-auth` 的 `signIn`，所以这个类型更多像是预留接口。

`Auth` 是 hook 返回值结构，包含 `signIn`、`signOut`、`status`、`session`。其中 `status` 来自 `useSession`，可能是 `"authenticated"`、`"unauthenticated"` 或 `"loading"`；`session` 是 `next-auth` 的 `Session | null`。

`UseAuthOptions` 支持两个选项：`protectedRoute` 用于声明当前调用方是否是受保护页面；`isAllowed` 用于在已登录后做额外授权判断，例如根据 `session.user.superAdmin` 或组织角色决定是否允许访问。根据当前片段推断，这个能力目前尚未在其他文件中实际传入，依据是 `rg "isAllowed"` 只发现了本文件内使用。

## 谁调用它

直接调用方包括：

`next/src/pages/index.tsx` 调用 `useAuth()` 获取 `session`，用于首页或 agent 创建相关流程中的登录态判断。

`next/src/pages/settings.tsx` 调用 `useAuth({ protectedRoute: true })`，说明设置页需要登录访问；同时它使用 `session?.user` 控制高级设置是否可用。

`next/src/hooks/useAgent.ts` 调用 `useAuth()` 获取 `status`，用于 agent 相关 hook 根据认证状态决定后续行为。

`next/src/components/drawer/LeftSidebar.tsx` 调用 `useAuth()` 获取 `session`、`signIn`、`signOut`、`status`。侧边栏用 `status` 决定是否加载用户 agent 列表，用 `signIn` 展示登录入口，用 `signOut` 传给用户菜单。

`next/src/components/dialog/SignInDialog.tsx` 调用 `useAuth()` 获取 `signIn`，用于弹窗内触发登录。

此外，`next/src/components/sidebar/AuthItem.tsx` 不直接调用 `useAuth`，但接收 `LeftSidebar` 传入的 `session`、`signIn`、`signOut`，属于间接消费者。

## 它调用谁

它调用 `next-auth/react` 的三个核心 API：

`useSession()` 是认证状态来源，返回当前 `session` 和 `status`。

`signIn()` 触发 NextAuth 登录流程。因为服务端 auth 配置里设置了 `pages.signIn: "/signin"`，默认登录会被导向自定义登录页 `next/src/pages/signin.tsx`。

`signOut({ callbackUrl: "/" })` 触发退出登录，并在完成后回到首页。

它还调用 `next/router` 的 `useRouter()`，从中取出 `push`。当受保护页面已登录但不满足 `isAllowed(session)` 时，hook 会执行 `push("/404")`，把用户送到 404 页面。

相关服务端配置位于 `next/src/server/auth/auth.ts`、`next/src/server/auth/local-auth.ts`、`next/src/server/auth/index.ts`。这些文件决定 provider、登录页、session 字段填充和本地 credentials 登录行为。`next/src/types/next-auth.d.ts` 扩展了 `Session` 类型，使 `session.user` 包含 `id`、`superAdmin`、`organizations` 等业务字段。

## 核心流程

组件调用 `useAuth()` 后，hook 首先通过 `useSession()` 读取 NextAuth 的当前会话状态。随后通过 `useEffect` 监听 `protectedRoute`、`isAllowed`、`status`、`session` 和 `push` 的变化。

当 `protectedRoute` 为 `true` 且 `status === "unauthenticated"` 时，hook 会调用 `handleSignIn()`。这会触发 NextAuth 默认登录流程，结合项目 auth 配置，用户一般会被引导到 `/signin`。

当 `protectedRoute` 为 `true` 且 `status === "authenticated"` 时，hook 会继续执行授权检查。如果调用方提供了 `isAllowed`，且 `isAllowed(session)` 返回 `false`，则通过 `push("/404")` 跳转到 404 页面。这里把“未登录认证”和“已登录但无权限”区分成两个路径：前者去登录，后者去 404。

最后 hook 返回统一对象：`signIn`、`signOut`、`status`、`session`。调用方不需要直接接触 `next-auth/react`，可以只围绕这个本地 hook 编写 UI 逻辑。

## 关键函数的高层作用

`useAuth` 是唯一关键函数。它承担三层职责：读取会话、暴露登录退出动作、在受保护路由上执行自动跳转。它不是完整权限系统，而是前端侧的认证门面和导航拦截器。

`handleSignIn` 是对 `next-auth` `signIn` 的简单包装。虽然 `Auth.signIn` 类型声明允许传入 `provider?: Provider`，当前实现没有使用该参数，因此调用 `signIn("google")` 这类意图通过本 hook 目前不会生效。项目真正按 provider 登录的逻辑在 `next/src/pages/signin.tsx` 中直接调用 `next-auth/react` 的 `signIn(detail.id, { callbackUrl: "/" })`。

`handleSignOut` 是退出包装，固定使用 `callbackUrl: "/"`。这意味着所有通过 `useAuth().signOut()` 退出的入口都会回到首页，例如侧边栏用户菜单。

`useEffect` 中的保护逻辑是该文件最敏感的部分。它把认证状态变化转化为副作用：未登录时触发登录，登录但无权限时跳到 404。由于它运行在 React 客户端渲染阶段，因此它不能替代服务端权限校验，只能改善前端访问体验。

## 修改风险

第一，`signIn` 类型和实现当前不一致。`Auth.signIn` 声明接受 `provider?: Provider`，但 `handleSignIn` 没有参数，也没有传给 NextAuth。如果未来调用方以为 `useAuth().signIn("github")` 会直接走 GitHub 登录，会得到与预期不符的行为。修复时需要确认是否所有登录都应先进入 `/signin`，还是允许组件直接指定 provider。

第二，`protectedRoute` 的默认参数写法存在细节风险。函数参数默认值是整个对象 `{ protectedRoute: false, isAllowed: () => true }`，但如果调用方传入 `{ protectedRoute: true }`，解构后的 `isAllowed` 实际是 `undefined`，不是默认函数。当前判断里有 `isAllowed && !isAllowed(session)`，所以不会报错；但如果后续代码假设 `isAllowed` 总是函数，就可能引入异常。

第三，自动 `signIn()` 是客户端副作用，可能造成页面短暂闪烁或重复跳转。尤其是 `status` 从 `"loading"` 变为 `"unauthenticated"` 时才触发登录，调用方在 loading 阶段需要自己处理 UI，否则受保护页面内容可能短暂显示默认状态。

第四，`isAllowed(session)` 的权限判断依赖 `Session` 业务字段是否完整。类型扩展中 `session.user` 包含 `superAdmin`、`organizations`，但这些字段需要服务端 session callback 正确填充。如果服务端 auth 配置调整，前端授权判断可能静默失效或把用户错误导向 404。

第五，`signOut` 固定跳转首页会影响所有使用该 hook 的组件。如果某些页面希望退出后留在当前页、跳转到 `/signin` 或带上回跳参数，直接改这里会改变全局行为，影响侧边栏和认证菜单。

第六，这个 hook 只做前端访问控制，不能作为数据安全边界。像 `LeftSidebar` 中 `api.agent.getAll.useQuery` 仍然需要后端 API 自己校验用户身份；页面层 `protectedRoute` 只能避免普通用户在 UI 上进入某些视图，不能防止直接请求接口。
