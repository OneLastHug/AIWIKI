# 文件：mobile/app/index.tsx

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
import { useEffect, useState } from 'react';
import { Redirect } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { useConnection } from '../src/context/ConnectionContext';

export default function IndexScreen() {
  const { isConfigured, connectionState, isRestoring } = useConnection();
  const [authFailedExpired, setAuthFailedExpired] = useState(false);

  // Give auto-recovery 5 seconds before redirecting to connect screen
  useEffect(() => {
    if (connectionState === 'auth_failed') {
      const timer = setTimeout(() => setAuthFailedExpired(true), 5000);
      return () => clearTimeout(timer);
    }
    setAuthFailedExpired(false);
  }, [connectionState]);

  useEffect(() => {
    if (!isRestoring) {
      SplashScreen.hideAsync();
    }
  }, [isRestoring]);

  // Keep splash screen visible while restoring saved connection
  if (isRestoring) {
    return null;
  }

  if (!isConfigured || (connectionState === 'auth_failed' && authFailedExpired)) {
    return <Redirect href='/connect' />;
  }

  return <Redirect href='/(tabs)/chat' />;
}

```
