# 子系统：src/agents/sandbox

## 解决什么问题

`src/agents/sandbox` 负责给 agent 会话准备一个隔离运行环境，并把“模型看到的工作区”“容器或远端 shell 中的工作区”“宿主机真实文件系统”统一成可控的运行上下文。它解决的核心问题不是单纯启动 Docker，而是让 bash/exec、读写文件、浏览器控制、子会话继承、工具权限和清理管理都能围绕同一份 `SandboxContext` 工作。

这个子系统支持两类后端：默认的 `docker` 后端，以及通过 SSH 在远端机器上执行的 `ssh` 后端。Docker 后端会创建或复用容器，SSH 后端会把工作区上传到远端路径并通过远端 shell 执行命令。两者都被抽象为 `SandboxBackendHandle`，上层 agent 不需要直接判断“这是容器还是远端机器”。

另一个重要职责是文件桥接。agent 的读写/edit/apply_patch 类工具不能直接信任模型输入路径，也不能随意穿透容器挂载边界。因此 `SandboxFsBridge` 负责解析路径、校验读写权限、处理软链接/硬链接/rename 等危险操作，并根据后端选择本地 Docker bridge 或远端 shell bridge。

## 相关目录和文件

公开入口是 `src/agents/sandbox.ts`，它把配置解析、上下文创建、后端注册、容器管理、SSH、文件桥、工具策略等能力重新导出给上游使用。真正的实现集中在 `src/agents/sandbox/*`。

配置相关文件包括 `src/agents/sandbox/config.ts`、`src/agents/sandbox/types.ts`、`src/agents/sandbox/constants.ts`、`src/agents/sandbox/config-hash.ts`。其中 `config.ts` 从全局和 agent 级配置解析 `SandboxConfig`，合并 Docker、browser、SSH、prune、tools 等设置；`config-hash.ts` 用于判断运行时配置是否变化，影响容器是否需要重建。

运行时创建路径在 `src/agents/sandbox/context.ts`。它负责判断当前 session 是否需要 sandbox，准备 workspace，调用后端 factory，写入 registry，按需启动 browser sandbox，并组装 `SandboxContext`。

后端层由 `src/agents/sandbox/backend.ts`、`src/agents/sandbox/docker-backend.ts`、`src/agents/sandbox/ssh-backend.ts`、`src/agents/sandbox/docker.ts`、`src/agents/sandbox/ssh.ts` 组成。`backend.ts` 是注册表，内置注册 `docker` 与 `ssh`；具体创建和命令执行分别在 Docker/SSH 文件中。

文件系统桥接在 `src/agents/sandbox/fs-bridge.ts`、`src/agents/sandbox/remote-fs-bridge.ts`、`src/agents/sandbox/fs-paths.ts`、`src/agents/sandbox/fs-bridge-path-safety.ts`、`src/agents/sandbox/fs-bridge-mutation-helper.ts`。它们共同处理路径映射、挂载解析、安全检查和原子式变更计划。

生命周期和管理相关文件包括 `src/agents/sandbox/registry.ts`、`src/agents/sandbox/manage.ts`、`src/agents/sandbox/prune.ts`、`src/agents/sandbox/workspace.ts`、`src/agents/sandbox/workspace-mounts.ts`、`src/agents/sandbox/browser.ts`。安全策略相关文件包括 `src/agents/sandbox/validate-sandbox-security.ts`、`src/agents/sandbox/tool-policy.ts`、`src/agents/sandbox/runtime-status.ts`。

## 核心对象

`SandboxConfig` 是配置聚合对象，包含 `mode`、`backend`、`scope`、`workspaceAccess`、`workspaceRoot`、`docker`、`ssh`、`browser`、`tools`、`prune`。它由 `resolveSandboxConfigForAgent` 解析，来源是全局默认配置和 agent 级配置。

`SandboxContext` 是运行时核心对象，包含 `enabled`、`backendId`、`sessionKey`、`workspaceDir`、`agentWorkspaceDir`、`workspaceAccess`、`runtimeId`、`containerName`、`containerWorkdir`、`docker`、`tools`、`browser`、`fsBridge`、`backend`。上游工具拿到它后，就能知道命令该在哪个 workdir 执行，文件工具该通过哪个 bridge 访问。

`SandboxBackendHandle` 是后端抽象。它至少提供运行时 id、workdir、环境变量、`buildExecSpec` 和 `runShellCommand`；SSH 后端还会提供 `finalizeExec` 与远端 shell bridge 所需的远端路径信息。Docker 后端通过 `docker exec` 生成命令；SSH 后端通过 `ssh` 命令和远端脚本执行。

`SandboxFsBridge` 是文件工具边界。它提供 `resolvePath`、`readFile`、`writeFile`、`mkdirp`、`remove`、`rename`、`stat` 等操作。Docker bridge 能返回宿主侧 `hostPath`，远端 bridge 通常只返回容器/远端路径语义，不暴露本地宿主路径。

`SandboxToolPolicyResolved` 与 `SandboxToolPolicy` 负责工具 allow/deny 规则。`resolveSandboxToolPolicyForAgent` 会合并默认、全局、agent 级策略，`isToolAllowed` 和 `classifyToolAgainstSandboxToolPolicy` 用于运行前判断工具是否可用。

## 运行流程

典型入口是上游 runner 调用 `resolveSandboxContext`。它先用 `resolveSandboxRuntimeStatus` 判断当前 `sessionKey` 对应的 agent 是否处于 sandbox 模式；如果不需要 sandbox，直接返回 `null`。如果需要，则调用 `resolveSandboxConfigForAgent` 得到完整配置。

