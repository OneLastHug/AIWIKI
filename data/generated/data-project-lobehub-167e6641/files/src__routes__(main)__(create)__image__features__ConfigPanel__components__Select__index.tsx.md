# 文件：src/routes/(main)/(create)/image/features/ConfigPanel/components/Select/index.tsx

## 文件职责
这个文件位于 `src/routes/(main)/(create)/image/features/ConfigPanel/components/Select`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { type GridProps } from '@lobehub/ui';
import { Block, Center, Grid, Select, Text } from '@lobehub/ui';
import { cssVar } from 'antd-style';
import { type ReactNode } from 'react';
import { memo } from 'react';
import useMergeState from 'use-merge-value';
import { useIsDark } from '@/hooks/useIsDark';
export interface SizeSelectProps extends Omit<GridProps, 'children' | 'onChange'> {
export default SizeSelect;
```

## 主要对外内容
```text
export interface SizeSelectProps extends Omit<GridProps, 'children' | 'onChange'> {
const canParseAsRatio = (value: string): boolean => {
const SizeSelect = memo<SizeSelectProps>(({ options, onChange, value, defaultValue, ...rest }) => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
'use client';

import { type GridProps } from '@lobehub/ui';
import { Block, Center, Grid, Select, Text } from '@lobehub/ui';
import { cssVar } from 'antd-style';
import { type ReactNode } from 'react';
import { memo } from 'react';
import useMergeState from 'use-merge-value';

import { useIsDark } from '@/hooks/useIsDark';

export interface SizeSelectProps extends Omit<GridProps, 'children' | 'onChange'> {
  defaultValue?: 'auto' | string;
  onChange?: (value: string) => void;
  options?: { label?: string; value: 'auto' | string }[];
  value?: 'auto' | string;
}

/**
 * Check if a size value can be parsed as valid aspect ratio
 */
const canParseAsRatio = (value: string): boolean => {
  if (value === 'auto') return true;

  const parts = value.split('x');
  if (parts.length !== 2) return false;

  const [width, height] = parts.map(Number);
  return !isNaN(width) && !isNaN(height) && width > 0 && height > 0;
};

const SizeSelect = memo<SizeSelectProps>(({ options, onChange, value, defaultValue, ...rest }) => {
  const isDarkMode = useIsDark();
  const [active, setActive] = useMergeState('auto', {
    defaultValue,
    onChange,
    value,
  });

  // Check if all options can be parsed as valid ratios
  const hasInvalidRatio = options?.some((item) => !canParseAsRatio(item.value));

  // If any option cannot be parsed as ratio, fallback to regular Select
  if (hasInvalidRatio) {
    return (
      <Select options={options} style={{ width: '100%' }} value={active} onChange={onChange} />
    );
  }
  return (
    <Block padding={4} variant={'filled'} {...rest}>
      <Grid gap={4} maxItemWidth={72} rows={16}>
        {options?.map((item) => {
          const isActive = active === item.value;
          let content: ReactNode;

          if (item.value === 'auto') {
            content = (
              <div
                style={{
                  border: `2px dashed ${isActive ? cssVar.colorText : cssVar.colorTextDescription}`,
                  borderRadius: 3,
                  height: 16,
                  width: 16,
                }}
              />
            );
          } else {
            const [width, height] = item.value.split('x').map(Number);
            const isWidthGreater = width > height;
            content = (
              <div
                style={{
                  aspectRatio: `${width} / ${height}`,
                  border: `2px solid ${isActive ? cssVar.colorText : cssVar.colorTextDescription}`,
                  borderRadius: 3,
                  height: isWidthGreater ? undefined : 16,
                  width: isWidthGreater ? 16 : undefined,
                }}
              />
            );
          }

          return (
            <Block
              clickable
              align={'center'}
              gap={4}
              justify={'center'}
              key={item.value}
              padding={8}
              shadow={isActive && !isDarkMode}
              variant={'filled'}
              style={{
                backgroundColor: isActive ? cssVar.colorBgElevated : 'transparent',
              }}
              onClick={() => {
                setActive(item.value);
                onChange?.(item.value);
              }}
            >
              <Center height={16} style={{ marginTop: 4 }} width={16}>
                {content}
              </Center>
              <Text fontSize={12} type={isActive ? undefined : 'secondary'}>
                {item.label || item.value}
              </Text>
            </Block>
          );
        })}
      </Grid>
    </Block>
  );
});

export default SizeSelect;

```
