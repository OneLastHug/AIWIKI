# 目录：src/routes/(main)/settings/common/features/Appearance/ThemeSwatches

## 它负责什么

`ThemeSwatches` 是设置页“外观”区域里用于选择主题颜色的两个色板组件集合。它不负责保存设置，也不负责真正应用主题，只负责把用户在 UI 色板中点选的颜色转换成设置系统可识别的主题色名称，然后通过 `onChange` 交还给上层表单。

这个目录下有两类颜色选择：

- `ThemeSwatchesPrimary`：选择主色，也就是界面强调色、品牌色一类的颜色，对应用户设置里的 `general.primaryColor`。
- `ThemeSwatchesNeutral`：选择中性色，也就是灰阶色调倾向，对应用户设置里的 `general.neutralColor`。

从职责边界看，它是一个很薄的 UI 适配层：底层色板 UI、颜色常量、颜色反查函数都来自 `@lobehub/ui`；上层保存逻辑来自设置表单和 `useUserStore`。本目录只把两边接起来。

## 关键组成

`index.ts` 是目录出口：

```ts
export { default as ThemeSwatchesNeutral } from './ThemeSwatchesNeutral';
export { default as ThemeSwatchesPrimary } from './ThemeSwatchesPrimary';
```

它把两个默认导出的组件重新命名导出，方便上层通过：

```ts
import { ThemeSwatchesNeutral, ThemeSwatchesPrimary } from './ThemeSwatches';
```

一次性引入。

`ThemeSwatchesPrimary.tsx` 负责主色选择。它的核心依赖包括：

- `PrimaryColors`：来自 `@lobehub/ui` 的主色名称类型。
- `ColorSwatches`：实际渲染颜色格子的 UI 组件。
- `primaryColors`：主色名称到具体颜色值的映射。
- `findCustomThemeName`：根据颜色值反查主题色名称。
- `useTranslation('color')`：读取颜色名称的国际化文案。

它接收两个可选 props：

```ts
interface IProps {
  onChange?: (v: PrimaryColors) => void;
  value?: PrimaryColors;
}
```

这里的 `value` 不是十六进制颜色值，而是 `PrimaryColors` 这样的主题色 key，例如 `blue`、`red`、`magenta` 等。组件内部再通过 `primaryColors[value]` 转成 `ColorSwatches` 需要的实际颜色值。

它提供的主色列表包括：

- default
- red
- orange
- gold
- yellow
- lime
- green
- cyan
- blue
- geekblue
- purple
- magenta
- volcano

其中 `default` 使用的是透明色：

```ts
color: 'rgba(0, 0, 0, 0)'
```

根据当前片段推断，这个透明色代表“恢复默认主题色”，因为 `handleSelect` 找不到对应主题名时会传出空字符串：

```ts
const name = findCustomThemeName('primary', v) as PrimaryColors;
onChange?.(name || '');
```

`ThemeSwatchesNeutral.tsx` 结构与主色组件基本一致，只是颜色类型和颜色表换成了中性色：

- `NeutralColors`
- `neutralColors`
- `findCustomThemeName('neutral', v)`

它支持的中性色列表包括：

- default
- mauve
- olive
- sage
- sand
- slate

同样，`default` 也是透明色，并通过 `name || ''` 向上层表示清空自定义中性色设置。

两个组件都用 `memo` 包裹，说明它们是纯 UI 受控组件，期望在 props 不变时减少重复渲染。

## 上下游关系

上游调用方主要是：

```text
src/routes/(main)/settings/common/features/Appearance/index.tsx
```

这个文件把两个色板组件放进 `@lobehub/ui` 的 `Form` 中：

```tsx
{
  children: <ThemeSwatchesPrimary />,
  desc: t('settingAppearance.primaryColor.desc'),
  label: t('settingAppearance.primaryColor.title'),
  minWidth: undefined,
  name: 'primaryColor',
},
{
  children: <ThemeSwatchesNeutral />,
  desc: t('settingAppearance.neutralColor.desc'),
  label: t('settingAppearance.neutralColor.title'),
  minWidth: undefined,
  name: 'neutralColor',
}
```

