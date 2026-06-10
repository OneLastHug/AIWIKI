# 文件：packages/desktop/src/common/adapter/apiModelMapper.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
/**
 * @license
 * Copyright 2025 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import type { TProviderWithModel } from '../config/storage';

export type ApiProviderWithModel = {
  provider_id: string;
  model: string;
  use_model?: string;
};

function hasCompleteModelIdentity(
  model?: TProviderWithModel
): model is TProviderWithModel & { id: string; use_model: string } {
  return Boolean(
    model &&
    typeof model.id === 'string' &&
    model.id.trim().length > 0 &&
    typeof model.use_model === 'string' &&
    model.use_model.trim().length > 0
  );
}

// ── Frontend → Backend ──────────────────────────────────────────────────

export function toApiModel(m: TProviderWithModel): ApiProviderWithModel {
  return {
    provider_id: m.id,
    model: m.use_model,
  };
}

export function toApiModelOptional(m?: TProviderWithModel): ApiProviderWithModel | undefined {
  return hasCompleteModelIdentity(m) ? toApiModel(m) : undefined;
}

// ── Backend → Frontend ──────────────────────────────────────────────────

export function fromApiModel(raw: ApiProviderWithModel): TProviderWithModel {
  return {
    id: raw.provider_id,
    platform: '',
    name: '',
    base_url: '',
    api_key: '',
    use_model: raw.use_model ?? raw.model,
  };
}

function fromApiModelOptional(raw?: ApiProviderWithModel | null): TProviderWithModel | undefined {
  return raw ? fromApiModel(raw) : undefined;
}

export function fromApiConversation<T>(raw: T): T {
  if (!raw || typeof raw !== 'object') return raw;

  const r = raw as T & {
    model?: ApiProviderWithModel | null;
    extra?: Record<string, unknown> | null;
  };
  const next = { ...r } as unknown as T & {
    model?: TProviderWithModel;
    extra?: Record<string, unknown> | null;
  };

  if ('model' in r) {
    next.model = fromApiModelOptional(r.model);
  }

  const extra = r.extra;
  if (extra && typeof extra === 'object' && !('custom_workspace' in extra)) {
    const workspace = typeof extra.workspace === 'string' ? extra.workspace : '';
    const isTemporary = extra.is_temporary_workspace === true;
    next.extra = {
      ...extra,
      custom_workspace: workspace.length > 0 && !isTemporary,
    };
  }

  return next;
}

export function fromApiPaginatedConversations<T>(result: { items: T[]; total: number; has_more: boolean }): {
  items: T[];
  total: number;
  has_more: boolean;
} {
  return {
    ...result,
    items: result.items.map(fromApiConversation),
  };
}

```
