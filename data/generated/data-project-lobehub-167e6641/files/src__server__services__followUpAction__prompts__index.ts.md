# 文件：src/server/services/followUpAction/prompts/index.ts

## 文件职责
这个文件位于 `src/server/services/followUpAction/prompts`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import type { FollowUpHint } from '@lobechat/types';
import { BASE_SYSTEM_PROMPT } from './base';
import { buildOnboardingAddendum } from './onboarding';
export interface BuiltPrompt {
export const buildSuggestionPrompt = (params: {
export { BASE_SYSTEM_PROMPT };
```

## 主要对外内容
```text
export interface BuiltPrompt {
export const buildSuggestionPrompt = (params: {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import type { FollowUpHint } from '@lobechat/types';

import { BASE_SYSTEM_PROMPT } from './base';
import { buildOnboardingAddendum } from './onboarding';

export interface BuiltPrompt {
  system: string;
  user: string;
}

export const buildSuggestionPrompt = (params: {
  assistantText: string;
  hint?: FollowUpHint;
}): BuiltPrompt => {
  const { assistantText, hint } = params;

  const sections = [BASE_SYSTEM_PROMPT];

  if (hint?.kind === 'onboarding') {
    sections.push(buildOnboardingAddendum(hint.phase));
  }

  return {
    system: sections.join('\n\n'),
    user: `Last assistant message:\n"""\n${assistantText.trim()}\n"""`,
  };
};

export { BASE_SYSTEM_PROMPT };

```
