#!/usr/bin/env python3
"""
Fetch and recognize email addresses for scholars using OCR.

This script:
1. Loads scholars from authors.json and sorts by citation count
2. Downloads email images (white background) from data-proxy API
3. Uses PaddleOCR VL model to recognize email text
4. Falls back to Qwen3-VL-Plus if PaddleOCR fails
5. Stores recognized emails in data/enriched/scholars/<aminer_id>.json

Features:
- Skips scholars who already have email addresses
- Uses local cache for email images
- Respects rate limits with configurable delays
- Supports testing with specific scholar IDs
- Automatic fallback to Qwen3-VL-Plus for better accuracy

Usage:
    # Process all scholars (sorted by citations, high to low)
    python fetch_email_addresses.py

    # Test with specific scholars
    python fetch_email_addresses.py --ids 53f46ca8dabfaec09f2584aa 5629598545cedb339885912b

    # Custom API URLs and delays
    python fetch_email_addresses.py --api-url http://localhost:37804 --delay 2

    # Force refresh cached images
    python fetch_email_addresses.py --force-refresh

Environment:
    Required - PaddleOCR API credentials:
    export PADDLE_OCR_API_URL="https://h0y2i794u98027ue.aistudio-app.com/layout-parsing"
    export PADDLE_OCR_TOKEN="your_token"

    Optional - Qwen3-VL-Plus fallback (improves accuracy):
    export DASHSCOPE_API_KEY="sk-xxx"
"""

import argparse
import base64
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional, Set
import sys

import httpx


# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
AUTHORS_FILE = PROJECT_ROOT / "data" / "aaai-26" / "authors.json"
ENRICHED_DIR = PROJECT_ROOT / "data" / "enriched" / "scholars"
EMAIL_IMG_DIR = PROJECT_ROOT / "data" / "aminer" / "email-imgs"
SCHOLARS_DIR = PROJECT_ROOT / "data" / "aminer" / "scholars"

# API Configuration
DEFAULT_DATA_PROXY_URL = "http://localhost:37804"
DEFAULT_DELAY = 2.0  # seconds between requests
DEFAULT_OCR_DELAY = 3.0  # OCR API is slower

# OCR Configuration (must be set via environment variables)
PADDLE_OCR_API_URL = None
PADDLE_OCR_TOKEN = None

# Qwen VL Configuration (fallback OCR)
DASHSCOPE_API_KEY = None


