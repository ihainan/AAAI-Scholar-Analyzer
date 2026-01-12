#!/usr/bin/env python3
"""
Enrich scholar data by fetching external links and additional info using Claude Agent SDK.

This script reads scholars from aaai-26-ai-talents.json that have validated AMiner IDs,
combines their data with AMiner cache, and uses an Agent to search for external links
(homepage, Google Scholar, DBLP, etc.) and supplementary information.

Usage:
    python enrich_scholar_data.py <json_file_path> [options]

Example:
    python enrich_scholar_data.py ../data/aaai-26-ai-talents.json
    python enrich_scholar_data.py ../data/aaai-26-ai-talents.json --mode overwrite
    python enrich_scholar_data.py ../data/aaai-26-ai-talents.json --ids 53f466dfdabfaedd74e6b9e2
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


def get_validated_scholars(data: dict) -> list[dict]:
    """
    Extract scholars with validated AMiner IDs from the data.

    Returns only scholars where:
    - aminer_validation.status == "success"
    - aminer_validation.is_same_person == True
    - aminer_id exists and is not empty/failed
    """
    scholars = []
    for talent in data.get("talents", []):
        validation = talent.get("aminer_validation", {})
        aminer_id = talent.get("aminer_id", "")

        if (validation.get("status") == "success" and
            validation.get("is_same_person") is True and
            aminer_id and aminer_id != "failed"):
            scholars.append(talent)

    return scholars


def truncate_list(items: list | None, max_items: int = 2) -> list | None:
    """Truncate a list to max_items, preserving None."""
    if items is None:
        return None
    return items[:max_items]


def build_scholar_context(scholar: dict, aminer_data: dict | None) -> dict:
    """
    Build a combined context for the Agent, truncating large lists.

    Args:
        scholar: Scholar data from aaai-26-ai-talents.json
        aminer_data: AMiner cache data (if available)

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

    return context


def build_prompt(scholar_json: str) -> str:
    """Build the prompt for the Agent."""
    return f"""你是一个学者信息调研专家。我们已经从 AAAI 2026 官网和 AMiner 获取了该学者的基础信息（注意：projects、papers、patents 仅展示前 2 条，实际数据更多）：

```json
{scholar_json}
```

请通过联网搜索，获取以下**外部链接和联系方式**（AMiner 不提供这些信息）：

1. `homepage` - 个人主页 URL（通常是 .edu 域名下的个人页面）
2. `google_scholar` - Google Scholar 主页 URL
3. `dblp` - DBLP 主页 URL
4. `linkedin` - LinkedIn 个人主页 URL
5. `twitter` - X/Twitter 账号 URL
6. `email` - 公开邮箱地址（优先从官方主页获取最新的）
7. `orcid` - ORCID ID 或 URL
8. `semantic_scholar` - Semantic Scholar 主页 URL
9. `photo_url` - 学者头像 URL（优先从官方主页获取）

此外，如果 AMiner 数据中以下字段缺失或不完整，请补充：

10. `research_interests` - 研究领域关键词列表（仅当上述 JSON 中缺失时补充）
11. `title` - 职称如 Professor/Associate Professor（仅当上述 JSON 中缺失时补充）
12. `phd_institution` - 博士毕业院校（仅当上述 JSON 中缺失时补充）
13. `phd_year` - 博士毕业年份（仅当上述 JSON 中缺失时补充）
14. `additional_info` - 其他重要补充信息（如 Fellow 身份、重要奖项等，限 200 字）

**输出格式示例（仅包含成功获取的字段）：**

```json
{{
  "homepage": "https://www.cs.example.edu/~johnsmith",
  "google_scholar": "https://scholar.google.com/citations?user=abcd1234",
  "dblp": "https://dblp.org/pid/123/4567.html",
  "linkedin": "https://www.linkedin.com/in/johnsmith",
  "twitter": "https://twitter.com/johnsmith",
  "email": "john.smith@example.edu",
  "orcid": "https://orcid.org/0000-0001-2345-6789",
  "semantic_scholar": "https://www.semanticscholar.org/author/12345678",
  "photo_url": "https://www.cs.example.edu/~johnsmith/photo.jpg",
  "research_interests": ["Machine Learning", "Natural Language Processing", "Computer Vision"],
  "title": "Professor",
  "phd_institution": "Stanford University",
  "phd_year": 2005,
  "additional_info": "ACM Fellow (2018), IEEE Fellow (2020). Best Paper Award at NeurIPS 2019."
}}
```

如果遇到致命错误导致无法获取任何信息：

```json
{{
  "status": "error",
  "error": "错误描述"
}}
```

**注意事项：**
- 只返回你有 90% 以上信心确认属于该学者的信息
- 获取失败的字段直接跳过，不要返回
- 如果所有字段都获取失败，返回空对象 `{{}}`
- URL 必须是完整的 https:// 格式"""


