# 文件：packages/model-bank/src/modelProviders/openrouter.ts

## 文件职责
这个文件位于 `packages/model-bank/src/modelProviders`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import type { ModelProviderCard } from '@/types/llm';
export default OpenRouter;
```

## 主要对外内容
```text
const OpenRouter: ModelProviderCard = {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import type { ModelProviderCard } from '@/types/llm';

// ref :[URL已移除]
const OpenRouter: ModelProviderCard = {
  chatModels: [],
  checkModel: 'google/gemma-2-9b-it:free',
  description:
    'OpenRouter provides access to many frontier models from OpenAI, Anthropic, LLaMA, and more, letting users pick the best model and price for their use case.',
  id: 'openrouter',
  modelList: { showModelFetcher: true },
  modelsUrl: '[URL已移除]',
  name: 'OpenRouter',
  settings: {
    // OpenRouter don't support browser request
    // [URL已移除]
    disableBrowserRequest: true,
    proxyUrl: {
      placeholder: '[URL已移除]',
    },
    sdkType: 'openai',
    searchMode: 'params',
    showModelFetcher: true,
  },
  url: '[URL已移除]',
};

export default OpenRouter;

```
