# 目录：optional-skills/mlops/saelens/references

## 它负责什么

`optional-skills/mlops/saelens/references` 是 `optional-skills/mlops/saelens` 这个可选技能的参考资料目录，用来补充 `SKILL.md` 中的 SAELens 使用说明。它不包含可执行代码、脚本或模板，而是以 Markdown 文档形式沉淀 Sparse Autoencoder（SAE）相关的 API 速查、教程流程和概念说明。

从邻近上下文看，`optional-skills/mlops/saelens/SKILL.md` 是技能的主入口，负责告诉 Hermes 这个 skill 何时使用、如何安装 `sae-lens`、核心概念是什么，以及常见工作流如何组织。`references` 目录则承担“展开阅读材料”的角色：当主文档只给出工作流概要时，这里进一步说明 `SAE`、`LanguageModelSAERunnerConfig`、`SAETrainingRunner`、`ActivationsStore`、`HookedSAETransformer` 等对象的用途，以及预训练 SAE 分析、自定义 SAE 训练、特征归因、steering、ablation、跨 prompt 特征比较等流程。

这个目录的内容偏学习资料，不是项目运行时的导入模块。根据当前片段推断，它主要服务于模型在调用 skill 时的上下文补充，帮助使用者围绕 SAELens 完成机制可解释性实验，而不是改变 Hermes 自身的工具注册、CLI、gateway 或插件行为。

## 直接子目录地图

该目录当前没有直接子目录，只有三份 Markdown 参考文件：

`optional-skills/mlops/saelens/references/README.md` 是目录级概览，说明 references 下包含哪些材料，并给出安装、基本用法、核心概念、关键指标和可用预训练 SAE 的入口视角。它相当于这个参考资料包的索引页。

`optional-skills/mlops/saelens/references/api.md` 是 API 速查文档，按类和对象组织内容。重点覆盖 `SAE` 的加载、属性和核心方法，`SAEConfig` 的配置字段，`LanguageModelSAERunnerConfig` 的训练参数，`SAETrainingRunner` 的训练调用，`ActivationsStore` 的激活批处理，以及 `HookedSAETransformer` 与 TransformerLens 的集成方式。后半部分还概览了 `standard`、`gated`、`topk`、`jumprelu` 等 SAE 架构和部分工具函数。

`optional-skills/mlops/saelens/references/tutorials.md` 是任务式教程集合，按实验目标组织。它从加载和分析预训练 SAE 开始，随后进入自定义训练、特征归因与 steering、特征 ablation、跨 prompt 比较等实践流程。它更像“照着做”的实验路线，而不是 API 字典。

## 关键入口

最直接的入口是 `optional-skills/mlops/saelens/references/README.md`。它先解释这个 references 目录的范围，再指向 `api.md` 和 `tutorials.md`。如果只想快速判断这个目录“有什么”，应该先读它。

从 skill 层面看，真正的上游入口是 `optional-skills/mlops/saelens/SKILL.md`。该文件在 `Reference Documentation` 一节中引用 references 下的文档，并在更早的章节中定义了 SAELens 的用途：训练和分析 Sparse Autoencoders，用稀疏、可解释特征分解语言模型激活。也就是说，`references` 不是独立技能入口，而是 `SKILL.md` 的支撑材料。

从使用路径看，关键 API 入口集中在 `api.md` 中的这些对象：`SAE.from_pretrained()`、`SAE.load_from_disk()`、`sae.encode()`、`sae.decode()`、`LanguageModelSAERunnerConfig`、`SAETrainingRunner.run()`、`ActivationsStore.from_sae()`。这些名字构成了 SAELens 常见操作的骨架：加载 SAE、拿到模型激活、编码为稀疏特征、解码重构、配置训练、执行训练、收集激活批次。

从教程入口看，`tutorials.md` 的 `Tutorial 1` 是最适合入门的实践入口，因为它把 `HookedTransformer`、`SAE.from_pretrained()`、`model.run_with_cache()`、`sae.encode()`、`sae.decode()` 串成了一条最小可运行链路。

## 主流程位置

主流程不在这个目录中实现，而是在文档中以代码片段描述。整体可以分成两条主线。

第一条是“预训练 SAE 分析流程”，主要出现在 `SKILL.md` 的 `Workflow 1`、`references/README.md` 的 `Basic Usage`、以及 `references/tutorials.md` 的 `Tutorial 1`。流程是：用 `HookedTransformer.from_pretrained()` 加载语言模型，用 `SAE.from_pretrained()` 加载匹配层的 SAE，通过 `model.run_with_cache()` 获取 hook 点激活，再用 `sae.encode()` 得到稀疏特征，用 top-k 或激活计数观察每个 token 的主要特征，最后用 `sae.decode()` 检查重构质量。这个流程用于特征发现、稀疏性观察和解释性分析。

