#!/usr/bin/env python3
"""
Label scholar data using Claude Agent SDK.

This script reads enriched scholar data and uses an Agent to determine various labels
(e.g., Chinese, Student) based on comprehensive information from multiple sources.

Usage:
    python label_scholar_data.py --labels-file <labels.json> [options]

Example:
    python label_scholar_data.py --labels-file config/labels.json
    python label_scholar_data.py --labels-file config/labels.json --mode overwrite
    python label_scholar_data.py --labels-json '{"labels": [{"name": "Chinese", "description": "..."}]}'
    python label_scholar_data.py --labels-file config/labels.json --ids 53f466dfdabfaedd74e6b9e2
"""

import argparse
import asyncio
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from agent_utils import MessageFormatter


def get_project_root() -> Path:
    """Get the project root directory (parent of agent_scripts)."""
    return Path(__file__).parent.parent.resolve()


def load_json_file(file_path: Path) -> dict:
    """Load and parse a JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json_file(file_path: Path, data: dict) -> None:
    """Save data to a JSON file with proper formatting."""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')


def load_labels_definition(labels_file: Path | None, labels_json: str | None) -> dict:
    """
    Load labels definition from file or JSON string.

    Args:
        labels_file: Path to labels definition file
        labels_json: JSON string containing labels definition

    Returns:
        Labels definition dictionary
    """
    if labels_json:
        try:
            return json.loads(labels_json)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in --labels-json: {e}")
            sys.exit(1)
    elif labels_file:
        if not labels_file.exists():
            print(f"Error: Labels file not found: {labels_file}")
            sys.exit(1)
        return load_json_file(labels_file)
    else:
        print("Error: Either --labels-file or --labels-json must be provided")
        sys.exit(1)


def get_validated_scholars(data: dict) -> list[dict]:
    """
    Extract scholars from input data supporting both 'talents' (scholars.json)
    and 'authors' (authors.json) formats.

    Behavior:
    - If an entry has 'aminer_validation', require status == "success" and is_same_person is True.
    - Otherwise, if an entry has a non-empty aminer_id (and not "failed"), include it (best-effort).
    """
    scholars = []

    # Support both formats: prefer 'talents' (scholars.json) but fall back to 'authors'
    entries = data.get("talents") or data.get("authors") or []

    for entry in entries:
        validation = entry.get("aminer_validation")
        aminer_id = entry.get("aminer_id", "")

        if validation:
            # Keep original strict validation behavior when metadata is present
            if (validation.get("status") == "success" and
                validation.get("is_same_person") is True and
                aminer_id and aminer_id != "failed"):
                scholars.append(entry)
        else:
            # Best-effort: include entries that have an AMiner ID even if no validation metadata
            if aminer_id and aminer_id != "failed":
                scholars.append(entry)

    return scholars


def get_citation_count(entry: dict) -> int:
    """Best-effort citation count used for prioritization (high to low)."""
    value = entry.get("n_citation")
    if value is None:
        stats = entry.get("statistics")
        if isinstance(stats, dict):
            value = stats.get("n_citation")

    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def truncate_list(items: list | None, max_items: int = 2) -> list | None:
    """Truncate a list to max_items, preserving None."""
    if items is None:
        return None
    return items[:max_items]


def build_scholar_context(
    scholar: dict,
    aminer_data: dict | None,
    enriched_data: dict | None,
    labels_definition: dict
) -> dict:
    """
    Build a combined context for the Agent, truncating large lists.

    Args:
        scholar: Scholar data from aaai-26-ai-talents.json
        aminer_data: AMiner cache data (if available)
        enriched_data: Enriched data from data/enriched/scholars/<id>.json
        labels_definition: Labels definition to judge

    Returns:
        Combined context dictionary with truncated lists
    """
    context = {
        "basic_info": {
            "name": scholar.get("name"),
            "aliases": scholar.get("aliases"),
            "affiliation": scholar.get("affiliation"),
            "roles": scholar.get("roles"),
            "description": scholar.get("description"),
        },
        "aminer_id": scholar.get("aminer_id"),
    }

    # Add AMiner data (truncated)
    if aminer_data:
        # Include detail and figure (usually small)
        if aminer_data.get("detail"):
            context["aminer_detail"] = aminer_data["detail"]
        if aminer_data.get("figure"):
            context["aminer_figure"] = aminer_data["figure"]

        # Truncate large lists
        if aminer_data.get("projects"):
            context["aminer_projects"] = truncate_list(aminer_data["projects"], 2)
        if aminer_data.get("papers"):
            context["aminer_papers"] = truncate_list(aminer_data["papers"], 2)
        if aminer_data.get("patents"):
            context["aminer_patents"] = truncate_list(aminer_data["patents"], 2)

    # Add enriched data (excluding labels and metadata)
    if enriched_data:
        enriched_fields = {
            k: v for k, v in enriched_data.items()
            if k not in ["aminer_id", "last_updated", "labels"]
        }
        if enriched_fields:
            context["enriched_data"] = enriched_fields

    # Add labels to judge
    context["labels_to_judge"] = labels_definition.get("labels", [])

    return context


def build_prompt(scholar_json: str) -> str:
    """Build the prompt for the Agent."""
    return f"""你是一个学者信息分析专家。我们需要你基于提供的学者信息，判断该学者是否符合指定的标签定义。