async def enrich_scholar(scholar: dict, aminer_data: dict | None, project_root: Path) -> dict:
    """
    Use Claude Agent SDK to enrich scholar data with external links.

    Args:
        scholar: Scholar data from aaai-26-ai-talents.json
        aminer_data: AMiner cache data (if available)
        project_root: Project root directory path

    Returns:
        Result dictionary with enriched data or error info
    """
    try:
        from claude_agent_sdk import query, ClaudeAgentOptions
    except ImportError:
        print("Error: claude_agent_sdk is not installed. Please install it with:")
        print("  pip install claude-agent-sdk")
        sys.exit(1)

    # Build context and prompt
    context = build_scholar_context(scholar, aminer_data)
    scholar_json = json.dumps(context, indent=2, ensure_ascii=False)
    prompt = build_prompt(scholar_json)

    options = ClaudeAgentOptions(
        cwd=str(project_root),
        setting_sources=["project"],
        allowed_tools=["WebSearch", "WebFetch", "Read"],
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
                if isinstance(message.content, str):
                    result_text = message.content
                elif isinstance(message.content, list):
                    for block in message.content:
                        if hasattr(block, "text"):
                            result_text = block.text
    except Exception as e:
        return {"status": "error", "error": f"Agent execution failed: {str(e)}"}

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
    mode: str = "skip",
    target_ids: list[str] | None = None,
) -> dict:
    """
    Process all validated scholars and enrich their data.

    Args:
        json_file_path: Path to aaai-26-ai-talents.json
        aminer_dir: Directory containing AMiner cache files
        enriched_dir: Directory to save enriched data files
        mode: Processing mode - "skip" or "overwrite"
        target_ids: Optional list of specific AMiner IDs to process

    Returns:
        Statistics dictionary with processing results
    """
    project_root = get_project_root()

    # Load the JSON file
    print(f"Loading JSON file: {json_file_path}")
    data = load_json_file(json_file_path)

    # Get validated scholars
    scholars = get_validated_scholars(data)
    print(f"Found {len(scholars)} scholars with validated AMiner IDs")

    # Filter by target IDs if specified
    if target_ids:
        scholars = [s for s in scholars if s.get("aminer_id") in target_ids]
        print(f"Filtered to {len(scholars)} scholars matching target IDs")

    # Ensure output directory exists
    enriched_dir.mkdir(parents=True, exist_ok=True)

    # Track statistics
    stats = {
        "total": len(scholars),
        "processed": 0,
        "skipped": 0,
        "success": 0,
        "empty": 0,
        "failed": 0,
        "errors": []  # List of (aminer_id, name, error_message)
    }

    for idx, scholar in enumerate(scholars, 1):
        name = scholar.get("name", "Unknown")
        aminer_id = scholar.get("aminer_id")
        enriched_file = enriched_dir / f"{aminer_id}.json"
        aminer_file = aminer_dir / f"{aminer_id}.json"

        # Check if enriched file exists
        if enriched_file.exists():
            if mode == "skip":
                print(f"[{idx}/{stats['total']}] {Colors.DIM}Skipping{Colors.ENDC} {name} ({aminer_id}) - enriched file exists")
                stats["skipped"] += 1
                continue
            else:
                # Archive existing file
                archive_path = archive_file(enriched_file)
                print(f"[{idx}/{stats['total']}] Archived existing file to: {archive_path.name}")

        print(f"[{idx}/{stats['total']}] {Colors.CYAN}Enriching{Colors.ENDC} {name} ({aminer_id})")

        # Load AMiner cache if available
        aminer_data = None
        if aminer_file.exists():
            try:
                aminer_data = load_json_file(aminer_file)
                print(f"       Loaded AMiner cache")
            except Exception as e:
                print(f"       {Colors.YELLOW}Warning{Colors.ENDC}: Failed to load AMiner cache: {e}")

        # Call Agent to enrich data
        result = await enrich_scholar(scholar, aminer_data, project_root)

        # Check result
        if result.get("status") == "error":
            error_msg = result.get("error", "Unknown error")
            print(f"       {Colors.RED}[ERROR]{Colors.ENDC} {error_msg}")
            stats["failed"] += 1
            stats["errors"].append((aminer_id, name, error_msg))
            continue

        # Check if result is empty
        if not result or len(result) == 0:
            print(f"       {Colors.YELLOW}[EMPTY]{Colors.ENDC} No data retrieved")
            stats["empty"] += 1
            # Still save empty result with metadata
            enriched_data = {
                "aminer_id": aminer_id,
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }
            save_json_file(enriched_file, enriched_data)
            continue

        # Build enriched data with metadata
        enriched_data = {
            "aminer_id": aminer_id,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            **result
        }

        # Save enriched data
        save_json_file(enriched_file, enriched_data)
        field_count = len([k for k in result.keys() if k != "status"])
        print(f"       {Colors.GREEN}[SUCCESS]{Colors.ENDC} Saved {field_count} fields to: {enriched_file.name}")
        stats["success"] += 1
        stats["processed"] += 1

    return stats


