# 文件：src/server/services/agentGroup/index.ts

## 文件职责
这个文件位于 `src/server/services/agentGroup`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { DEFAULT_AGENT_CONFIG, DEFAULT_CHAT_GROUP_CHAT_CONFIG } from '@lobechat/const';
import { type LobeChatDatabase } from '@lobechat/database';
import { type LobeAgentConfig } from '@lobechat/types';
import { cleanObject, merge } from '@lobechat/utils';
import { type PartialDeep } from 'type-fest';
import { AgentModel } from '@/database/models/agent';
import { ChatGroupModel } from '@/database/models/chatGroup';
import { type UserModel } from '@/database/models/user';
import { AgentGroupRepository } from '@/database/repositories/agentGroup';
import { type ChatGroupConfig } from '@/database/types/chatGroup';
import { getServerDefaultAgentConfig } from '@/server/globalConfig';
export class AgentGroupService {
```

## 主要对外内容
```text
type DefaultAgentConfig = Awaited<ReturnType<UserModel['getUserSettingsDefaultAgentConfig']>>;
export class AgentGroupService {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { DEFAULT_AGENT_CONFIG, DEFAULT_CHAT_GROUP_CHAT_CONFIG } from '@lobechat/const';
import { type LobeChatDatabase } from '@lobechat/database';
import { type LobeAgentConfig } from '@lobechat/types';
import { cleanObject, merge } from '@lobechat/utils';
import { type PartialDeep } from 'type-fest';

import { AgentModel } from '@/database/models/agent';
import { ChatGroupModel } from '@/database/models/chatGroup';
import { type UserModel } from '@/database/models/user';
import { AgentGroupRepository } from '@/database/repositories/agentGroup';
import { type ChatGroupConfig } from '@/database/types/chatGroup';
import { getServerDefaultAgentConfig } from '@/server/globalConfig';

type DefaultAgentConfig = Awaited<ReturnType<UserModel['getUserSettingsDefaultAgentConfig']>>;

/**
 * ChatGroup Service
 *
 * Encapsulates "mutation + query" logic for chat group operations.
 * Handles agent config merging for group members.
 */
export class AgentGroupService {
  private readonly agentModel: AgentModel;
  private readonly chatGroupModel: ChatGroupModel;
  private readonly agentGroupRepo: AgentGroupRepository;

  constructor(db: LobeChatDatabase, userId: string) {
    this.agentModel = new AgentModel(db, userId);
    this.chatGroupModel = new ChatGroupModel(db, userId);
    this.agentGroupRepo = new AgentGroupRepository(db, userId);
  }

  /**
   * Get group detail by ID.
   */
  getGroupDetail(groupId: string) {
    return this.agentGroupRepo.findByIdWithAgents(groupId);
  }

  /**
   * Get all groups with member details.
   */
  getGroups() {
    return this.chatGroupModel.queryWithMemberDetails();
  }

  /**
   * Delete a group and its associated virtual agents.
   *
   * This method:
   * 1. Gets all agents in the group to identify virtual ones
   * 2. Deletes the group (CASCADE will delete chatGroupsAgents entries)
   * 3. Deletes all virtual agents that were members of this group
   *
   * @param groupId - The group ID to delete
   * @returns The deleted group and list of deleted virtual agent IDs
   */
  async deleteGroup(groupId: string) {
    // 1. Get all agents in the group to identify virtual ones
    const groupAgents = await this.chatGroupModel.getGroupAgents(groupId);
    const agentIds = groupAgents.map((ga) => ga.agentId);

    // 2. Check which agents are virtual
    const { virtualAgents } = await this.agentGroupRepo.checkAgentsBeforeRemoval(groupId, agentIds);
    const virtualAgentIds = virtualAgents.map((a) => a.id);

    // 3. Delete the group (CASCADE will delete chatGroupsAgents entries)
    const deletedGroup = await this.chatGroupModel.delete(groupId);

    // 4. Delete virtual agents
    if (virtualAgentIds.length > 0) {
      await this.agentModel.batchDelete(virtualAgentIds);
    }

    return {
      deletedVirtualAgentIds: virtualAgentIds,
      group: deletedGroup,
    };
  }

  /**
   * Normalize ChatGroupConfig with defaults.
   * Merges DEFAULT_CHAT_GROUP_CHAT_CONFIG with the provided config.
   */
  normalizeGroupConfig(config?: ChatGroupConfig | null): ChatGroupConfig | undefined {
    return config
      ? {
          ...DEFAULT_CHAT_GROUP_CHAT_CONFIG,
          ...config,
        }
      : undefined;
  }

  /**
   * Merge agents with default configs.
   *
   * Merge order (later values override earlier):
   * 1. DEFAULT_AGENT_CONFIG - hardcoded defaults
   * 2. serverDefaultAgentConfig - from environment variable
   * 3. userDefaultAgentConfig - from user settings
   * 4. agent - actual agent config from database
   *
   * @param defaultAgentConfig - User's default agent config from settings
   * @param agents - Array of agents to merge
   * @returns Merged agents array
   */
  mergeAgentsDefaultConfig<T extends Record<string, any>>(
    defaultAgentConfig: DefaultAgentConfig,
    agents: T[],
  ) {
    const userDefaultAgentConfig =
      (defaultAgentConfig as { config?: PartialDeep<LobeAgentConfig> })?.config || {};

    const serverDefaultAgentConfig = getServerDefaultAgentConfig();
    const baseConfig = merge(DEFAULT_AGENT_CONFIG, serverDefaultAgentConfig);
    const withUserConfig = merge(baseConfig, userDefaultAgentConfig);

    return agents.map((agent) => merge(withUserConfig, cleanObject(agent)) as T);
  }
}

```