随后 `context.ts` 会准备 workspace。`scope` 决定目录复用粒度：`session`、`agent` 或 `shared`。`workspaceAccess` 决定真实工作目录是 agent 原工作区还是 sandbox 工作区：`rw` 可直接使用 agent workspace，`ro` 或 `none` 会创建隔离目录，并在需要时同步 skills 到 sandbox workspace。这里也会解析 Docker 用户，尽量让容器内 uid/gid 匹配工作区权限。

然后系统通过 `requireSandboxBackendFactory` 找到后端。Docker 后端调用 `ensureSandboxContainer` 创建或复用容器；SSH 后端解析远端 runtime 路径、建立 SSH 会话并确保远端工作区可用。后端创建完成后，`updateRegistry` 会记录 runtime id、backend id、session scope、镜像或目标信息，用于后续 list/remove/prune 和配置匹配检查。

如果启用了 browser sandbox，`resolveSandboxContext` 会确认后端声明 `capabilities.browser === true`，再调用 `ensureSandboxBrowser` 创建浏览器容器和 bridge/noVNC 地址。最后组装 `SandboxContext`，并优先使用后端自带 `createFsBridge`，否则用默认 `createSandboxFsBridge`。

命令执行时，上游 bash 工具会使用 `backend.buildExecSpec` 生成实际 argv。文件工具则走 `fsBridge`，由 bridge 把模型输入路径解析到允许的挂载根，再执行安全读写或 mutation 命令。

## 上下游依赖

上游主要来自 `src/agents/pi-embedded-runner/run/attempt.ts`、`src/agents/bash-tools.shared.ts`、`src/agents/openclaw-tools.ts`、`src/agents/pi-tools.read.ts`、`src/agents/apply-patch.ts`、`src/agents/subagent-spawn.ts`、`src/agents/acp-spawn.ts`、`src/agents/system-prompt.ts`。这些模块分别消费 sandbox 上下文、exec spec、文件桥、运行状态和提示词中的 sandbox 信息。

对外暴露到插件 SDK 的一部分在 `src/plugin-sdk/agent-harness-runtime.ts`，包括 `resolveSandboxContext` 和部分 sandbox bind/path helper。根据当前片段推断，这是为了让 agent harness 或插件测试场景能复用核心 sandbox 语义，但生产插件不应绕过 SDK 直接依赖内部实现。

下游依赖包括 Docker CLI、SSH 命令、OpenClaw 配置类型、agent scope 配置、browser profile/auth、skills 同步、路径安全工具和 registry 文件。Docker 安全配置还依赖 `validateSandboxSecurity` 对 bind mount、network、seccomp、apparmor 等进行限制。

## 修改时最容易踩的坑

第一，不能把 Docker 假设写死到上层。当前目录已经有 `docker` 和 `ssh` 两个后端，新增逻辑应优先走 `SandboxBackendHandle`、`runShellCommand`、`createFsBridge`，不要在通用路径里直接拼 `docker exec`。

第二，路径安全不能只做字符串 normalize。`fs-bridge` 需要处理挂载根、只读/可写边界、软链接、硬链接、rename 目标和命令前后 recheck。绕开 `SandboxFsPathGuard`、`fs-bridge-mutation-helper` 或 `remote-fs-bridge` 的 pinned parent 逻辑，容易造成越权写入。

第三，`workspaceAccess`、`scope` 和 `workspaceRoot` 会共同影响真实目录。`shared` scope 会忽略 agent 级部分配置，`rw` 与 `ro/none` 的 workspace 选择不同；改配置解析时要同步考虑 `context.ts` 的 workspace 布局和 registry 生命周期。

第四，browser sandbox 不是普通附属字段。只有后端声明支持 browser 时才能启用，且需要 browser auth、bridge URL、noVNC URL、网络配置和独立镜像 hash。改 Docker 配置 hash 或 browser create 参数时，要考虑旧容器是否应重建。

第五，工具策略分层容易误判。allow/deny 有默认、全局、agent 来源，上游提示词和运行时阻断都依赖同一套结果。修改 `tool-policy.ts` 时要同时检查 `runtime-status.ts` 和相关测试。

第六，SSH 后端没有本地 `hostPath` 语义。依赖 `hostPath` 的逻辑通常只适用于 Docker 或本地 bridge；远端 bridge 需要通过远端 mutation 脚本完成读写。

## 推荐阅读顺序

1. 先读 `src/agents/sandbox.ts`，了解公开 API 边界和哪些对象被上游使用。
2. 再读 `src/agents/sandbox/types.ts`，建立 `SandboxConfig`、`SandboxContext`、`SandboxBackendHandle`、`SandboxFsBridge` 的概念模型。
3. 接着读 `src/agents/sandbox/config.ts` 和 `src/agents/sandbox/runtime-status.ts`，理解什么时候启用 sandbox、配置如何合并。
4. 然后读 `src/agents/sandbox/context.ts`，把 session、workspace、backend、browser、registry 串成完整流程。
5. 后端实现按需读：Docker 方向看 `src/agents/sandbox/docker-backend.ts`、`src/agents/sandbox/docker.ts`；SSH 方向看 `src/agents/sandbox/ssh-backend.ts`、`src/agents/sandbox/ssh.ts`、`src/agents/sandbox/remote-fs-bridge.ts`。
6. 最后读文件安全链路：`src/agents/sandbox/fs-bridge.ts`、`src/agents/sandbox/fs-paths.ts`、`src/agents/sandbox/fs-bridge-path-safety.ts`、`src/agents/sandbox/fs-bridge-mutation-helper.ts`，并对照相关 `*.test.ts` 理解边界条件。