第二条是“自定义 SAE 训练流程”，主要出现在 `SKILL.md` 的 `Workflow 2`、`references/api.md` 的 `LanguageModelSAERunnerConfig` 与 `SAETrainingRunner`、以及 `references/tutorials.md` 的 `Tutorial 2`。流程是：选择 `model_name`、`hook_name`、`hook_layer`、`d_in`，设置 `architecture`、`d_sae` 或 expansion factor，再配置 `lr`、`l1_coefficient`、`l1_warm_up_steps`、`training_tokens`、`dataset_path`、batch 相关参数、日志与 checkpoint，最后通过 `SAETrainingRunner(cfg).run()` 执行训练。训练后的质量判断依赖 `l0`、`ce_loss_score`、`mse_loss`、`l1_loss`、`dead_features` 等指标。

扩展分析流程则集中在 `references/tutorials.md` 后半部分：特征归因通过 `W_dec @ W_U` 估算特征到目标 token logit 的贡献；steering 通过把某个 feature direction 加到 residual stream 上影响生成；ablation 通过编码激活、清零指定 feature、再解码来观察预测概率变化；跨 prompt 比较通过收集多个语义相近 prompt 的 feature activations，寻找稳定激活的共同特征。

## 推荐阅读顺序

建议先读 `optional-skills/mlops/saelens/SKILL.md`，因为它解释了这个 skill 的使用边界：什么时候应该用 SAELens，什么时候应该直接用 TransformerLens 或其他干预工具。读完后再进入 references，不容易把 API 速查误认为完整实验设计。

第二步读 `optional-skills/mlops/saelens/references/README.md`。它用很短的篇幅给出目录索引、安装方式、基本使用代码、Sparse Autoencoder 的结构、训练损失、关键指标和预训练 SAE 类型，适合作为上下文定位。

第三步读 `optional-skills/mlops/saelens/references/tutorials.md` 的前两个教程。`Tutorial 1` 建立预训练 SAE 分析的最小闭环，`Tutorial 2` 建立自定义训练的配置和保存流程。对大多数学习者来说，先理解这两条路径，比先逐项看 API 参数更有效。

第四步再读 `optional-skills/mlops/saelens/references/api.md`。这时可以把它当作字典使用：遇到 `SAEConfig`、`LanguageModelSAERunnerConfig`、`ActivationsStore`、`HookedSAETransformer` 或架构选择问题时，再回到对应章节查字段和方法。

最后阅读 `tutorials.md` 的归因、steering、ablation、跨 prompt 比较部分。这些内容依赖前面的激活获取、特征编码和重构理解，适合作为进一步做机制解释实验时的参考。

## 常见误区

一个常见误区是把 `references` 当成 Hermes 插件或工具实现目录。当前目录没有 Python 模块、没有注册函数、没有入口脚本；它只是 `saelens` optional skill 的 Markdown 参考资料。真正的 skill 元数据和主说明在 `optional-skills/mlops/saelens/SKILL.md`。

第二个误区是只看 `api.md` 就开始训练 SAE。`api.md` 列出了大量配置参数，但训练质量取决于 hook 点、模型维度、扩展倍率、稀疏惩罚、warm-up、数据集、batch、训练 token 数和 dead feature 处理策略。更合理的路线是先读 `tutorials.md` 的训练流程，再回到 `api.md` 查参数。

第三个误区是把 `sae.encode()` 得到的高激活 feature 直接等同于“已解释概念”。文档中的教程展示了如何找到 top features，但解释性仍需要跨样本验证、重构质量检查、特征归因、ablation 或 steering 这类后续实验支撑。单次 prompt 的 top-k 激活只能作为候选线索。

第四个误区是忽略模型、hook 点和 SAE 的匹配关系。预训练 SAE 通常绑定具体 `release`、`sae_id`、层号和 hook 名，例如 residual stream 的某一层。如果模型和 SAE 对不上，`d_in`、激活位置或语义空间都可能不匹配，后续特征分析也就没有可靠意义。

第五个误区是只追求更稀疏。`l1_coefficient` 提高会降低 L0，但也可能牺牲重构和 CE loss recovery；过强稀疏还可能导致 dead features 或解释质量下降。目录中的资料反复把 `L0`、`CE Loss Score`、`Dead Features`、`Explained Variance` 放在一起看，说明训练评价需要多指标平衡。
