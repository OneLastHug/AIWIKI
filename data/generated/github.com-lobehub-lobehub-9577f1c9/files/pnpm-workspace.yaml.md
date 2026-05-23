# 文件：pnpm-workspace.yaml

## 一句话定位
这是仓库的 pnpm 工作区总入口，负责告诉 pnpm 哪些目录属于同一个 monorepo、哪些依赖需要强制版本覆盖，以及哪些第三方包要走补丁或受限构建策略。根据当前片段推断，它是整个仓库依赖联动的基础配置之一。

## 它暴露/定义了什么
它定义了四类信息：`packages` 里的工作区范围，`onlyBuiltDependencies` 里允许在安装阶段执行构建的包，`overrides` 里的依赖版本强制收敛规则，以及 `patchedDependencies` 里本地补丁的映射。这里把 `packages/**`、根目录、`e2e`、`apps/desktop/src/main` 纳入同一工作区，意味着这些目录里的 `package.json` 会被 pnpm 统一管理。

## 谁调用它
真正“调用”它的是 pnpm 本身，以及所有依赖 pnpm 工作区图谱的命令，比如 `pnpm install`、`pnpm -r exec`、`pnpm --filter ...`、`pnpm run ...`。从根 `package.json` 可以看到，仓库大量脚本直接使用 pnpm，CI 里也反复执行 `pnpm install` 和 `pnpm install --frozen-lockfile`，所以这个文件会被安装、链接、过滤、递归执行等流程持续读取。根 `package.json` 里还有 `workspaces` 字段，但在这个仓库里，pnpm 主要还是以 `pnpm-workspace.yaml` 来决定工作区边界。

## 它调用谁
它本身不调用运行时代码，而是把规则下发给 pnpm 以及由 pnpm 管理的各个包。受它影响的对象主要是 `packages/**` 下的共享包、根项目、`e2e` 测试工程和 `apps/desktop/src/main`。另外，`patchedDependencies` 明确指向 `patches/@upstash__qstash.patch`，说明安装时还会读到这个补丁文件。`overrides` 则会影响所有间接依赖的解析结果，最终落到各个 `package.json` 的依赖树上。

## 核心流程
安装时，pnpm 先读取这个文件，扫描所有匹配的目录，找到其中的 `package.json`，把它们组装成一个工作区。随后，像 `workspace:*` 这类内部依赖会在工作区内互相链接，而不是去远端仓库拉包。接着，`overrides` 会把指定依赖统一压到固定版本，减少同名包在不同子包里的漂移。最后，`patchedDependencies` 会在安装阶段对指定包应用本地补丁，`onlyBuiltDependencies` 则限制只有少数包可以在安装时触发构建动作。这个流程决定了仓库能否稳定地在单一 lockfile 下工作。

## 关键函数的高层作用
这个文件没有函数，重点是几个配置项的高层作用。`packages` 负责定义“哪些目录算工作区成员”；`overrides` 负责把容易分叉的三方依赖收敛到同一版本；`patchedDependencies` 负责把上游缺陷或定制行为固定在仓库内；`onlyBuiltDependencies` 负责控制安装期构建面，减少不可控脚本执行。它们合在一起，保证内部包之间可以用 `workspace:*` 方式稳定互联。

## 修改风险
最常见的风险是工作区范围改错。比如新增包放在未被匹配的目录里，pnpm 就不会把它纳入 monorepo，`workspace:*` 依赖会失效。第二类风险是 `overrides` 改动过大，可能把某些子包需要的版本行为一起改掉，导致隐性兼容问题。第三类风险是补丁文件和上游版本脱节，安装虽然成功，但运行时行为已经不是预期。还有一个容易忽略的问题是，`pnpm-workspace.yaml` 和根 `package.json` 的 `workspaces` 配置如果长期不一致，工具链之间会出现认知分裂，表现为安装结果、过滤范围或递归脚本行为不一致。
