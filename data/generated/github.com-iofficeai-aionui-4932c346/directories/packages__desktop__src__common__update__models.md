# 子系统：packages/desktop/src/common/update/models

## 解决什么问题

这个目录负责“更新域”的数据模型层，核心目标是把版本号、强制升级阈值、更新类型判断等逻辑收拢到一个可复用的模型里，而不是散落在 UI、进程层或接口处理代码中。就当前片段看，这里主要处理的是版本信息的标准化、校验和语义判断，避免上层直接拿字符串做比较而引入错误。

`VersionInfo` 这一层把“当前版本 `current`、最新版本 `latest`、最低强制版本 `minimumRequired`、发布说明 `releaseNotes`”封装成一个对象，并提供一组面向更新场景的派生判断，例如是否有可用更新、是否必须强更、更新是 major/minor/patch 还是没有变化。

## 相关目录和文件

当前目录下可确认的文件只有 `VersionInfo.ts`。它是这个子系统的核心模型文件，也是当前能直接看到的唯一实现。

从命名和代码职责推断，`packages/desktop/src/common/update/` 很可能是整个更新功能的公共基础层，模型层之外通常还会有请求更新信息、发起检查、展示提示、执行升级等配套代码。根据当前片段推断，这个目录会被 `process` 侧的更新逻辑以及 `renderer` 侧的更新提示界面共同依赖。

## 核心对象

`VersionUpdateType` 是一个很轻量的类型别名，限定更新类型只能是 `'major' | 'minor' | 'patch' | 'none'`，这让上层不需要自己解析 diff 结果。

`VersionInfoJSON` 是外部输入/输出的结构体，表示从接口、IPC 或持久化层拿到的原始数据。它保留了 JSON 的松散性，其中 `minimumRequired` 和 `releaseNotes` 都是可选字段。

`VersionInfo` 是这个目录最重要的对象。它的关键特点有三点：

1. 通过 `create` 和 `fromJSON` 统一入口做版本合法性校验。
2. 通过 `toJSON` 输出稳定的数据结构，便于跨层传递。
3. 通过 `isUpdateAvailable`、`isForced`、`getUpdateType()`、`isBreakingUpdate()` 等方法，把业务判断封装为可读的领域语义。

它还提供 `withLatestVersion()` 和 `afterUpgrade()` 这类“构造新状态”的方法，说明这个模型不仅用于读取，也用于派生下一步状态。

## 运行流程

根据当前片段推断，典型流程是这样的：

1. 更新模块拿到原始版本数据，通常来自远端检查结果或本地缓存。
2. 调用 `VersionInfo.fromJSON()` 或 `VersionInfo.create()` 构造实例。
3. 在构造时，`current`、`latest`、`minimumRequired` 都会经过 `semver.valid()` 校验，非法版本号会直接抛错。
4. 上层用 `isUpdateAvailable` 判断是否存在新版本，用 `isForced` 或 `requiresForceUpdate()` 判断是否必须升级。
5. `getUpdateType()` 通过 `semver.diff()` 把更新归类为 major/minor/patch/none。
6. 如果升级完成，`afterUpgrade()` 会生成一个新的 `VersionInfo`，把当前版本推进到新版本。
7. 如果远端版本变化但当前状态要保持不变，`withLatestVersion()` 可只更新 latest 和 release notes。

这套流程的价值在于：比较规则集中，状态转换显式，上层只消费结果，不重复实现 semver 逻辑。

## 上下游依赖

上游依赖主要有两类。第一类是 `semver` 库，这个模型的大部分语义判断都建立在它的 `valid`、`gt`、`lt`、`gte`、`compare` 和 `diff` 上。第二类是更新数据来源，可能是接口响应、IPC 消息或本地配置；当前片段没有直接看到来源文件，但 `VersionInfoJSON` 明确说明它面向的是外部输入。

下游依赖则是所有需要展示或执行更新决策的模块。根据当前片段推断，通常包括：
- 更新检查服务，用来判断有没有新版本；
- 安装/升级流程，用来判断是否强制升级；
- 版本提示 UI，用来展示更新类型、版本差异和 release notes；
- 可能的本地状态记录，用来在升级后刷新 `current`。

## 修改时最容易踩的坑

第一，版本号校验很严格。`create()` 和 `withLatestVersion()`、`afterUpgrade()` 都会调用 `assertValidVersion()`，传入非 semver 格式会直接抛异常。改调用方时，不能默认“看起来像版本号就行”。

第二，`minimumRequired` 是强更逻辑的关键字段。它不是简单的附加信息，而是会影响 `isForced`、`satisfiesMinimumVersion()` 和 `isBreakingUpdate()` 的结果。改接口字段名或空值语义时要特别小心。

第三，`getUpdateType()` 对 `premajor`、`preminor`、`prepatch`、`prerelease` 做了归类。如果上层拿这个结果做 UI 文案或策略分支，改动归类规则会影响展示和流程。

第四，`toJSON()` 会把 `undefined` 字段原样带出去。若下游是严格的序列化或协议层，可能需要确认空值和缺失字段的处理方式。

## 推荐阅读顺序

1. 先看 `packages/desktop/src/common/update/models/VersionInfo.ts`，理解版本模型本身。
2. 再顺着搜索 `VersionInfo` 的使用点，确认它被谁构造、谁消费。
3. 然后看更新检查和更新提示相关目录，理解这个模型怎样驱动 UI 与流程。
4. 最后回头看 `semver` 相关判断，确认 major/minor/patch 与强更规则的边界。

如果只记一个结论，这个目录不是“存版本号”的地方，而是“把更新语义变成稳定领域对象”的地方。