def load_sorted_scholar_ids() -> List[tuple[str, int]]:
    """
    Load scholar IDs from authors.json, sorted by citation count (high to low).

    Returns:
        List of (aminer_id, n_citation) tuples, sorted by citation count descending
    """
    if not AUTHORS_FILE.exists():
        print(f"Error: Authors file not found: {AUTHORS_FILE}")
        sys.exit(1)

    try:
        with open(AUTHORS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        authors = data.get('authors', [])
        if not authors:
            print("Warning: No authors found in authors.json")
            return []

        # Extract aminer_id and n_citation, sort by citations descending
        scholars = []
        for author in authors:
            aminer_id = author.get('aminer_id')
            n_citation = author.get('n_citation')
            # Handle None values - treat as 0
            if n_citation is None:
                n_citation = 0
            if aminer_id:
                scholars.append((aminer_id, n_citation))

        # Sort by citations (high to low), handle None values as 0
        scholars.sort(key=lambda x: x[1] if x[1] is not None else 0, reverse=True)

        return scholars

    except Exception as e:
        print(f"Error: Failed to load authors.json: {e}")
        sys.exit(1)


def load_scholar_data(aminer_id: str) -> Optional[Dict]:
    """Load scholar data from aminer/scholars directory."""
    scholar_file = SCHOLARS_DIR / f"{aminer_id}.json"
    if not scholar_file.exists():
        return None

    try:
        with open(scholar_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Extract useful information
        detail = data.get('detail', {})
        return {
            'name': detail.get('name', ''),
            'name_zh': detail.get('name_zh', ''),
            'orgs': detail.get('orgs', []),
            'position': detail.get('position', '')
        }
    except Exception as e:
        print(f"    Warning: Failed to load scholar data: {e}")
        return None


def load_enriched_data(aminer_id: str) -> Optional[Dict]:
    """Load enriched data for a scholar."""
    enriched_file = ENRICHED_DIR / f"{aminer_id}.json"
    if not enriched_file.exists():
        return None

    try:
        with open(enriched_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"    Warning: Failed to load enriched data: {e}")
        return None


def save_enriched_data(aminer_id: str, data: Dict) -> bool:
    """Save enriched data for a scholar."""
    enriched_file = ENRICHED_DIR / f"{aminer_id}.json"
    ENRICHED_DIR.mkdir(parents=True, exist_ok=True)

    try:
        with open(enriched_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"    Error: Failed to save enriched data: {e}")
        return False


def has_email_in_enriched(aminer_id: str) -> bool:
    """Check if scholar already has email in enriched data."""
    data = load_enriched_data(aminer_id)
    if data and data.get('email'):
        return True
    return False


def get_cached_email_image(aminer_id: str) -> Optional[tuple[Path, str]]:
    """
    Check if email image already exists in cache.

    Returns:
        (image_path, marker_path) if image exists or no-email marker exists
        None if not cached
    """
    no_email_marker = EMAIL_IMG_DIR / f"{aminer_id}.no_email"

    # Check for no-email marker
    if no_email_marker.exists():
        return None, "no_email"

    # Check for existing image files
    for ext in ['.png', '.jpg', '.jpeg']:
        image_path = EMAIL_IMG_DIR / f"{aminer_id}{ext}"
        if image_path.exists():
            return image_path, "exists"

    return None, "missing"


def download_email_image(
    client: httpx.Client,
    api_url: str,
    aminer_id: str,
    authorization: str,
    x_signature: str,
    x_timestamp: str,
    format: str = "png",
    force_refresh: bool = False
) -> Dict[str, any]:
    """
    Download email image for a scholar using the data-proxy API.

    Returns:
        Dictionary with status information:
        - success: bool
        - status_code: int
        - message: str
        - image_path: Path (if success)
    """
    # Check cache first (unless force refresh)
    if not force_refresh:
        cached_result, cache_status = get_cached_email_image(aminer_id)
        if cache_status == "no_email":
            return {
                "success": False,
                "status_code": 404,
                "message": "No email (cached)"
            }
        elif cache_status == "exists":
            return {
                "success": True,
                "status_code": 200,
                "message": "Already cached",
                "image_path": cached_result
            }

    # Download from API
    endpoint = f"{api_url}/api/aminer/scholar/email"
    params = {
        "id": aminer_id,
        "format": format,
        "force_refresh": str(force_refresh).lower()
    }
    headers = {
        "Authorization": authorization,
        "X-Signature": x_signature,
        "X-Timestamp": x_timestamp
    }

    try:
        response = client.get(endpoint, params=params, headers=headers, timeout=60.0)

        if response.status_code == 200:
            # Save to cache
            EMAIL_IMG_DIR.mkdir(parents=True, exist_ok=True)
            ext = '.png' if format.lower() == 'png' else '.jpg'
            image_path = EMAIL_IMG_DIR / f"{aminer_id}{ext}"

            with open(image_path, 'wb') as f:
                f.write(response.content)

            return {
                "success": True,
                "status_code": 200,
                "message": "Downloaded",
                "image_path": image_path
            }
        elif response.status_code == 404:
            # No email available - create marker
            EMAIL_IMG_DIR.mkdir(parents=True, exist_ok=True)
            no_email_marker = EMAIL_IMG_DIR / f"{aminer_id}.no_email"
            no_email_marker.touch()

            return {
                "success": False,
                "status_code": 404,
                "message": "No email available"
            }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "message": f"HTTP {response.status_code}"
            }

    except httpx.TimeoutException:
        return {
            "success": False,
            "status_code": 504,
            "message": "Timeout"
        }
    except Exception as e:
        return {
            "success": False,
            "status_code": 0,
            "message": f"Error: {str(e)}"
        }


def recognize_email_with_ocr(
    client: httpx.Client,
    image_path: Path,
    ocr_api_url: str,
    ocr_token: str
) -> Dict[str, any]:
    """
    Recognize email text from image using PaddleOCR VL model.

    Returns:
        Dictionary with:
        - success: bool
        - text: str (raw OCR text)
        - emails: List[str] (extracted email addresses)
        - message: str
    """
    try:
        # Read and encode image
        with open(image_path, 'rb') as f:
            image_bytes = f.read()

        image_base64 = base64.b64encode(image_bytes).decode('ascii')

        # Prepare request
        headers = {
            "Authorization": f"token {ocr_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "file": image_base64,
            "fileType": 1,  # Image
            "useDocOrientationClassify": False,  # Disable rotation detection
            "useDocUnwarping": False,
            "useChartRecognition": False
        }

        # Send request
        response = client.post(ocr_api_url, json=payload, headers=headers, timeout=60.0)

        if response.status_code != 200:
            return {
                "success": False,
                "text": "",
                "emails": [],
                "message": f"OCR API error: HTTP {response.status_code}"
            }

        # Parse response
        result = response.json()["result"]
        layout_results = result.get("layoutParsingResults", [])

        if not layout_results:
            return {
                "success": False,
                "text": "",
                "emails": [],
                "message": "No OCR results"
            }

        # Extract text
        markdown_text = layout_results[0].get("markdown", {}).get("text", "")

        if not markdown_text:
            return {
                "success": False,
                "text": "",
                "emails": [],
                "message": "Empty OCR result"
            }

        # Clean and normalize text
        cleaned_text = normalize_email_text(markdown_text)

        # Extract email addresses
        emails = extract_emails(cleaned_text)

        if not emails:
            return {
                "success": False,
                "text": cleaned_text,
                "emails": [],
                "message": "No email addresses found in text"
            }

        return {
            "success": True,
            "text": cleaned_text,
            "emails": emails,
            "message": f"Found {len(emails)} email(s)"
        }

    except httpx.TimeoutException:
        return {
            "success": False,
            "text": "",
            "emails": [],
            "message": "OCR timeout"
        }
    except Exception as e:
        return {
            "success": False,
            "text": "",
            "emails": [],
            "message": f"OCR error: {str(e)}"
        }


def recognize_email_with_qwen3_vl(
    image_path: Path,
    api_key: str,
    scholar_info: Optional[Dict] = None
) -> Dict[str, any]:
    """
    Recognize email text from image using Qwen3-VL-Plus model (fallback method).

    Args:
        image_path: Path to the email image
        api_key: Dashscope API key
        scholar_info: Optional dict with scholar's name, orgs, etc. for context

    Returns:
        Dictionary with:
        - success: bool
        - text: str (raw recognized text)
        - emails: List[str] (extracted email addresses)
        - message: str
    """
    try:
        from openai import OpenAI

        # Read and encode image to base64
        with open(image_path, 'rb') as f:
            image_bytes = f.read()

        image_base64 = base64.b64encode(image_bytes).decode('utf-8')

        # Determine MIME type
        if image_path.suffix.lower() == '.png':
            mime_type = 'image/png'
        elif image_path.suffix.lower() in ['.jpg', '.jpeg']:
            mime_type = 'image/jpeg'
        else:
            mime_type = 'image/png'

        image_data_url = f"data:{mime_type};base64,{image_base64}"

        # Create OpenAI client with Aliyun endpoint
        client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )

        # Build context information
        context_info = ""
        if scholar_info:
            context_parts = []

            # Add name
            if scholar_info.get('name'):
                name_part = f"学者姓名：{scholar_info['name']}"
                if scholar_info.get('name_zh'):
                    name_part += f"（{scholar_info['name_zh']}）"
                context_parts.append(name_part)

            # Add organizations
            if scholar_info.get('orgs'):
                orgs_text = "；".join(scholar_info['orgs'])
                context_parts.append(f"所属机构：{orgs_text}")

            # Add position
            if scholar_info.get('position'):
                context_parts.append(f"职位：{scholar_info['position']}")

            if context_parts:
                context_info = "\n\n背景信息（仅供参考，用于推断邮箱地址的合理性）：\n" + "\n".join(context_parts) + "\n"

        # Improved prompt for better accuracy
        improved_prompt = f"""请仔细识别这张图片中的英文邮箱地址。
{context_info}
要求：
1. 仔细观察图片中的每个字符，特别注意容易混淆的字符（如 l 和 i、0 和 O、1 和 l、t 和 f 等）
2. 识别所有的邮箱地址，多个邮箱地址用英文分号（;）分隔
3. 验证每个邮箱地址的格式是否正确（格式：username@domain）
4. 特别注意域名部分的拼写，确保常见的大学、公司域名拼写正确（如 tsinghua、rutgers、microsoft、gmail、ust.hk 等）
5. 邮箱的用户名部分通常与学者姓名相关（如姓名缩写、全拼等），请结合背景信息验证合理性
6. 逐个检查识别结果，确认每个字符是否准确
7. 如果某个字符不太清晰，请根据背景信息、上下文和常见邮箱格式推断

请先思考识别过程，然后在最后一行输出最终的识别结果（只输出邮箱地址，不要包含任何其他解释）。"""

        # Call Qwen3-VL-Plus API
        completion = client.chat.completions.create(
            model="qwen3-vl-plus",
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": image_data_url}
                    },
                    {
                        "type": "text",
                        "text": improved_prompt
                    }
                ]
            }],
            temperature=0.1,  # Lower temperature for more deterministic output
            timeout=60.0
        )

        # Get response
        raw_text = completion.choices[0].message.content

        if not raw_text:
            return {
                "success": False,
                "text": "",
                "emails": [],
                "message": "Empty response from Qwen3-VL"
            }

        # Extract the last line as the final result
        lines = raw_text.strip().split('\n')
        final_line = lines[-1].strip()

        # Clean and normalize the final line
        cleaned_text = normalize_email_text(final_line)

        # Extract email addresses
        emails = extract_emails(cleaned_text)

        if not emails:
            return {
                "success": False,
                "text": cleaned_text,
                "emails": [],
                "message": "No email addresses found in Qwen3-VL output"
            }

        return {
            "success": True,
            "text": cleaned_text,
            "emails": emails,
            "message": f"Found {len(emails)} email(s) with Qwen3-VL"
        }

    except ImportError:
        return {
            "success": False,
            "text": "",
            "emails": [],
            "message": "OpenAI package not installed (required for Qwen3-VL)"
        }
    except Exception as e:
        return {
            "success": False,
            "text": "",
            "emails": [],
            "message": f"Qwen3-VL error: {str(e)}"
        }


