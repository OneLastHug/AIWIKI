# 文件：src/routes/(main)/community/(detail)/provider/features/Sidebar/RelatedModels/index.tsx

## 文件职责
这个文件位于 `src/routes/(main)/community/(detail)/provider/features/Sidebar/RelatedModels`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { Flexbox } from '@lobehub/ui';
import qs from 'query-string';
import { memo } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import urlJoin from 'url-join';
import Title from '../../../../../features/Title';
import { useDetailContext } from '../../DetailProvider';
import Item from './Item';
export default Related;
```

## 主要对外内容
```text
const Related = memo(() => {
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
import { Link } from 'react-router-dom';
import urlJoin from 'url-join';

import Title from '../../../../../features/Title';
import { useDetailContext } from '../../DetailProvider';
import Item from './Item';

const Related = memo(() => {
  const { t } = useTranslation('discover');
  const { models = [], identifier } = useDetailContext();

  return (
    <Flexbox gap={16}>
      <Title
        more={t('models.details.related.more')}
        moreLink={qs.stringifyUrl({
          query: {
            category: identifier,
          },
          url: '/community/model',
        })}
      >
        {t('models.details.related.listTitle')}
      </Title>
      <Flexbox gap={8}>
        {models?.slice(0, 6)?.map((item, index) => {
          const link = urlJoin('/community/model', item.id);
          return (
            <Link key={index} style={{ color: 'inherit', overflow: 'hidden' }} to={link}>
              <Item {...item} />
            </Link>
          );
        })}
      </Flexbox>
    </Flexbox>
  );
});

export default Related;

```
