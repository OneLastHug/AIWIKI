# 目录：security

## 它负责什么

`security` 是 OpenClaw 仓库内用于承载“可提交、可阻断回归”的安全扫描规则与配套工具的目录。它不是完整的安全响应中心，也不是漏洞研究素材库；维护者侧的 advisory triage、探测器生成提示、候选规则实验材料等，根据当前片段说明，放在公开仓库之外。这个目录保留的是已经适合随仓库提交、可被本地和 CI 复用的稳定产物。

从职责上看，`security` 主要服务 OpenGrep 规则包生命周期：维护者先在外部或本地规则源目录中验证候选规则，再通过脚本编译进仓库内的 `security/opengrep/precise.yml`。提交后的规则会被元数据检查、OpenGrep 校验、本地 wrapper 和 GitHub workflow 使用，作为 PR diff 扫描和手动全仓扫描的安全回归防线。

这里的核心设计取向是“低噪声、可追溯、能阻断”。也就是说，进入 `precise.yml` 的规则应当能捕获它所针对的漏洞行为或确认过的变体，并且每条规则都带有来源信息，方便从扫描命中反查 advisory、review 记录或其他来源标识。

## 直接子目录地图

`security/` 当前结构很小，直接子目录只有 `security/opengrep/`。

`security/README.md` 是目录总览，说明安全工具目录的边界、规则生命周期、本地运行方式、CI 运行方式，以及编辑、静默、删除规则时应遵循的原则。

`security/opengrep/` 是实际规则包与工具脚本所在位置。它包含 `security/opengrep/README.md`、`security/opengrep/precise.yml`、`security/opengrep/compile-rules.mjs`、`security/opengrep/check-rule-metadata.mjs`，以及规则源组织目录 `security/opengrep/rules/`。

`security/opengrep/rules/` 是规则源的归档式区域。当前可见的规则路径包括 `security/opengrep/rules/openclaw-policy/no-raw-http2-connect.yml`。不过根据 `security/README.md` 和 `security/opengrep/README.md` 的描述，仓库真正用于运行的主规则包是已编译的 `security/opengrep/precise.yml`，而不是让调用方逐个扫描每个源规则文件。

## 关键入口

第一个入口是 `security/README.md`。读者如果只是想理解这个目录为什么存在、怎样和 CI 接上、规则进入仓库前需要满足什么质量要求，应先看它。它给出了目录边界，也明确了 `scripts/run-opengrep.sh` 是本地和 CI 扫描的统一 wrapper。

第二个入口是 `security/opengrep/README.md`。它更聚焦 OpenGrep super-config，解释 `precise.yml` 的定位、规则命名方式、元数据字段、重新编译流程、本地校验命令，以及为什么运行 OpenGrep 时使用 `--no-strict` 和 `--no-git-ignore`。

第三个入口是 `security/opengrep/precise.yml`。这是提交到仓库的 compiled rulepack，也就是扫描时真正引用的规则配置。根据当前片段推断，它是 CI 和本地 wrapper 的稳定输入，规则源发生变化后应通过编译脚本更新它，而不是手工长期维护它。

第四个入口是 `security/opengrep/compile-rules.mjs`。它负责从 `--rules-dir` 指定的目录递归读取 `.yml` / `.yaml`，解析顶层 `rules` 数组，要求规则带有 `metadata.ghsa` 或 `metadata.advisory-id`，补齐或校验 advisory 相关元数据，重写 rule id，并把新规则追加或替换到 `precise.yml`。

第五个入口是 `security/opengrep/check-rule-metadata.mjs`。它读取默认的 `security/opengrep/precise.yml`，检查每条规则是否有可追溯的 metadata，例如 `advisory-id` / `ghsa`、`advisory-url`、`detector-bucket`、`source-rule-id`，并确保 rule id 的来源前缀与元数据一致。

## 主流程位置

