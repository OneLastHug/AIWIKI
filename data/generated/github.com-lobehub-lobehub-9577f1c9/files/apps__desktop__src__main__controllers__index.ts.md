# 文件：apps/desktop/src/main/controllers/index.ts

## 它负责什么

`apps/desktop/src/main/controllers/index.ts` 是桌面端 Electron main process 的 controller 基础入口文件。它不实现某个具体业务能力，而是提供一套给所有 `controllers/*Ctr.ts` 复用的基础设施：

1. 定义所有桌面 controller 的基类 `ControllerModule`
2. 从 `@/utils/ipc` 重新导出 `IpcMethod` 装饰器
3. 提供 `shortcut(...)` 装饰器，用来把 controller 方法登记为桌面快捷键动作
4. 提供 `createProtocolHandler(...)` 装饰器，用来把 controller 方法登记为协议 URL 处理器
5. 约定 controller 可选生命周期钩子：`beforeAppReady`、`afterAppReady`

在 LobeHub Desktop 架构里，`apps/desktop/src/main` 属于 Electron 主进程，负责窗口、系统能力、IPC、菜单、快捷键、协议处理等平台相关逻辑。渲染进程复用 Web/SPA 代码，需要通过 IPC 调用这些能力。`controllers/index.ts` 就是这层 IPC controller 体系的公共基座。

可以把它理解为：“每个桌面控制器都从这里拿到统一的父类和装饰器，然后被注册到 IPC 系统里”。

## 关键组成

### `shortcutDecorator`

```ts
const shortcutDecorator = (name: string) => (target: any, methodName: string, descriptor?: any) => {
  const actions = IoCContainer.shortcuts.get(target.constructor) || [];
  actions.push({ methodName, name });

  IoCContainer.shortcuts.set(target.constructor, actions);

  return descriptor;
};
```

这是底层快捷键装饰器工厂。

它接收一个快捷键动作名 `name`，返回真正用于方法上的 decorator。decorator 被应用到类方法时，会拿到：

- `target`：类原型对象
- `methodName`：被装饰的方法名
- `descriptor`：方法描述符

核心逻辑是把 `{ methodName, name }` 存到 `IoCContainer.shortcuts` 这个 `WeakMap` 里，key 是 `target.constructor`，也就是当前 controller 类。

也就是说，某个 controller 类中如果有方法被 `@shortcut(...)` 标记，这个文件不会立刻执行快捷键逻辑，而是先把“哪个类的哪个方法对应哪个快捷键”记录起来。后续快捷键管理器或应用初始化流程再读取这些元数据并完成绑定。

根据当前片段推断，`IoCContainer.shortcuts` 是一个轻量的 decorator 元数据容器，专门服务于桌面 main process 的依赖注册和行为发现。

### `DesktopHotkeyIdCompatible`

```ts
type DesktopHotkeyIdCompatible = DesktopHotkeyId | 'quickComposer';
```

这里扩展了可接受的快捷键 ID 类型。

`DesktopHotkeyId` 来自 `@lobechat/types`，代表项目内正式定义的桌面快捷键 ID。但这里额外允许 `'quickComposer'`。这说明 `quickComposer` 可能是一个历史遗留、尚未并入通用类型、或桌面端特有的快捷键动作。

这类类型别名的作用是让 `shortcut(...)` 的入参既有类型约束，又兼容当前桌面端实际存在的动作名。

### `shortcut`

```ts
export const shortcut = (method: DesktopHotkeyIdCompatible) => shortcutDecorator(method);
```

这是对外暴露的快捷键装饰器。

具体 controller 中可以写类似：

```ts
@shortcut('someHotkeyId')
someMethod() {
  // ...
}
```

它的语义不是“注册键盘按键”，而是“声明这个 controller 方法可以作为某个快捷键动作的处理函数”。真正按键组合、用户配置、系统注册等工作通常会在快捷键管理模块里完成。

### `protocolDecorator`

```ts
const protocolDecorator =
  (urlType: string, action: string) => (target: any, methodName: string, descriptor?: any) => {
    const handlers = IoCContainer.protocolHandlers.get(target.constructor) || [];
    handlers.push({ action, methodName, urlType });

    IoCContainer.protocolHandlers.set(target.constructor, handlers);

    return descriptor;
  };
```

这是协议处理器的底层装饰器工厂。

它和 `shortcutDecorator` 模式完全类似，只是记录的数据变成：

- `urlType`：协议 URL 的类型，例如注释里提到的 `'plugin'`
- `action`：具体动作，例如 `'install'`
- `methodName`：当前 controller 方法名

记录位置是 `IoCContainer.protocolHandlers`。

