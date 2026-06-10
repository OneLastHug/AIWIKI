# 文件：packages/ai/src/providers/cloudflare.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
import type { Api, Model } from "../types.ts";

/** Workers AI direct endpoint. */
export const CLOUDFLARE_WORKERS_AI_BASE_URL =
	"[URL已移除]{CLOUDFLARE_ACCOUNT_ID}/ai/v1";

/** AI Gateway Unified API. [URL已移除] */
export const CLOUDFLARE_AI_GATEWAY_COMPAT_BASE_URL =
	"[URL已移除]{CLOUDFLARE_ACCOUNT_ID}/{CLOUDFLARE_GATEWAY_ID}/compat";

/** AI Gateway → OpenAI passthrough. Used until /compat supports /v1/responses. */
export const CLOUDFLARE_AI_GATEWAY_OPENAI_BASE_URL =
	"[URL已移除]{CLOUDFLARE_ACCOUNT_ID}/{CLOUDFLARE_GATEWAY_ID}/openai";

/** AI Gateway → Anthropic passthrough. */
export const CLOUDFLARE_AI_GATEWAY_ANTHROPIC_BASE_URL =
	"[URL已移除]{CLOUDFLARE_ACCOUNT_ID}/{CLOUDFLARE_GATEWAY_ID}/anthropic";

export function isCloudflareProvider(provider: string): boolean {
	return provider === "cloudflare-workers-ai" || provider === "cloudflare-ai-gateway";
}

/** Substitute `{VAR}` placeholders in a Cloudflare baseUrl from process.env. */
export function resolveCloudflareBaseUrl(model: Model<Api>): string {
	const url = model.baseUrl;
	if (!url.includes("{")) return url;
	const baseUrl = url.replace(/\{([A-Z_][A-Z0-9_]*)\}/g, (_match, name: string) => {
		const value = process.env[name];
		if (!value) {
			throw new Error(`${name} is required for provider ${model.provider} but is not set.`);
		}
		return value;
	});
	return baseUrl;
}

```
