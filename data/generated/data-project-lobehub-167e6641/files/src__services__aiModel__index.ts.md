# 文件：src/services/aiModel/index.ts

## 文件职责
这个文件位于 `src/services/aiModel`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import {
import { lambdaClient } from '@/libs/trpc/client';
export interface GetAiProviderModelListParams {
export class AiModelService {
export const aiModelService = new AiModelService();
```

## 主要对外内容
```text
export interface GetAiProviderModelListParams {
export class AiModelService {
export const aiModelService = new AiModelService();
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import {
  type AiModelSortMap,
  type AiProviderModelListItem,
  type CreateAiModelParams,
  isAiModelVisible,
  type ToggleAiModelEnableParams,
  type UpdateAiModelParams,
} from 'model-bank';

import { lambdaClient } from '@/libs/trpc/client';

export interface GetAiProviderModelListParams {
  enabled?: boolean;
  limit?: number;
  offset?: number;
}

export class AiModelService {
  createAiModel = async (params: CreateAiModelParams) => {
    return lambdaClient.aiModel.createAiModel.mutate(params);
  };

  getAiProviderModelList = async (
    id: string,
    params?: GetAiProviderModelListParams,
  ): Promise<AiProviderModelListItem[]> => {
    const models = await lambdaClient.aiModel.getAiProviderModelList.query({ id, ...params });
    return models.filter(isAiModelVisible);
  };

  getAiModelById = async (id: string) => {
    return lambdaClient.aiModel.getAiModelById.query({ id });
  };

  toggleModelEnabled = async (params: ToggleAiModelEnableParams) => {
    return lambdaClient.aiModel.toggleModelEnabled.mutate(params);
  };

  updateAiModel = async (id: string, providerId: string, value: UpdateAiModelParams) => {
    return lambdaClient.aiModel.updateAiModel.mutate({ id, providerId, value });
  };

  batchUpdateAiModels = async (id: string, models: AiProviderModelListItem[]) => {
    return lambdaClient.aiModel.batchUpdateAiModels.mutate({ id, models });
  };

  batchToggleAiModels = async (id: string, models: string[], enabled: boolean) => {
    return lambdaClient.aiModel.batchToggleAiModels.mutate({ enabled, id, models });
  };

  clearModelsByProvider = async (providerId: string) => {
    return lambdaClient.aiModel.clearModelsByProvider.mutate({ providerId });
  };

  clearRemoteModels = async (providerId: string) => {
    return lambdaClient.aiModel.clearRemoteModels.mutate({ providerId });
  };

  updateAiModelOrder = async (providerId: string, items: AiModelSortMap[]) => {
    return lambdaClient.aiModel.updateAiModelOrder.mutate({ providerId, sortMap: items });
  };

  deleteAiModel = async (params: { id: string; providerId: string }) => {
    return lambdaClient.aiModel.removeAiModel.mutate(params);
  };
}

export const aiModelService = new AiModelService();

```
