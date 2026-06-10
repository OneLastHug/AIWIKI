# 目录：src/commands/skill-store

## 它负责什么

`src/commands/skill-store` 是一组围绕 `/skill-store` 的本地 JSX 命令实现，职责是让用户浏览、查询、创建、删除和安装远程 skills。根据当前片段推断，它面向的是 Anthropic skill marketplace 这一类后端能力，因为 `index.tsx` 的命令说明、`skillsApi.ts` 的接口注释，以及 `launchSkillStore.tsx` 的流程都在围绕 `/v1/skills` 这条 API 线展开。

这个目录的定位很清晰：它不是一个单纯的 UI 组件目录，也不是纯 API 层，而是一个完整的命令闭环。命令定义负责挂载和延迟加载，参数解析负责把用户输入拆成动作，执行器负责调用 API 并落盘，视图负责把结果渲染成终端界面，测试则覆盖这条链路的关键入口。

## 直接子目录地图

这个目录下没有再细分的业务子目录，唯一直接子目录是 `__tests__`。从文件名看，它主要用来验证四个层次：

- `index.test.ts`：命令定义是否正确挂载
- `parseArgs.test.ts`：命令参数语法是否正确
- `launchSkillStore.test.ts`：主执行流程是否正确
- `api.test.ts`：技能 API 封装是否符合预期

因此，`src/commands/skill-store` 的结构更像“单命令模块 + 测试目录”，而不是多层功能包。业务实现文件都平铺在目录根部，说明这个功能簇的边界已经被收敛在一个命令入口里。

## 关键入口

最重要的入口是 `index.tsx`。它导出 `skillStoreCommand`，声明了命令名 `skill-store`、别名 `ss` 和 `cloud-skills`、参数提示、可见性判断，以及真正的懒加载入口 `load()`。这里的关键点是：`load()` 只在需要时才动态导入 `launchSkillStore.js`，把真正的执行逻辑延后到命令触发时再加载。

第二层入口是 `launchSkillStore.tsx`。这是命令的主调度点，导出 `callSkillStore`，接收 `args` 后先走 `parseSkillStoreArgs()`，然后按动作分支处理 `list`、`get`、`versions`、`version`、`create`、`delete`、`install` 七类操作。

第三层入口是 `parseArgs.ts`。它定义了命令语法和返回类型 `SkillStoreArgs`，是主流程前的第一道门。这里决定了用户输入如何被解释成具体动作，也决定了错误提示长什么样。

第四层入口是 `skillsApi.ts`。它是所有远程读写操作的 HTTP 封装，统一围绕 `/v1/skills?beta=true` 及其子路径工作。根据代码注释，这里还强制要求 `beta=true`，并且在请求前做了 workspace host 保护和 API key 准备。

最后是 `SkillStoreView.tsx`。它不是业务决策点，但它承载了各个分支的终端输出，是命令结果的呈现入口。

## 主流程位置

主流程集中在 `launchSkillStore.tsx`，可以把它理解成这条命令的控制中枢。典型路径是：

`index.tsx` 注册命令  
`launchSkillStore.tsx` 作为执行器被调用  
`parseArgs.ts` 解析出动作  
`skillsApi.ts` 请求远端 skills 接口  
`SkillStoreView.tsx` 按模式渲染结果

其中最核心的分支是 `install`。它不是简单把单条 skill 内容写入本地，而是先判断是否指定版本：  
- 指定版本时，直接拉取 `getSkillVersion(id, version)`  
- 未指定版本时，先取 skill 元信息，再取版本列表，排序后选最新版本  
- 最后把正文写到 `getClaudeConfigHomeDir()/skills/<safeName>/SKILL.md`

这说明安装流程不仅依赖远端 API，也涉及本地配置目录写入。换句话说，这个目录把“云端 skill 市场”和“本地 skill 文件系统”连起来了。

另外，`launchSkillStore.tsx` 还嵌入了 `logEvent()` 埋点，所以它的主流程同时承担了行为追踪和失败归因。错误时会统一进入 `SkillStoreView` 的 `error` 模式。

## 推荐阅读顺序

1. 先看 `index.tsx`，确认命令是怎么注册和懒加载的。  
2. 再看 `parseArgs.ts`，把命令语法和动作枚举记住。  
3. 然后看 `launchSkillStore.tsx`，这是最重要的流程中心。  
4. 接着看 `skillsApi.ts`，理解所有远端读写如何落到 `/v1/skills`。  
5. 最后看 `SkillStoreView.tsx`，把每种动作对应的输出形式串起来。  
6. 有余力再看 `__tests__` 下的测试，验证你的理解是否和预期一致。

## 常见误区

一个常见误区是把这个目录当成纯展示层。实际上它的核心是命令控制流，视图只是最后一步。

第二个误区是忽略 `index.tsx` 的懒加载设计。真正的业务逻辑不在注册文件里，而是在 `launchSkillStore.tsx`，所以只看命令定义会误判整体复杂度。

第三个误区是以为 `skillsApi.ts` 只是普通请求封装。根据当前片段推断，它实际上还承担了认证准备、host 保护、重试和错误分类，这些都影响命令行为。

第四个误区是低估安装分支。`install` 不是“下载一个文件”，而是“选定版本、提取正文、规范化目录名、写入本地 `SKILL.md`”，它同时连接了远端版本语义和本地技能目录结构。
