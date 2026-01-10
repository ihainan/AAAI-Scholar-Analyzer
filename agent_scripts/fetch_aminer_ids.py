#!/usr/bin/env python3
"""
Fetch AMiner IDs for scholars in a JSON file using Claude Agent SDK.

This script reads a JSON file containing scholar information and uses
Claude Agent SDK with the AMiner skill to fetch AMiner IDs for each scholar.

Usage:
    python fetch_aminer_ids.py <json_file_path>

Example:
    python fetch_aminer_ids.py /data/aaai-26-ai-talents.json
"""

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

from agent_utils import MessageFormatter, print_message


def get_project_root() -> Path:
    """Get the project root directory (parent of agent_scripts)."""
    return Path(__file__).parent.parent.resolve()


async def fetch_aminer_id_for_scholar(scholar: dict, project_root: Path) -> dict | None:
    """
    Use Claude Agent SDK to fetch AMiner ID for a scholar.

    Args:
        scholar: Scholar information dictionary
        project_root: Project root directory path

    Returns:
        Result dictionary with status and aminer_id/error, or None if failed
    """
    try:
        from claude_agent_sdk import query, ClaudeAgentOptions
    except ImportError:
        print("Error: claude_agent_sdk is not installed. Please install it with:")
        print("  pip install claude-agent-sdk")
        sys.exit(1)

    # Build the prompt for the agent
    scholar_json = json.dumps(scholar, indent=2, ensure_ascii=False)

    prompt = f"""你是一个学者详细信息调研专家。我们从一个学术会议网站上获取到了某个学者相关的一些信息，如下所示：

```
{scholar_json}
```

我需要你通过 Aminer Skill，调用 Aminer 的 API 接口，获取到该学者的详细信息。

我需要你在之后的结果输出且仅输出如下格式的信息：

{{
    "status": "success",
    "aminer_id": "123456789"
}}

或者失败情况下

{{
    "status": "error",
    "error": "error message"
}}

注意事项：

1. 如果中间某一步骤出现了问题，并且无法解决，请直接汇报错误。
2. 如当出现以下任一情况，必须联网检索：
2.1 多候选且歧义（差距 < 10 分）
2.2 候选机构与输入机构不一致
2.3 输入信息过少（只有 name）
3. 当你获取到 Aminer 返回的学者的详情之后，请根据你获取的信息，联网查询该学者相关的资料，做二次确认，确认没问题之后再输出结果。例如你可以找到该学者公开主页/机构页面/Google Scholar/LinkedIn/论文页中能证实其姓名与机构（或研究方向）。将核验结果用于重新评估候选匹配度。
4. 如果你不能有 90% 以上的信心确定学者信息的准确性，请直接按照失败处理。"""

    options = ClaudeAgentOptions(
        # model="claude-sonnet-4-5-20250929",
        cwd=str(project_root),
        setting_sources=["project"],
        allowed_tools=["Skill", "Bash", "WebSearch", "WebFetch", "Read"],
        permission_mode="bypassPermissions"
    )

    result_text = ""
    formatter = MessageFormatter(indent="    ")

    try:
        async for message in query(prompt=prompt, options=options):
            # Format and print each message
            formatter.print(message)

            # Collect the result text from the agent's response
            if hasattr(message, "result"):
                result_text = message.result
            elif hasattr(message, "content"):
                # Handle text content
                if isinstance(message.content, str):
                    result_text = message.content
                elif isinstance(message.content, list):
                    for block in message.content:
                        if hasattr(block, "text"):
                            result_text = block.text
    except Exception as e:
        return {"status": "error", "error": f"Agent execution failed: {str(e)}"}

    # Parse the result to extract the JSON response
    return parse_agent_result(result_text)


