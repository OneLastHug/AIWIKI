# 文件：datagen-config-examples/run_browser_tasks.sh

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
#!/bin/bash

# =============================================================================
# Example: Browser-Focused Data Generation
# =============================================================================
#
# Generates tool-calling trajectories for browser automation tasks.
# The agent navigates websites, fills forms, extracts information, etc.
#
# Distribution: browser 97%, web 20%, vision 12%, terminal 15%
#
# Prerequisites:
#   - OPENROUTER_API_KEY in ~/.hermes/.env
#   - BROWSERBASE_API_KEY in ~/.hermes/.env (for browser tools)
#   - A dataset JSONL file with one {"prompt": "..."} per line
#
# Usage:
#   cd ~/.hermes/hermes-agent
#   bash datagen-config-examples/run_browser_tasks.sh
#
# Output: data/browser_tasks_example/trajectories.jsonl
# =============================================================================

mkdir -p logs

LOG_FILE="logs/browser_tasks_$(date +%Y%m%d_%H%M%S).log"
echo "📝 Logging to: $LOG_FILE"

# Point to the example dataset in this directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

python batch_runner.py \
  --dataset_file="$SCRIPT_DIR/example_browser_tasks.jsonl" \
  --batch_size=5 \
  --run_name="browser_tasks_example" \
  --distribution="browser_tasks" \
  --model="anthropic/claude-sonnet-4" \
  --base_url="[URL已移除]" \
  --num_workers=3 \
  --max_turns=30 \
  --ephemeral_system_prompt="You are an AI assistant with browser automation capabilities. Your primary task is to navigate and interact with web pages to accomplish user goals.

IMPORTANT GUIDELINES:

1. SEARCHING: Do NOT search directly on Google via the browser — they block automated searches. Use the web_search tool first to find URLs, then navigate to them with browser tools.

2. COOKIE/PRIVACY DIALOGS: After navigating to a page, check for cookie consent or privacy popups. Dismiss them by clicking Accept/Close/OK before interacting with other elements. Take a fresh browser_snapshot afterward.

3. HANDLING TIMEOUTS: If an action times out, the element may be blocked by an overlay. Take a new snapshot and look for dialogs to dismiss. If none, try an alternative approach or report the issue.

4. GENERAL: Use browser tools to click, fill forms, and extract information. Use terminal for local file operations. Verify your actions and handle errors gracefully." \
  2>&1 | tee "$LOG_FILE"

echo "✅ Done. Log: $LOG_FILE"

# =============================================================================
# Common options you can add:
#
#   --resume                  Resume from checkpoint if interrupted
#   --verbose                 Enable detailed logging
#   --max_tokens=63000        Set max response tokens
#   --reasoning_disabled      Disable model thinking/reasoning tokens
#   --providers_allowed="anthropic,google"  Restrict to specific providers
#   --prefill_messages_file="configs/prefill.json"  Few-shot priming
# =============================================================================

```