这通常用于处理类似自定义协议或深链 URL 的入口。例如用户打开某个 `lobehub://...` 类型链接，主进程解析出 URL 类型和动作后，可以根据这些注册信息找到对应 controller 方法执行。

### `createProtocolHandler`

```ts
export const createProtocolHandler = (urlType: string) => (action: string) =>
  protocolDecorator(urlType, action);
```

这是对外使用的协议 handler 装饰器工厂。

它是一个两层函数：

1. 先固定 `urlType`
2. 再固定 `action`
3. 最终得到方法 decorator

用法根据注释大概会像这样：

```ts
const pluginProtocolHandler = createProtocolHandler('plugin');

@pluginProtocolHandler('install')
installPlugin() {
  // ...
}
```

这种写法比直接传两个字符串更利于按 URL 类型组织协议处理逻辑。

### `IControllerModule`

```ts
interface IControllerModule {
  afterAppReady?: () => void;
  app: App;
  beforeAppReady?: () => void;
}
```

这是 controller 实例应具备的基础形状。

字段含义：

- `app: App`：注入的桌面应用核心对象
- `beforeAppReady?: () => void`：Electron app ready 之前的可选钩子
- `afterAppReady?: () => void`：Electron app ready 之后的可选钩子

这里的 `App` 来自 `@/core/App`。目标文件没有展开 `App`，但从 `ShortcutCtr.ts` 的用法可以看到 controller 会通过 `this.app` 访问主进程能力，例如：

```ts
this.app.shortcutManager.getShortcutsConfig()
this.app.shortcutManager.updateShortcutConfig(id, accelerator)
```

所以 `ControllerModule` 不是纯工具类，它是所有 controller 访问桌面应用上下文的入口。

### `ControllerModule`

```ts
export class ControllerModule extends IpcService implements IControllerModule {
  constructor(public app: App) {
    super();
    this.app = app;
  }
}
```

这是本文件最重要的导出。

它继承自 `IpcService`，说明每个 controller 本质上也是一个 IPC service。具体业务 controller 会继承它，例如同目录的 `ShortcutCtr.ts`：

```ts
export default class ShortcutController extends ControllerModule {
  static override readonly groupName = 'shortcut';

  @IpcMethod()
  getShortcutsConfig() {
    return this.app.shortcutManager.getShortcutsConfig();
  }

  @IpcMethod()
  updateShortcutConfig(...) {
    return this.app.shortcutManager.updateShortcutConfig(id, accelerator);
  }
}
```

从这个例子可以看出：

- `ControllerModule` 负责给子类提供 `this.app`
- `IpcService` 负责让子类进入 IPC service 体系
- 子类通过 `static groupName` 定义 IPC 分组名
- 子类方法通过 `@IpcMethod()` 暴露给 IPC 调用方

根据当前片段推断，渲染进程最终会通过类似 `ipc.shortcut.getShortcutsConfig()` 的形式调用到 `ShortcutController.getShortcutsConfig()`，其中 `shortcut` 来源于 `groupName = 'shortcut'`，方法名来源于 `@IpcMethod()` 标记的方法。

### `IControlModule`

```ts
export type IControlModule = typeof ControllerModule;
```

这是 `ControllerModule` 类构造器本身的类型别名。

它描述的是“ControllerModule 这个类”，而不是 controller 实例。这个类型可用于接收 controller 类构造器的注册逻辑。不过在邻近的 `registry.ts` 中，实际用于 controller 构造器数组的是从 `@/utils/ipc` 引入的 `IpcServiceConstructor`。

### `IpcMethod` re-export

```ts
export { IpcMethod } from '@/utils/ipc';
```

这个 re-export 很关键。

业务 controller 不需要直接知道 `@/utils/ipc` 的具体位置，可以统一从当前目录入口导入：

```ts
import { ControllerModule, IpcMethod } from '.';
```

同目录 `ShortcutCtr.ts` 就是这样写的。

这样做的好处是 controller 层的公共 API 收口到 `controllers/index.ts`，后续如果 IPC 装饰器内部实现移动，业务 controller 的 import 不一定需要全部改动。

## 上下游关系

### 上游依赖

`index.ts` 依赖三类上游：

1. 类型定义：`DesktopHotkeyId`

来自 `@lobechat/types`，用于约束 `shortcut(...)` 可接受的快捷键 ID。

2. 应用核心对象：`App`

来自 `@/core/App`。所有 controller 实例都会持有 `app`，并通过它访问桌面主进程中的窗口、快捷键、菜单、服务、管理器等能力。

3. 基础设施：`IoCContainer` 与 `IpcService`

`IoCContainer` 位于 `apps/desktop/src/main/core/infrastructure/IoCContainer.ts`，当前能看到两个静态 `WeakMap`：

