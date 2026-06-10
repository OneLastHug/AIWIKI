# 目录：packages/desktop/src/renderer/pages/cron

## 它负责什么

这个目录是 renderer 侧“定时任务 / Cron 调度”功能的集中区，核心职责不是单一页面，而是一整套围绕 scheduled task 的前端实现：任务列表展示、任务详情、创建与编辑、状态提示、执行结果入口，以及启动时对 Cron 数据的修复处理。根据当前片段推断，它更像一个功能域目录，而不是纯粹的路由页目录，因为里面同时放了页面、公共组件、数据 hook 和启动修复逻辑。

从引用关系看，这里还和全局应用启动流程有联动：`packages/desktop/src/renderer/main.tsx` 会在应用 bootstrap 时调用 `repairAllCronJobTimeZonesOnce`，说明这个目录不仅服务于 UI，还承担了一部分“启动即校正”的业务初始化责任。

## 直接子目录地图

这个目录下的直接子目录和文件比较清晰，主要分成两块：

- `ScheduledTasksPage/`：主页面区域，负责把 Cron 任务作为一个完整页面呈现出来。
  - `index.tsx`：页面入口，负责列表/操作区的组合。
  - `TaskDetailPage.tsx`：任务详情视图。
  - `CreateTaskDialog.tsx`：新建或编辑任务的弹窗。
  - `CronStatusTag.tsx`：任务状态标签。
  - `jobAgentMeta.ts`：任务相关的元数据配置，通常用于描述 agent 与任务的映射。
- `components/`：更偏通用的局部组件。
  - `CronJobManager.tsx`：任务管理容器级组件，通常负责编排列表、筛选、动作触发。
  - `CronJobIndicator.tsx`：状态或运行提示类的小组件。
- 顶层文件：
  - `index.ts`：目录出口，通常用于统一导出该功能域的公开 API。
  - `cronUtils.ts`：Cron 格式化、时间计算、展示文本拼装等公共工具。
  - `useCronJobs.ts`：数据获取和状态同步的 hook。
  - `repairCronJobTimeZone.ts`：时区修复逻辑，偏启动维护用途。

## 关键入口

如果只抓入口，优先看这几个位置：

1. `ScheduledTasksPage/index.tsx`  
   这是这个目录最像“用户真正看到的页面入口”的文件。结合命名和引用关系，它大概率负责把任务列表、操作按钮、状态展示、创建弹窗串起来，是 Cron 功能的主 UI 入口。

2. `index.ts`  
   这是目录级出口。一般情况下，外部模块不会直接深挖 `ScheduledTasksPage/` 里面的内部文件，而是通过这里拿到页面或工具的统一导出。

3. `useCronJobs.ts`  
   这是主流程的数据入口。页面层不是直接拼接口调用，而是通过 hook 拉取任务列表、刷新状态、绑定操作结果，因此它通常决定页面数据如何流动。

4. `repairCronJobTimeZone.ts`  
   这是另一个关键入口，但它属于启动时入口，不是页面入口。`main.tsx` 已明确引用它，说明应用初始化阶段会主动检查并修复缺失的 schedule timezone。

## 主流程位置

主流程大致可以分成“展示流程”和“启动修复流程”两条线：

1. 展示流程  
   `ScheduledTasksPage/index.tsx` 负责页面编排；`useCronJobs.ts` 提供任务数据；`cronUtils.ts` 负责把 Cron 表达式、下一次执行时间、状态文案转成可读信息；`components/` 里的 `CronJobManager.tsx`、`CronJobIndicator.tsx` 提供可复用的操作和展示部件。  
   也就是说，页面不是单文件闭环，而是“页面入口 + 数据 hook + 工具函数 + 局部组件”拼出来的。

2. 启动修复流程  
   `repairCronJobTimeZone.ts` 负责扫描 jobs，发现 `kind === 'cron'` 且缺少 `tz` 的任务后补齐时区。`main.tsx` 在应用启动时触发它，这意味着这个目录里有一段跨页面的维护逻辑，目标是避免老数据或迁移数据在 Cron 运行时出错。

3. 用户操作闭环  
   从命名推断，创建任务会走 `CreateTaskDialog.tsx`，查看详情会走 `TaskDetailPage.tsx`，任务状态显示会走 `CronStatusTag.tsx`，管理动作则集中在 `CronJobManager.tsx` 和页面入口中。这个闭环通常覆盖“查看 - 创建 - 调整 - 运行 - 修复”几步。

## 推荐阅读顺序

如果你要快速建立心智模型，建议按这个顺序看：

1. `index.ts`：先确认对外暴露了什么。
2. `ScheduledTasksPage/index.tsx`：看页面主编排。
3. `useCronJobs.ts`：看数据怎么进来、怎么刷新。
4. `cronUtils.ts`：看 Cron 文案和时间展示规则。
5. `ScheduledTasksPage/CreateTaskDialog.tsx`、`TaskDetailPage.tsx`、`CronStatusTag.tsx`：补齐交互细节。
6. `components/CronJobManager.tsx`、`components/CronJobIndicator.tsx`：看复用组件边界。
7. `repairCronJobTimeZone.ts`：最后看启动修复逻辑，它比较独立，但很关键。

## 常见误区

- 误以为这是单纯的页面目录。实际上这里同时包含页面、共享组件、hook、工具和 bootstrap 修复逻辑。
- 只看 `ScheduledTasksPage/index.tsx` 就以为看完了。真正的数据流和状态更新通常在 `useCronJobs.ts` 和 `cronUtils.ts` 里。
- 忽略 `repairCronJobTimeZone.ts`。这个文件不是 UI 逻辑，但它被 `main.tsx` 直接调用，说明它影响整个 Cron 功能的数据可用性。
- 把 `components/` 当成随便堆放的 UI 小件。根据命名，它们更像被页面和其他子页共享的功能组件，不是纯展示碎片。
- 只按“页面路由”理解这个目录。它更像一个功能域边界，里面的职责横跨显示层、数据层和初始化修复层。
