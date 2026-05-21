# 文件：src/services/aiProvider/index.ts

## 文件职责
这个文件位于 `src/services/aiProvider`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { lambdaClient } from '@/libs/trpc/client';
import {
export class AiProviderService {
export const aiProviderService = new AiProviderService();
```

## 主要对外内容
```text
export class AiProviderService {
export const aiProviderService = new AiProviderService();
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { lambdaClient } from '@/libs/trpc/client';
import {
  type AiProviderDetailItem,
  type AiProviderRuntimeState,
  type AiProviderSortMap,
  type CreateAiProviderParams,
  type UpdateAiProviderConfigParams,
} from '@/types/aiProvider';

export class AiProviderService {
  createAiProvider = async (params: CreateAiProviderParams) => {
    return lambdaClient.aiProvider.createAiProvider.mutate(params);
  };

  getAiProviderList = async () => {
    return lambdaClient.aiProvider.getAiProviderList.query();
  };

  getAiProviderById = async (id: string): Promise<AiProviderDetailItem | undefined> => {
    return lambdaClient.aiProvider.getAiProviderById.query({ id });
  };

  toggleProviderEnabled = async (id: string, enabled: boolean) => {
    return lambdaClient.aiProvider.toggleProviderEnabled.mutate({ enabled, id });
  };

  updateAiProvider = async (id: string, value: any) => {
    return lambdaClient.aiProvider.updateAiProvider.mutate({ id, value });
  };

  updateAiProviderConfig = async (id: string, value: UpdateAiProviderConfigParams) => {
    return lambdaClient.aiProvider.updateAiProviderConfig.mutate({ id, value });
  };

  updateAiProviderOrder = async (items: AiProviderSortMap[]) => {
    return lambdaClient.aiProvider.updateAiProviderOrder.mutate({ sortMap: items });
  };

  deleteAiProvider = async (id: string) => {
    return lambdaClient.aiProvider.removeAiProvider.mutate({ id });
  };

  getAiProviderRuntimeState = async (isLogin?: boolean): Promise<AiProviderRuntimeState> => {
    return lambdaClient.aiProvider.getAiProviderRuntimeState.query({ isLogin });
  };
}

export const aiProviderService = new AiProviderService();

```