```ts
static shortcuts: WeakMap<any, { methodName: string; name: string }[]> = new WeakMap();

static protocolHandlers: WeakMap<any, { action: string; methodName: string; urlType: string }[]> =
  new WeakMap();
```

`IpcService` 和 `IpcMethod` 来自 `@/utils/ipc`。当前任务读取到的路径中没有展开其实现，但从使用方式可以确定它负责 IPC service 的基础抽象和方法装饰器能力。

### 下游使用者

最直接的下游是同目录各个 controller 文件，例如：

- `ShortcutCtr.ts`
- `SystemCtr.ts`
- `MenuCtr.ts`
- `BrowserWindowsCtr.ts`
- `NotificationCtr.ts`
- `HeterogeneousAgentCtr.ts`
- `McpCtr.ts`
- `UpdaterCtr.ts`

这些 controller 通常会：

1. 继承 `ControllerModule`
2. 声明 `static groupName`
3. 用 `@IpcMethod()` 暴露方法
4. 在方法内调用 `this.app.xxx` 或其他 main process 服务

例如 `ShortcutCtr.ts`：

```ts
import { ControllerModule, IpcMethod } from '.';

export default class ShortcutController extends ControllerModule {
  static override readonly groupName = 'shortcut';

  @IpcMethod()
  getShortcutsConfig() {
    return this.app.shortcutManager.getShortcutsConfig();
  }
}
```

另外，`registry.ts` 是 controller 体系的注册清单：

```ts
export const controllerIpcConstructors = [
  HeterogeneousAgentCtr,
  AuthCtr,
  BrowserWindowsCtr,
  ...
  UpdaterCtr,
] as const satisfies readonly IpcServiceConstructor[];
```

这说明具体 controller 类不会靠文件扫描自动注册，而是显式加入 `controllerIpcConstructors`。新建 controller 时，如果只写了类但没有加入 `registry.ts`，大概率不会被 IPC 系统加载。

`registry.ts` 还导出了：

```ts
export type DesktopIpcServices = MergeIpcService<DesktopControllerServices>;
```

这表示它会把所有 controller 构造器对应的 IPC service 类型合并成一个桌面端 IPC 服务类型。渲染进程或 preload/client 侧可以据此获得类型安全的调用接口。

## 运行/调用流程

从当前文件和邻近文件可以梳理出典型流程：

1. 编写具体 controller

例如 `ShortcutController` 继承 `ControllerModule`：

```ts
export default class ShortcutController extends ControllerModule {
  static override readonly groupName = 'shortcut';
}
```

这一步让它具备两个基础能力：

- 是一个 `IpcService`
- 构造时能拿到 `App`

2. 用 `@IpcMethod()` 标记可被 IPC 调用的方法

```ts
@IpcMethod()
getShortcutsConfig() {
  return this.app.shortcutManager.getShortcutsConfig();
}
```

根据当前片段推断，`IpcMethod` 会把这个方法记录为 IPC 暴露方法。注册系统后续读取这些元数据，把它映射成 renderer/preload 可调用的 API。

3. 如有需要，用 `@shortcut(...)` 标记快捷键动作

如果某个 controller 方法要响应桌面快捷键，可以使用：

```ts
@shortcut('someHotkeyId')
someAction() {
  // ...
}
```

装饰器执行时不会直接绑定系统快捷键，而是把 `{ methodName, name }` 存入 `IoCContainer.shortcuts`。

4. 如有需要，用 `createProtocolHandler(...)` 标记协议处理动作

例如根据注释，可创建某个 URL 类型的处理器：

```ts
const pluginHandler = createProtocolHandler('plugin');

@pluginHandler('install')
install() {
  // ...
}
```

装饰器会把 `{ urlType, action, methodName }` 存入 `IoCContainer.protocolHandlers`。

5. 在 `registry.ts` 注册 controller 类

```ts
controllerIpcConstructors = [
  ...
  ShortcutController,
  ...
]
```

只有进入这个数组，controller 才会成为桌面端 IPC service 集合的一部分。

6. 应用启动时实例化 controller

根据当前片段推断，主进程启动逻辑会读取 `controllerIpcConstructors`，对每个 controller 构造器传入同一个 `App` 实例：

```ts
new SomeController(app)
```

因为 `ControllerModule` 的构造函数是：

```ts
constructor(public app: App) {
  super();
  this.app = app;
}
```

所以所有子类都能通过 `this.app` 访问主进程应用上下文。

7. IPC、快捷键、协议系统读取元数据并完成绑定

