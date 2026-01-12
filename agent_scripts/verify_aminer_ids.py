#!/usr/bin/env python3
"""
Verify AMiner IDs for scholars in a JSON file using Claude Agent SDK.

This script reads a JSON file containing scholar information with AMiner IDs
and uses Claude Agent SDK with the AMiner skill to verify that the AMiner ID
matches the scholar's other information.

Usage:
    python verify_aminer_ids.py <json_file_path>

Example:
    python verify_aminer_ids.py /data/aaai-26-ai-talents.json
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


async def verify_aminer_id_for_scholar(scholar: dict, project_root: Path) -> dict | None:
    """
    Use Claude Agent SDK to verify AMiner ID for a scholar.

    Args:
        scholar: Scholar information dictionary (must contain aminer_id)
        project_root: Project root directory path

    Returns:
        Result dictionary with status, is_same_person, and reason, or error info
    """
    try:
        from claude_agent_sdk import query, ClaudeAgentOptions
    except ImportError:
        print("Error: claude_agent_sdk is not installed. Please install it with:")
        print("  pip install claude-agent-sdk")
        sys.exit(1)

    # Build the prompt for the agent
    # Create a copy without aminer_validation to avoid confusion
    scholar_info = {k: v for k, v in scholar.items() if k != "aminer_validation"}
    scholar_json = json.dumps(scholar_info, indent=2, ensure_ascii=False)

    prompt = f"""你是一个学者详细信息验证专家。我们从 AAAI 2026 学术会议网站上获取到了某个学者相关的一些信息，然后又尝试获取了其 Aminer ID，汇总信息如下：

```
{scholar_json}
```

你现在的目标是：通过 aminer_id 字段的值，调用 Aminer Skill 获取学者的详细信息，然后判断 Aminer ID 对应的学者，与其他字段信息（如 name、affiliation、roles、description 等）对应的学者，是否有 90% 以上的信心认为是同一个人。

我需要你在之后的结果输出且仅输出如下格式的信息：

当确认是同一个人时：
{{
    "status": "success",
    "is_same_person": true,
    "confirmed_aminer_id": "最终确认的正确 AMiner ID",
    "reason": "简短说明匹配原因（不超过50字）"
}}

当确认不是同一个人时：
{{
    "status": "success",
    "is_same_person": false,
    "reason": "简短说明不匹配的原因（不超过50字）"
}}

或者执行出错时：
{{
    "status": "error",
    "error": "error message"
}}

注意事项：

