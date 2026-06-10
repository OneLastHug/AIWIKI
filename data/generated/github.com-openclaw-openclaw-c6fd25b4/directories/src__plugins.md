# 目录：src/plugins

## 它负责什么

`src/plugins` 是 OpenClaw 插件系统在 core 侧的控制面与运行面汇合处。根据 `src/plugins/AGENTS.md`，这个目录明确负责 plugin discovery、manifest validation、loading、registry assembly 和 contract enforcement。换句话说，它不是某个具体插件的业务实现目录，而是 core 如何发现插件、读取插件元数据、校验插件清单、安装外部插件、装配运行时注册表、暴露宿主能力、执行插件 runtime 的基础设施层。

这里的核心边界是“manifest-first”和“控制面 / 运行面分离”。控制面处理发现、manifest 解析、配置校验、setup/onboarding 提示、activation planning；运行面才处理真正的插件执行。目录里大量文件以 `manifest-*`、`installed-plugin-index-*`、`activation-*`、`loader-*`、`registry-*`、`runtime-*`、`provider-*`、`web-*`、`hooks-*` 命名，正好对应这些职责。

需要注意，`src/plugins` 仍然是 core 代码。具体官方或外部插件通常在 `extensions/` 或安装目录中，不能把这里理解为“插件源码集合”。这里更像插件平台、插件宿主和插件契约层。

## 直接子目录地图

`src/plugins/runtime` 是插件运行时 façade 和 gateway/runtime 绑定区域。这里有 `src/plugins/runtime/index.ts`、`runtime-config.ts`、`runtime-agent.ts`、`runtime-channel.ts`、`runtime-llm.runtime.ts`、`runtime-tasks.ts` 等文件，负责向插件提供 `PluginRuntime` 能力，例如 config、agent、channel、events、logging、media、taskflow、LLM、model auth、gateway nodes/subagent 等。

`src/plugins/contracts` 是契约测试和边界守卫集中区。文件名显示它覆盖 plugin SDK、manifest、registry、provider、runtime seams、host hooks、setup wizard、package boundaries 等契约。它不是生产主流程入口，而是防止 core 与插件、SDK、bundled plugin 之间边界漂移。

`src/plugins/compat` 放兼容注册相关的小型模块，例如 `registry.ts`、`types.ts`。从命名看，它服务于旧接口或兼容记录的集中管理，而不是鼓励新路径继续扩展兼容层。

`src/plugins/capability-runtime-vitest-shims` 是测试 shim 区，包含 `config-runtime.ts`、`media-runtime.ts`、`speech-core.ts`，用于 Vitest 下替代或隔离部分 capability runtime。

`src/plugins/test-helpers` 放插件测试夹具和帮助器，例如 archive、filesystem、managed npm plugin、registry jiti mocks 等。它服务测试搭建，不是线上流程。

`src/plugins/contracts/inventory`、`src/plugins/contracts/test-helpers` 是契约测试的辅助分区；根据当前片段推断，它们分别承载契约清单或契约测试夹具，依据是目录名和 `contracts` 下大量 `*.contract.test.ts` 文件。

## 关键入口

`src/plugins/loader.ts` 是最重要的装载入口之一。它导入 discovery、manifest registry、config-state、registry、runtime、channel setup、installed index、SDK alias、module loader cache 等模块，并定义 `PluginLoadOptions`、`PluginLoadResult`。从这些导入关系可以看出，loader 负责把“发现到的候选插件”变成可用的 `PluginRegistry`，同时处理启用状态、缓存、setup-only channel plugin、manifest registry、runtime options、gateway handlers、tool discovery 等装载选项。

`src/plugins/registry.ts` 是注册表构建入口。它接收插件注册调用，把插件声明的能力落到 core 可查询的数据结构里。当前片段显示它处理 command、channel、provider、embedding provider、memory、hooks、HTTP route、gateway method、interactive handler、agent harness、context engine、detached task lifecycle 等注册面。

`src/plugins/runtime/index.ts` 是 runtime façade 入口。它通过 `createRuntime*` 系列函数组装 `PluginRuntime`，并大量使用 lazy import，例如 TTS、media understanding、LLM、model auth。这里体现了 `AGENTS.md` 要求的“冷路径不急切导入重 runtime surface”。

`src/plugins/manifest.ts` 是 manifest 类型、读取、校验和规范化相关入口。片段中可见 `PLUGIN_MANIFEST_FILENAME`、manifest load cache、channel config、model catalog、provider endpoint、activation capability 等类型定义。它决定插件清单能表达什么。

`src/plugins/install.ts` 是安装入口，处理 npm、git、archive、plugin dir/file 等安装场景。它校验 `openclaw.extensions`、plugin id、host version、security scan、npm integrity、peer dependency link 等安装安全与一致性问题。

`src/plugins/discovery.ts`、`manifest-registry.ts`、`installed-plugin-index.ts`、`plugin-registry-snapshot.ts`、`plugin-metadata-snapshot.ts` 是理解“插件从哪里来、当前有哪些、快照如何表达”的关键支撑入口。