这里有一个重要点：调用处没有显式传入 `value` 和 `onChange`，但色板组件本身定义了这两个 props。根据当前片段推断，`@lobehub/ui` 的 `Form` 会根据表单项的 `name`，把受控表单字段的 `value/onChange` 注入到 `children` 中。依据是：`ThemeSwatchesPrimary` 和 `ThemeSwatchesNeutral` 都是受控组件形态，而调用处只通过 `name: 'primaryColor'`、`name: 'neutralColor'` 绑定字段。

再往上，`Appearance/index.tsx` 从用户设置 store 中取当前配置：

```ts
const { general } = useUserStore(settingsSelectors.currentSettings, isEqual);
```

然后把它作为表单初始值：

```tsx
<Form initialValues={general} ... />
```

当表单值变化时，会调用：

```ts
await setSettings({ general: value });
```

因此，色板选择最终写入的是用户设置里的 `general.primaryColor` 和 `general.neutralColor`。

这些字段的类型定义在：

```text
packages/types/src/user/settings/general.ts
```

对应字段是：

```ts
neutralColor?: NeutralColors;
primaryColor?: PrimaryColors;
```

下游应用主题的位置是：

```text
src/layout/GlobalProvider/AppTheme.tsx
```

它通过 selector 读取用户设置：

```ts
userGeneralSettingsSelectors.primaryColor(s)
userGeneralSettingsSelectors.neutralColor(s)
```

然后传给 `ThemeProvider`：

```tsx
customTheme={{
  neutralColor: neutralColor ?? defaultNeutralColor,
  primaryColor: primaryColor ?? defaultPrimaryColor,
}}
```

同时还会把它们写入 cookie：

```ts
setCookie(LOBE_THEME_PRIMARY_COLOR, primaryColor);
setCookie(LOBE_THEME_NEUTRAL_COLOR, neutralColor);
```

所以整体链路是：

```text
ThemeSwatches 用户点击
→ ColorSwatches onChange
→ findCustomThemeName 反查颜色名称
→ Form 字段 primaryColor / neutralColor 更新
→ useUserStore.setSettings({ general: value })
→ userGeneralSettingsSelectors 读取设置
→ AppTheme ThemeProvider customTheme 生效
```

## 运行/调用流程

页面层入口有两个相关场景。

第一个是通用设置页：

```text
src/routes/(main)/settings/common/index.tsx
```

它渲染：

```tsx
<Common />
<Appearance />
```

第二个是外观设置页：

```text
src/routes/(main)/settings/appearance/index.tsx
```

它渲染：

```tsx
<Common />
<Appearance />
<Desktop />
<ChatAppearance />
```

也就是说，`ThemeSwatches` 不是独立页面，而是嵌在 `Appearance` 表单中的一个字段控件。

具体流程如下：

1. 用户进入设置页的“通用”或“外观”相关页面。
2. 页面渲染 `Appearance`。
3. `Appearance` 从 `useUserStore` 读取当前 `general` 设置。
4. 如果用户状态还没初始化，先显示 `Skeleton`。
5. 初始化完成后，`Form` 用 `initialValues={general}` 填充表单。
6. `primaryColor` 字段对应 `ThemeSwatchesPrimary`。
7. `neutralColor` 字段对应 `ThemeSwatchesNeutral`。
8. 用户点击某个颜色格子。
9. `ColorSwatches` 把被选中的颜色值传给 `handleSelect`。
10. `handleSelect` 用 `findCustomThemeName('primary' | 'neutral', v)` 把颜色值反查成主题名。
11. 组件调用 `onChange?.(name || '')`，把主题名交给表单。
12. `Form` 触发 `onValuesChange`。
13. `Appearance` 调用 `setSettings({ general: value })` 保存设置。
14. `AppTheme` 读取新的 `primaryColor/neutralColor`，传给 `ThemeProvider`，界面主题随之更新。

