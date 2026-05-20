# 文件：src/server/routers/lambda/config/index.test.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from 'vitest';

/**
 * This file contains the root router of your tRPC-backend
 */
import { createCallerFactory } from '@/libs/trpc/lambda';
import { type AuthContext } from '@/libs/trpc/lambda/context';
import { createContextInner } from '@/libs/trpc/lambda/context';

import { configRouter } from './index';

const createCaller = createCallerFactory(configRouter);
let ctx: AuthContext;
let router: ReturnType<typeof createCaller>;

beforeEach(async () => {
  vi.resetAllMocks();
  ctx = await createContextInner();
  router = createCaller(ctx);
});

describe('configRouter', () => {
  describe('getGlobalConfig', () => {
    describe('Model Provider env', () => {
      describe('OPENAI_MODEL_LIST', () => {
        it('custom deletion, addition, and renaming of models', async () => {
          process.env.OPENAI_MODEL_LIST =
            '-all,+llama,+claude-2，-gpt-3.5-turbo,gpt-4-0125-preview=gpt-4-turbo,gpt-4-0125-preview=gpt-4-32k';

          const response = await router.getGlobalConfig();

          // Assert
          const result = response.serverConfig.aiProvider?.openai;

          expect(result).toMatchSnapshot();
          process.env.OPENAI_MODEL_LIST = '';
        });

        it('should work correct with gpt-4', async () => {
          process.env.OPENAI_MODEL_LIST =
            '-all,+gpt-3.5-turbo-1106,+gpt-3.5-turbo,+gpt-4,+gpt-4-32k,+gpt-4-1106-preview,+gpt-4-vision';

          const response = await router.getGlobalConfig();

          const result = response.serverConfig.aiProvider?.openai?.serverModelLists;

          expect(result).toMatchSnapshot();

          process.env.OPENAI_MODEL_LIST = '';
        });

        it('duplicate naming model', async () => {
          process.env.OPENAI_MODEL_LIST =
            'gpt-4-0125-preview=gpt-4-turbo，gpt-4-0125-preview=gpt-4-32k';

          const response = await router.getGlobalConfig();

          const result = response.serverConfig.aiProvider?.openai?.serverModelLists;

          expect(result?.find((s) => s.id === 'gpt-4-0125-preview')?.displayName).toEqual(
            'gpt-4-32k',
          );

          process.env.OPENAI_MODEL_LIST = '';
        });

        it('should delete model', async () => {
          process.env.OPENAI_MODEL_LIST = '-gpt-4';

          const response = await router.getGlobalConfig();

          const result = response.serverConfig.aiProvider?.openai?.serverModelLists;

          expect(result?.find((r) => r.id === 'gpt-4')).toBeUndefined();

          process.env.OPENAI_MODEL_LIST = '';
        });

        it('show the hidden model', async () => {
          process.env.OPENAI_MODEL_LIST = '+gpt-4-1106-preview';

          const response = await router.getGlobalConfig();

          const result = response.serverConfig.aiProvider?.openai?.serverModelLists;

          const model = result?.find((o) => o.id === 'gpt-4-1106-preview');

          expect(model).toMatchSnapshot();

          process.env.OPENAI_MODEL_LIST = '';
        });

        it('only add the model', async () => {
          process.env.OPENAI_MODEL_LIST = 'model1,model2,model3，model4';

          const response = await router.getGlobalConfig();

          const result = response.serverConfig.aiProvider?.openai?.serverModelLists;

          expect(result).toContainEqual(
            expect.objectContaining({
              displayName: 'model1',
              id: 'model1',
              enabled: true,
            }),
          );
          expect(result).toContainEqual(
            expect.objectContaining({
              displayName: 'model2',
              enabled: true,
              id: 'model2',
            }),
          );
          expect(result).toContainEqual(
            expect.objectContaining({
              displayName: 'model3',
              enabled: true,
              id: 'model3',
            }),
          );
          expect(result).toContainEqual(
            expect.objectContaining({
              displayName: 'model4',
              enabled: true,
              id: 'model4',
            }),
          );

          process.env.OPENAI_MODEL_LIST = '';
        });
      });

      describe('OPENROUTER_MODEL_LIST', () => {
        it('custom deletion, addition, and renaming of models', async () => {
          process.env.OPENROUTER_MODEL_LIST =
            '-all,+meta-llama/llama-3.1-8b-instruct:free,+google/gemma-2-9b-it:free';

          const response = await router.getGlobalConfig();

          // Assert
          const result = response.serverConfig.aiProvider?.openrouter;

          expect(result).toMatchSnapshot();

          process.env.OPENROUTER_MODEL_LIST = '';
        });
      });

      it('should enable the default DeepSeek provider without a server API key', async () => {
        const originalApiKey = process.env.DEEPSEEK_API_KEY;
        delete process.env.DEEPSEEK_API_KEY;

        const response = await router.getGlobalConfig();

        expect(response.serverConfig.aiProvider?.deepseek?.enabled).toBe(true);

        if (originalApiKey === undefined) {
          delete process.env.DEEPSEEK_API_KEY;
        } else {
          process.env.DEEPSEEK_API_KEY = originalApiKey;
        }
      });
    });
  });

  describe('getDefaultAgentConfig', () => {
    it('should return the default agent config', async () => {
      process.env.DEFAULT_AGENT_CONFIG =
        'plugins=search-engine,lobe-image-designer;enableAutoCreateTopic=true;model=gemini-pro;provider=google;';

      const response = await router.getDefaultAgentConfig();

      expect(response).toEqual({
        enableAutoCreateTopic: true,
        model: 'gemini-pro',
        plugins: ['search-engine', 'lobe-image-designer'],
        provider: 'google',
      });

      process.env.DEFAULT_AGENT_CONFIG = '';
    });

    it('should return another config', async () => {
      process.env.DEFAULT_AGENT_CONFIG =
        'model=meta-11ama/11ama-3-70b-instruct:nitro;provider=openrouter;enableAutoCreateTopic=true;params.max_tokens=700';

      const response = await router.getDefaultAgentConfig();

      expect(response).toEqual({
        enableAutoCreateTopic: true,
        model: 'meta-11ama/11ama-3-70b-instruct:nitro',
        params: { max_tokens: 700 },
        provider: 'openrouter',
      });

      process.env.DEFAULT_AGENT_CONFIG = '';
    });
  });
});

```
