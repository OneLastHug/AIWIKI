# 目录：docs/prds/settings/skills

## 它负责什么

`docs/prds/settings/skills` 是设置模块下“Skills / 技能”能力的 PRD 文档目录，角色是描述用户在设置页中如何管理、查看或配置技能相关能力。它不是运行时代码目录，也不是技能实现目录；它更像产品需求地图中的一个节点，用来把“设置页里的技能管理”从更大的 `docs/prds/settings` 范围中拆出来。

从当前目录结构看，`docs/prds/settings` 下按设置页功能域拆分为 `about`、`display`、`llm_providers`、`skills`、`system`。因此 `skills` 在这里应当和“关于页”“显示设置”“模型提供商设置”“系统设置”同级，关注的是设置界面中与技能中心、技能列表、启用状态、安装或配置入口有关的产品需求，而不是会话中使用技能的完整交互。会话输入框、ACP 会话里调用技能的行为，在邻近文档中更可能由 `docs/prds/conversations/acp/skills.md` 承担。

根据当前片段推断，这个目录的边界是：说明设置页如何呈现和管理技能；不负责定义每个具体 Skill 的内容、执行协议、后端加载机制，也不负责对话过程中技能被注入、选择、触发后的完整链路。依据是 `docs/prds/settings/skills` 只出现在设置 PRD 树下，而会话域另有 `docs/prds/conversations/acp/skills.md`，测试目录中也存在 `tests/e2e/docs/skills-hub`、`tests/e2e/helpers/skillsHub.ts` 这类面向“skills hub”的资料。

## 直接子目录地图

当前 `docs/prds/settings/skills` 没有直接子目录。目录下只看到一个入口文档：

- `docs/prds/settings/skills/README.md`：本目录的主文档，承担技能设置页 PRD 的总入口。它应当描述功能目标、页面范围、主要交互、数据状态和验收口径。

从目录分层看，当前没有继续拆出 `install`、`marketplace`、`detail`、`permissions`、`runtime` 等子目录。这意味着在 overview 层面阅读时，不需要逐层展开；先把它当成一个单页 PRD 节点即可。如果后续技能设置变复杂，可能会按“技能列表”“技能详情”“安装/更新”“权限/来源”“失败状态”继续拆分，但这属于根据当前片段推断，不是现有目录事实。

## 关键入口

本目录的关键入口是 `docs/prds/settings/skills/README.md`。阅读它时应优先确认三件事：第一，技能设置页到底面向什么用户任务，例如浏览已安装技能、发现可用技能、启用或禁用技能、查看技能说明、跳转到技能详情；第二，它和会话页技能使用之间的关系，例如设置页是否只管理全局状态，会话页是否读取这些状态来生成技能菜单；第三，它是否对“Skills Hub”这类概念做了命名约束。

邻近入口包括 `docs/prds/settings/display/README.md`、`docs/prds/settings/llm_providers/README.md`、`docs/prds/settings/system/README.md`、`docs/prds/settings/about/README.md`。这些文件用于理解设置页整体的信息架构：`skills` 不是孤立页面，而是 Settings 下的一项配置域。若要理解技能在对话中的实际使用入口，应再看 `docs/prds/conversations/acp/skills.md`，因为 ACP 会话文档更接近消息输入、技能快捷注入、会话上下文和发送流程。

测试和实现侧的线索包括 `tests/e2e/docs/skills-hub`、`tests/e2e/helpers/skillsHub.ts`、`tests/unit/skills/useAssistantSkillsIntegration.dom.test.ts`。这些路径不属于本目录，但它们说明“skills hub / assistant skills integration”可能是后续验证和实现映射的重要落点。

## 主流程位置

在 PRD 层，本目录的主流程位置大致是：用户进入 Settings，然后进入 Skills 区域，在这里查看技能集合，理解技能状态，并进行管理操作。主流程不应从具体技能执行开始，而应从“设置页如何组织技能能力”开始。也就是说，`docs/prds/settings/skills/README.md` 应该回答“用户在哪里找到技能管理”“列表里展示什么”“用户可以做哪些操作”“操作结果如何影响后续会话”这些问题。

