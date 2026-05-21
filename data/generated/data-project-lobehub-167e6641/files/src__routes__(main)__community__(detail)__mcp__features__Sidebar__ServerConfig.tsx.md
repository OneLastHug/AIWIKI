# 文件：src/routes/(main)/community/(detail)/mcp/features/Sidebar/ServerConfig.tsx

## 文件职责
这个文件位于 `src/routes/(main)/community/(detail)/mcp/features/Sidebar`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { Flexbox } from '@lobehub/ui';
import qs from 'query-string';
import { memo } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router-dom';
import { getRecommendedDeployment } from '@/features/MCP/utils';
import Platform from '@/features/MCPPluginDetail/Deployment/Platform';
import { useDetailContext } from '@/features/MCPPluginDetail/DetailProvider';
import { McpNavKey } from '@/types/discover';
import Title from '../../../../features/Title';
export default ServerConfig;
```

## 主要对外内容
```text
const ServerConfig = memo(() => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { Flexbox } from '@lobehub/ui';
import qs from 'query-string';
import { memo } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router-dom';

import { getRecommendedDeployment } from '@/features/MCP/utils';
import Platform from '@/features/MCPPluginDetail/Deployment/Platform';
import { useDetailContext } from '@/features/MCPPluginDetail/DetailProvider';
import { McpNavKey } from '@/types/discover';

import Title from '../../../../features/Title';

const ServerConfig = memo(() => {
  const { t } = useTranslation('discover');
  const { pathname } = useLocation();
  const installLink = qs.stringifyUrl({
    query: {
      activeTab: McpNavKey.Deployment,
    },
    url: pathname,
  });
  const { deploymentOptions = [], identifier } = useDetailContext();
  const recommendedDeployment = getRecommendedDeployment(deploymentOptions);

  return (
    <Flexbox gap={16}>
      <Title more={t('mcp.details.sidebar.moreServerConfig')} moreLink={installLink}>
        {t('mcp.details.sidebar.serverConfig')}
      </Title>
      <Platform lite connection={recommendedDeployment?.connection} identifier={identifier} />
    </Flexbox>
  );
});

export default ServerConfig;

```
