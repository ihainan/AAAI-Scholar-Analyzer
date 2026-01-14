"""
AMiner API service for fetching and converting scholar data.
"""

import json
import logging
import uuid
from typing import Optional

import httpx
from fastapi import HTTPException

from config import settings
from services.cache_service import (
    get_cache_path,
    get_cache_stats,
    is_cache_valid,
    read_json_cache,
    write_json_cache,
)
from utils.http_client import http_client

logger = logging.getLogger(__name__)


async def fetch_aminer_web_api(
    scholar_id: str,
    authorization: str,
    x_signature: str,
    x_timestamp: str
) -> dict:
    """
    Fetch scholar data from AMiner web API with automatic retry.

    Args:
        scholar_id: AMiner scholar ID
        authorization: Authorization token from header
        x_signature: X-Signature from header
        x_timestamp: X-Timestamp from header

    Returns:
        Raw API response from AMiner web API

    Raises:
        HTTPException: If API request fails after all retry attempts
    """
    import asyncio

    url = "https://apiv2.aminer.cn/magic?a=getPerson__personapi.get___"

    headers = {
        "Accept": "application/json, text/plain, */*",
        "Authorization": authorization,
        "Content-Type": "application/json",
        "X-Signature": x_signature,
        "X-Timestamp": x_timestamp,
    }

    payload = [{
        "action": "personapi.get",
        "parameters": {"ids": [scholar_id]},
        "schema": {
            "person": [
                "id", "name", "name_zh", "avatar", "num_view", "is_follow",
                "work", "work_zh", "hide", "nation", "language", "bind",
                "acm_citations", "links", "educations", "tags", "tags_zh",
                "num_view", "num_follow", "is_upvoted", "num_upvoted",
                "is_downvoted", "is_lock",
                {"indices": ["hindex", "gindex", "pubs", "citations", "newStar", "risingStar", "activity", "diversity", "sociability"]},
                {"profile": ["position", "position_zh", "affiliation", "affiliation_zh", "work", "work_zh", "gender", "lang", "homepage", "phone", "email", "fax", "bio", "bio_zh", "edu", "edu_zh", "address", "note", "homepage", "title", "titles"]}
            ]
        }
    }]

    # Retry configuration
    max_attempts = 2  # Try once, retry once
    retry_delay = 5   # 5 seconds delay before retry

    for attempt in range(1, max_attempts + 1):
        try:
            if attempt > 1:
                logger.warning(f"[AMiner API] Retry attempt {attempt - 1}/{max_attempts - 1} for scholar {scholar_id}")
            else:
                logger.info(f"[AMiner API] Fetching scholar data for ID: {scholar_id}")

            logger.debug(f"[AMiner API] Request URL: {url}")
            logger.debug(f"[AMiner API] Request payload: {json.dumps(payload, ensure_ascii=False)}")

            response = await http_client.post(url, json=payload, headers=headers)
            response.raise_for_status()

            result = response.json()
            logger.info(f"[AMiner API] Successfully fetched data for scholar {scholar_id} (attempt {attempt})")
            logger.debug(f"[AMiner API] Full response: {json.dumps(result, ensure_ascii=False, indent=2)}")

            return result

        except httpx.HTTPError as e:
            if attempt < max_attempts:
                logger.warning(
                    f"[AMiner API] Request failed for scholar {scholar_id} (attempt {attempt}/{max_attempts}), "
                    f"retrying in {retry_delay}s... Error: {str(e)}"
                )
                await asyncio.sleep(retry_delay)
            else:
                # All attempts exhausted
                logger.error(f"[AMiner API] Failed to fetch scholar {scholar_id} after {max_attempts} attempts: {str(e)}")
                raise HTTPException(
                    status_code=502,
                    detail=f"Failed to fetch from AMiner API after {max_attempts} attempts: {str(e)}"
                )

    # This should never be reached, but just in case
    raise HTTPException(status_code=502, detail=f"Unexpected error fetching scholar {scholar_id}")


def convert_web_api_to_official_format(web_response: dict) -> dict:
    """
    Convert AMiner web API response to official API format.

    Args:
        web_response: Raw response from AMiner web API

    Returns:
        Response in official API format

    Raises:
        HTTPException: If response format is invalid
    """
    try:
        data = web_response["data"][0]["data"][0]
    except (KeyError, IndexError, TypeError):
        raise HTTPException(status_code=500, detail="Invalid AMiner API response format")

    profile = data.get("profile", {})

    return {
        "code": 200,
        "success": True,
        "msg": "",
        "data": {
            # Basic info
            "id": data.get("id", ""),
            "name": data.get("name", ""),
            "name_zh": data.get("name_zh", ""),

            # Bio and education
            "bio": profile.get("bio", ""),
            "bio_zh": profile.get("bio_zh", ""),
            "edu": profile.get("edu", ""),
            "edu_zh": profile.get("edu_zh", ""),

            # Position and organization
            "position": profile.get("position", ""),
            "position_zh": profile.get("position_zh", ""),
            "orgs": [profile.get("affiliation")] if profile.get("affiliation") else [],
            "org_zhs": [profile.get("org_zh")] if profile.get("org_zh") else [],

            # Missing fields (return empty values)
            "honor": [],
            "award": "",
            "create_time": "",
            "update_time": "",
            "year": None,
            "domain": "",
            "person_id": data.get("id", ""),
        },
        "log_id": f"custom_{uuid.uuid4().hex[:16]}"
    }