- `IpcMethod` 元数据用于生成 IPC 调用入口
- `IoCContainer.shortcuts` 用于快捷键动作绑定
- `IoCContainer.protocolHandlers` 用于协议 URL 动作分发
- `beforeAppReady` / `afterAppReady` 可用于应用生命周期前后执行初始化

8. 渲染进程触发调用

最终用户在界面上操作时，renderer 侧通过 preload 暴露的 IPC client 调用 main process。例如根据 `ShortcutCtr.ts` 推断，渲染进程可能调用桌面 IPC 的 `shortcut.getShortcutsConfig`，主进程分发到 `ShortcutController.getShortcutsConfig()`，再由它调用 `this.app.shortcutManager` 返回结果。

## 小白阅读顺序

1. 先读 `ControllerModule`

从这里理解所有 controller 为什么都有 `this.app`：

```ts
export class ControllerModule extends IpcService implements IControllerModule
```

重点看它继承了 `IpcService`，并在构造函数里接收 `App`。这就是 controller 连接“IPC 系统”和“桌面应用核心对象”的地方。

2. 再读 `IControllerModule`

这个 interface 告诉你 controller 的生命周期约定：

```ts
beforeAppReady?: () => void;
afterAppReady?: () => void;
```

看到某个 controller 里实现了这两个方法时，就知道它不是普通 IPC 方法，而是应用启动前后要执行的初始化逻辑。

3. 然后读 `IpcMethod` 的导出和示例 controller

看 `ShortcutCtr.ts` 这样的简单文件最容易理解：

```ts
import { ControllerModule, IpcMethod } from '.';
```

这说明业务 controller 统一从当前 `index.ts` 拿公共基类和 IPC 装饰器。

4. 再读 `registry.ts`

`index.ts` 定义了“controller 应该长什么样”，`registry.ts` 定义了“哪些 controller 真正被加载”。

读 `controllerIpcConstructors` 可以快速建立桌面端 main process 能力地图，例如认证、窗口、CLI、Git、本地文件、MCP、通知、系统、更新等。

5. 最后读 `shortcut` 和 `createProtocolHandler`

这两个装饰器属于扩展能力。先理解 IPC controller 主链路，再看快捷键和协议处理，会更容易区分：

- `@IpcMethod()`：给 renderer 调用
- `@shortcut(...)`：给快捷键系统发现
- `createProtocolHandler(...)`：给协议 URL 分发系统发现

## 常见误区

1. 误以为 `shortcut(...)` 会直接注册系统快捷键

不会。它只是把方法名和快捷键动作名写入 `IoCContainer.shortcuts`。真正的快捷键注册、按键组合监听、冲突处理等逻辑应该在快捷键管理相关模块中完成。

2. 误以为 `createProtocolHandler(...)` 会直接监听 URL

不会。它只是登记“某个 controller 方法可以处理某种 `urlType + action`”。真正的协议注册和 URL 解析应该由 Electron app 或协议管理模块处理。

3. 误以为继承 `ControllerModule` 就能自动暴露所有方法

不能。普通方法不会天然成为 IPC API。需要用 `@IpcMethod()` 标记，且 controller 类需要被加入 `registry.ts` 的 `controllerIpcConstructors`。

4. 误以为 `ControllerModule` 是业务类

它不是业务类，而是 controller 层基类。具体业务在 `AuthCtr.ts`、`ShortcutCtr.ts`、`McpCtr.ts`、`SystemCtr.ts` 等文件里。`index.ts` 的职责是提供公共机制。

5. 误以为 `app` 是前端 React app

这里的 `App` 是 Electron main process 里的核心应用对象，路径是 `@/core/App`。它不是 React 组件，也不是 Next.js app。controller 通过它访问桌面端系统能力和管理器。

6. 误以为 `IControlModule` 表示 controller 实例类型

```ts
export type IControlModule = typeof ControllerModule;
```

这里的 `typeof ControllerModule` 表示类构造器类型，不是 `new ControllerModule(app)` 之后的实例类型。看 TypeScript 时要区分“类本身的类型”和“类实例的类型”。

7. 误以为新增 controller 只需要新建文件

按照当前结构，新增 controller 至少还需要：

- 继承 `ControllerModule`
- 设置 `static groupName`
- 给 IPC 方法加 `@IpcMethod()`
- 在 `registry.ts` 中加入 controller 构造器
- 如涉及渲染进程调用，还要配套 IPC 类型和 renderer service

8. 误以为 `IoCContainer` 是完整依赖注入容器

从当前片段看，`IoCContainer` 只保存了 decorator 产生的元数据：`shortcuts` 和 `protocolHandlers`。它更像一个轻量元数据注册表，而不是传统意义上负责创建对象、解析依赖、管理生命周期的完整 IoC 容器。
