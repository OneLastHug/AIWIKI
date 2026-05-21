# 文件：src/routes/(main)/settings/provider/ProviderMenu/index.tsx

## 文件职责
这个文件位于 `src/routes/(main)/settings/provider/ProviderMenu`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { Flexbox, Icon, SearchBar } from '@lobehub/ui';
import { cssVar } from 'antd-style';
import { SearchIcon } from 'lucide-react';
import { type ReactNode } from 'react';
import { memo } from 'react';
import { useTranslation } from 'react-i18next';
import SkeletonList from '@/features/NavPanel/components/SkeletonList';
import { useAiInfraStore } from '@/store/aiInfra/store';
import AddNew from './AddNew';
import ProviderList from './List';
import SearchResult from './SearchResult';
export default ProviderMenu;
```

## 主要对外内容
```text
interface ProviderMenuProps {
const Layout = memo(({ children, mobile }: ProviderMenuProps) => {
const ProviderMenu = ({
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
'use client';

import { Flexbox, Icon, SearchBar } from '@lobehub/ui';
import { cssVar } from 'antd-style';
import { SearchIcon } from 'lucide-react';
import { type ReactNode } from 'react';
import { memo } from 'react';
import { useTranslation } from 'react-i18next';

import SkeletonList from '@/features/NavPanel/components/SkeletonList';
import { useAiInfraStore } from '@/store/aiInfra/store';

import AddNew from './AddNew';
import ProviderList from './List';
import SearchResult from './SearchResult';

interface ProviderMenuProps {
  children: ReactNode;
  mobile?: boolean;
}
const Layout = memo(({ children, mobile }: ProviderMenuProps) => {
  const { t } = useTranslation('modelProvider');

  const [providerSearchKeyword, useFetchAiProviderList] = useAiInfraStore((s) => [
    s.providerSearchKeyword,
    s.useFetchAiProviderList,
    s.initAiProviderList,
  ]);

  useFetchAiProviderList();

  const width = mobile ? undefined : 280;
  return (
    <Flexbox
      width={width}
      style={{
        background: cssVar.colorBgContainer,
        borderRight: `1px solid ${cssVar.colorBorderSecondary}`,
        minWidth: width,
        overflow: mobile ? undefined : 'scroll',
      }}
    >
      <Flexbox
        horizontal
        align={'center'}
        gap={8}
        justify={'space-between'}
        padding={8}
        width={'100%'}
        style={{
          background: cssVar.colorBgContainer,
          borderBottom: `1px solid ${cssVar.colorBorderSecondary}`,
          marginBottom: 8,
          position: 'sticky',
          top: 0,
          zIndex: 50,
        }}
      >
        <SearchBar
          allowClear
          placeholder={t('menu.searchProviders')}
          style={{ width: '100%' }}
          value={providerSearchKeyword}
          variant={'borderless'}
          prefix={
            <Icon
              color={cssVar.colorTextDescription}
              icon={SearchIcon}
              style={{
                marginRight: 12,
              }}
            />
          }
          styles={{
            input: {
              paddingBlock: 3,
              paddingLeft: 6,
            },
          }}
          onInputChange={(v) => {
            useAiInfraStore.setState({ providerSearchKeyword: v });
          }}
        />
        <AddNew />
      </Flexbox>
      {children}
    </Flexbox>
  );
});

const ProviderMenu = ({
  mobile,
  onProviderSelect = () => {},
}: {
  mobile?: boolean;
  onProviderSelect?: (providerKey: string) => void;
}) => {
  const [initAiProviderList, providerSearchKeyword] = useAiInfraStore((s) => [
    s.initAiProviderList,
    s.providerSearchKeyword,
  ]);

  let Content = <ProviderList mobile={mobile} onProviderSelect={onProviderSelect} />;

  // loading
  if (!initAiProviderList) Content = <SkeletonList />;

  // search
  if (!!providerSearchKeyword) Content = <SearchResult onProviderSelect={onProviderSelect} />;

  return <Layout mobile={mobile}>{Content}</Layout>;
};

export default ProviderMenu;

```
