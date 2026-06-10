# 目录：docs/guides

## 它负责什么

`docs/guides` 是仓库里给用户、运维和测试人员看的“怎么做”目录，内容偏操作手册而不是设计说明。根据 `docs/README.md` 和 `docs/contributing/file-structure.md`，这里收纳的是部署、测试、WebUI 启动、CDP 调试这一类指南。它的定位很明确：帮助人把 AionUi 跑起来、连起来、查问题，而不是解释系统架构为什么这么设计。

从当前片段看，这个目录里的文档都围绕实际使用场景展开：服务器部署、浏览器访问模式、调试工具接入、Hub 后端测试链路。它更像一组入口说明书，配合代码里的启动参数、运行模式和测试脚本使用。

## 直接子目录地图

根据当前片段推断，`docs/guides` 下没有更深的子目录，只有 4 个直接子文件：

- `docs/guides/deploy-server.md`：Headless Linux 服务器部署指南，重点是云主机、容器、Xvfb 和代理兜底。
- `docs/guides/webui.md`：WebUI 启动指南，重点是 `--webui` 模式在 Windows、macOS、Linux、Android/Termux 下怎么起。
- `docs/guides/cdp.md`：CDP（Chrome DevTools Protocol）指南，重点是开发调试和 MCP 工具接入。
- `docs/guides/hub-testing.md`：Hub Backend 测试指南，重点是测试分层、安装链路和 UI/E2E 验证。

这个目录是平铺结构，没有再按平台、环境或主题拆更细的层级。

## 关键入口

最直接的入口是 `docs/README.md`，它把 `guides/` 明确标成 “Users & operators”，并列出“部署、测试、运行产品”的总入口。对于新读者来说，`docs/README.md` 相当于目录导航页。

目录内的关键文档入口则是这 4 篇：

- `docs/guides/deploy-server.md`：如果你关心无头服务器、容器、远程访问，就从这里开始。
- `docs/guides/webui.md`：如果你要用浏览器访问 AionUi，或者确认 `--webui` 的启动方式，就看这里。
- `docs/guides/cdp.md`：如果你要接 Chrome DevTools、Playwright MCP、Puppeteer MCP，或者排查远程调试端口，就看这里。
- `docs/guides/hub-testing.md`：如果你要理解 Hub backend 的测试结构、测试边界和执行方式，就看这里。

从仓库结构看，`docs/contributing/file-structure.md` 也是一个间接入口，因为它说明了“Guide documents belong in `docs/guides/`”，能帮助你区分这个目录和 `docs/architecture/`、`docs/contributing/`、`docs/specs/` 的边界。

## 主流程位置

这里讲的是“文档对应的主流程在哪”，不是逐文件展开。根据当前片段推断，`docs/guides` 这几篇文档分别对应该产品的几个主链路：

- WebUI 启动链路：核心应落在 `packages/desktop/src/index.ts` 的启动逻辑，以及 `packages/desktop/src/process/webserver/` 这一类 WebUI 服务代码。文档里讲的 `--webui`、远程访问、端口提示，都是这条链路的外显。
- CDP 调试链路：核心更集中在 `packages/desktop/src/process/utils/configureChromium.ts`，以及设置界面的 `packages/desktop/src/renderer/components/settings/SettingsModal/contents/SystemModalContent/DevSettings.tsx`。搜索结果还显示 `packages/desktop/src/index.ts` 会打印 CDP 就绪信息，说明主流程在 main process，UI 只是开关和状态展示。
- Headless 部署链路：文档主要描述的是打包产物的启动与系统环境配合，尤其是 `--webui`、`xvfb-run`、代理自动兜底这类运行方式。仓库里与之最直接相关的仍是启动入口和 WebUI 服务侧逻辑，具体实现细节要结合 `packages/desktop/src/index.ts` 与 webserver 相关模块理解。
- Hub 测试链路：这里的主流程不在运行时，而在测试目录，重点是 `tests/integration/hub-install-flow.test.ts` 和 `tests/e2e/specs/hub-backend-install.e2e.ts`。文档描述的安装、热重载、连接、发起会话，都是测试用例在覆盖的完整链路。

## 推荐阅读顺序

如果你是第一次看这个目录，建议按使用场景读，而不是按文件名猜：

1. 先看 `docs/README.md`，确认 `guides/` 在整个文档体系里的位置。
2. 如果目标是上线或远程跑，先读 `docs/guides/deploy-server.md`。
3. 如果目标是浏览器模式访问，读 `docs/guides/webui.md`。
4. 如果目标是调试和 MCP 集成，读 `docs/guides/cdp.md`。
5. 如果目标是验证 Hub 相关能力或写测试，读 `docs/guides/hub-testing.md`。

这个顺序的好处是先建立“怎么跑”，再看“怎么调试”，最后看“怎么测”。

## 常见误区

- 把 `docs/guides` 当成架构文档目录。这里不是讲设计决策的，设计和系统拆解应该去 `docs/architecture/`。
- 把部署指南和开发者指南混在一起。`docs/guides` 偏用户/运维/测试操作，`docs/contributing/` 才是开发流程、规范和工具链。
- 只看文档，不回头找代码入口。像 WebUI、CDP 这种内容都和 `packages/desktop/src/index.ts`、`packages/desktop/src/process/webserver/`、`packages/desktop/src/process/utils/configureChromium.ts` 直接相关，不对照代码会只看到“怎么用”，看不到“从哪儿进”。
- 把 `hub-testing.md` 误认为产品功能说明。它本质上是测试策略和测试链路说明，重点是验证路径，不是给普通用户的操作手册。
- 以为这里会有很多分层目录。根据当前片段推断，`docs/guides` 目前是扁平目录，后续新增指南大概率也会以单篇 Markdown 的方式继续扩展。
