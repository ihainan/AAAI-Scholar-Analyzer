#!/usr/bin/env python3
"""
AMiner API Client

This script provides command-line access to AMiner's academic query APIs.
API key is read from the AMINER_API_KEY environment variable.

Usage:
    python aminer_api.py org-search <org_name1> [org_name2 ...]
    python aminer_api.py org-detail <org_id1> [org_id2 ...]
    python aminer_api.py person-search --name <name> [--org-id <org_id>] [--offset <n>] [--size <n>]
    python aminer_api.py person-detail <person_id>
    python aminer_api.py person-projects <person_id>
    python aminer_api.py person-papers <person_id> [--offset <n>] [--size <n>]
    python aminer_api.py person-figure <person_id>
    python aminer_api.py person-patents <person_id>
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


def make_request(endpoint: str, data: dict) -> dict:
    """Make a POST request to the AMiner API."""
    api_key = get_api_key()
    url = f"{BASE_URL}{endpoint}"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json;charset=utf-8"
    }

    request_body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=request_body, headers=headers, method="POST")

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


def make_get_request(endpoint: str, params: Optional[dict] = None) -> dict:
    """Make a GET request to the AMiner API."""
    api_key = get_api_key()

    if params:
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


def search_organization(org_names: list[str]) -> dict:
    """
    Search for organization IDs by name.

    Args:
        org_names: List of organization names to search for.

    Returns:
        API response with organization IDs.
    """
    return make_request("/organization/search", {"orgs": org_names})


def get_organization_detail(org_ids: list[str]) -> dict:
    """
    Get organization details by ID.

    Args:
        org_ids: List of organization IDs to retrieve.

    Returns:
        API response with organization details.
    """
    return make_request("/organization/detail", {"ids": org_ids})


MAX_PAGE_SIZE = 10


def search_person(
    name: str,
    org_ids: Optional[list[str]] = None,
    offset: int = 0,
    size: int = 10
) -> dict:
    """
    Search for scholars by name, optionally filtered by organization.

    Args:
        name: Scholar name to search for.
        org_ids: Optional list of organization IDs to filter by.
        offset: Pagination offset (default: 0).
        size: Number of results per page (default: 10, max: 10).

    Returns:
        API response with scholar information.
    """
    if size > MAX_PAGE_SIZE:
        print(f"Warning: size exceeds maximum ({MAX_PAGE_SIZE}), using {MAX_PAGE_SIZE}", file=sys.stderr)
        size = MAX_PAGE_SIZE

    data = {
        "name": name,
        "offset": offset,
        "size": size
    }
    if org_ids:
        data["org_id"] = org_ids

    return make_request("/person/search", data)


def get_person_detail(person_id: str) -> dict:
    """
    Get detailed information about a scholar.

    Args:
        person_id: The scholar's ID.

    Returns:
        API response with scholar details including bio, education, honors, etc.
    """
    return make_get_request("/person/detail", {"id": person_id})


def get_person_projects(person_id: str) -> dict:
    """
    Get projects associated with a scholar.

    Args:
        person_id: The scholar's ID.

    Returns:
        API response with scholar's project list.
    """
    return make_get_request("/project/person/v3/open", {"id": person_id})


MAX_PAPERS_PAGE_SIZE = 20


def get_person_papers(
    person_id: str,
    offset: int = 0,
    size: int = 20
) -> dict:
    """
    Get papers authored by a scholar with client-side pagination.

    The API returns all papers at once, but this function provides
    client-side pagination to limit the response size.

    Args:
        person_id: The scholar's ID.
        offset: Pagination offset (default: 0).
        size: Number of results per page (default: 20, max: 20).

    Returns:
        API response with paginated paper list and total count.
    """
    if size > MAX_PAPERS_PAGE_SIZE:
        print(f"Warning: size exceeds maximum ({MAX_PAPERS_PAGE_SIZE}), using {MAX_PAPERS_PAGE_SIZE}", file=sys.stderr)
        size = MAX_PAPERS_PAGE_SIZE

    result = make_get_request("/person/paper/relation", {"id": person_id})

    if result.get("success") and "data" in result:
        all_papers = result["data"]
        total = len(all_papers)
        paginated_papers = all_papers[offset:offset + size]
        result["data"] = paginated_papers
        result["total"] = total
        result["offset"] = offset
        result["size"] = size

    return result


def get_person_figure(person_id: str) -> dict:
    """
    Get scholar's profile/figure including research interests, education, and work history.

    Args:
        person_id: The scholar's ID.

    Returns:
        API response with scholar's research interests, education and work history.
    """
    return make_get_request("/person/figure", {"id": person_id})


def get_person_patents(person_id: str) -> dict:
    """
    Get patents associated with a scholar.

    Args:
        person_id: The scholar's ID.

    Returns:
        API response with scholar's patent list.
    """
    return make_get_request("/person/patent/relation", {"id": person_id})


def main():
    parser = argparse.ArgumentParser(
        description="AMiner Academic Query API Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Search for organization ID
    python aminer_api.py org-search "University of Alberta"

    # Search for multiple organizations
    python aminer_api.py org-search "MIT" "Stanford University"

    # Get organization details
    python aminer_api.py org-detail 5f71b2941c455f439fe3cd7c

    # Search for a scholar
    python aminer_api.py person-search --name "Adam Parker"

    # Search for a scholar in a specific organization
    python aminer_api.py person-search --name "Adam Parker" --org-id 5f71b2941c455f439fe3cd7c

    # Search with pagination (get next 10 results)
    python aminer_api.py person-search --name "John Smith" --offset 10

    # Get scholar details
    python aminer_api.py person-detail 53f466dfdabfaedd74e6b9e2

    # Get scholar's projects
    python aminer_api.py person-projects 53f466dfdabfaedd74e6b9e2

    # Get scholar's papers (with pagination)
    python aminer_api.py person-papers 53f466dfdabfaedd74e6b9e2
    python aminer_api.py person-papers 53f466dfdabfaedd74e6b9e2 --offset 20 --size 10

    # Get scholar's research profile/figure
    python aminer_api.py person-figure 53f466dfdabfaedd74e6b9e2

    # Get scholar's patents
    python aminer_api.py person-patents 53f466dfdabfaedd74e6b9e2
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # org-search subcommand
    org_search_parser = subparsers.add_parser(
        "org-search",
        help="Search for organization IDs by name"
    )
    org_search_parser.add_argument(
        "names",
        nargs="+",
        help="Organization names to search for"
    )

    # org-detail subcommand
    org_detail_parser = subparsers.add_parser(
        "org-detail",
        help="Get organization details by ID"
    )
    org_detail_parser.add_argument(
        "ids",
        nargs="+",
        help="Organization IDs to retrieve details for"
    )

    # person-search subcommand
    person_search_parser = subparsers.add_parser(
        "person-search",
        help="Search for scholars by name"
    )
    person_search_parser.add_argument(
        "--name",
        required=True,
        help="Scholar name to search for"
    )
    person_search_parser.add_argument(
        "--org-id",
        nargs="+",
        dest="org_ids",
        help="Organization ID(s) to filter by"
    )
    person_search_parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Pagination offset (default: 0)"
    )
    person_search_parser.add_argument(
        "--size",
        type=int,
        default=10,
        help="Number of results per page (default: 10, max: 10)"
    )

    # person-detail subcommand
    person_detail_parser = subparsers.add_parser(
        "person-detail",
        help="Get detailed information about a scholar"
    )
    person_detail_parser.add_argument(
        "id",
        help="Scholar ID"
    )

    # person-projects subcommand
    person_projects_parser = subparsers.add_parser(
        "person-projects",
        help="Get projects associated with a scholar"
    )
    person_projects_parser.add_argument(
        "id",
        help="Scholar ID"
    )

    # person-papers subcommand
    person_papers_parser = subparsers.add_parser(
        "person-papers",
        help="Get papers authored by a scholar"
    )
    person_papers_parser.add_argument(
        "id",
        help="Scholar ID"
    )
    person_papers_parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Pagination offset (default: 0)"
    )
    person_papers_parser.add_argument(
        "--size",
        type=int,
        default=20,
        help="Number of results per page (default: 20, max: 20)"
    )

    # person-figure subcommand
    person_figure_parser = subparsers.add_parser(
        "person-figure",
        help="Get scholar's profile including research interests, education and work history"
    )
    person_figure_parser.add_argument(
        "id",
        help="Scholar ID"
    )

    # person-patents subcommand
    person_patents_parser = subparsers.add_parser(
        "person-patents",
        help="Get patents associated with a scholar"
    )
    person_patents_parser.add_argument(
        "id",
        help="Scholar ID"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "org-search":
        result = search_organization(args.names)
    elif args.command == "org-detail":
        result = get_organization_detail(args.ids)
    elif args.command == "person-search":
        result = search_person(
            name=args.name,
            org_ids=args.org_ids,
            offset=args.offset,
            size=args.size
        )
    elif args.command == "person-detail":
        result = get_person_detail(args.id)
    elif args.command == "person-projects":
        result = get_person_projects(args.id)
    elif args.command == "person-papers":
        result = get_person_papers(
            person_id=args.id,
            offset=args.offset,
            size=args.size
        )
    elif args.command == "person-figure":
        result = get_person_figure(args.id)
    elif args.command == "person-patents":
        result = get_person_patents(args.id)
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
