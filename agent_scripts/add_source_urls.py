#!/usr/bin/env python3
"""
从 markdown 文件的 frontmatter 中提取 source_url，
并添加到 talents JSON 文件的每个记录中。
"""

import json
import re
from pathlib import Path


def extract_source_url(md_file_path: Path) -> str | None:
    """从 markdown 文件的 YAML frontmatter 中提取 source_url"""
    if not md_file_path.exists():
        print(f"Warning: File not found: {md_file_path}")
        return None

    content = md_file_path.read_text(encoding='utf-8')

    # 匹配 YAML frontmatter
    frontmatter_match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not frontmatter_match:
        print(f"Warning: No frontmatter found in {md_file_path}")
        return None

    frontmatter = frontmatter_match.group(1)

    # 提取 source_url
    url_match = re.search(r'^source_url:\s*(.+)$', frontmatter, re.MULTILINE)
    if not url_match:
        print(f"Warning: No source_url found in {md_file_path}")
        return None

    return url_match.group(1).strip()


def main():
    # 路径设置
    base_dir = Path(__file__).parent.parent
    input_file = base_dir / "data" / "aaai-26-ai-talents.json"
    output_file = base_dir / "data" / "aaai-26-ai-talents-with-urls.json"
    data_base_path = base_dir / "data" / "aaai-26"

    # 读取 JSON 文件
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 构建 source 到 URL 的映射缓存
    source_url_cache: dict[str, str | None] = {}

    # 处理每个 talent 记录
    for talent in data['talents']:
        source_urls = []

        for source in talent.get('sources', []):
            # 检查缓存
            if source not in source_url_cache:
                md_path = data_base_path / source
                source_url_cache[source] = extract_source_url(md_path)

            url = source_url_cache[source]
            if url and url not in source_urls:  # 去重
                source_urls.append(url)

        # 添加 source_urls 字段
        talent['source_urls'] = source_urls

    # 写入新文件
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Done! Output written to: {output_file}")
    print(f"Processed {len(data['talents'])} talents")


if __name__ == '__main__':
    main()
