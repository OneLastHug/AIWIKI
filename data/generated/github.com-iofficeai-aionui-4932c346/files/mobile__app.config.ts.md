# 文件：mobile/app.config.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
import { ExpoConfig, ConfigContext } from 'expo/config';

import VERSION from './versions/version.json';

export default ({ config }: ConfigContext): ExpoConfig => {
  return {
    ...config,
    name: 'AionUi Mobile',
    slug: 'aionui-mobile',
    version: VERSION.version,
    orientation: 'portrait',
    icon: './assets/images/icon.png',
    scheme: 'aionui-mobile',
    userInterfaceStyle: 'automatic',
    ios: {
      supportsTablet: true,
      bundleIdentifier: 'ai.resopod.aionui',
      buildNumber: String(VERSION.buildNumber),
      infoPlist: {
        ITSAppUsesNonExemptEncryption: false,
        NSCameraUsageDescription: 'AionUi needs camera access to scan QR codes for server login.',
      },
    },
    android: {
      adaptiveIcon: {
        foregroundImage: './assets/images/icon.png',
        backgroundColor: '#000000',
      },
      package: 'ai.resopod.aionui',
      versionCode: VERSION.buildNumber,
    },
    web: {
      output: 'static',
      favicon: './assets/images/icon.png',
    },
    plugins: ['expo-router', 'expo-secure-store', 'expo-dev-client', 'expo-camera'],
    experiments: {
      typedRoutes: true,
    },
    extra: {
      eas: {
        projectId: '34b66303-fd5c-4d86-a790-0665d55f2017',
      },
    },
  };
};

```
