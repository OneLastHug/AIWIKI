# 子系统：packages/coding-agent/docs/images

## 解决什么问题
这个目录存放 `coding-agent` 文档站和 README 需要的静态图片资源，主要解决两类问题：一是给终端界面、会话树、扩展 UI 这些抽象概念提供可视化示例，二是给项目品牌和第三方入口页提供统一的视觉素材。根据当前片段推断，这里不是运行时代码，而是“文档可读性资产层”，核心价值是把 `docs/*.md` 里的说明落到真实界面截图上。

## 相关目录和文件
最直接的引用方是 `packages/coding-agent/README.md`、`packages/coding-agent/docs/usage.md`、`packages/coding-agent/docs/sessions.md`。它们分别引用了 `docs/images/interactive-mode.png`、`docs/images/tree-view.png`、`docs/images/doom-extension.png`、`docs/images/exy.png`。  
文档导航本身由 `packages/coding-agent/docs/index.md` 和 `packages/coding-agent/docs/docs.json` 组织，前者定义内容入口，后者定义站点导航和重定向。图片目录虽然不出现在 `docs.json` 的导航项里，但它是这些页面渲染截图的实际来源。

## 核心对象
这里的“核心对象”就是四张图：  
`interactive-mode.png`：展示 pi 的交互主界面，包括启动头部、消息区、编辑器、底部状态栏。  
`tree-view.png`：展示 `/tree` 会话树界面，强调分支浏览和回跳。  
`doom-extension.png`：展示扩展注入后的自定义 UI 场景，说明扩展系统不仅能加命令，还能改界面。  
`exy.png`：项目品牌图标，出现在 README 顶部，用于建立识别度。  
这些图不是业务对象，但它们承担了“界面证据”和“品牌锚点”的作用。

## 运行流程
文档页面在构建或渲染时，通过 Markdown 里的相对路径引用这些图片。以 `docs/usage.md` 为例，页面先解释交互模式，再用 `images/interactive-mode.png` 让读者看到界面构成；`docs/sessions.md` 则用 `images/tree-view.png` 说明树状会话历史。README 里同样把这些图嵌入到对应章节中，形成“文字说明 -> 截图验证”的阅读路径。  
所以这个目录的工作流很简单：作者更新文档内容时同步更新截图，文档渲染器只负责按相对路径加载，不做额外逻辑处理。

## 上下游依赖
上游依赖是 `coding-agent` 的实际产品形态：交互模式、会话树、扩展机制、品牌视觉。也就是说，先有这些功能和 UI，才会产生对应截图。  
下游依赖是文档阅读者、站点生成器和 README 展示页。`index.md`、`usage.md`、`sessions.md` 以及 README 都直接消费这里的图片。若图片失真、过时或路径失效，文档会立刻失去说明力。  
从依赖关系看，这里与 `src/modes/interactive/*`、`src/core/session-manager.ts`、`src/core/skills.ts`、`src/core/slash-commands.ts` 等实现形成间接对应，但图片本身不参与编译和执行。

## 修改时最容易踩的坑
第一，图片路径是相对引用，改名或移动后必须同步改所有 Markdown 引用，否则页面会静默破图。  
第二，截图内容容易过时，尤其是交互界面里的快捷键、布局和状态栏信息，一旦 UI 改版，旧图会误导读者。  
第三，README 和 `docs/*.md` 往往同时引用同一张图，更新时容易只改一处。  
第四，`exy.png` 这种品牌图和功能截图的用途不同，不要混用，否则会影响首页识别和章节说明。  
第五，文档站使用相对路径，跨目录复制文档时，图片引用要重新检查。

## 推荐阅读顺序
先看 `packages/coding-agent/docs/index.md`，建立整个文档体系的定位；再看 `packages/coding-agent/docs/usage.md` 和 `packages/coding-agent/docs/sessions.md`，理解这些截图具体支撑的概念；然后回到 `packages/coding-agent/README.md` 看它们在产品入口页里的呈现方式；最后再对照 `packages/coding-agent/docs/images` 目录里的四张图，确认每张图分别服务哪个章节。