## 主流程位置

插件控制面主流程大致从发现开始：`src/plugins/discovery.ts` 找到候选插件；`src/plugins/manifest.ts` 和 `src/plugins/manifest-registry.ts` 读取并组织 manifest；`src/plugins/config-state.ts`、`activation-source-config.ts`、`activation-planner.ts` 判断配置、默认启用、显式启用和 activation 状态；随后 `src/plugins/loader.ts` 按 `PluginLoadOptions` 载入必要模块。

进入装配阶段后，`src/plugins/loader.ts` 会围绕 `src/plugins/registry.ts` 创建或填充 `PluginRegistry`。插件通过 SDK 暴露的注册 API 申明命令、provider、channel、hook、tool、HTTP route、setup、memory、web/search/extractor 等能力；registry 负责把这些能力存成 core 能消费的结构。`src/plugins/loader-records.ts`、`loader-cache-state.ts`、`plugin-module-loader-cache.ts`、`loader-provenance.ts` 则负责记录装载结果、缓存、错误和来源追踪。

运行面主流程集中在 `src/plugins/runtime` 和根部的 `src/plugins/runtime.ts`。`src/plugins/runtime/index.ts` 创建插件可调用的 runtime surface；`runtime/gateway-bindings.ts`、`runtime/gateway-request-scope.ts` 把 gateway 场景下的请求作用域、nodes/subagent 能力接进 runtime；`runtime/runtime-registry-loader.ts`、`runtime/standalone-runtime-registry-loader.ts` 从不同运行环境装载 registry。根据当前片段推断，gateway 启动时会准备真实的 subagent/nodes runtime，而普通插件 runtime 默认拿到的是会抛出清晰错误的 unavailable façade，依据是 `createLateBindingSubagent` 和 `createLateBindingNodes` 的实现注释。

安装流程独立但会影响后续发现：`src/plugins/install.ts` 负责把外部包落到可发现位置；`install-paths.ts`、`install-source-info.ts`、`install-security-scan.ts`、`installed-plugin-index-*` 管安装路径、安全扫描、来源信息和索引记录。安装不是每次运行时请求都重新发生，符合这里“metadata process-stable”的设计原则。

## 推荐阅读顺序

先读 `src/plugins/AGENTS.md`，掌握边界原则：manifest-first、控制面 / 运行面分离、避免冷路径急切加载、不要给 bundled plugin 私设后门。

第二步读 `src/plugins/types.ts`、`src/plugins/runtime/types.ts`、`src/plugins/manifest.ts`，先建立插件定义、runtime surface、manifest schema 的数据模型。

第三步读 `src/plugins/discovery.ts`、`src/plugins/manifest-registry.ts`、`src/plugins/config-state.ts`、`src/plugins/activation-planner.ts`，理解插件在未执行 runtime 前如何被发现、筛选、启用和计划激活。

第四步读 `src/plugins/loader.ts` 和 `src/plugins/registry.ts`。这是从“metadata 和模块入口”到“可用注册表”的主桥梁，读完基本能理解 core 如何接收插件能力。

第五步读 `src/plugins/runtime/index.ts` 以及 `src/plugins/runtime` 下的 gateway、config、agent、channel、task、LLM 相关文件，补齐插件真正执行时能调用哪些宿主能力。

最后按兴趣读专项：安装看 `src/plugins/install.ts` 和 `installed-plugin-index-*`；provider 看 `provider-*`、`providers.ts`；web 能力看 `web-search-*`、`web-fetch-*`、`web-content-*`；hook 看 `hooks.ts`、`host-hooks.ts`、`hook-runner-global.ts`；契约保障看 `src/plugins/contracts`。

## 常见误区

不要把 `src/plugins` 当作插件业务目录。具体插件实现通常不在这里；这里维护的是插件平台和宿主契约。

不要跳过 manifest 直接理解 runtime。OpenClaw 的插件设计强调 manifest-first，很多发现、配置、setup、activation 决策应在不执行插件 runtime 的情况下完成。

不要认为 registry 只是一个简单 map。`src/plugins/registry.ts` 同时承载 provider、channel、hooks、gateway methods、commands、memory、tools、HTTP routes、agent harness 等多类能力注册，是插件能力进入 core 的汇合点。

不要把 bundled plugin 的便利路径当作外部插件也能使用的私有 API。`src/plugins/AGENTS.md` 明确要求 loader 行为对齐公开 Plugin SDK 和 manifest contracts，不能创建只有内置插件能用的后门。

不要在请求热路径里重新扫描文件、重读 manifest 或反复 discovery。这里的设计假设 gateway plugin metadata 在进程运行期间稳定，变化应通过重启、安装、reload 或 doctor 这类明确生命周期处理。

不要忽略 `src/plugins/contracts`。这个目录看起来像测试，但它实际定义了插件系统的边界红线；修改 loader、registry、SDK surface、manifest 或 runtime seam 时，契约测试往往比单个功能测试更能说明风险。
