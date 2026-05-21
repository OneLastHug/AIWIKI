# 文件：src/server/services/agentDocumentVfs/index.ts

## 文件职责
这个文件位于 `src/server/services/agentDocumentVfs`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import type { LobeChatDatabase } from '@lobechat/database';
import {
import { DOCUMENT_FOLDER_TYPE } from '@/database/schemas';
import { createMarkdownEditorSnapshot } from '../agentDocuments/headlessEditor';
import { AgentDocumentVfsError } from './errors';
import { createSkillMount } from './mounts/skills/createSkillMount';
import {
import type { SkillMount } from './mounts/skills/SkillMount';
import type { SkillMountNode } from './mounts/skills/types';
import type {
export class AgentDocumentVfsService {
```

## 主要对外内容
```text
const LOBE_PATH = './lobe';
const LOBE_SKILLS_PATH = './lobe/skills';
const DEFAULT_LIST_LIMIT = 100;
const MAX_LIST_LIMIT = 500;
const MAX_RECURSIVE_COPY_CHILDREN = 5000;
const SYNTHETIC_DIRECTORY_MODE = AgentAccess.LIST | AgentAccess.READ;
interface AgentDocumentVfsContext {
interface AgentDocumentWriteOptions {
interface AgentDocumentMkdirOptions {
interface AgentDocumentDeleteOptions {
interface AgentDocumentCopyOptions {
export class AgentDocumentVfsService {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import type { LobeChatDatabase } from '@lobechat/database';

import {
  AgentAccess,
  type AgentDocument,
  AgentDocumentModel,
} from '@/database/models/agentDocuments';
import { DOCUMENT_FOLDER_TYPE } from '@/database/schemas';

import { createMarkdownEditorSnapshot } from '../agentDocuments/headlessEditor';
import { AgentDocumentVfsError } from './errors';
import { createSkillMount } from './mounts/skills/createSkillMount';
import {
  getUnifiedSkillNamespaceParentPath,
  getUnifiedSkillNamespaceRootPath,
  isUnifiedSkillPath as isSkillPath,
  SKILL_NAMESPACES,
  type SkillNamespace,
} from './mounts/skills/path';
import type { SkillMount } from './mounts/skills/SkillMount';
import type { SkillMountNode } from './mounts/skills/types';
import type {
  AgentDocumentListOptions,
  AgentDocumentNode,
  AgentDocumentReadResult,
  AgentDocumentStats,
  AgentDocumentTrashEntry,
} from './types';

const LOBE_PATH = './lobe';
const LOBE_SKILLS_PATH = './lobe/skills';
/**
 * Default cap for VFS directory reads while the public API still returns arrays.
 * Keep this near path constants because it is part of the VFS surface, not storage policy.
 */
const DEFAULT_LIST_LIMIT = 100;
/**
 * Maximum one-call VFS directory read size.
 * Prevents accidental wide-directory materialization from CLI or tool callers.
 */
const MAX_LIST_LIMIT = 500;
/**
 * Internal recursive copy safety cap.
 * This is intentionally separate from public listing pagination so `rename()` never drops children.
 */
const MAX_RECURSIVE_COPY_CHILDREN = 5000;

const SYNTHETIC_DIRECTORY_MODE = AgentAccess.LIST | AgentAccess.READ;

interface AgentDocumentVfsContext {
  agentId: string;
  topicId?: string;
}

interface AgentDocumentWriteOptions {
  createMode?: 'always-new' | 'if-missing' | 'must-exist';
}

interface AgentDocumentMkdirOptions {
  recursive?: boolean;
}

interface AgentDocumentDeleteOptions {
  recursive?: boolean;
}

interface AgentDocumentCopyOptions {
  overwrite?: boolean;
}

/**
 * Unified filesystem view for ordinary agent documents plus mounted subtrees.
 *
 * Use when:
 * - Router path APIs need one filesystem-shaped surface
 * - CLI commands should stop reasoning about skill-only path aliases
 *
 * Expects:
 * - Ordinary documents remain backed by `agent_documents` + `documents`
 * - Mounted subtrees can translate into existing services during migration
 *
 * Returns:
 * - Plain-data VFS nodes, stats, and read results
 *
 * Call stack:
 *
 * agentDocumentRouter.listDocumentsByPath/statDocumentByPath
 *   -> {@link AgentDocumentVfsService.list}
 *   -> {@link AgentDocumentVfsService.stat}
 *     -> ordinary document query helpers
 *     -> mounted subtree query helpers
 */
export class AgentDocumentVfsService {
  private agentDocumentModel: AgentDocumentModel;
  private skillMount: SkillMount;

  constructor(db: LobeChatDatabase, userId: string) {
    this.agentDocumentModel = new AgentDocumentModel(db, userId);
    this.skillMount = createSkillMount(db, userId);
  }

  /**
   * Lists direct children for a unified VFS directory path.
   *
   * Use when:
   * - Implementing `ls` or `tree`
   * - Enumerating either ordinary documents or mounted subtree entries
   *
   * Expects:
   * - Only direct children are returned
   * - The current phase ignores pagination cursors while preserving the call shape
   *
   * Returns:
   * - Plain-data directory entries
   */
  async list(
    path: string,
    ctx: AgentDocumentVfsContext,
    options: AgentDocumentListOptions = {},
  ): Promise<AgentDocumentNode[]> {
    // NOTICE:
    // This directory listing does not copy Node.js `readdir` exactly.
    // The backend is document rows plus mounted subtrees rather than a local syscall-driven filesystem.
    // We keep `list` lightweight and avoid content loads so callers do not trigger a `list -> stat` N+1 loop.
    const normalizedPath = normalizeAgentDocumentPath(path);

    if (normalizedPath === './') {
      const [ordinaryNodes, lobeNode] = await Promise.all([
        this.listOrdinaryNodes(ctx.agentId, null, './', options),
        Promise.resolve(this.createSyntheticDirectoryNode(LOBE_PATH, 'lobe')),
      ]);

      return [...ordinaryNodes, lobeNode];
    }

    const syntheticChildren = this.listSyntheticChildren(normalizedPath);

    if (syntheticChildren) return syntheticChildren;

    if (isSkillPath(normalizedPath)) {
      const nodes = await this.skillMount.list({
        agentId: ctx.agentId,
        path: normalizedPath,
        topicId: ctx.topicId,
      });

      return applyListLimit(
        nodes.map((node) => this.toMountedNode(node)),
        options,
      );
    }

    const parentNode = await this.resolveOrdinaryPath(normalizedPath, ctx.agentId);

    if (!parentNode) {
      throw new AgentDocumentVfsError(`Path not found: ${normalizedPath}`, 'NOT_FOUND');
    }

    if (parentNode.fileType !== DOCUMENT_FOLDER_TYPE) {
      throw new AgentDocumentVfsError(`Path is not a directory: ${normalizedPath}`, 'BAD_REQUEST');
    }

    return this.listOrdinaryNodes(ctx.agentId, parentNode.documentId, normalizedPath, options);
  }

  /**
   * Resolves a unified VFS path into detailed node state.
   *
   * Use when:
   * - Implementing `stat`
   * - Backing the `statDocumentByPath` router API
   *
   * Returns:
   * - Detailed VFS node state or `undefined` when the path is not found
   */
  async stat(path: string, ctx: AgentDocumentVfsContext): Promise<AgentDocumentStats | undefined> {
    const normalizedPath = normalizeAgentDocumentPath(path);
    const syntheticNode = this.getSyntheticNode(normalizedPath);

    if (syntheticNode) return syntheticNode;

    if (isSkillPath(normalizedPath)) {
      const node = await this.skillMount.get({
        agentId: ctx.agentId,
        path: normalizedPath,
        topicId: ctx.topicId,
      });

      return this.toMountedStats(node);
    }

    const ordinaryNode = await this.resolveOrdinaryPath(normalizedPath, ctx.agentId);
    return ordinaryNode ? this.toOrdinaryStats(ordinaryNode, normalizedPath) : undefined;
  }

  /**
   * Reads file content from a unified VFS path.
   *
   * Use when:
   * - A caller needs the file body rather than only `stat` metadata
   *
   * Returns:
   * - File content payload
   */
  async read(path: string, ctx: AgentDocumentVfsContext): Promise<AgentDocumentReadResult> {
    const normalizedPath = normalizeAgentDocumentPath(path);

    if (isSkillPath(normalizedPath)) {
      const node = await this.skillMount.get({
        agentId: ctx.agentId,
        path: normalizedPath,
        topicId: ctx.topicId,
      });

      if (node.type !== 'file') {
        throw new AgentDocumentVfsError(`Path is not a file: ${path}`, 'BAD_REQUEST');
      }

      return {
        content: node.content ?? '',
        contentType: node.contentType,
        path: node.path,
      };
    }

    const node = await this.resolveOrdinaryPath(normalizedPath, ctx.agentId);

    if (!node) {
      throw new AgentDocumentVfsError(`Path not found: ${path}`, 'NOT_FOUND');
    }

    if (node.fileType === DOCUMENT_FOLDER_TYPE) {
      throw new AgentDocumentVfsError(`Path is not a file: ${path}`, 'BAD_REQUEST');
    }

    return {
      content: node.content,
      contentType: 'text/markdown',
      path: normalizedPath,
    };
  }

  /**
   * Writes file content through the unified VFS surface.
   *
   * Use when:
   * - Updating an ordinary agent document by path
   * - Creating or updating a writable mounted skill entry during the migration period
   *
   * Expects:
   * - `createMode` controls whether missing paths are created or rejected
   *
   * Returns:
   * - The updated file state
   */
  async write(
    path: string,
    content: string,
    ctx: AgentDocumentVfsContext,
    options: AgentDocumentWriteOptions = {},
  ): Promise<AgentDocumentStats> {
    const normalizedPath = normalizeAgentDocumentPath(path);
    const createMode = options.createMode ?? 'if-missing';

    if (isSkillPath(normalizedPath)) {
      return this.writeMountedSkill(normalizedPath, content, ctx, createMode);
    }

    return this.writeOrdinaryDocument(normalizedPath, content, ctx, createMode);
  }

  /**
   * Creates a directory through the unified VFS surface.
   *
   * Use when:
   * - CLI `mkdir` targets the ordinary document tree
   *
   * Returns:
   * - The created or existing directory state
   */
  async mkdir(
    path: string,
    ctx: AgentDocumentVfsContext,
    options: AgentDocumentMkdirOptions = {},
  ): Promise<AgentDocumentStats> {
    const normalizedPath = normalizeAgentDocumentPath(path);

    if (isSkillPath(normalizedPath)) {
      throw new AgentDocumentVfsError(
        `mkdir is not supported for mounted path: ${path}`,
        'BAD_REQUEST',
      );
    }

    if (
      normalizedPath === './' ||
      normalizedPath === LOBE_PATH ||
      normalizedPath.startsWith(`${LOBE_PATH}/`)
    ) {
      throw new AgentDocumentVfsError(`Cannot create reserved path: ${path}`, 'BAD_REQUEST');
    }

    const segments = splitAgentDocumentPath(normalizedPath);
    let parentId: string | null = null;
    let currentPath = './';
    let currentNode: AgentDocument | undefined;

    for (const [index, segment] of segments.entries()) {
      const isLeaf = index === segments.length - 1;
      const nextPath = buildOrdinaryPath(currentPath, segment);
      const existing = await this.agentDocumentModel.findByParentAndFilename(
        ctx.agentId,
        parentId,
        segment,
      );

      if (existing) {
        if (existing.fileType !== DOCUMENT_FOLDER_TYPE) {
          throw new AgentDocumentVfsError(
            `Path segment is not a directory: ${nextPath}`,
            'BAD_REQUEST',
          );
        }

        currentNode = existing;
        parentId = existing.documentId;
        currentPath = nextPath;
        continue;
      }

      if (!isLeaf && !options.recursive) {
        throw new AgentDocumentVfsError(`Parent path not found: ${nextPath}`, 'BAD_REQUEST');
      }

      const created = await this.agentDocumentModel.create(ctx.agentId, segment, '', {
        fileType: DOCUMENT_FOLDER_TYPE,
        parentId,
        title: segment,
      });

      currentNode = created;
      parentId = created.documentId;
      currentPath = nextPath;
    }

    if (!currentNode) {
      throw new AgentDocumentVfsError(`Invalid directory path: ${path}`, 'BAD_REQUEST');
    }

    return this.toOrdinaryStats(currentNode, normalizedPath);
  }

  /**
   * Renames or moves a path through the unified VFS surface.
   *
   * Use when:
   * - CLI `mv` needs filesystem-style `rename(from, to)`
   *
   * Returns:
   * - The destination node state
   */
  async rename(
    fromPath: string,
    toPath: string,
    ctx: AgentDocumentVfsContext,
    options: AgentDocumentCopyOptions = {},
  ): Promise<AgentDocumentStats> {
    const sourcePath = normalizeAgentDocumentPath(fromPath);
    const destinationPath = normalizeAgentDocumentPath(toPath);

    if (sourcePath === destinationPath) {
      const existing = await this.stat(sourcePath, ctx);

      if (!existing) {
        throw new AgentDocumentVfsError(`Path not found: ${fromPath}`, 'NOT_FOUND');
      }

      return existing;
    }

    const sourceNode = await this.stat(sourcePath, ctx);

    if (!sourceNode) {
      throw new AgentDocumentVfsError(`Path not found: ${fromPath}`, 'NOT_FOUND');
    }

    assertNotSelfReferentialCopy(sourcePath, destinationPath, sourceNode);

    if (!isSkillPath(sourcePath) && !isSkillPath(destinationPath)) {
      return this.renameOrdinaryPath(sourcePath, destinationPath, ctx, options);
    }

    const copied = await this.copy(sourcePath, destinationPath, ctx, options);
    await this.delete(sourcePath, ctx, {
      recursive: copied.type === 'directory',
    });

    return copied;
  }

  /**
   * Copies a path through the unified VFS surface.
   *
   * Use when:
   * - CLI `cp` needs filesystem-style path copying
   *
   * Returns:
   * - The destination node state
   */
  async copy(
    fromPath: string,
    toPath: string,
    ctx: AgentDocumentVfsContext,
    options: AgentDocumentCopyOptions = {},
  ): Promise<AgentDocumentStats> {
    const sourcePath = normalizeAgentDocumentPath(fromPath);
    const destinationPath = normalizeAgentDocumentPath(toPath);
    const sourceNode = await this.stat(sourcePath, ctx);

    if (!sourceNode) {
      throw new AgentDocumentVfsError(`Path not found: ${fromPath}`, 'NOT_FOUND');
    }

    assertNotSelfReferentialCopy(sourcePath, destinationPath, sourceNode);

    const existingDestination = await this.stat(destinationPath, ctx);

    if (existingDestination && !options.overwrite) {
      throw new AgentDocumentVfsError(`Path already exists: ${toPath}`, 'BAD_REQUEST');
    }

    if (sourceNode.type === 'directory') {
      await this.mkdir(destinationPath, ctx, { recursive: true });

      const children = await this.listChildrenForRecursiveCopy(sourcePath, ctx);
      for (const child of children) {
        await this.copy(child.path, `${destinationPath}/${child.name}`, ctx, options);
      }

      const copiedDirectory = await this.stat(destinationPath, ctx);

      if (!copiedDirectory) {
        throw new AgentDocumentVfsError(`Failed to reload copied path: ${toPath}`, 'BAD_REQUEST');
      }

      return copiedDirectory;
    }

    const { content } = await this.read(resolveReadablePath(sourcePath), ctx);
    return this.write(destinationPath, content, ctx, {
      createMode: options.overwrite ? 'if-missing' : 'always-new',
    });
  }

  /**
   * Soft-deletes a VFS path into agent-scoped trash.
   *
   * Use when:
   * - CLI `rm` should preserve restorable state
   *
   * Returns:
   * - Void
   */
  async delete(
    path: string,
    ctx: AgentDocumentVfsContext,
    options: AgentDocumentDeleteOptions = {},
  ): Promise<void> {
    const normalizedPath = normalizeAgentDocumentPath(path);

    if (isSkillPath(normalizedPath)) {
      await this.deleteMountedSkill(normalizedPath, ctx);
      return;
    }

    const node = await this.resolveOrdinaryPath(normalizedPath, ctx.agentId);

    if (!node) {
      throw new AgentDocumentVfsError(`Path not found: ${path}`, 'NOT_FOUND');
    }

    const subtree = await this.collectOrdinarySubtree(node, ctx.agentId, true);

    if (node.fileType === DOCUMENT_FOLDER_TYPE && !options.recursive) {
      throw new AgentDocumentVfsError(
        `recursive=true is required for directory delete: ${path}`,
        'BAD_REQUEST',
      );
    }

    for (const item of subtree) {
      await this.agentDocumentModel.delete(
        item.id,
        item.fileType === DOCUMENT_FOLDER_TYPE ? 'recursive-delete' : 'user-delete',
      );
    }
  }

  /**
   * Lists agent-scoped trash entries.
   *
   * Use when:
   * - CLI `trash ls` needs a recovery-oriented view
   *
   * Returns:
   * - Flat trash entries with reconstructed paths
   */
  async listTrash(ctx: AgentDocumentVfsContext, path?: string): Promise<AgentDocumentTrashEntry[]> {
    const deletedDocs = await this.agentDocumentModel.listDeletedByAgent(ctx.agentId);
    const entries = await Promise.all(
      deletedDocs.map(async (doc) => {
        const path = await this.buildOrdinaryPathFromNode(doc, ctx.agentId);
        return {
          ...this.toOrdinaryStats(doc, path),
          deleteReason: doc.deleteReason,
          deletedAt: doc.deletedAt ?? new Date(0),
        } satisfies AgentDocumentTrashEntry;
      }),
    );

    if (!path) return entries;

    const normalizedPath = normalizeAgentDocumentPath(path);
    return entries.filter(
      (entry) => entry.path === normalizedPath || entry.path.startsWith(`${normalizedPath}/`),
    );
  }

  /**
   * Restores a trash entry back into the live VFS tree.
   *
   * Use when:
   * - CLI `trash restore` needs to reactivate a soft-deleted path
   *
   * Returns:
   * - The restored node state
   */
  async restoreFromTrash(
    agentDocumentId: string,
    ctx: AgentDocumentVfsContext,
  ): Promise<AgentDocumentStats> {
    const root = await this.agentDocumentModel.findByIdWithOptions(agentDocumentId, {
      includeDeleted: true,
    });

    if (!root?.deletedAt) {
      throw new AgentDocumentVfsError(`Trash entry not found: ${agentDocumentId}`, 'NOT_FOUND');
    }

    const ancestors = await this.collectDeletedAncestors(root, ctx.agentId);
    const subtree = await this.collectOrdinarySubtree(root, ctx.agentId, true);

    for (const ancestor of ancestors.reverse()) {
      if (ancestor.deletedAt) {
        await this.agentDocumentModel.restore(ancestor.id);
      }
    }

    for (const item of subtree) {
      if (item.deletedAt) {
        await this.agentDocumentModel.restore(item.id);
      }
    }

    const restored = await this.resolveOrdinaryPath(
      await this.buildOrdinaryPathFromNode(root, ctx.agentId),
      ctx.agentId,
    );

    if (!restored) {
      throw new AgentDocumentVfsError(`Failed to restore path: ${agentDocumentId}`, 'BAD_REQUEST');
    }

    return this.toOrdinaryStats(
      restored,
      await this.buildOrdinaryPathFromNode(restored, ctx.agentId),
    );
  }

  /**
   * Permanently removes a trash entry and its subtree.
   *
   * Use when:
   * - CLI `trash rm` should erase recoverable state
   *
   * Returns:
   * - Void
   */
  async deletePermanently(agentDocumentId: string, ctx: AgentDocumentVfsContext): Promise<void> {
    const root = await this.agentDocumentModel.findByIdWithOptions(agentDocumentId, {
      includeDeleted: true,
    });

    if (!root?.deletedAt) {
      throw new AgentDocumentVfsError(`Trash entry not found: ${agentDocumentId}`, 'NOT_FOUND');
    }

    const subtree = await this.collectOrdinarySubtree(root, ctx.agentId, true);

    for (const item of subtree.reverse()) {
      await this.agentDocumentModel.permanentlyDelete(item.id);
    }
  }

  async restoreFromTrashByPath(
    path: string,
    ctx: AgentDocumentVfsContext,
  ): Promise<AgentDocumentStats> {
    const entry = await this.findTrashEntryByPath(path, ctx);

    if (!entry) {
      throw new AgentDocumentVfsError(`Trash entry not found: ${path}`, 'NOT_FOUND');
    }

    return this.restoreFromTrash(entry.agentDocumentId!, ctx);
  }

  async deletePermanentlyByPath(path: string, ctx: AgentDocumentVfsContext): Promise<void> {
    const entry = await this.findTrashEntryByPath(path, ctx);

    if (!entry) {
      throw new AgentDocumentVfsError(`Trash entry not found: ${path}`, 'NOT_FOUND');
    }

    await this.deletePermanently(entry.agentDocumentId!, ctx);
  }

  private async listOrdinaryNodes(
    agentId: string,
    parentId: string | null,
    parentPath: string,
    options: AgentDocumentListOptions = {},
  ): Promise<AgentDocumentNode[]> {
    const docs = await this.agentDocumentModel.listByParent(agentId, parentId, {
      cursor: options.cursor,
    });
    const visibleDocs = selectOldestByFilename(docs);
    return applyListLimit(
      visibleDocs.map((doc) =>
        this.toOrdinaryNode(doc, buildOrdinaryPath(parentPath, doc.filename)),
      ),
      options,
    );
  }

  private async resolveOrdinaryPath(
    path: string,
    agentId: string,
  ): Promise<AgentDocument | undefined> {
    return this.resolveOrdinaryPathWithOptions(path, agentId);
  }

  private async resolveOrdinaryPathWithOptions(
    path: string,
    agentId: string,
    options?: { includeDeleted?: boolean },
  ): Promise<AgentDocument | undefined> {
    if (path === './') return undefined;

    const segments = splitAgentDocumentPath(path);
    let parentId: string | null = null;
    let current: AgentDocument | undefined;

    for (const segment of segments) {
      const candidates = await this.agentDocumentModel.listByParentAndFilename(
        agentId,
        parentId,
        segment,
        {
          ...options,
        },
      );

      current = selectOldestAgentDocument(candidates);
      if (!current) return undefined;
      parentId = current.documentId;
    }

    return current;
  }

  private async listChildrenForRecursiveCopy(
    path: string,
    ctx: AgentDocumentVfsContext,
  ): Promise<AgentDocumentNode[]> {
    const syntheticChildren = this.listSyntheticChildren(path);

    if (syntheticChildren) return syntheticChildren;

    if (isSkillPath(path)) {
      const nodes = await this.skillMount.list({
        agentId: ctx.agentId,
        path,
        topicId: ctx.topicId,
      });

      return nodes.map((node) => this.toMountedNode(node));
    }

    const parentNode = await this.resolveOrdinaryPath(path, ctx.agentId);

    if (!parentNode) {
      throw new AgentDocumentVfsError(`Path not found: ${path}`, 'NOT_FOUND');
    }

    if (parentNode.fileType !== DOCUMENT_FOLDER_TYPE) {
      throw new AgentDocumentVfsError(`Path is not a directory: ${path}`, 'BAD_REQUEST');
    }

    const docs = await this.agentDocumentModel.listByParent(ctx.agentId, parentNode.documentId, {
      limit: MAX_RECURSIVE_COPY_CHILDREN + 1,
    });

    if (docs.length > MAX_RECURSIVE_COPY_CHILDREN) {
      throw new AgentDocumentVfsError(
        `Directory has too many direct children to copy safely: ${path}`,
        'BAD_REQUEST',
      );
    }

    return docs.map((doc) => this.toOrdinaryNode(doc, buildOrdinaryPath(path, doc.filename)));
  }

  private async writeMountedSkill(
    path: string,
    content: string,
    ctx: AgentDocumentVfsContext,
    createMode: NonNullable<AgentDocumentWriteOptions['createMode']>,
  ): Promise<AgentDocumentStats> {
    const existing = await this.skillMount
      .get({
        agentId: ctx.agentId,
        path,
        topicId: ctx.topicId,
      })
      .catch((error) => {
        if (error instanceof AgentDocumentVfsError && error.code === 'NOT_FOUND') return undefined;
        throw error;
      });

    if (!existing && createMode === 'must-exist') {
      throw new AgentDocumentVfsError(`Path not found: ${path}`, 'NOT_FOUND');
    }

    if (existing && createMode === 'always-new
```
