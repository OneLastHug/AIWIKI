# 文件：src/server/services/followUpAction/index.ts

## 文件职责
这个文件位于 `src/server/services/followUpAction`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import type { FollowUpChip, FollowUpExtractInput, FollowUpExtractResult } from '@lobechat/types';
import debug from 'debug';
import type { LobeChatDatabase } from '@/database/type';
import { initModelRuntimeFromDB } from '@/server/modules/ModelRuntime';
import { buildSuggestionPrompt } from './prompts';
import { RawResponseSchema, SUGGESTION_RESPONSE_JSON_SCHEMA } from './schema';
export class FollowUpActionService {
```

## 主要对外内容
```text
const log = debug('lobe-server:follow-up-action-service');
const EMPTY_RESULT = (messageId: string): FollowUpExtractResult => ({ chips: [], messageId });
export class FollowUpActionService {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import type { FollowUpChip, FollowUpExtractInput, FollowUpExtractResult } from '@lobechat/types';
import debug from 'debug';

import type { LobeChatDatabase } from '@/database/type';
import { initModelRuntimeFromDB } from '@/server/modules/ModelRuntime';

import { buildSuggestionPrompt } from './prompts';
import { RawResponseSchema, SUGGESTION_RESPONSE_JSON_SCHEMA } from './schema';

const log = debug('lobe-server:follow-up-action-service');

const EMPTY_RESULT = (messageId: string): FollowUpExtractResult => ({ chips: [], messageId });

export class FollowUpActionService {
  private readonly db: LobeChatDatabase;
  private readonly userId: string;

  constructor(db: LobeChatDatabase, userId: string) {
    this.db = db;
    this.userId = userId;
  }

  async extract({
    topicId,
    hint,
    modelConfig,
  }: FollowUpExtractInput): Promise<FollowUpExtractResult> {
    // Resolve the latest assistant message that actually has user-facing text.
    // Tool-call-only messages have empty content and must be skipped.
    const row = await this.db.query.messages.findFirst({
      columns: { content: true, id: true },
      orderBy: (m, { desc }) => desc(m.createdAt),
      where: (m, { and, eq, isNotNull, ne }) =>
        and(
          eq(m.userId, this.userId),
          eq(m.topicId, topicId),
          eq(m.role, 'assistant'),
          isNotNull(m.content),
          ne(m.content, ''),
        ),
    });

    if (!row) return EMPTY_RESULT('');

    const text = (row.content ?? '').trim();
    if (!text) return EMPTY_RESULT(row.id);

    const { system, user } = buildSuggestionPrompt({ assistantText: text, hint });
    const { model, provider } = modelConfig;

    let raw: unknown;
    try {
      const modelRuntime = await initModelRuntimeFromDB(this.db, this.userId, provider);
      raw = await modelRuntime.generateObject({
        messages: [
          { content: system, role: 'system' as const },
          { content: user, role: 'user' as const },
        ],
        model,
        schema: SUGGESTION_RESPONSE_JSON_SCHEMA,
      });
    } catch (error) {
      log('LLM call failed: %O', error);
      return EMPTY_RESULT(row.id);
    }

    const parsed = RawResponseSchema.safeParse(raw);
    if (!parsed.success) {
      log('LLM response did not match schema: %O', parsed.error.flatten());
      return EMPTY_RESULT(row.id);
    }

    const chips: FollowUpChip[] = parsed.data.chips
      .filter(
        (c) =>
          c.label.length >= 1 &&
          c.label.length <= 40 &&
          c.message.length >= 1 &&
          c.message.length <= 200,
      )
      .slice(0, 4);

    return { chips, messageId: row.id };
  }
}

```
