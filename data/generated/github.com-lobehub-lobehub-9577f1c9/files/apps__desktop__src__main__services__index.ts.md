# 文件：apps/desktop/src/main/services/index.ts

## 它负责什么

这个文件是 desktop 主进程里“服务层”的最小公共基类入口。它本身不实现具体业务，而是提供一个统一的 `ServiceModule` 父类，让同目录下的 `fileSrv.ts`、`fileSearchSrv.ts`、`contentSearchSrv.ts`、`gatewayConnectionSrv.ts` 这些服务都能继承同一套上下文注入方式。

它的核心作用只有两个：

1. 保存 `app` 实例引用，方便每个 service 访问主进程能力、存储、工具管理器等。
2. 导出一个构造器类型 `IServiceModule`，供 `App.ts` 在批量加载服务时做类型约束。

## 关键组成

`ServiceModule` 只有一个构造函数：

```ts
constructor(public app: App) {
  this.app = app;
}
```

这里的 `public app: App` 已经完成了两件事：
- 在实例上挂出 `app` 属性；
- 让子类天然拿到 `this.app`，不需要自己重复声明。

紧接着导出的 `IServiceModule = typeof ServiceModule` 也很关键。它不是“服务实例类型”，而是“服务类构造器类型”。根据当前片段推断，`App.ts` 里会把 `import.meta.glob('@/services/*Srv.ts', { eager: true })` 的结果当成一组服务类，再统一 `new ServiceClass(this)` 实例化，所以这里需要的是“能被 new 的类类型”。

## 上下游关系

上游是 `apps/desktop/src/main/core/App.ts`。那里会扫描 `@/services/*Srv.ts`，把所有符合命名规则的服务文件加载进来，再通过 `addService` 统一创建实例。`index.ts` 在这里充当类型和基类支点。

下游是各个具体服务文件：
- `fileSrv.ts`：读写本地文件、写 metadata、处理 `desktop://` 路径。
- `fileSearchSrv.ts`：封装文件搜索模块。
- `contentSearchSrv.ts`：封装内容 grep 能力。
- `gatewayConnectionSrv.ts`：管理 device-gateway WebSocket 连接。

这些文件都 `import { ServiceModule } from './index'` 并 `extends ServiceModule`，说明它们共享同一种注入模式：先拿到 `app`，再从 `app` 里访问配置、存储、日志、工具管理器或路径信息。

## 运行/调用流程

1. `App` 启动时执行服务扫描，匹配 `apps/desktop/src/main/services/*Srv.ts`。
2. 扫描结果里的每个服务类都会被传给 `addService`。
3. `addService` 执行 `new ServiceClass(this)`，把当前 `App` 实例注入给服务。
4. 服务子类通过继承 `ServiceModule` 获得 `this.app`。
5. 之后具体业务方法再通过 `this.app` 读取状态或调用底层能力，例如：
   - `fileSrv.ts` 里用 `this.app.appStoragePath`
   - `gatewayConnectionSrv.ts` 里用 `this.app.storeManager`
   - `contentSearchSrv.ts` 里用 `this.app.toolDetectorManager`

换句话说，这个文件不负责“做事”，它负责把“服务做事时需要的上下文”统一接起来。

## 小白阅读顺序

1. 先看这个文件，理解 `ServiceModule` 只是一个基类。
2. 再看 `apps/desktop/src/main/core/App.ts` 里的服务加载逻辑，搞清楚为什么服务会被自动实例化。
3. 然后挑一个具体服务，比如 `fileSrv.ts`，观察它如何使用 `this.app`。
4. 最后回到 `IServiceModule`，理解它为什么是 `typeof ServiceModule`，而不是普通接口。

## 常见误区

1. 以为 `index.ts` 是“服务总入口”并导出了所有 service。实际上它只定义了公共基类，真正的服务文件是同目录下的 `*Srv.ts`。
2. 把 `IServiceModule` 当成实例接口。这里它更像“构造器类型”，因为 `App.ts` 需要 `new ServiceClass(this)`。
3. 忽略了文件命名规则。`App.ts` 通过 glob 扫描 `*Srv.ts`，所以新服务如果不按这个命名，可能不会被自动加载。
4. 误以为服务之间直接互相持有引用。根据当前片段推断，它们主要是通过 `App` 作为共享上下文间接协作，而不是服务互相直接依赖。