学者的综合信息如下（注意：AMiner 的 projects、papers、patents 仅展示前 2 条，实际数据更多）：

```json
{scholar_json}
```

**任务说明：**

请根据上述信息中的 `labels_to_judge` 字段，逐一判断该学者是否符合每个标签的定义。对于每个标签，你需要：

1. 仔细阅读标签的 `description`（判断标准）
2. 综合分析所有可用信息（basic_info、aminer_detail、aminer_figure、enriched_data 等）
3. 给出判断结果：
   - `value`: `true`（符合）、`false`（不符合）、`null`（信息不足，无法判断）
   - `confidence`: `"high"`（高信心）、`"medium"`（中等信心）、`"low"`（低信心）
   - `reason`: 详细说明你的判断依据（100-200字），列出支持你判断的关键证据

**输出格式：**

```json
{{
  "results": [
    {{
      "name": "Chinese",
      "value": true,
      "confidence": "high",
      "reason": "姓名为中文拼音（Zhang Wei），本科和博士均毕业于中国大陆高校（清华大学），目前在北京大学任教，个人主页使用中英双语。综合判断为华人学者。"
    }},
    {{
      "name": "Student",
      "value": false,
      "confidence": "high",
      "reason": "职称为 Associate Professor，个人主页明确显示 2018 年入职北京大学，已指导多名博士生，发表多篇论文作为通讯作者。明确不是学生身份。"
    }}
  ]
}}
```

**重要提醒：**

- 必须对 `labels_to_judge` 中的**每个标签**都给出判断结果
- 如果现有信息不足以做出准确判断，可以进行网络搜索获取补充信息（如访问个人主页、查询最新动态等）
- 如果经过搜索仍无法判断，使用 `value: null` 和 `confidence: "low"`
- `reason` 必须具体、有依据，不要使用模糊的表述
- 返回标准 JSON 格式，确保可以被解析

如果遇到致命错误导致无法完成判断：

