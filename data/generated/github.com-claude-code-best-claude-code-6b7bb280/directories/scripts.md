# 目录：scripts

## 它可能负责什么
这个目录包含 17 个被抽样展示的文件。请从文件命名、子目录和关键源码入手理解它在项目中的职责。

## 文件列表节选
```text
scripts/vite-plugin-feature-flags.ts
scripts/check-bundle-integrity.ts
scripts/probe-subscription-endpoints.ts
scripts/verify-autofix-pr.ts
scripts/post-build.ts
scripts/smoke-test-commands.ts
scripts/run-parallel.mjs
scripts/setup-chrome-mcp.mjs
scripts/dump-prompt.ts
scripts/dev.ts
scripts/postinstall.cjs
scripts/defines.ts
scripts/rcs.ts
scripts/probe-local-wiring.ts
scripts/dev-debug.ts
scripts/rcs-ccb.sh
scripts/vite-plugin-import-meta-require.ts
```

## 小白阅读建议
- 先看项目说明、`index` 入口、路由、业务服务、类型/结构定义等文件。英文文件名只是代码命名，不要求先理解英文语义。
- 暂时跳过构建产物、测试快照和重复样板。
- 如果这里是业务目录，优先找“谁调用它”和“它调用谁”。