规则生产主流程位于 `security/opengrep/compile-rules.mjs`。流程可以概括为：解析命令行参数，定位 `--rules-dir`，递归列出 YAML 文件，跳过 `precise.yml`，读取每个文件的顶层 `rules`，对每条 rule 调用重写逻辑，生成带来源前缀的新 rule id，并注入标准 metadata。之后脚本会与既有 `precise.yml` 合并，默认只追加新 id；只有传入 `--replace-precise` 时才按输入规则源重建整个 precise rulepack。

规则元数据校验主流程位于 `security/opengrep/check-rule-metadata.mjs`。它的主线是读取 rulepack，解析 YAML，遍历 `rules`，逐条验证 metadata 对象、rule id 形状、GHSA 格式、advisory URL 字段、`detector-bucket` 是否为 `precise`，以及 `source-rule-id` 是否存在。这个脚本对应仓库里的 `pnpm check:opengrep-rule-metadata` 检查，属于提交前和 CI 中都应保持稳定的规则 provenance 防线。

扫描执行主流程不在 `security` 目录内，而是在 `scripts/run-opengrep.sh`。根据 `security/README.md`，这个 wrapper 会统一处理路径、排除规则、输出格式，并引用 `security/opengrep/precise.yml`。CI 侧还有 `.github/workflows/opengrep-precise.yml` 和 `.github/workflows/opengrep-precise-full.yml`：前者用于 PR diff 扫描，后者用于维护者手动触发的全仓扫描。路径排除的单一来源是仓库根目录 `.semgrepignore`。

## 推荐阅读顺序

1. 先读 `security/README.md`，建立目录边界：这里保存的是已提交规则包和校验运行工具，不是完整的漏洞调查工作区。

2. 再读 `security/opengrep/README.md`，理解 `precise.yml` 为什么是 compiled super-config，以及规则 id、metadata、校验命令的约定。

3. 接着读 `security/opengrep/compile-rules.mjs`，重点看参数解析、`listYamlFiles`、`readRuleFile`、`rewriteRule`、合并输出这些位置，理解规则如何从源 YAML 变成仓库内的 compiled rule。

4. 然后读 `security/opengrep/check-rule-metadata.mjs`，重点看 `validateRuleMetadata`，理解为什么规则必须携带 durable provenance，而不是只靠文件名或外部表格追踪来源。

5. 最后看 `security/opengrep/precise.yml` 和 `security/opengrep/rules/`。前者用于了解当前实际运行的规则形态，后者用于观察源规则组织方式。只做概览时不需要逐条解释每个 rule。

## 常见误区

不要把 `security/opengrep/precise.yml` 当成普通手写配置长期直接编辑。文档明确建议优先修改源规则 YAML，再运行 `security/opengrep/compile-rules.mjs` 重新生成，因为编译过程会统一处理 id、metadata、重复规则和 OpenGrep 校验。

不要把进入 `precise.yml` 的规则理解成“越多越好”。这里的规则定位是 blocking PR-diff check 和手动全仓 audit，要求低噪声。探索性、容易误报、依赖运行时状态或产品策略才能判断的问题，不适合直接进入 precise rulepack。

不要忽略 metadata。这个目录的一个核心约束就是规则必须可追溯。`security/opengrep/check-rule-metadata.mjs` 会强制检查来源 id、advisory 字段、bucket 和 source rule id；缺少这些信息的规则即使语法能跑，也不符合仓库约定。

不要以为扫描范围只由 OpenGrep 默认行为决定。根据当前片段，仓库使用 `scripts/run-opengrep.sh` 统一运行，并且 `.semgrepignore` 是跳过测试、fixtures、mocks 等路径的单一来源；同时 `--no-git-ignore` 会避免某些有意义源码因为 `.gitignore` 被漏扫。

不要把 `security` 目录和外部 advisory 处置流程混为一谈。这里保存的是 durable artifacts：规则包、编译脚本、元数据检查脚本和说明文档。维护者调查、候选规则生成、敏感 advisory 工作流根据当前片段推断并不在这个公开目录中。