def parse_agent_result(result_text: str) -> dict | None:
    """
    Parse the agent's result text to extract the JSON response.

    Args:
        result_text: Raw text output from the agent

    Returns:
        Parsed result dictionary or None if parsing failed
    """
    if not result_text:
        return {"status": "error", "error": "Empty response from agent"}

    # Try to find JSON in the result text
    # Look for JSON blocks in various formats

    # Try to find JSON in code blocks first
    json_patterns = [
        r'```json\s*\n?(.*?)\n?```',  # ```json ... ```
        r'```\s*\n?(.*?)\n?```',       # ``` ... ```
        r'\{[^{}]*"status"[^{}]*\}',   # Simple JSON object with status
    ]

    for pattern in json_patterns:
        matches = re.findall(pattern, result_text, re.DOTALL)
        for match in matches:
            try:
                # Clean up the match
                json_str = match.strip()
                if not json_str.startswith('{'):
                    # Try to find the JSON object in the match
                    start = json_str.find('{')
                    if start != -1:
                        end = json_str.rfind('}') + 1
                        json_str = json_str[start:end]

                result = json.loads(json_str)
                if "status" in result:
                    return result
            except json.JSONDecodeError:
                continue

    # Try to find any JSON object in the text
    try:
        # Find all potential JSON objects
        start_idx = result_text.find('{')
        while start_idx != -1:
            # Try to find matching closing brace
            depth = 0
            for i, char in enumerate(result_text[start_idx:], start_idx):
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        json_str = result_text[start_idx:i+1]
                        try:
                            result = json.loads(json_str)
                            if "status" in result:
                                return result
                        except json.JSONDecodeError:
                            pass
                        break
            start_idx = result_text.find('{', start_idx + 1)
    except Exception:
        pass

    return {"status": "error", "error": f"Could not parse agent response: {result_text[:500]}..."}


def load_json_file(file_path: Path) -> dict:
    """Load and parse a JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json_file(file_path: Path, data: dict) -> None:
    """Save data to a JSON file."""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')


async def process_scholars(json_file_path: Path) -> None:
    """
    Process all scholars in the JSON file and fetch their AMiner IDs.

    Args:
        json_file_path: Path to the JSON file containing scholar information
    """
    project_root = get_project_root()

    # Load the JSON file
    print(f"Loading JSON file: {json_file_path}")
    data = load_json_file(json_file_path)

    if "talents" not in data:
        print("Error: JSON file does not contain 'talents' field")
        sys.exit(1)

    talents = data["talents"]
    total_count = len(talents)
    print(f"Found {total_count} scholars to process")

    # Track statistics
    processed = 0
    skipped = 0
    success = 0
    failed = 0

    for idx, scholar in enumerate(talents, 1):
        name = scholar.get("name", "Unknown")

        # Check if already has aminer_id (either success or failed)
        if "aminer_id" in scholar:
            aminer_id = scholar["aminer_id"]
            if aminer_id == "failed":
                print(f"[{idx}/{total_count}] Skipping {name} (previously failed)")
            else:
                print(f"[{idx}/{total_count}] Skipping {name} (already has aminer_id: {aminer_id})")
            skipped += 1
            continue

        print(f"\n[{idx}/{total_count}] Processing: {name}")
        print(f"  Affiliation: {scholar.get('affiliation', 'Unknown')}")

        # Fetch AMiner ID using the agent
        result = await fetch_aminer_id_for_scholar(scholar, project_root)

        if result and result.get("status") == "success":
            aminer_id = result.get("aminer_id")
            if aminer_id:
                print(f"  SUCCESS: Found AMiner ID: {aminer_id}")
                scholar["aminer_id"] = aminer_id
                success += 1

                # Save the updated JSON file after each successful update
                save_json_file(json_file_path, data)
                print(f"  Updated JSON file")
            else:
                print(f"  FAILED: No AMiner ID in response")
                scholar["aminer_id"] = "failed"
                save_json_file(json_file_path, data)
                print(f"  Marked as failed in JSON file")
                failed += 1
        else:
            error_msg = result.get("error", "Unknown error") if result else "No response"
            print(f"  FAILED: {error_msg}")
            scholar["aminer_id"] = "failed"
            save_json_file(json_file_path, data)
            print(f"  Marked as failed in JSON file")
            failed += 1

        processed += 1

    # Print summary
    print("\n" + "=" * 50)
    print("Processing Complete")
    print("=" * 50)
    print(f"Total scholars: {total_count}")
    print(f"Skipped (already have aminer_id): {skipped}")
    print(f"Processed: {processed}")
    print(f"  - Success: {success}")
    print(f"  - Failed: {failed}")


def main():
    parser = argparse.ArgumentParser(
        description="Fetch AMiner IDs for scholars using Claude Agent SDK",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python fetch_aminer_ids.py /data/aaai-26-ai-talents.json
    python fetch_aminer_ids.py ../data/aaai-26-ai-talents.json
        """
    )

    parser.add_argument(
        "json_file",
        type=str,
        help="Path to the JSON file containing scholar information"
    )

    args = parser.parse_args()

    json_file_path = Path(args.json_file).resolve()

    if not json_file_path.exists():
        print(f"Error: File not found: {json_file_path}")
        sys.exit(1)

    if not json_file_path.suffix == ".json":
        print(f"Warning: File does not have .json extension: {json_file_path}")

    # Run the async processing
    asyncio.run(process_scholars(json_file_path))


if __name__ == "__main__":
    main()
