# 目录：apps/ios/fastlane/metadata

## 它负责什么

`apps/ios/fastlane/metadata` 是 iOS 发布链路里供 Fastlane `deliver` 读取的 App Store Connect 文案元数据目录。它本身不构建应用、不签名、不上传 IPA，也不决定 TestFlight build number；它只保存“应用商店页面”和“审核联系信息”这类文本材料，供同级 `apps/ios/fastlane/Fastfile` 中的 `ios metadata` lane 在执行 `deliver` 时提交。

从现有结构看，这个目录服务于 App Store Connect 的 metadata-only 上传场景：应用名称、副标题、描述、关键词、宣传文本、隐私链接、支持链接、营销链接、版本说明，以及首次提交或审核所需的联系人信息。`apps/ios/fastlane/metadata/README.md` 明确说明它由 `fastlane deliver` 使用，并给出 `DELIVER_METADATA=1 fastlane ios metadata` 这条上传路径。

需要注意的是，`release_notes.txt` 虽然落在这里，但它不是单独维护的任意文案。README 说明它从 `apps/ios/CHANGELOG.md` 生成，并受 `pnpm ios:version:sync`、`pnpm ios:version:pin -- --from-gateway` 等版本同步流程影响。因此这个目录既是 App Store 文案的存放点，也是 iOS 版本发布材料的输出面之一。

## 直接子目录地图

`apps/ios/fastlane/metadata/en-US` 是主要 locale 目录，保存面向 App Store 展示的英文美国区文案。当前可见文件包括 `name.txt`、`subtitle.txt`、`description.txt`、`keywords.txt`、`promotional_text.txt`、`release_notes.txt`、`privacy_url.txt`、`support_url.txt`、`marketing_url.txt`。这些文件对应 Fastlane `deliver` 的标准 metadata 布局，上传时由 Fastlane 按 locale 自动发现。

`apps/ios/fastlane/metadata/review_information` 保存 App Store 审核联系人信息。当前可见文件包括 `first_name.txt`、`last_name.txt`、`email_address.txt`、`phone_number.txt`、`notes.txt`。README 特别提示首次 app version 可能需要这些 review contact files。这里的内容面向审核流程，不是普通 App Store 页面文案。

`apps/ios/fastlane/metadata/README.md` 是本目录的人工入口文档，解释 metadata-only 上传、可选 screenshot 上传、认证变量、版本说明生成规则，以及 app lookup 失败时可用的 `ASC_APP_IDENTIFIER`、`ASC_APP_ID` 覆盖方式。

## 关键入口

本目录的直接说明入口是 `apps/ios/fastlane/metadata/README.md`。阅读它可以先理解这个目录为什么存在、如何触发上传、哪些环境变量会影响上传行为。

实际执行入口不在本目录，而在 `apps/ios/fastlane/Fastfile` 的 `lane :metadata`。这个 lane 会先调用 `sync_ios_versioning!`，确保 iOS 版本相关产物没有过期；然后通过 `asc_api_key` 取得 App Store Connect API key；再组装 `deliver_options`，最后调用 `deliver(**deliver_options)`。其中 `skip_metadata` 由 `DELIVER_METADATA` 控制，`skip_screenshots` 由 `DELIVER_SCREENSHOTS` 控制。也就是说，目录里的 metadata 文件只有在 `DELIVER_METADATA=1` 时才会被实际提交。

认证入口集中在同一个 `Fastfile` 里的 `private_lane :asc_api_key`，并由 `apps/ios/fastlane/Appfile` 说明默认 bundle id 和可用认证方式。`Appfile` 设置 `app_identifier("ai.openclaw.client")`，同时注明认证可来自 `APP_STORE_CONNECT_API_KEY_PATH`、`ASC_KEY_PATH`，或者 `ASC_KEY_ID`、`ASC_ISSUER_ID`、`ASC_KEY_CONTENT` / Keychain fallback。`apps/ios/fastlane/SETUP.md` 则是更完整的 Fastlane 配置和维护者操作说明。

## 主流程位置

metadata 上传主流程可以按四段理解。

第一段是准备认证。`apps/ios/fastlane/Fastfile` 的 `asc_api_key` 会读取 `apps/ios/fastlane/.env`，清理空环境变量，然后按优先级选择 App Store Connect API key 来源：JSON key path、`.p8` 文件路径、环境变量中的 key content，或 macOS Keychain 中的 key content。Keychain 路径还包含十六进制 PEM 解码逻辑，用来处理 `security find-generic-password -w` 返回的特殊内容。

