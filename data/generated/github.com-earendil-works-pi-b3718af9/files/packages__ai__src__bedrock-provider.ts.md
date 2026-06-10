# 文件：packages/ai/src/bedrock-provider.ts
## 一句话定位
这是 `packages/ai` 里给 Amazon Bedrock 提供的“导出适配层”，本身不实现模型调用逻辑，只把 `./providers/amazon-bedrock.ts` 里的 `streamBedrock` 和 `streamSimpleBedrock` 重新封装成一个标准模块对象 `bedrockProviderModule`，方便统一注册、延迟加载和测试注入。

## 它暴露/定义了什么
这个文件只暴露一个常量：`bedrockProviderModule`。它的结构很简单，包含两个方法名：
- `streamBedrock`
- `streamSimpleBedrock`

这两个方法都直接来自 `./providers/amazon-bedrock.ts`。  
根据当前片段推断，它的存在目的不是增加业务能力，而是把 Bedrock provider 变成和其他 provider 一样的“模块形态”，便于外层用统一接口处理。

## 谁调用它
最直接的调用方是 `packages/ai/src/providers/register-builtins.ts` 这一套注册逻辑。那里有 `loadBedrockProviderModule()` 和 `setBedrockProviderModule()` 两条路径：
- 正常运行时，`loadBedrockProviderModule()` 通过动态导入 `./amazon-bedrock.ts` 后，把 `streamBedrock`、`streamSimpleBedrock` 包装成统一的 `LazyProviderModule`
- 测试或特殊场景下，`setBedrockProviderModule()` 可以注入一个替代模块，绕过真实 Bedrock 实现

因此，这个文件更像是 Bedrock provider 的稳定入口对象，而不是直接被业务代码逐个引用的实现层。

## 它调用谁
它只调用 `./providers/amazon-bedrock.ts`，而且是静态导入：
- `streamBedrock`
- `streamSimpleBedrock`

除此之外没有自己的控制流、状态管理或 I/O。真正和 AWS SDK、认证、region 解析、请求体组装、流式事件处理打交道的是 `amazon-bedrock.ts`。

## 核心流程
1. 从 `./providers/amazon-bedrock.ts` 引入 Bedrock 的两个流式函数。
2. 组装成一个普通对象 `bedrockProviderModule`。
3. 外层注册器在需要 Bedrock 能力时，读取这个对象并把它转换成统一的 provider 模式。
4. 如果是测试或替代实现，`register-builtins.ts` 可以用注入模块覆盖同名能力。

这个文件没有复杂流程，核心价值在于“统一形状”和“隔离实现细节”。

## 关键函数的高层作用
- `streamBedrock`：Bedrock 的主流式入口，处理完整对话流、工具调用、上下文、请求参数和响应事件。
- `streamSimpleBedrock`：更轻量的流式入口，通常面向简化调用路径，内部会复用 `streamBedrock` 的主体能力。
- `bedrockProviderModule`：把上面两个函数打包成一个模块对象，供注册器和测试注入系统消费。

## 修改风险
这个文件看起来很小，但改动风险不低，因为它是 provider 适配边界的一部分：
- 如果导出字段名改了，`register-builtins.ts` 的 Bedrock 注册会直接失效
- 如果把 `streamBedrock` 和 `streamSimpleBedrock` 的映射关系弄错，会造成简单模式和完整模式行为不一致
- 如果改成懒加载或动态导入，可能影响 Node-only 兼容性和测试注入方式
- 如果删除这个桥接层，而外层还依赖 `BedrockProviderModule` 这种统一结构，注册逻辑会出现类型或运行时断裂

总的来说，它是一个很薄的胶水文件，真正的业务风险不在这里的实现量，而在它承接了 Bedrock provider 的统一入口语义。
