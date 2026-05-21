# 文件：src/routes/(main)/(create)/image/features/ConfigPanel/components/AspectRatioSelect/index.tsx

## 文件职责
这个文件位于 `src/routes/(main)/(create)/image/features/ConfigPanel/components/AspectRatioSelect`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import type { GridProps } from '@lobehub/ui';
import { Block, Center, Grid, Text } from '@lobehub/ui';
import { cssVar } from 'antd-style';
import type { ReactNode } from 'react';
import { memo } from 'react';
import useMergeState from 'use-merge-value';
import { useIsDark } from '@/hooks/useIsDark';
export interface AspectRatioSelectProps extends Omit<GridProps, 'children' | 'onChange'> {
export default AspectRatioSelect;
```

## 主要对外内容
```text
const isRatioValue = (value: string): boolean => {
export interface AspectRatioSelectProps extends Omit<GridProps, 'children' | 'onChange'> {
const AspectRatioSelect = memo<AspectRatioSelectProps>(
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
'use client';

import type { GridProps } from '@lobehub/ui';
import { Block, Center, Grid, Text } from '@lobehub/ui';
import { cssVar } from 'antd-style';
import type { ReactNode } from 'react';
import { memo } from 'react';
import useMergeState from 'use-merge-value';

import { useIsDark } from '@/hooks/useIsDark';

/**
 * Check if a value can be parsed as a valid aspect ratio (e.g. "16:9")
 */
const isRatioValue = (value: string): boolean => {
  const parts = value.split(':');
  if (parts.length !== 2) return false;
  const [w, h] = parts.map(Number);
  return !isNaN(w) && !isNaN(h) && w > 0 && h > 0;
};

export interface AspectRatioSelectProps extends Omit<GridProps, 'children' | 'onChange'> {
  defaultValue?: string;
  onChange?: (value: string) => void;
  options?: { label?: string; value: string }[];
  value?: string;
}

const AspectRatioSelect = memo<AspectRatioSelectProps>(
  ({ options, onChange, value, defaultValue, ...rest }) => {
    const isDarkMode = useIsDark();
    const [active, setActive] = useMergeState('1:1', {
      defaultValue: defaultValue || '1:1',
      onChange,
      value,
    });

    return (
      <Block padding={4} variant={'filled'} {...rest}>
        <Grid gap={4} maxItemWidth={48} rows={16}>
          {options?.map((item) => {
            const isActive = active === item.value;
            let content: ReactNode;

            if (isRatioValue(item.value)) {
              const [width, height] = item.value.split(':').map(Number);
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
            } else {
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
  },
);

export default AspectRatioSelect;

```