1. 如果中间某一步骤出现了问题，并且无法解决，请直接汇报错误。
2. 判断依据包括但不限于：姓名是否一致、机构是否匹配、研究方向是否与 roles 描述相符。
3. 如依靠 Aminer 获取的信息和已有其他字段信息，依旧不能判断是或者不是同一个人（例如存在同名学者、机构信息差异较大等情况），请联网检索更多信息进行确认。
4. 只要没有 90% 的信心认为是同一个人，请返回 is_same_person 为 false。
5. reason 字段请简洁明了，不超过 50 字，说明判断的关键依据。
6. 如果原始提供的 aminer_id 无法查询到学者信息，但你通过其他方式（如按姓名搜索）找到了正确的学者，请在 confirmed_aminer_id 中返回正确的 ID。这样可以纠正原始数据中可能存在的错误。"""

    options = ClaudeAgentOptions(
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


def get_scholar_status(scholar: dict) -> str:
    """
    Determine the verification status of a scholar.

    Returns:
        - "no_aminer_id": aminer_id field does not exist
        - "aminer_id_failed": aminer_id is "failed"
        - "already_verified": aminer_validation already exists
        - "needs_verification": has valid aminer_id but no aminer_validation
    """
    if "aminer_id" not in scholar:
        return "no_aminer_id"

    if scholar["aminer_id"] == "failed":
        return "aminer_id_failed"

    if "aminer_validation" in scholar:
        return "already_verified"

    return "needs_verification"


async def process_scholars(json_file_path: Path) -> None:
    """
    Process all scholars in the JSON file and verify their AMiner IDs.

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
    print(f"Found {total_count} scholars in file")

    # Track statistics
    stats = {
        "no_aminer_id": 0,
        "aminer_id_failed": 0,
        "already_verified": 0,
        "verified_same": 0,
        "verified_different": 0,
        "verification_error": 0,
        "id_corrected": 0,
    }

    for idx, scholar in enumerate(talents, 1):
        name = scholar.get("name", "Unknown")
        status = get_scholar_status(scholar)

        if status == "no_aminer_id":
            print(f"[{idx}/{total_count}] Skipping {name} (no aminer_id)")
            stats["no_aminer_id"] += 1
            continue

        if status == "aminer_id_failed":
            print(f"[{idx}/{total_count}] Skipping {name} (aminer_id fetch failed)")
            stats["aminer_id_failed"] += 1
            continue

        if status == "already_verified":
            validation = scholar.get("aminer_validation", {})
            validation_status = validation.get("status", "unknown")
            if validation_status == "success":
                is_same = validation.get("is_same_person", "unknown")
                print(f"[{idx}/{total_count}] Skipping {name} (already verified: is_same_person={is_same})")
            else:
                print(f"[{idx}/{total_count}] Skipping {name} (already processed: status={validation_status})")
            stats["already_verified"] += 1
            continue

        # needs_verification
        aminer_id = scholar.get("aminer_id")
        print(f"\n[{idx}/{total_count}] Verifying: {name}")
        print(f"  Affiliation: {scholar.get('affiliation', 'Unknown')}")
        print(f"  AMiner ID: {aminer_id}")

        # Verify AMiner ID using the agent
        result = await verify_aminer_id_for_scholar(scholar, project_root)

        if result and result.get("status") == "success":
            is_same_person = result.get("is_same_person", False)
            reason = result.get("reason", "No reason provided")

            scholar["aminer_validation"] = {
                "status": "success",
                "is_same_person": is_same_person,
                "reason": reason
            }

            if is_same_person:
                # Check if confirmed_aminer_id differs from original
                confirmed_id = result.get("confirmed_aminer_id")
                if confirmed_id and confirmed_id != aminer_id:
                    print(f"  ID CORRECTED: {aminer_id} -> {confirmed_id}")
                    scholar["aminer_id"] = confirmed_id
                    scholar["aminer_validation"]["original_aminer_id"] = aminer_id
                    stats["id_corrected"] += 1

                print(f"  VERIFIED: Same person - {reason}")
                stats["verified_same"] += 1
            else:
                print(f"  VERIFIED: Different person - {reason}")
                stats["verified_different"] += 1
        else:
            error_msg = result.get("error", "Unknown error") if result else "No response"
            print(f"  ERROR: {error_msg}")

            scholar["aminer_validation"] = {
                "status": "error",
                "error": error_msg
            }
            stats["verification_error"] += 1

        # Save the updated JSON file after each verification
        save_json_file(json_file_path, data)
        print(f"  Updated JSON file")

    # Print summary
    print("\n" + "=" * 50)
    print("Verification Complete")
    print("=" * 50)
    print(f"Total scholars: {total_count}")
    print(f"Skipped (no aminer_id): {stats['no_aminer_id']}")
    print(f"Skipped (aminer_id failed): {stats['aminer_id_failed']}")
    print(f"Skipped (already verified): {stats['already_verified']}")
    print(f"Verified this run:")
    print(f"  - Same person: {stats['verified_same']}")
    print(f"  - Different person: {stats['verified_different']}")
    print(f"  - Errors: {stats['verification_error']}")
    if stats["id_corrected"] > 0:
        print(f"  - IDs corrected: {stats['id_corrected']}")


def main():
    parser = argparse.ArgumentParser(
        description="Verify AMiner IDs for scholars using Claude Agent SDK",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python verify_aminer_ids.py /data/aaai-26-ai-talents.json
    python verify_aminer_ids.py ../data/aaai-26-ai-talents.json
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
