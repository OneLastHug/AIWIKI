# 文件：mobile/app/(tabs)/files/index.tsx

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
import React, { useEffect } from 'react';
import { View, StyleSheet } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { DrawerActions } from '@react-navigation/routers';
import { Ionicons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';
import { MobileFileTabHeader } from '../../../src/components/files/MobileFileTabHeader';
import { FileContentView } from '../../../src/components/files/FileContentView';
import { useFilesTab } from '../../../src/context/FilesTabContext';
import { useWorkspace } from '../../../src/context/WorkspaceContext';
import { ThemedText } from '../../../src/components/ui/ThemedText';
import { useThemeColor } from '../../../src/hooks/useThemeColor';

export default function FilesIndexScreen() {
  const { t } = useTranslation();
  const { tabs, activeTabIndex, closeAllTabs } = useFilesTab();
  const { currentWorkspace, workspaceChanged } = useWorkspace();
  const navigation = useNavigation();
  const background = useThemeColor({}, 'background');
  const iconColor = useThemeColor({}, 'icon');

  // Reset tabs when workspace changes to a different project
  useEffect(() => {
    if (workspaceChanged) {
      closeAllTabs();
    }
  }, [workspaceChanged, closeAllTabs]);

  const openDrawer = () => {
    navigation.dispatch(DrawerActions.openDrawer());
  };

  const currentTab = tabs[activeTabIndex];

  // No workspace state
  if (!currentWorkspace) {
    return (
      <View style={[styles.container, { backgroundColor: background }]}>
        <MobileFileTabHeader onOpenDrawer={openDrawer} />
        <View style={styles.emptyState}>
          <Ionicons name='folder-open-outline' size={48} color={iconColor} style={{ opacity: 0.4 }} />
          <ThemedText style={styles.emptyText}>{t('workspace.noWorkspace')}</ThemedText>
        </View>
      </View>
    );
  }

  // No file open — show empty state with hint to open drawer
  if (!currentTab) {
    return (
      <View style={[styles.container, { backgroundColor: background }]}>
        <MobileFileTabHeader onOpenDrawer={openDrawer} />
        <View style={styles.emptyState}>
          <Ionicons name='document-outline' size={48} color={iconColor} style={{ opacity: 0.4 }} />
          <ThemedText style={styles.emptyText}>{t('files.empty')}</ThemedText>
        </View>
      </View>
    );
  }

  return (
    <View style={[styles.container, { backgroundColor: background }]}>
      <MobileFileTabHeader onOpenDrawer={openDrawer} />
      <FileContentView path={currentTab.path} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  emptyState: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 12,
    padding: 32,
  },
  emptyText: {
    textAlign: 'center',
    opacity: 0.6,
    fontSize: 15,
  },
});

```
