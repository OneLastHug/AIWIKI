# 目录：src/commands/buddy

## 它负责什么
`src/commands/buddy` 负责把 `/buddy` 这条 slash command 接入到 CLI 的命令体系里。这个目录本身不承载 companion 的核心算法，而是负责“命令注册 + 参数分流 + 调度执行”：

1. `index.ts` 定义 `/buddy` 作为一个 `local-jsx` 命令，并决定它是否在当前状态下可见。
2. `buddy.ts` 实现命令被触发后的具体行为：`/buddy off`、`/buddy on`、`/buddy pet`，以及无参数时的孵化或展示 companion。
3. 真正的 companion 数据、渲染和反应逻辑都交给相邻的 `src/buddy` 模块，目录本身只是入口层。

根据当前片段推断，这个目录的设计目标是把 buddy 功能保持成一个可按 feature flag 裁切的独立命令，而不是把逻辑散落在主输入流程里。

## 直接子目录地图
这个目录下面没有子目录，只有两个文件：

- `src/commands/buddy/index.ts`：命令定义文件，负责注册、隐藏条件和延迟加载。
- `src/commands/buddy/buddy.ts`：命令执行文件，负责实际的 `/buddy` 行为。

也就是说，这里是一个很薄的命令包装层，不是一个多层业务目录。真正需要理解的扩展面在 `src/buddy`。

## 关键入口
最关键的入口有三个：

- `src/commands/buddy/index.ts`  
  定义 `name: 'buddy'`、`type: 'local-jsx'`、`immediate: true`，并通过 `load: () => import('./buddy.js')` 延迟加载实现文件。
- `src/commands/buddy/buddy.ts`  
  导出 `call(...)`，这是命令的实际执行入口。
- `src/commands.ts`  
  在命令总表里通过 `feature('BUDDY')` 条件加载 `./commands/buddy/index.js`，说明 buddy 是可裁剪功能。
- `src/utils/processUserInput/processSlashCommand.tsx`  
  这里统一处理 `local-jsx` 命令：先 `load()`，再调用模块的 `call(...)`，如果返回 JSX 就交给 UI 层展示。

## 主流程位置
从用户输入到 companion 结果，大致链路是：

1. 用户输入 `/buddy`。
2. `processSlashCommand.tsx` 识别到这是 `local-jsx` 命令。
3. 它动态加载 `src/commands/buddy/buddy.ts`。
4. `buddy.ts` 读取当前 companion 状态：
   - `off`：写入全局配置，静音 companion；
   - `on`：取消静音；
   - `pet`：触发宠物动作、更新 `companionPetAt`、触发 reaction；
   - 无参数：如果已有 companion，返回 `CompanionCard` JSX；如果没有，就生成种子、抽取物种、写入存档并输出孵化文案。
5. 如果返回了 JSX，REPL 会把它作为本地面板渲染出来；如果只是文本结果，则写入 transcript。

这条链路的重点不是算法，而是“命令 -> 状态更新 -> UI 组件”的装配关系。真正的 companion 生态还依赖 `src/buddy/companion.ts`、`src/buddy/CompanionCard.tsx`、`src/buddy/companionReact.ts`、`src/buddy/useBuddyNotification.tsx` 等相邻模块。

## 推荐阅读顺序
1. `src/commands/buddy/index.ts`  
   先看命令是怎么注册和隐藏的。
2. `src/commands/buddy/buddy.ts`  
   再看具体分支：`off`、`on`、`pet`、孵化、展示。
3. `src/commands.ts` 中的 `feature('BUDDY')` 段落  
   理解这个命令是怎么被装进总命令表的。
4. `src/utils/processUserInput/processSlashCommand.tsx` 的 `local-jsx` 分支  
   搞清楚命令返回 JSX 时如何进入 UI。
5. `src/buddy/companion.ts`、`src/buddy/types.ts`、`src/buddy/CompanionCard.tsx`  
   再去看 companion 的数据模型和渲染细节。

## 常见误区
1. 把 `src/commands/buddy` 当成 companion 核心实现目录。  
   实际上它只是命令入口，核心逻辑在 `src/buddy`。

2. 以为 `/buddy` 一定始终可见。  
   `index.ts` 通过 `isBuddyLive()` 控制隐藏，且 `src/commands.ts` 还受 `feature('BUDDY')` 影响。

3. 只看 `buddy.ts` 就以为理解了完整流程。  
   它只处理命令分支，真正的状态保存、反应生成、卡片展示都在别处。

4. 忽略 `local-jsx` 命令机制。  
   `/buddy` 不是普通文本命令，它会在 REPL 内直接渲染组件，这决定了它的执行路径和 transcript 行为。