第二段是版本产物校验。`lane :metadata` 调用 `sync_ios_versioning!`，后者执行 `scripts/ios-sync-versioning.ts --check`。根据当前片段推断，这一步用于保证 `apps/ios/CHANGELOG.md`、`apps/ios/version.json` 以及生成到 metadata 的 `release_notes.txt` 等版本相关文件保持同步；依据是 `metadata/README.md` 和 `SETUP.md` 都把 `release_notes.txt` 与 `pnpm ios:version:sync` 绑定起来。

第三段是 app 定位。`lane :metadata` 会读取 `ASC_APP_IDENTIFIER` 和 `ASC_APP_ID`。如果提供 bundle id，就传给 `deliver_options[:app_identifier]`；如果只提供 numeric App Store Connect app id，则将 `app_identifier` 显式置空并设置 `deliver_options[:app]`。代码注释说明这是为了处理 `deliver` 默认偏向从 `Appfile` 读取 app identifier 的行为。

第四段是调用 `deliver`。`deliver_options` 包含 `api_key`、`force: true`、`skip_screenshots`、`skip_metadata`、`run_precheck_before_submit: false`，最终交给 Fastlane 上传。这里没有构建、归档、TestFlight 上传逻辑；这些属于同一 `Fastfile` 中的 `beta_archive`、`beta` 和相关 helper。

## 推荐阅读顺序

建议先读 `apps/ios/fastlane/metadata/README.md`，建立本目录的用途边界：它是 `fastlane deliver` 的 metadata 源，不是完整发布脚本。

第二步看 `apps/ios/fastlane/metadata/en-US` 的文件名即可，不必逐文件深读。overview 层面只需要知道这里是 App Store 展示文案 locale；真正要改发布文案时，再打开具体的 `description.txt`、`release_notes.txt` 等文件。

第三步看 `apps/ios/fastlane/metadata/review_information` 的文件名，理解它和普通展示文案不同，属于审核联系信息。涉及隐私、联系人或真实手机号时要格外谨慎，避免把真实敏感信息扩散到文档或日志。

第四步读 `apps/ios/fastlane/Fastfile` 的 `lane :metadata`、`asc_api_key`、`sync_ios_versioning!`。这几个位置解释 metadata 如何从静态文件变成 App Store Connect API 调用。

第五步读 `apps/ios/fastlane/Appfile` 和 `apps/ios/fastlane/SETUP.md`，补齐 bundle id、认证变量、Keychain 配置、`ASC_APP_ID` fallback、版本同步命令等周边上下文。

## 常见误区

不要把 `metadata` 目录理解成 iOS 应用源码。它不包含 Swift、Xcode project 配置、签名配置或构建产物，只是 Fastlane 约定格式的 App Store 文案目录。

不要以为执行 `fastlane ios metadata` 一定会上传 metadata。`Fastfile` 中 `skip_metadata: ENV["DELIVER_METADATA"] != "1"` 表示只有设置 `DELIVER_METADATA=1` 才上传文案；否则 metadata 会被跳过。同理，截图上传由 `DELIVER_SCREENSHOTS=1` 单独控制。

不要手工随意改 `release_notes.txt` 后直接认为版本说明完成。当前说明明确指出它由 `apps/ios/CHANGELOG.md` 生成，版本同步需要走 `pnpm ios:version:sync`。如果直接改生成产物，后续同步可能覆盖或造成检查失败。

不要把 `apps/ios/fastlane/.env` 和网关运行时 APNs 配置混为一谈。`SETUP.md` 明确区分 Fastlane/App Store Connect auth 与 gateway-side direct APNs push delivery；前者服务上传和 TestFlight，后者服务本地 iOS 推送运行环境。

不要在学习文档或输出中泄露真实外部链接、联系人、手机号或密钥。`privacy_url.txt`、`support_url.txt`、`marketing_url.txt` 这类文件可能包含公开链接，`review_information` 可能包含审核联系人信息；写概览时说明角色即可，不需要展开具体值。

不要把 `ASC_APP_IDENTIFIER` 和 `ASC_APP_ID` 当成同一种东西。前者是 bundle id，后者是 App Store Connect numeric app id。`Fastfile` 对只提供 `ASC_APP_ID` 的情况做了特殊处理，说明 app lookup 是 metadata 上传中一个独立风险点。