这里的“default”选项需要特别注意。它在 UI 上是一个透明颜色格子，但真正向上层传递时不是透明色字符串，而是空字符串。根据当前片段推断，这代表清除用户自定义颜色，让 `AppTheme` 回退到 `defaultPrimaryColor` 或 `defaultNeutralColor`。

## 小白阅读顺序

建议按这个顺序读：

1. 先读 `ThemeSwatches/index.ts`  
   了解这个目录对外只暴露两个组件：`ThemeSwatchesPrimary` 和 `ThemeSwatchesNeutral`。

2. 再读 `ThemeSwatchesPrimary.tsx`  
   重点看三个点：`IProps`、`handleSelect`、`ColorSwatches` 的 `colors/value/onChange`。读完这个文件后，基本就理解了主色选择的完整逻辑。

3. 接着读 `ThemeSwatchesNeutral.tsx`  
   它和主色组件几乎同构。对比阅读可以看出：两个组件的区别主要是颜色类型、颜色映射表、`findCustomThemeName` 的第一个参数，以及可选颜色列表。

4. 然后读 `src/routes/(main)/settings/common/features/Appearance/index.tsx`  
   这里能看到色板组件如何进入设置表单，以及字段名为什么是 `primaryColor` 和 `neutralColor`。

5. 再读 `packages/types/src/user/settings/general.ts`  
   这里能确认这两个字段属于用户通用设置，并且类型来自 `@lobehub/ui`。

6. 最后读 `src/layout/GlobalProvider/AppTheme.tsx`  
   这里能看到保存后的颜色设置如何真正应用到 `ThemeProvider`，也就是 UI 主题最终生效的位置。

## 常见误区

第一个误区是把 `value` 理解成具体颜色值。  
在这两个组件里，`value` 是 `PrimaryColors` 或 `NeutralColors` 类型的主题名称，不是 `#1677ff` 这样的颜色字符串。组件内部会用 `primaryColors[value]` 或 `neutralColors[value]` 转成实际颜色。

第二个误区是认为 `ThemeSwatches` 会自己保存设置。  
它不会访问 `useUserStore`，也不会调用 `setSettings`。保存动作发生在上层 `Appearance/index.tsx` 的 `Form onValuesChange` 中。

第三个误区是认为 `default` 对应某个真实主题色。  
从当前片段看，`default` 在色板中用透明色表示，选择后通过 `name || ''` 传出空字符串。下游 `AppTheme` 再通过 `primaryColor ?? defaultPrimaryColor`、`neutralColor ?? defaultNeutralColor` 回退默认值。需要注意的是，如果空字符串是否会被进一步规范化，取决于 store 或表单层的处理；仅根据当前片段，只能确定组件传出的是 `''`。

第四个误区是忽略 `findCustomThemeName` 的作用。  
`ColorSwatches` 的 `onChange` 给到的是颜色值，而用户设置里保存的是主题名。`findCustomThemeName('primary', v)` 和 `findCustomThemeName('neutral', v)` 就是中间的反查桥梁。

第五个误区是只看 `ThemeSwatches` 目录就以为主题已经生效。  
这个目录只负责选择。真正让主题生效的是 `src/layout/GlobalProvider/AppTheme.tsx` 里的 `ThemeProvider customTheme`。

第六个误区是新增颜色时只改一个地方。  
如果要新增主色或中性色，不能只在 `colors` 数组里加一项，还要确认 `@lobehub/ui` 里的 `primaryColors` / `neutralColors` 是否存在对应 key，`findCustomThemeName` 能否反查，`PrimaryColors` / `NeutralColors` 类型是否包含该名称，以及 `color` 命名空间里是否有对应翻译 key。