在产品流程上，可以把它放在两个链路之间：

第一条是设置链路：`docs/prds/settings` 下的页面导航进入 `docs/prds/settings/skills`。这里关心设置页菜单、页面标题、空状态、加载状态、错误状态、权限或来源提示等。

第二条是会话链路：设置里的技能状态会影响会话侧能力，尤其是 ACP 会话中输入框附近的技能快捷入口或上下文注入。对应文档位置是 `docs/prds/conversations/acp/skills.md`。根据当前片段推断，设置页负责“管理技能”，会话页负责“使用技能”；两者之间应通过技能元数据、启用状态、助手配置或 workspace / conversation 上下文发生关联。

如果追实现代码，不能只在 `docs/prds/settings/skills` 内找。需要从设置页面路由、skills hub 组件、助手技能集成 hook、E2E helper 几个方向定位。但就本任务的 overview 来说，主流程位置仍然以 PRD 目录关系为准：`docs/prds/settings/skills/README.md` 是需求入口，`docs/prds/conversations/acp/skills.md` 是下游使用场景补充。

## 推荐阅读顺序

1. 先读 `docs/prds/settings/skills/README.md`，建立技能设置页的范围感：它讲的是管理页、入口页，还是完整技能中心。
2. 再读 `docs/prds/settings/display/README.md`、`docs/prds/settings/llm_providers/README.md`、`docs/prds/settings/system/README.md`，理解 Settings 模块的通用页面结构、设置项表达方式和跨页面一致性。
3. 接着读 `docs/prds/conversations/acp/skills.md`，把“设置中管理技能”和“会话中使用技能”连起来，避免把两个场景混成一个页面。
4. 如果要继续落到测试和实现，可再看 `tests/e2e/docs/skills-hub`、`tests/e2e/helpers/skillsHub.ts`、`tests/unit/skills/useAssistantSkillsIntegration.dom.test.ts`，这些路径更适合验证功能行为和集成边界。
5. 最后再回到 `docs/prds/settings/skills/README.md`，检查 PRD 是否覆盖了入口、状态、操作反馈、异常场景和与会话侧联动的说明。

## 常见误区

一个常见误区是把 `docs/prds/settings/skills` 当成技能运行时目录。它不是 Skill 脚本、插件、prompt 模板或执行器的位置；它只是设置页技能能力的产品文档目录。真正的执行逻辑、集成 hook、E2E helper 或会话注入逻辑，应在应用源码和测试目录中寻找。

第二个误区是把“设置页技能管理”和“会话页技能调用”写在同一个文档里。设置页应关注管理、状态和配置；会话页应关注选择、注入、展示和发送链路。当前仓库已经在 PRD 树中把 settings 和 conversations 分开，`docs/prds/conversations/acp/skills.md` 的存在也提示这两个场景需要分层描述。

第三个误区是过度展开每个技能。这个目录目前没有子目录，也没有按具体技能拆分的结构，因此 overview 文档不应逐个解释 Skill。更合适的粒度是说明 Skills Hub 或 Skills 设置页承载什么、从哪里进入、影响哪些下游流程。

第四个误区是忽略 Settings 的整体一致性。`skills` 与 `about`、`display`、`llm_providers`、`system` 同级，说明它应该服从设置页统一的信息架构、状态表达和交互风格，而不是设计成完全独立的功能岛。

第五个误区是把测试线索当成 PRD 事实。`tests/e2e/docs/skills-hub`、`tests/e2e/helpers/skillsHub.ts` 能提示实现和验证方向，但如果 `docs/prds/settings/skills/README.md` 没有明确写出某个交互，就应标注为“根据当前片段推断”，不要把测试路径里的命名直接等同于最终产品需求。