def normalize_email_text(text: str) -> str:
    """
    Normalize OCR text to fix common recognition issues.

    Common issues:
    - Chinese punctuation: ； → ;  ， → ,  。 → .
    - Extra spaces
    - Line breaks
    """
    # Replace Chinese punctuation with English equivalents
    replacements = {
        '；': ';',
        '，': ',',
        '。': '.',
        '：': ':',
        '（': '(',
        '）': ')',
        '【': '[',
        '】': ']',
        '｀': '`',
        '＠': '@',  # Full-width @ to ASCII @
    }

    for chinese, english in replacements.items():
        text = text.replace(chinese, english)

    # Remove line breaks and extra spaces
    text = ' '.join(text.split())

    return text


def extract_emails(text: str) -> List[str]:
    """
    Extract email addresses from text.

    Handles:
    - Multiple emails separated by ; , or space
    - Validation of email format

    Note: All emails matching the pattern are extracted, including those with
    anti-spam text like "removethisifyouarehuman". Filtering should be done
    in post-processing if needed.
    """
    # Email regex pattern
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

    # Find all potential emails
    potential_emails = re.findall(email_pattern, text)

    # Remove duplicates while preserving order
    seen = set()
    unique_emails = []
    for email in potential_emails:
        if email.lower() not in seen:
            seen.add(email.lower())
            unique_emails.append(email)

    return unique_emails


