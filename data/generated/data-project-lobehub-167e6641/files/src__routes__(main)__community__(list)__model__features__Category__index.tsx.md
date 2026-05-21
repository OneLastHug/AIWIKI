# 文件：src/routes/(main)/community/(list)/model/features/Category/index.tsx

## 文件职责
这个文件位于 `src/routes/(main)/community/(list)/model/features/Category`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { Icon, Tag } from '@lobehub/ui';
import qs from 'query-string';
import { memo, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { withSuspense } from '@/components/withSuspense';
import { useQuery } from '@/hooks/useQuery';
import { SCROLL_PARENT_ID } from '@/routes/(main)/community/features/const';
import { useDiscoverStore } from '@/store/discover';
import CategoryMenu from '../../../../components/CategoryMenu';
import { useCategory } from './useCategory';
export default withSuspense(Category);
```

## 主要对外内容
```text
const Category = memo(() => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
'use client';

import { Icon, Tag } from '@lobehub/ui';
import qs from 'query-string';
import { memo, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { withSuspense } from '@/components/withSuspense';
import { useQuery } from '@/hooks/useQuery';
import { SCROLL_PARENT_ID } from '@/routes/(main)/community/features/const';
import { useDiscoverStore } from '@/store/discover';

import CategoryMenu from '../../../../components/CategoryMenu';
import { useCategory } from './useCategory';

const Category = memo(() => {
  const useModelCategories = useDiscoverStore((s) => s.useModelCategories);
  const { category = 'all', q } = useQuery() as { category?: string; q?: string };
  const { data: items = [] } = useModelCategories({ q });
  const navigate = useNavigate();
  const cates = useCategory();

  const genUrl = (key: string) =>
    qs.stringifyUrl(
      {
        query: { category: key === 'all' ? null : key, q },
        url: '/community/model',
      },
      { skipNull: true },
    );

  const handleClick = (key: string) => {
    navigate(genUrl(key));
    const scrollableElement = document?.querySelector(`#${SCROLL_PARENT_ID}`);
    if (!scrollableElement) return;
    scrollableElement.scrollTo({ behavior: 'smooth', top: 0 });
  };
  const total = useMemo(() => items.reduce((acc, item) => acc + item.count, 0), [items]);

  return (
    <CategoryMenu
      mode={'inline'}
      selectedKeys={[category]}
      items={cates.map((item) => {
        const itemData = items.find((i) => i.category === item.key);
        return {
          extra:
            item.key === 'all'
              ? total > 0 && (
                  <Tag
                    size={'small'}
                    style={{
                      borderRadius: 12,
                      paddingInline: 6,
                    }}
                  >
                    {total}
                  </Tag>
                )
              : itemData && (
                  <Tag
                    size={'small'}
                    style={{
                      borderRadius: 12,
                      paddingInline: 6,
                    }}
                  >
                    {itemData.count}
                  </Tag>
                ),
          ...item,
          icon: <Icon icon={item.icon} size={18} />,
          label: <Link to={genUrl(item.key)}>{item.label}</Link>,
        };
      })}
      onClick={(v) => handleClick(v.key as string)}
    />
  );
});

export default withSuspense(Category);

```
