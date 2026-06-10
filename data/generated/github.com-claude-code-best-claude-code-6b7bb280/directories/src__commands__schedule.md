# 目录：src/commands/schedule

## 它负责什么

`src/commands/schedule` 负责一个本地 JSX slash command：管理“云端定时触发器”（scheduled remote agent triggers / cloud cron）。它不是本地进程里的 cron 调度器实现，而是 Claude 订阅认证平面上的 `/v1/code/triggers` HTTP API 的命令层封装：用户在 REPL 中输入命令后，这里解析参数、调用远端 triggers API、把结果渲染成 Ink 组件，并通过 `onDone` 给消息流返回系统提示。

这个目录目前的用户可见主命令名是 `/triggers`，别名是 `/cron`。虽然目录名叫 `schedule`，文件内也有 `/schedule` 的历史提示，但 `src/commands/schedule/index.ts` 明确说明：primary name 已从 `schedule` 改为 `triggers`，目的是避免和上游 bundled skill `src/skills/bundled/scheduleRemoteAgents.ts` 的 `/schedule` 冲突。也就是说，学习这个目录时应把它理解为“远端 triggers 管理命令”，而不是普通的 `/schedule` 技能入口。

它支持的动作包括：`list`、`get ID`、`create CRON PROMPT`、`update ID FIELD VALUE`、`delete ID`、`run ID`、`enable ID`、`disable ID`。其中 `create` 使用 5 字段 cron 表达式，命令层做轻量结构校验，语义校验主要交给服务端或 `src/utils/cron.js`。

## 直接子目录地图

该目录只有一个直接子目录：

`src/commands/schedule/__tests__`：就近测试目录，覆盖命令 metadata、参数解析、API 包装和 `callSchedule` 主处理函数。它的存在说明此目录被当作一个相对独立的命令模块维护，核心边界是“slash command 参数到 API 调用和 UI 输出”的转换。

目录根部的关键文件是：

`src/commands/schedule/index.ts`：命令注册对象，声明 command 类型、名称、别名、描述、参数提示、可用性和懒加载入口。

`src/commands/schedule/launchSchedule.tsx`：命令执行主流程，导出 `callSchedule`，根据解析后的 action 分发到不同 API 函数，并返回 `ScheduleView`。

`src/commands/schedule/parseArgs.ts`：纯参数解析模块，把用户输入字符串转换为 `ScheduleArgs` 联合类型。

`src/commands/schedule/triggersApi.ts`：远端 triggers API 的薄 HTTP 客户端，负责鉴权头、base URL、错误分类、重试和具体 HTTP 方法。

`src/commands/schedule/ScheduleView.tsx`：Ink 展示层，根据不同 mode 渲染列表、详情、创建成功、更新成功、删除、运行、启停和错误状态。

## 关键入口

最靠近全局命令系统的入口是 `src/commands/schedule/index.ts`。它导出默认对象 `scheduleCommand: Command`，类型是 `local-jsx`，`name` 为 `triggers`，`aliases` 为 `['cron']`，`availability` 限制为 `['claude-ai']`，并通过 `load` 懒加载 `./launchSchedule.js`，返回 `{ call: m.callSchedule }`。

全局注册点在 `src/commands.ts`。该文件 import `scheduleCommand`，并把它放进 `COMMANDS` 数组。因此 REPL 的 slash command 发现、过滤和执行链路并不是从 `src/commands/schedule` 自己启动，而是由全局 `getCommands()` 一类机制收集后，再在用户输入 slash command 时调用。

真正的运行入口是 `callSchedule`，定义在 `src/commands/schedule/launchSchedule.tsx`。它接收 `LocalJSXCommandCall` 约定的 `(onDone, _context, args)`，先记录 analytics 事件，再调用 `parseScheduleArgs(args ?? '')`。如果参数无效，直接 `onDone` 返回 usage 和错误原因；如果有效，就按 action 进入对应分支。

## 主流程位置

主流程集中在 `src/commands/schedule/launchSchedule.tsx`，结构是线性的 action 分发：

`list` 分支调用 `listTriggers()`，成功后渲染 `ScheduleView` 的 `list` mode；空列表时也会给出 “No scheduled triggers found.” 的系统提示。

`get` 分支调用 `getTrigger(id)`，成功后渲染 `detail` mode，展示状态、cron 人类可读描述、agent、next run、last run 和 prompt。

