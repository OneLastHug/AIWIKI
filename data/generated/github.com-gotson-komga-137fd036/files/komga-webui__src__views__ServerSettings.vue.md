# 文件：komga-webui/src/views/ServerSettings.vue

## 它负责什么

这个文件实现的是后端管理里的“服务器设置”编辑页。它不是单纯展示信息，而是一个完整的设置表单：先从后端拉取当前配置，再把配置拆成可编辑字段，做校验、保存、回填，最后在某些关键配置变化后触发后续动作。

从现有代码看，它最核心的职责有三件：

1. 编辑服务器级配置，例如 `serverPort`、`serverContextPath`、`taskPoolSize`、`thumbnailSize`、`koboPort` 等。
2. 处理“多来源配置”的展示方式，尤其是 `serverPort`、`serverContextPath`、`kepubifyPath` 这类字段，会同时展示 `configurationSource` 和 `databaseSource`。
3. 在 `thumbnailSize` 变化后，弹出确认框，决定是否重建缩略图。

## 关键组成

- `template` 部分是一整块表单界面，使用了 `v-container`、`v-row`、`v-col` 和一系列 Vuetify 控件。
- 主要输入项包括：
  - `v-select`：`thumbnailSize`
  - `v-checkbox`：`deleteEmptyCollections`、`deleteEmptyReadLists`、`renewRememberMeKey`、`koboProxy`
  - `v-text-field`：`taskPoolSize`、`rememberMeDurationDays`、`serverPort`、`serverContextPath`、`koboPort`、`kepubifyPath`
- `file-browser-dialog` 用来选择 `kepubifyPath`。
- `confirmation-dialog` 用来确认是否重建缩略图。
- `data()` 里维护了三个关键状态：
  - `form`：当前编辑值
  - `existingSettings`：后端返回的原始设置
  - `dialogRegenerateThumbnails`、`modalFileBrowserKepubify`：两个弹窗状态
- `validations` 使用 `vuelidate` 规则，约束最小值、最大值、必填和 `serverContextPath` 格式。
- `computed` 里有三类东西：
  - `thumbnailSizes()`：把 `ThumbnailSizeDto` 转成下拉选项
  - 若干 `xxxErrors()`：把校验失败转成提示文本
  - `saveDisabled()`、`discardDisabled()`：控制按钮可用性
- `methods` 里有三个动作：
  - `refreshSettings()`：拉取并回填设置
  - `saveSettings()`：只提交被修改过的字段
  - `regenerateThumbnails()`：调用书籍服务触发缩略图重建

这里还依赖 `komga-webui/src/types/komga-settings.ts` 里的 `SettingsDto`、`SettingMultiSource`、`ThumbnailSizeDto`，它们定义了这个页面要读写的数据形状。

## 上下游关系

上游入口在 `komga-webui/src/router.ts`。根据当前片段推断，路由会动态加载 `SettingsServer.vue`，而 `SettingsServer.vue` 再把 `ServerSettings.vue` 和 `ServerManagement.vue` 组合到同一个设置页里，所以这个文件本身是“页面中的一个设置面板”，不是独立路由页。

它的直接数据上游是 `this.$komgaSettings.getSettings()`。根据当前片段推断，`$komgaSettings` 是通过 Vue 插件或原型注入的全局服务对象，负责从后端读取和更新设置。

它的直接下游主要有两个：

- `this.$komgaSettings.updateSettings(newSettings)`：提交修改
- `this.$komgaBooks.regenerateThumbnails(forBiggerResultOnly)`：在缩略图尺寸变更后触发书籍缩略图重建

另外，`existingSettings.serverPort?.configurationSource`、`existingSettings.serverContextPath?.configurationSource`、`existingSettings.kepubifyPath?.configurationSource` 说明这些字段不是简单字符串或数字，而是来自 `SettingMultiSource<T>` 的复合结构，页面要同时处理“配置来源”和“数据库里的实际值”。

## 运行/调用流程

1. 组件挂载后执行 `mounted()`，立即调用 `refreshSettings()`。
2. `refreshSettings()` 从 `$komgaSettings.getSettings()` 读取当前设置。
3. 读取结果先合并进 `form`，再把 `serverPort`、`serverContextPath`、`kepubifyPath` 这些多来源字段单独改成 `databaseSource`，这样表单里拿到的是可编辑的真实值。
4. 同时把整份设置保存到 `existingSettings`，用于提示配置来源、显示 placeholder、判断缩略图尺寸是否变化。
5. 用户编辑字段时，`@input`、`@change`、`@blur` 会触发 `$v.form.xxx.$touch()`，让校验状态变成 dirty。
6. `saveDisabled` 依赖 `$invalid` 和 `$anyDirty`，所以没改动或校验没过时不能保存。
7. 点击保存后，`saveSettings()` 只把 dirty 的字段组装进 `newSettings`，然后调用 `$komgaSettings.updateSettings(newSettings)`。
8. 保存成功后再次 `refreshSettings()` 回填最新值。
9. 如果 `thumbnailSize` 被改了，页面会打开 `dialogRegenerateThumbnails`。
10. 用户在确认框里选择后，会调用 `regenerateThumbnails(true/false)`，把选择结果传给 `$komgaBooks.regenerateThumbnails()`。

## 小白阅读顺序

1. 先看 `template`，搞清楚页面上有哪些字段、哪些按钮、哪些弹窗。
2. 再看 `data()`，理解每个表单字段的初始值和页面状态。
3. 接着看 `validations` 和各个 `xxxErrors()`，理解哪些输入被限制、错误提示怎么来的。
4. 然后读 `refreshSettings()`，看设置是怎么从后端加载并回填到表单的。
5. 再读 `saveSettings()`，重点看它如何只提交 dirty 字段，以及为什么 `serverContextPath` 空字符串会被转成 `null`。
6. 最后看 `SettingsServer.vue` 和 `router.ts`，把这个组件放回整个设置页和路由入口里。

## 常见误区

- `form` 里的值不等于后端原始值。像 `serverPort`、`serverContextPath`、`kepubifyPath` 这些字段，界面编辑的是 `databaseSource`，不是完整的 `SettingMultiSource` 对象。
- 保存不是整表覆盖，而是“按 dirty 字段打补丁”。没改过的字段不会被发给后端。
- `serverContextPath` 为空时会被显式转成 `null`，不是直接传空字符串。
- 看到 `configurationSource` 的 tooltip，不代表这个值不能改，只是提示当前值来自哪里。
- `thumbnailSize` 改动后不会立刻重建缩略图，而是先弹确认框，让用户决定是否执行。
- `renewRememberMeKey` 是一次性的动作开关，不是普通长期配置项，保存时会作为更新参数发给后端。
