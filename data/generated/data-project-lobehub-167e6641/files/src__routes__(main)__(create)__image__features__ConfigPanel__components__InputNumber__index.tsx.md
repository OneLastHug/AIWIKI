# 文件：src/routes/(main)/(create)/image/features/ConfigPanel/components/InputNumber/index.tsx

## 文件职责
这个文件位于 `src/routes/(main)/(create)/image/features/ConfigPanel/components/InputNumber`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { Button, Flexbox, InputNumber, Tooltip } from '@lobehub/ui';
import { Dices } from 'lucide-react';
import { MAX_SEED } from 'model-bank';
import { type CSSProperties } from 'react';
import { memo, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { generateUniqueSeeds } from '@/utils/number';
export interface SeedNumberInputProps {
export default SeedNumberInput;
```

## 主要对外内容
```text
export interface SeedNumberInputProps {
const SeedNumberInput = memo<SeedNumberInputProps>(
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
'use client';

import { Button, Flexbox, InputNumber, Tooltip } from '@lobehub/ui';
import { Dices } from 'lucide-react';
import { MAX_SEED } from 'model-bank';
import { type CSSProperties } from 'react';
import { memo, useCallback } from 'react';
import { useTranslation } from 'react-i18next';

import { generateUniqueSeeds } from '@/utils/number';

export interface SeedNumberInputProps {
  className?: string;
  onChange: (value: number | null | undefined) => void;
  placeholder?: string;
  style?: CSSProperties;
  value?: number | null;
}

const SeedNumberInput = memo<SeedNumberInputProps>(
  ({ value, onChange, style, className, ...rest }) => {
    const { t } = useTranslation('image');

    const handleClick = useCallback(() => {
      const randomSeed = generateUniqueSeeds(1)[0];
      onChange?.(randomSeed);
    }, [onChange]);

    return (
      <Flexbox horizontal className={className} gap={4} style={style}>
        <InputNumber
          max={MAX_SEED}
          min={0}
          placeholder={t('config.seed.random')}
          step={1}
          style={{ width: '100%' }}
          value={value}
          onChange={onChange as any}
          {...rest}
        />
        <Tooltip title={t('config.seed.random')}>
          <Button
            icon={Dices}
            style={{ flex: 'none', width: 48 }}
            variant={'outlined'}
            onClick={handleClick}
          />
        </Tooltip>
      </Flexbox>
    );
  },
);

export default SeedNumberInput;

```
