# 文件：src/config/routes/index.ts

## 文件职责
这个文件位于 `src/config/routes`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { type LucideIcon } from 'lucide-react';
import {
export interface NavigationRoute {
export const NAVIGATION_ROUTES: NavigationRoute[] = [
export const getRouteById = (id: string): NavigationRoute | undefined =>
export const getNavigableRoutes = (): NavigationRoute[] =>
```

## 主要对外内容
```text
export interface NavigationRoute {
export const NAVIGATION_ROUTES: NavigationRoute[] = [
export const getRouteById = (id: string): NavigationRoute | undefined =>
export const getNavigableRoutes = (): NavigationRoute[] =>
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { type LucideIcon } from 'lucide-react';
import {
  BrainCircuit,
  FilePenIcon,
  Image,
  LibraryBigIcon,
  ListTodoIcon,
  Settings,
  ShapesIcon,
  Video,
} from 'lucide-react';

export interface NavigationRoute {
  /** CMDK i18n key in common namespace */
  cmdkKey: string;
  /** Electron i18n key in electron namespace */
  electronKey: string;
  /** Route icon component */
  icon: LucideIcon;
  /** Unique route identifier */
  id: string;
  /** Keywords for CMDK search (fallback) */
  keywords?: string[];
  /** i18n key for CMDK keywords in common namespace */
  keywordsKey?: string;
  /** Route path */
  path: string;
  /** Path prefix for checking current location */
  pathPrefix: string;
  /** Whether route supports dynamic titles (for specific items) */
  useDynamicTitle?: boolean;
}

/**
 * Shared navigation route configuration
 * Used by both Electron navigation and CommandMenu (CMDK)
 */
export const NAVIGATION_ROUTES: NavigationRoute[] = [
  {
    cmdkKey: 'cmdk.community',
    electronKey: 'navigation.discover',
    icon: ShapesIcon,
    id: 'community',
    keywords: ['discover', 'market', 'assistant', 'model', 'provider', 'mcp'],
    keywordsKey: 'cmdk.keywords.community',
    path: '/community',
    pathPrefix: '/community',
  },
  {
    cmdkKey: 'cmdk.video',
    electronKey: 'navigation.video',
    icon: Video,
    id: 'video',
    keywords: ['video', 'generate', 'seedance', 'kling'],
    keywordsKey: 'cmdk.keywords.video',
    path: '/video',
    pathPrefix: '/video',
  },
  {
    cmdkKey: 'cmdk.painting',
    electronKey: 'navigation.image',
    icon: Image,
    id: 'image',
    keywords: ['painting', 'art', 'generate', 'draw'],
    keywordsKey: 'cmdk.keywords.painting',
    path: '/image',
    pathPrefix: '/image',
  },
  {
    cmdkKey: 'cmdk.resource',
    electronKey: 'navigation.resources',
    icon: LibraryBigIcon,
    id: 'resource',
    keywords: ['knowledge', 'files', 'library', 'documents'],
    keywordsKey: 'cmdk.keywords.resources',
    path: '/resource',
    pathPrefix: '/resource',
  },
  {
    cmdkKey: 'cmdk.pages',
    electronKey: 'navigation.pages',
    icon: FilePenIcon,
    id: 'page',
    keywords: ['documents', 'write', 'notes'],
    keywordsKey: 'cmdk.keywords.pages',
    path: '/page',
    pathPrefix: '/page',
    useDynamicTitle: true,
  },
  {
    cmdkKey: 'cmdk.memory',
    electronKey: 'navigation.memory',
    icon: BrainCircuit,
    id: 'memory',
    keywords: ['identities', 'contexts', 'preferences', 'experiences'],
    keywordsKey: 'cmdk.keywords.memory',
    path: '/memory',
    pathPrefix: '/memory',
  },
  {
    cmdkKey: 'cmdk.tasks',
    electronKey: 'navigation.tasks',
    icon: ListTodoIcon,
    id: 'tasks',
    keywords: ['tasks', 'todo', 'agent', 'kanban'],
    keywordsKey: 'cmdk.keywords.tasks',
    path: '/tasks',
    pathPrefix: '/tasks',
  },
  {
    cmdkKey: 'cmdk.settings',
    electronKey: 'navigation.settings',
    icon: Settings,
    id: 'settings',
    keywords: ['settings', 'preferences', 'configuration', 'options'],
    keywordsKey: 'cmdk.keywords.settings',
    path: '/settings',
    pathPrefix: '/settings',
  },
];

/**
 * Get route configuration by id
 */
export const getRouteById = (id: string): NavigationRoute | undefined =>
  NAVIGATION_ROUTES.find((r) => r.id === id);

/**
 * Get navigable routes for CMDK (excludes settings which has separate handling)
 */
export const getNavigableRoutes = (): NavigationRoute[] =>
  NAVIGATION_ROUTES.filter((r) =>
    ['community', 'video', 'image', 'resource', 'page', 'memory'].includes(r.id),
  );

```