def format_size(bytes_size: int) -> str:
    """Format bytes size to human readable string."""
    for unit in ['B', 'KB', 'MB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.0f}{unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.0f}GB"


def format_time(seconds: float) -> str:
    """Format seconds to human readable time."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Fetch and recognize scholar email addresses using OCR",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--ids",
        nargs="+",
        help="Specific AMiner IDs to process (for testing)"
    )
    parser.add_argument(
        "--api-url",
        default=DEFAULT_DATA_PROXY_URL,
        help=f"Data-proxy API URL (default: {DEFAULT_DATA_PROXY_URL})"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=f"Delay between requests in seconds (default: {DEFAULT_DELAY})"
    )
    parser.add_argument(
        "--ocr-delay",
        type=float,
        default=DEFAULT_OCR_DELAY,
        help=f"Delay for OCR requests in seconds (default: {DEFAULT_OCR_DELAY})"
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force refresh cached images"
    )
    parser.add_argument(
        "--format",
        choices=["png", "jpg"],
        default="png",
        help="Image format to download (default: png, smaller file size)"
    )
    parser.add_argument(
        "--aminer-auth",
        default="",
        help="AMiner authorization token (required for API)"
    )
    parser.add_argument(
        "--aminer-signature",
        default="",
        help="AMiner X-Signature (required for API)"
    )
    parser.add_argument(
        "--aminer-timestamp",
        default="",
        help="AMiner X-Timestamp (required for API)"
    )

    args = parser.parse_args()

    # Load configuration from environment variables
    import os
    global PADDLE_OCR_API_URL, PADDLE_OCR_TOKEN, DASHSCOPE_API_KEY

    PADDLE_OCR_API_URL = os.environ.get("PADDLE_OCR_API_URL")
    PADDLE_OCR_TOKEN = os.environ.get("PADDLE_OCR_TOKEN")
    DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY")

    if not PADDLE_OCR_API_URL or not PADDLE_OCR_TOKEN:
        print("Error: PaddleOCR API credentials required")
        print()
        print("Please set the following environment variables:")
        print("  export PADDLE_OCR_API_URL='https://h0y2i794u98027ue.aistudio-app.com/layout-parsing'")
        print("  export PADDLE_OCR_TOKEN='your_token'")
        print()
        sys.exit(1)

    # Qwen3-VL is optional (fallback)
    if DASHSCOPE_API_KEY:
        print("Info: Qwen3-VL-Plus fallback is enabled (DASHSCOPE_API_KEY found)")
    else:
        print("Info: Qwen3-VL-Plus fallback is disabled (DASHSCOPE_API_KEY not set)")

    # Load AMiner credentials from environment variables if not provided via command line
    if not args.aminer_auth:
        args.aminer_auth = os.environ.get("AMINER_AUTH", "")
    if not args.aminer_signature:
        args.aminer_signature = os.environ.get("AMINER_SIGNATURE", "")
    if not args.aminer_timestamp:
        args.aminer_timestamp = os.environ.get("AMINER_TIMESTAMP", "")

    # Check required AMiner credentials
    if not all([args.aminer_auth, args.aminer_signature, args.aminer_timestamp]):
        print("Error: AMiner API credentials required")
        print()
        print("Please provide credentials via command line or environment variables:")
        print()
        print("Option 1 - Command line:")
        print("  python fetch_email_addresses.py \\")
        print("    --aminer-auth 'YOUR_TOKEN' \\")
        print("    --aminer-signature 'YOUR_SIGNATURE' \\")
        print("    --aminer-timestamp 'YOUR_TIMESTAMP'")
        print()
        print("Option 2 - Environment variables:")
        print("  export AMINER_AUTH='YOUR_TOKEN'")
        print("  export AMINER_SIGNATURE='YOUR_SIGNATURE'")
        print("  export AMINER_TIMESTAMP='YOUR_TIMESTAMP'")
        print()
        sys.exit(1)

    # Load scholar IDs
    if args.ids:
        # Test mode: specific IDs
        scholars = [(aminer_id, 0) for aminer_id in args.ids]
        print(f"Testing with {len(scholars)} specified scholars")
    else:
        # Production mode: all scholars sorted by citations
        print("Loading scholars from authors.json...")
        scholars = load_sorted_scholar_ids()
        print(f"Found {len(scholars)} scholars (sorted by citations, high to low)")

    if not scholars:
        print("No scholars to process")
        return

    # Statistics
    stats = {
        "total": len(scholars),
        "skipped_has_email": 0,
        "skipped_no_email": 0,
        "skipped_cached": 0,
        "download_success": 0,
        "download_failed": 0,
        "ocr_success": 0,
        "ocr_failed": 0,
        "saved": 0,
        "errors": 0
    }

    start_time = time.time()

    # Create HTTP clients
    with httpx.Client() as client:
        for i, (aminer_id, n_citation) in enumerate(scholars, 1):
            # Progress
            progress = (i / stats["total"]) * 100
            citation_info = f"(citations: {n_citation})" if n_citation > 0 else ""
            print(f"\n[{i}/{stats['total']} ({progress:.1f}%)] {aminer_id} {citation_info}")

            # Check if already has email in enriched data
            if has_email_in_enriched(aminer_id):
                print(f"  ⊙ Skipped: Already has email in enriched data")
                stats["skipped_has_email"] += 1
                continue

            # Load scholar data for context (used in Qwen3-VL fallback)
            scholar_info = load_scholar_data(aminer_id)

            # Step 1: Download email image
            print(f"  [1/3] Downloading email image...")
            download_result = download_email_image(
                client, args.api_url, aminer_id,
                args.aminer_auth, args.aminer_signature, args.aminer_timestamp,
                format=args.format,
                force_refresh=args.force_refresh
            )

            if not download_result["success"]:
                if download_result["status_code"] == 404:
                    # First attempt returned no_email, wait and retry with force_refresh
                    print(f"      ⊘ {download_result['message']} - retrying in 10s...")
                    time.sleep(10)

                    print(f"      [Retry] Downloading with force_refresh...")
                    retry_result = download_email_image(
                        client, args.api_url, aminer_id,
                        args.aminer_auth, args.aminer_signature, args.aminer_timestamp,
                        format=args.format,
                        force_refresh=True
                    )

                    if not retry_result["success"]:
                        if retry_result["status_code"] == 404:
                            print(f"      ⊘ {retry_result['message']} (after retry)")
                            stats["skipped_no_email"] += 1
                        else:
                            print(f"      ✗ {retry_result['message']} (after retry)")
                            stats["download_failed"] += 1
                        continue
                    else:
                        # Retry succeeded, update download_result and continue processing
                        download_result = retry_result
                else:
                    print(f"      ✗ {download_result['message']}")
                    stats["download_failed"] += 1
                    continue

            # Download succeeded (either first attempt or after retry)
            image_path = download_result["image_path"]
            print(f"      ✓ {download_result['message']}: {image_path.name}")

            if download_result["message"] == "Already cached":
                stats["skipped_cached"] += 1
            else:
                stats["download_success"] += 1

            # Step 2: OCR recognition
            print(f"  [2/3] Recognizing email with OCR...")
            ocr_result = recognize_email_with_ocr(
                client, image_path, PADDLE_OCR_API_URL, PADDLE_OCR_TOKEN
            )

            if not ocr_result["success"]:
                print(f"      ✗ {ocr_result['message']}")
                if ocr_result["text"]:
                    print(f"      Raw text: {ocr_result['text']}")

                # Try fallback: Qwen3-VL-Plus
                if DASHSCOPE_API_KEY:
                    print(f"      [Fallback] Trying Qwen3-VL-Plus...")
                    qwen_result = recognize_email_with_qwen3_vl(
                        image_path, DASHSCOPE_API_KEY, scholar_info
                    )

                    if qwen_result["success"]:
                        # Qwen3-VL succeeded, use its result
                        print(f"      ✓ {qwen_result['message']}")
                        print(f"      Text: {qwen_result['text']}")
                        print(f"      Emails: {', '.join(qwen_result['emails'])}")
                        ocr_result = qwen_result  # Replace with Qwen result
                        stats["ocr_success"] += 1
                    else:
                        print(f"      ✗ {qwen_result['message']}")
                        stats["ocr_failed"] += 1
                        time.sleep(args.ocr_delay)
                        continue
                else:
                    # No fallback available
                    stats["ocr_failed"] += 1
                    time.sleep(args.ocr_delay)
                    continue
            else:
                print(f"      ✓ {ocr_result['message']}")
                print(f"      Text: {ocr_result['text']}")
                print(f"      Emails: {', '.join(ocr_result['emails'])}")
                stats["ocr_success"] += 1

            # Step 3: Save to enriched data
            print(f"  [3/3] Saving to enriched data...")

            # Load existing enriched data or create new
            enriched_data = load_enriched_data(aminer_id) or {
                "aminer_id": aminer_id
            }

            # Update email field (join multiple emails with semicolon)
            enriched_data["email"] = "; ".join(ocr_result["emails"])
            enriched_data["last_updated"] = datetime.now(timezone.utc).isoformat()

            if save_enriched_data(aminer_id, enriched_data):
                print(f"      ✓ Saved to {ENRICHED_DIR}/{aminer_id}.json")
                stats["saved"] += 1
            else:
                print(f"      ✗ Failed to save")
                stats["errors"] += 1

            # Delay before next request
            if i < stats["total"]:
                time.sleep(args.ocr_delay)

    # Summary
    elapsed_time = time.time() - start_time
    print("\n" + "=" * 70)
    print("Summary:")
    print(f"  Total scholars:          {stats['total']}")
    print(f"  Skipped (has email):     {stats['skipped_has_email']}")
    print(f"  Skipped (no email):      {stats['skipped_no_email']}")
    print(f"  Skipped (cached):        {stats['skipped_cached']}")
    print(f"  Downloaded:              {stats['download_success']}")
    print(f"  Download failed:         {stats['download_failed']}")
    print(f"  OCR success:             {stats['ocr_success']}")
    print(f"  OCR failed:              {stats['ocr_failed']}")
    print(f"  Saved to enriched:       {stats['saved']}")
    print(f"  Errors:                  {stats['errors']}")
    print(f"  Time elapsed:            {format_time(elapsed_time)}")
    if stats["ocr_success"] > 0:
        print(f"  Avg time/scholar:        {elapsed_time/(stats['ocr_success']):.1f}s")
    print("=" * 70)


if __name__ == "__main__":
    main()