```json
{{
  "status": "error",
  "error": "错误描述"
}}
```"""


async def label_scholar(
    scholar: dict,
    aminer_data: dict | None,
    enriched_data: dict | None,
    labels_definition: dict,
    project_root: Path
) -> dict:
    """
    Use Claude Agent SDK to label scholar data.

    Args:
        scholar: Scholar data from aaai-26-ai-talents.json
        aminer_data: AMiner cache data (if available)
        enriched_data: Enriched data (if available)
        labels_definition: Labels definition
        project_root: Project root directory path

    Returns:
        Result dictionary with label judgments or error info
    """
    try:
        from claude_agent_sdk import query, ClaudeAgentOptions
    except ImportError:
        print("Error: claude_agent_sdk is not installed. Please install it with:")
        print("  pip install claude-agent-sdk")
        sys.exit(1)

    # Build context and prompt
    context = build_scholar_context(scholar, aminer_data, enriched_data, labels_definition)
    scholar_json = json.dumps(context, indent=2, ensure_ascii=False)
    prompt = build_prompt(scholar_json)

    options = ClaudeAgentOptions(
        cwd=str(project_root),
        setting_sources=["project"],
        allowed_tools=["WebSearch", "WebFetch", "Read"],
        permission_mode="bypassPermissions"
    )

    # NOTE: The SDK may emit multiple message types (AssistantMessage, ResultMessage, etc.).
    # We collect all text blocks rather than overwriting `result_text`, and we ignore non-string
    # `result` payloads to avoid clobbering the extracted answer.
    result_chunks: list[str] = []
    formatter = MessageFormatter(indent="    ")

    try:
        async for message in query(prompt=prompt, options=options):
            # Format and print each message
            formatter.print(message)

            # Some SDK message types may expose a final string result
            if hasattr(message, "result") and isinstance(message.result, str):
                if message.result.strip():
                    result_chunks.append(message.result)

            # Assistant content is typically a sequence of blocks (often tuple, not always list)
            if hasattr(message, "content"):
                if isinstance(message.content, str):
                    if message.content.strip():
                        result_chunks.append(message.content)
                elif isinstance(message.content, (list, tuple)):
                    for block in message.content:
                        # TextBlock objects
                        if hasattr(block, "text") and isinstance(block.text, str):
                            if block.text.strip():
                                result_chunks.append(block.text)
                        # Dict-style blocks
                        elif isinstance(block, dict) and isinstance(block.get("text"), str):
                            if block["text"].strip():
                                result_chunks.append(block["text"])
    except Exception as e:
        return {"status": "error", "error": f"Agent execution failed: {str(e)}"}

    result_text = "\n".join(result_chunks).strip()
    return parse_agent_result(result_text)


def parse_agent_result(result_text: str) -> dict:
    """
    Parse the agent's result text to extract the JSON response.

    Args:
        result_text: Raw text output from the agent

    Returns:
        Parsed result dictionary
    """
    if not result_text:
        return {"status": "error", "error": "Empty response from agent"}

    # Try to find JSON in code blocks first
    json_patterns = [
        r'```json\s*\n?(.*?)\n?```',
        r'```\s*\n?(.*?)\n?```',
    ]

    for pattern in json_patterns:
        matches = re.findall(pattern, result_text, re.DOTALL)
        for match in matches:
            try:
                json_str = match.strip()
                if json_str.startswith('{'):
                    result = json.loads(json_str)
                    return result
            except json.JSONDecodeError:
                continue

    # Try to find any JSON object in the text
    try:
        start_idx = result_text.find('{')
        while start_idx != -1:
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
                            return result
                        except json.JSONDecodeError:
                            pass
                        break
            start_idx = result_text.find('{', start_idx + 1)
    except Exception:
        pass

    return {"status": "error", "error": f"Could not parse agent response: {result_text[:500]}..."}


def archive_file(file_path: Path) -> Path:
    """
    Archive an existing file by adding timestamp to filename.

    Args:
        file_path: Path to the file to archive

    Returns:
        Path to the archived file
    """
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    stem = file_path.stem
    archive_name = f"{stem}_archived_{timestamp}.json"
    archive_path = file_path.parent / archive_name
    shutil.copy2(file_path, archive_path)
    return archive_path


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    DIM = '\033[2m'
    BOLD = '\033[1m'
    ENDC = '\033[0m'


async def process_scholars(
    json_file_path: Path,
    aminer_dir: Path,
    enriched_dir: Path,
    labels_definition: dict,
    mode: str = "skip",
    target_ids: list[str] | None = None,
) -> dict:
    """
    Process all enriched scholars and label them.

    Args:
        json_file_path: Path to aaai-26-ai-talents.json
        aminer_dir: Directory containing AMiner cache files
        enriched_dir: Directory containing enriched data files
        labels_definition: Labels definition
        mode: Processing mode - "skip" or "overwrite"
        target_ids: Optional list of specific AMiner IDs to process

    Returns:
        Statistics dictionary with processing results
    """
    project_root = get_project_root()

    # Load the JSON file
    print(f"Loading JSON file: {json_file_path}")
    data = load_json_file(json_file_path)

    # Get scholars to process (supports both validated 'talents' entries and best-effort 'authors' entries)
    scholars = get_validated_scholars(data)
    print(f"Found {len(scholars)} scholars with usable AMiner IDs")

    # Filter to only those with enriched data
    enriched_scholars = []
    for scholar in scholars:
        aminer_id = scholar.get("aminer_id")
        enriched_file = enriched_dir / f"{aminer_id}.json"
        if enriched_file.exists():
            enriched_scholars.append(scholar)

    print(f"Found {len(enriched_scholars)} scholars with enriched data")
    scholars = enriched_scholars

    # Filter by target IDs if specified
    if target_ids:
        scholars = [s for s in scholars if s.get("aminer_id") in target_ids]
        print(f"Filtered to {len(scholars)} scholars matching target IDs")

    # Sort by citation count (high to low), so we prioritize high-impact scholars first
    scholars.sort(key=get_citation_count, reverse=True)

    # Track statistics
    label_names = [label["name"] for label in labels_definition.get("labels", [])]
    stats = {
        "total": len(scholars),
        "processed": 0,
        "skipped": 0,
        "success": 0,
        "empty": 0,
        "failed": 0,
        "errors": [],  # List of (aminer_id, name, error_message)
        "label_names": label_names,
    }

    for idx, scholar in enumerate(scholars, 1):
        name = scholar.get("name", "Unknown")
        aminer_id = scholar.get("aminer_id")
        enriched_file = enriched_dir / f"{aminer_id}.json"
        aminer_file = aminer_dir / f"{aminer_id}.json"

        # Load existing enriched data
        enriched_data = load_json_file(enriched_file)

        # Check if labels already exist
        if enriched_data.get("labels"):
            if mode == "skip":
                print(f"[{idx}/{stats['total']}] {Colors.DIM}Skipping{Colors.ENDC} {name} ({aminer_id}) - labels already exist")
                stats["skipped"] += 1
                continue
            else:
                # Archive will be done when saving
                print(f"[{idx}/{stats['total']}] Labels exist, will overwrite (archiving)")

        print(f"[{idx}/{stats['total']}] {Colors.CYAN}Labeling{Colors.ENDC} {name} ({aminer_id})")

        # Load AMiner cache if available
        aminer_data = None
        if aminer_file.exists():
            try:
                aminer_data = load_json_file(aminer_file)
                print(f"       Loaded AMiner cache")
            except Exception as e:
                print(f"       {Colors.YELLOW}Warning{Colors.ENDC}: Failed to load AMiner cache: {e}")

        # Call Agent to label data
        result = await label_scholar(scholar, aminer_data, enriched_data, labels_definition, project_root)

        # Check result
        if result.get("status") == "error":
            error_msg = result.get("error", "Unknown error")
            print(f"       {Colors.RED}[ERROR]{Colors.ENDC} {error_msg}")
            stats["failed"] += 1
            stats["errors"].append((aminer_id, name, error_msg))
            continue

        # Validate result structure
        if "results" not in result or not isinstance(result["results"], list):
            error_msg = "Invalid result structure: missing 'results' array"
            print(f"       {Colors.RED}[ERROR]{Colors.ENDC} {error_msg}")
            stats["failed"] += 1
            stats["errors"].append((aminer_id, name, error_msg))
            continue

        # Check if all labels were judged
        judged_labels = {r["name"] for r in result["results"]}
        expected_labels = set(label_names)
        if judged_labels != expected_labels:
            missing = expected_labels - judged_labels
            error_msg = f"Missing labels in result: {missing}"
            print(f"       {Colors.YELLOW}[WARNING]{Colors.ENDC} {error_msg}")

        # Archive if overwriting
        if enriched_data.get("labels") and mode == "overwrite":
            archive_path = archive_file(enriched_file)
            print(f"       Archived to: {archive_path.name}")

        # Update labels field
        enriched_data["labels"] = {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "results": result["results"]
        }

        # Save updated enriched data
        save_json_file(enriched_file, enriched_data)
        label_count = len(result["results"])
        print(f"       {Colors.GREEN}[SUCCESS]{Colors.ENDC} Labeled {label_count} fields, saved to: {enriched_file.name}")
        stats["success"] += 1
        stats["processed"] += 1

    return stats


def print_summary(stats: dict) -> None:
    """Print processing summary."""
    print("\n" + "=" * 60)
    print(f"{Colors.BOLD}Labeling Summary{Colors.ENDC}")
    print("=" * 60)
    print(f"Labels judged:      {', '.join(stats['label_names'])}")
    print(f"Total scholars:     {stats['total']}")
    print(f"Skipped:            {stats['skipped']}")
    print(f"Processed:          {stats['processed']}")
    print(f"  - Success:        {Colors.GREEN}{stats['success']}{Colors.ENDC}")
    print(f"  - Empty:          {Colors.YELLOW}{stats['empty']}{Colors.ENDC}")
    print(f"  - Failed:         {Colors.RED}{stats['failed']}{Colors.ENDC}")

    if stats["errors"]:
        print(f"\n{Colors.RED}Errors:{Colors.ENDC}")
        for aminer_id, name, error_msg in stats["errors"]:
            print(f"  - {name} ({aminer_id}): {error_msg}")


def main():
    parser = argparse.ArgumentParser(
        description="Label scholar data using Claude Agent SDK",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Label all enriched scholars using labels definition file
    python label_scholar_data.py --labels-file config/labels.json

    # Overwrite existing labels (with archiving)
    python label_scholar_data.py --labels-file config/labels.json --mode overwrite

    # Use JSON string to define labels
    python label_scholar_data.py --labels-json '{"labels": [{"name": "Chinese", "description": "..."}]}'

    # Label specific scholars only
    python label_scholar_data.py --labels-file config/labels.json --ids 53f466dfdabfaedd74e6b9e2

    # Custom directories
    python label_scholar_data.py --labels-file config/labels.json --enriched-dir ./enriched
        """
    )

    parser.add_argument(
        "--labels-file",
        type=str,
        default=None,
        help="Path to labels definition JSON file"
    )

    parser.add_argument(
        "--labels-json",
        type=str,
        default=None,
        help="Labels definition as JSON string (alternative to --labels-file)"
    )

    parser.add_argument(
        "--json-file",
        type=str,
        default=None,
        help="Path to aaai-26-ai-talents.json (default: data/aaai-26-ai-talents.json)"
    )

    parser.add_argument(
        "--aminer-dir",
        type=str,
        default=None,
        help="Directory containing AMiner cache files (default: data/aminer/scholars)"
    )

    parser.add_argument(
        "--enriched-dir",
        type=str,
        default=None,
        help="Directory containing enriched data files (default: data/enriched/scholars)"
    )

    parser.add_argument(
        "--mode",
        type=str,
        choices=["skip", "overwrite"],
        default="skip",
        help="Processing mode: skip existing (default) or overwrite (with archiving)"
    )

    parser.add_argument(
        "--ids",
        nargs="+",
        dest="target_ids",
        help="Only process specific AMiner IDs"
    )

    parser.add_argument(
        "--ids-file",
        type=str,
        dest="ids_file",
        help="File containing AMiner IDs to process (one per line)"
    )

    args = parser.parse_args()

    # Load labels definition
    labels_file = Path(args.labels_file).resolve() if args.labels_file else None
    labels_definition = load_labels_definition(labels_file, args.labels_json)

    # Validate labels definition
    if "labels" not in labels_definition or not isinstance(labels_definition["labels"], list):
        print("Error: Labels definition must contain a 'labels' array")
        sys.exit(1)

    if not labels_definition["labels"]:
        print("Error: Labels definition cannot be empty")
        sys.exit(1)

    for label in labels_definition["labels"]:
        if "name" not in label or "description" not in label:
            print(f"Error: Each label must have 'name' and 'description' fields: {label}")
            sys.exit(1)

    # Determine directories
    project_root = get_project_root()

    if args.json_file:
        json_file_path = Path(args.json_file).resolve()
    else:
        json_file_path = project_root / "data" / "aaai-26-ai-talents.json"

    if not json_file_path.exists():
        print(f"Error: File not found: {json_file_path}")
        sys.exit(1)

    if args.aminer_dir:
        aminer_dir = Path(args.aminer_dir).resolve()
    else:
        aminer_dir = project_root / "data" / "aminer" / "scholars"

    if args.enriched_dir:
        enriched_dir = Path(args.enriched_dir).resolve()
    else:
        enriched_dir = project_root / "data" / "enriched" / "scholars"

    if not enriched_dir.exists():
        print(f"Error: Enriched directory not found: {enriched_dir}")
        print("Please run enrich_scholar_data.py first to create enriched data")
        sys.exit(1)

    # Collect target IDs
    target_ids = args.target_ids or []
    if args.ids_file:
        ids_file_path = Path(args.ids_file).resolve()
        if ids_file_path.exists():
            with open(ids_file_path, 'r') as f:
                file_ids = [line.strip() for line in f if line.strip()]
                target_ids.extend(file_ids)
        else:
            print(f"Warning: IDs file not found: {ids_file_path}")

    target_ids = list(set(target_ids)) if target_ids else None

    # Print configuration
    label_names = [label["name"] for label in labels_definition["labels"]]
    print(f"Labels to judge: {', '.join(label_names)}")
    print(f"Source JSON file: {json_file_path}")
    print(f"AMiner cache directory: {aminer_dir}")
    print(f"Enriched data directory: {enriched_dir}")
    print(f"Mode: {args.mode}")
    if target_ids:
        print(f"Target IDs: {len(target_ids)} specified")
    print()

    # Process scholars
    stats = asyncio.run(process_scholars(
        json_file_path=json_file_path,
        aminer_dir=aminer_dir,
        enriched_dir=enriched_dir,
        labels_definition=labels_definition,
        mode=args.mode,
        target_ids=target_ids,
    ))

    # Print summary
    print_summary(stats)


if __name__ == "__main__":
    main()