def print_summary(stats: dict) -> None:
    """Print processing summary."""
    print("\n" + "=" * 60)
    print(f"{Colors.BOLD}Enrichment Summary{Colors.ENDC}")
    print("=" * 60)
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
        description="Enrich scholar data with external links using Claude Agent SDK",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Enrich all validated scholars (skip existing)
    python enrich_scholar_data.py ../data/aaai-26-ai-talents.json

    # Overwrite existing enriched files (with archiving)
    python enrich_scholar_data.py ../data/aaai-26-ai-talents.json --mode overwrite

    # Enrich specific scholars only
    python enrich_scholar_data.py ../data/aaai-26-ai-talents.json --ids 53f466dfdabfaedd74e6b9e2

    # Custom directories
    python enrich_scholar_data.py ../data/aaai-26-ai-talents.json --aminer-dir ./aminer --enriched-dir ./enriched
        """
    )

    parser.add_argument(
        "json_file",
        type=str,
        help="Path to the JSON file containing scholar information"
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
        help="Directory to save enriched data files (default: data/enriched/scholars)"
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

    # Resolve file path
    json_file_path = Path(args.json_file).resolve()
    if not json_file_path.exists():
        print(f"Error: File not found: {json_file_path}")
        sys.exit(1)

    # Determine directories
    project_root = get_project_root()
    if args.aminer_dir:
        aminer_dir = Path(args.aminer_dir).resolve()
    else:
        aminer_dir = project_root / "data" / "aminer" / "scholars"

    if args.enriched_dir:
        enriched_dir = Path(args.enriched_dir).resolve()
    else:
        enriched_dir = project_root / "data" / "enriched" / "scholars"

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

    print(f"AMiner cache directory: {aminer_dir}")
    print(f"Enriched output directory: {enriched_dir}")
    print(f"Mode: {args.mode}")
    if target_ids:
        print(f"Target IDs: {len(target_ids)} specified")
    print()

    # Process scholars
    stats = asyncio.run(process_scholars(
        json_file_path=json_file_path,
        aminer_dir=aminer_dir,
        enriched_dir=enriched_dir,
        mode=args.mode,
        target_ids=target_ids,
    ))

    # Print summary
    print_summary(stats)


if __name__ == "__main__":
    main()