def extract_enriched_fields(web_response: dict) -> dict:
    """
    Extract enriched fields from AMiner web API response.

    Args:
        web_response: Raw response from AMiner web API

    Returns:
        Dictionary with enriched fields
    """
    try:
        data = web_response["data"][0]["data"][0]
    except (KeyError, IndexError, TypeError):
        return {}

    profile = data.get("profile", {})
    links = data.get("links", {})
    enriched = {}

    # External links
    if links.get("gs", {}).get("url"):
        enriched["google_scholar"] = links["gs"]["url"]

    # DBLP link
    for resource in links.get("resource", {}).get("resource_link", []):
        if resource.get("id") == "dblp" and resource.get("url"):
            enriched["dblp"] = resource["url"]

    # Contact info
    if profile.get("homepage"):
        enriched["homepage"] = profile["homepage"]

    if profile.get("phone"):
        enriched["phone"] = profile["phone"]

    # AMiner avatar
    if data.get("avatar"):
        enriched["avatar_aminer"] = data["avatar"]

    # Academic indices
    if data.get("indices"):
        indices_data = data["indices"]
        enriched["indices"] = {
            "hindex": indices_data.get("hindex"),
            "gindex": indices_data.get("gindex"),
            "citations": indices_data.get("citations"),
            "pubs": indices_data.get("pubs"),
            "activity": indices_data.get("activity"),
            "diversity": indices_data.get("diversity"),
            "sociability": indices_data.get("sociability"),
            "newStar": indices_data.get("newStar"),
            "risingStar": indices_data.get("risingStar"),
        }

    # Research tags
    if data.get("tags"):
        enriched["research_tags"] = data["tags"][:10]

    if data.get("tags_score"):
        enriched["research_tags_scores"] = data["tags_score"][:10]

    # AMiner stats
    enriched["aminer_stats"] = {
        "num_viewed": data.get("num_viewed", 0),
        "num_followed": data.get("num_followed", 0),
        "num_upvoted": data.get("num_upvoted", 0),
    }

    # Other contact info
    if profile.get("address"):
        enriched["address"] = profile["address"]

    if profile.get("fax"):
        enriched["fax"] = profile["fax"]

    return enriched


async def get_scholar_detail(
    scholar_id: str,
    authorization: str,
    x_signature: str,
    x_timestamp: str,
    force_refresh: bool = False
) -> dict:
    """
    Get scholar detail from AMiner web API with caching.

    Args:
        scholar_id: AMiner scholar ID
        authorization: Authorization token
        x_signature: Request signature
        x_timestamp: Request timestamp
        force_refresh: Force refresh cache

    Returns:
        Scholar detail in official API format

    Raises:
        HTTPException: If request fails
    """
    logger.info(f"[Scholar Detail] Request for ID: {scholar_id}, Force Refresh: {force_refresh}")

    # Check cache
    cache_path = get_cache_path(settings.aminer_cache_dir, scholar_id)
    cache_stats = get_cache_stats(cache_path)

    if not force_refresh and cache_stats["exists"] and is_cache_valid(cache_path, settings.aminer_cache_ttl):
        # Return cached response
        logger.info(f"[Cache] HIT for scholar {scholar_id} - Age: {cache_stats['age_days']:.1f} days ({cache_stats['age_hours']:.1f} hours)")
        logger.info(f"[Cache] Returning cached data from: {cache_path}")

        cached_data = read_json_cache(cache_path)
        if cached_data:
            logger.debug(f"[Cache] Cached response: {json.dumps(cached_data, ensure_ascii=False, indent=2)}")
            return cached_data
        else:
            logger.error(f"[Cache] Failed to read cache for {scholar_id}")
            logger.info(f"[Cache] Falling back to fetching fresh data")
    else:
        if force_refresh:
            logger.info(f"[Cache] Force refresh requested for scholar {scholar_id}")
        elif not cache_stats["exists"]:
            logger.info(f"[Cache] MISS for scholar {scholar_id} - No cache file found")
        else:
            logger.info(f"[Cache] EXPIRED for scholar {scholar_id} - Age: {cache_stats['age_days']:.1f} days (TTL: 15 days)")

    # Fetch from AMiner web API
    logger.info(f"[Data Source] Fetching fresh data from AMiner web API for scholar {scholar_id}")
    web_response = await fetch_aminer_web_api(scholar_id, authorization, x_signature, x_timestamp)

    logger.info(f"[Data Processing] Converting web API response to official format")
    logger.debug(f"[Data Processing] Raw web API response: {json.dumps(web_response, ensure_ascii=False, indent=2)}")

    # Check if AMiner API returned an error
    if "data" in web_response and len(web_response["data"]) > 0:
        first_item = web_response["data"][0]
        if first_item.get("succeed") is False:
            error_code = first_item.get("code", "unknown")
            error_context = first_item.get("meta", {}).get("context", "")
            logger.error(f"[AMiner API] Request failed - Code: {error_code}, Context: {error_context}")
            raise HTTPException(
                status_code=404,
                detail=f"AMiner API error: Scholar not found or unavailable (code: {error_code})"
            )

    # Convert to official format
    official_response = convert_web_api_to_official_format(web_response)

    # Add enriched fields
    enriched_fields = extract_enriched_fields(web_response)
    if enriched_fields:
        logger.info(f"[Data Processing] Extracted {len(enriched_fields)} enriched fields")
        logger.debug(f"[Data Processing] Enriched fields: {json.dumps(enriched_fields, ensure_ascii=False, indent=2)}")
        official_response["enriched"] = enriched_fields

    # Cache the response
    if write_json_cache(cache_path, official_response):
        logger.info(f"[Cache] Cached response for scholar {scholar_id} to: {cache_path}")
    else:
        logger.error(f"[Cache] Failed to cache response for {scholar_id}")

    logger.info(f"[API Response] Successfully processed scholar {scholar_id}")
    return official_response