`create` 分支先用 `parseCronExpression(cron)` 做进一步 cron 校验，再调用 `createTrigger({ cron_expression: cron, prompt })`。成功后展示 `created` mode。

`update` 分支把用户传入的 `field/value` 转换为 `UpdateTriggerBody`。支持字段是 `enabled`、`cron_expression` 或 `cron`、`prompt`、`agent_id`。其中 `enabled` 会把 `'true'` 或 `'1'` 转成布尔 true，其它值会转成 false。然后调用 `updateTrigger(id, body)`。

`delete`、`run`、`enable`、`disable` 分别调用 `deleteTrigger(id)`、`runTrigger(id)`、`updateTrigger(id, { enabled: true })`、`updateTrigger(id, { enabled: false })`。所有 API 分支都采用类似错误处理：把异常转成 message，记录 `tengu_schedule_failed`，通过 `onDone` 输出系统消息，并返回 `ScheduleView` 的 `error` mode。

HTTP 细节集中在 `src/commands/schedule/triggersApi.ts`。它通过 `prepareApiRequest()` 获取 OAuth access token 和 organization UUID，通过 `assertSubscriptionBaseUrl(triggersBaseUrl())` 防止把 OAuth 凭据发送到非订阅 API host，然后加入 `anthropic-beta: ccr-triggers-2026-01-30` 和 `x-organization-uuid`。API 方法映射是：`GET /v1/code/triggers`、`GET /v1/code/triggers/{id}`、`POST /v1/code/triggers`、`POST /v1/code/triggers/{id}`、`DELETE /v1/code/triggers/{id}`、`POST /v1/code/triggers/{id}/run`。注意 update 使用 POST，不是 PATCH。

展示逻辑在 `src/commands/schedule/ScheduleView.tsx`。它只负责渲染，不发请求。`TriggerRow` 和详情视图都会调用 `cronToHuman(trigger.cron_expression, { utc: true })`，并把 `next_run`、`last_run`、`created_at` 转成 `toLocaleString()`。根据当前片段推断，服务端返回的时间字段应是可被 `Date` 解析的字符串，依据是这些字段被直接传入 `new Date(...)`。

## 推荐阅读顺序

1. 先读 `src/commands/schedule/index.ts`，明确这个目录暴露的是 `/triggers` 和 `/cron`，不是当前主命令名 `/schedule`。
2. 再读 `src/commands.ts` 中 `scheduleCommand` 的注册位置，理解它如何进入全局 slash command 列表。
3. 阅读 `src/commands/schedule/parseArgs.ts`，掌握用户输入会被归一化成哪些 `ScheduleArgs` action。
4. 阅读 `src/commands/schedule/launchSchedule.tsx`，这是最重要的业务流程文件，能看到每个 action 如何落到 API 调用和 UI mode。
5. 阅读 `src/commands/schedule/triggersApi.ts`，理解它和 Claude 订阅认证、beta header、错误分类、5xx 重试之间的关系。
6. 最后看 `src/commands/schedule/ScheduleView.tsx` 和 `src/commands/schedule/__tests__`，前者帮助理解终端输出，后者帮助确认命令行为边界。

## 常见误区

不要把目录名 `schedule` 等同于用户命令 `/schedule`。当前注册名是 `/triggers`，`/cron` 是别名；源码中的 `/schedule` usage 文案和注释更多是历史命名残留或语义描述。

不要把这个目录和内置工具 `CronCreate`、`CronDelete`、`CronList` 混为一谈。那些工具在 `packages/builtin-tools/src/tools/ScheduleCronTool`，并通过 `src/tools.ts` 进入工具系统；本目录是 slash command，调用的是远端 `/v1/code/triggers` API。两者都和 cron/schedule 有关，但入口、权限模型和持久化位置不同。

不要以为 `parseArgs.ts` 会完整校验 cron 语义。它的 `isValidCronExpression` 只检查是否正好 5 个字段；`launchSchedule.tsx` 还会调用 `parseCronExpression`，但最终语义和订阅权限仍依赖服务端响应。

不要把 update 当作 REST 常见的 PATCH。`triggersApi.ts` 的注释和实现都强调 update 是 `POST /v1/code/triggers/{trigger_id}`。

不要忽略鉴权和 host guard。`triggersApi.ts` 在构造 headers 前后处理 OAuth token、organization UUID 和订阅 base URL 校验，说明这个命令依赖登录状态和 Claude Pro/Max/Team 等订阅能力；403 会被分类成 “Subscription required”。
