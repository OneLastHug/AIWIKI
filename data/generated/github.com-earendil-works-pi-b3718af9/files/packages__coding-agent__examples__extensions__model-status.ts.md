# 文件：packages/coding-agent/examples/extensions/model-status.ts

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
/**
 * Model status extension - shows model changes in the status bar.
 *
 * Demonstrates the `model_select` hook which fires when the model changes
 * via /model command, Ctrl+P cycling, or session restore.
 *
 * Usage: pi -e ./model-status.ts
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
	pi.on("model_select", async (event, ctx) => {
		const { model, previousModel, source } = event;

		// Format model identifiers
		const next = `${model.provider}/${model.id}`;
		const prev = previousModel ? `${previousModel.provider}/${previousModel.id}` : "none";

		// Show notification on change
		if (source !== "restore") {
			ctx.ui.notify(`Model: ${next}`, "info");
		}

		// Update status bar with current model
		ctx.ui.setStatus("model", `🤖 ${model.id}`);

		// Log change details (visible in debug output)
		console.log(`[model_select] ${prev} → ${next} (${source})`);
	});
}

```
