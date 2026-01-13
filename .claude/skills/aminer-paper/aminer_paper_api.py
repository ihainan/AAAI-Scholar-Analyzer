#!/usr/bin/env python3
"""
AMiner Paper API Client

This script provides command-line access to AMiner's paper query APIs.
API key is read from the AMINER_API_KEY environment variable.

Usage:
    python aminer_paper_api.py paper-search --title <title> [--page <n>] [--size <n>]
    python aminer_paper_api.py paper-search-pro [--title <title>] [--keyword <kw>] [--abstract <abs>] [--author <auth>] [--org <org>] [--venue <venue>] [--order <order>] [--page <n>] [--size <n>]
    python aminer_paper_api.py paper-detail <paper_id>
"""

import argparse
import json
import os
import sys
from typing import Optional
import urllib.request
import urllib.error
import urllib.parse


BASE_URL = "https://datacenter.aminer.cn/gateway/open_platform/api"


def get_api_key() -> str:
    """Get API key from environment variable."""
    api_key = os.environ.get("AMINER_API_KEY")
    if not api_key:
        print("Error: AMINER_API_KEY environment variable is not set", file=sys.stderr)
        sys.exit(1)
    return api_key


def make_get_request(endpoint: str, params: Optional[dict] = None) -> dict:
    """Make a GET request to the AMiner API."""
    api_key = get_api_key()

    if params:
        # Filter out None values
        params = {k: v for k, v in params.items() if v is not None}
        query_string = urllib.parse.urlencode(params)
        url = f"{BASE_URL}{endpoint}?{query_string}"
    else:
        url = f"{BASE_URL}{endpoint}"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json;charset=utf-8"
    }

    req = urllib.request.Request(url, headers=headers, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else ""
        print(f"HTTP Error {e.code}: {e.reason}", file=sys.stderr)
        if error_body:
            print(f"Response: {error_body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"URL Error: {e.reason}", file=sys.stderr)
        sys.exit(1)


MAX_BASIC_SEARCH_SIZE = 20
DEFAULT_SEARCH_SIZE = 10


def search_paper(
    title: str,
    page: int = 0,
    size: int = DEFAULT_SEARCH_SIZE
) -> dict:
    """
    Search for papers by title.

    Args:
        title: Paper title to search for.
        page: Page number (default: 0).
        size: Number of results per page (default: 10, max: 20).

    Returns:
        API response with paper information.
    """
    if size > MAX_BASIC_SEARCH_SIZE:
        print(f"Warning: size exceeds maximum ({MAX_BASIC_SEARCH_SIZE}), using {MAX_BASIC_SEARCH_SIZE}", file=sys.stderr)
        size = MAX_BASIC_SEARCH_SIZE

    params = {
        "title": title,
        "page": page,
        "size": size
    }

    return make_get_request("/paper/search", params)


MAX_PRO_SEARCH_SIZE = 100


def search_paper_pro(
    title: Optional[str] = None,
    keyword: Optional[str] = None,
    abstract: Optional[str] = None,
    author: Optional[str] = None,
    org: Optional[str] = None,
    venue: Optional[str] = None,
    order: Optional[str] = None,
    page: int = 0,
    size: int = DEFAULT_SEARCH_SIZE
) -> dict:
    """
    Search for papers with advanced filters.

    Args:
        title: Paper title to search for.
        keyword: Keywords to search for.
        abstract: Abstract content to search for.
        author: Author name to search for.
        org: Organization/institution to search for.
        venue: Venue/journal name to search for.
        order: Sort order (e.g., 'year', 'n_citation' for descending order).
        page: Page number (default: 0).
        size: Number of results per page (default: 10, max: 100).

    Returns:
        API response with paper information.
    """
    if size > MAX_PRO_SEARCH_SIZE:
        print(f"Warning: size exceeds maximum ({MAX_PRO_SEARCH_SIZE}), using {MAX_PRO_SEARCH_SIZE}", file=sys.stderr)
        size = MAX_PRO_SEARCH_SIZE

    params = {
        "page": page,
        "size": size
    }

    # Add optional search parameters
    if title:
        params["title"] = title
    if keyword:
        params["keyword"] = keyword
    if abstract:
        params["abstract"] = abstract
    if author:
        params["author"] = author
    if org:
        params["org"] = org
    if venue:
        params["venue"] = venue
    if order:
        params["order"] = order

    return make_get_request("/paper/search/pro", params)


def get_paper_detail(paper_id: str) -> dict:
    """
    Get detailed information about a paper.

    Args:
        paper_id: The paper's ID.

    Returns:
        API response with paper details including abstract, authors, keywords, etc.
    """
    return make_get_request("/paper/detail", {"id": paper_id})


def main():
    parser = argparse.ArgumentParser(
        description="AMiner Paper Query API Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Basic paper search by title
    python aminer_paper_api.py paper-search --title "LongSplat"

    # Paper search with pagination
    python aminer_paper_api.py paper-search --title "LongSplat" --page 1 --size 20

    # Advanced paper search with multiple filters
    python aminer_paper_api.py paper-search-pro --title "neural network" --author "Hinton"

    # Search papers by keyword and venue
    python aminer_paper_api.py paper-search-pro --keyword "machine learning" --venue "NeurIPS"

    # Search with sorting by citations
    python aminer_paper_api.py paper-search-pro --title "transformer" --order "n_citation"

    # Get paper details
    python aminer_paper_api.py paper-detail 6880406d163c01c8507070d4
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # paper-search subcommand
    paper_search_parser = subparsers.add_parser(
        "paper-search",
        help="Search for papers by title"
    )
    paper_search_parser.add_argument(
        "--title",
        required=True,
        help="Paper title to search for"
    )
    paper_search_parser.add_argument(
        "--page",
        type=int,
        default=0,
        help="Page number (default: 0)"
    )
    paper_search_parser.add_argument(
        "--size",
        type=int,
        default=DEFAULT_SEARCH_SIZE,
        help=f"Number of results per page (default: {DEFAULT_SEARCH_SIZE}, max: {MAX_BASIC_SEARCH_SIZE})"
    )

    # paper-search-pro subcommand
    paper_search_pro_parser = subparsers.add_parser(
        "paper-search-pro",
        help="Search for papers with advanced filters"
    )
    paper_search_pro_parser.add_argument(
        "--title",
        help="Paper title to search for"
    )
    paper_search_pro_parser.add_argument(
        "--keyword",
        help="Keywords to search for"
    )
    paper_search_pro_parser.add_argument(
        "--abstract",
        help="Abstract content to search for"
    )
    paper_search_pro_parser.add_argument(
        "--author",
        help="Author name to search for"
    )
    paper_search_pro_parser.add_argument(
        "--org",
        help="Organization/institution to search for"
    )
    paper_search_pro_parser.add_argument(
        "--venue",
        help="Venue/journal name to search for"
    )
    paper_search_pro_parser.add_argument(
        "--order",
        help="Sort order (e.g., 'year', 'n_citation' for descending order)"
    )
    paper_search_pro_parser.add_argument(
        "--page",
        type=int,
        default=0,
        help="Page number (default: 0)"
    )
    paper_search_pro_parser.add_argument(
        "--size",
        type=int,
        default=DEFAULT_SEARCH_SIZE,
        help=f"Number of results per page (default: {DEFAULT_SEARCH_SIZE}, max: {MAX_PRO_SEARCH_SIZE})"
    )

    # paper-detail subcommand
    paper_detail_parser = subparsers.add_parser(
        "paper-detail",
        help="Get detailed information about a paper"
    )
    paper_detail_parser.add_argument(
        "id",
        help="Paper ID"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "paper-search":
        result = search_paper(
            title=args.title,
            page=args.page,
            size=args.size
        )
    elif args.command == "paper-search-pro":
        # Check that at least one search parameter is provided
        if not any([args.title, args.keyword, args.abstract, args.author, args.org, args.venue]):
            print("Error: At least one search parameter (--title, --keyword, --abstract, --author, --org, --venue) must be provided", file=sys.stderr)
            sys.exit(1)

        result = search_paper_pro(
            title=args.title,
            keyword=args.keyword,
            abstract=args.abstract,
            author=args.author,
            org=args.org,
            venue=args.venue,
            order=args.order,
            page=args.page,
            size=args.size
        )
    elif args.command == "paper-detail":
        result = get_paper_detail(args.id)
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
