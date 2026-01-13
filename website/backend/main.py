"""
Conference API Server

Provides endpoints for:
- Conference list
- Conference scholars list
- Scholar details
- Avatar proxy with caching
"""

import hashlib
import json
import os
import uuid
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
import logging

import httpx
from fastapi import FastAPI, HTTPException, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Conference API", version="0.1.0")

# CORS configuration - allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data directory path (configurable via environment variable)
DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).parent.parent.parent / "data"))
AMINER_SCHOLARS_DIR = DATA_DIR / "aminer" / "scholars"
ENRICHED_SCHOLARS_DIR = DATA_DIR / "enriched" / "scholars"

# Config directory path
CONFIG_DIR = Path(os.environ.get("CONFIG_DIR", Path(__file__).parent.parent.parent / "config"))
LABELS_CONFIG_PATH = CONFIG_DIR / "labels.json"

# Avatar cache directory (writable, separate from read-only data)
AVATAR_CACHE_DIR = Path(os.environ.get("AVATAR_CACHE_DIR", Path(__file__).parent / "avatar_cache"))
AVATAR_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# AMiner Web API cache directory (for scholar detail from web API)
AMINER_WEB_API_CACHE_DIR = Path(os.environ.get("AMINER_WEB_API_CACHE_DIR", Path(__file__).parent / "aminer_web_api_cache"))
AMINER_WEB_API_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# AMiner Web API cache TTL (15 days in seconds)
AMINER_WEB_API_CACHE_TTL = 15 * 24 * 60 * 60

# HTTP client for fetching remote avatars (shorter timeout to avoid slow responses)
http_client = httpx.AsyncClient(timeout=5.0, follow_redirects=True)

# Failed avatar fetch cache (to avoid retrying failed URLs)
AVATAR_FAIL_CACHE_TTL = 3600  # 1 hour before retrying failed URLs

# Cache timeout tracking
_cache_timestamp: dict[str, float] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes


def get_cache_key(func_name: str, *args) -> str:
    """Generate a cache key for function calls."""
    return f"{func_name}:{':'.join(str(a) for a in args)}"


def is_cache_valid(key: str) -> bool:
    """Check if cache entry is still valid."""
    if key not in _cache_timestamp:
        return False
    return (datetime.now().timestamp() - _cache_timestamp[key]) < CACHE_TTL_SECONDS


def update_cache_timestamp(key: str):
    """Update cache timestamp."""
    _cache_timestamp[key] = datetime.now().timestamp()


@lru_cache(maxsize=128)
def _load_json_file(file_path: str) -> dict:
    """Load and cache a JSON file."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_json_file(file_path: str) -> dict:
    """Load a JSON file with cache validation."""
    cache_key = get_cache_key("load_json", file_path)
    if not is_cache_valid(cache_key):
        _load_json_file.cache_clear()
    update_cache_timestamp(cache_key)
    return _load_json_file(file_path)


def get_aminer_avatar_url(aminer_id: str) -> str:
    """Generate AMiner avatar URL."""
    return f"https://static.aminer.cn/upload/avatar/{aminer_id}.jpg"


def get_avatar_cache_path(url: str) -> Path:
    """Generate cache file path for a given URL."""
    url_hash = hashlib.md5(url.encode()).hexdigest()
    # Extract extension from URL, default to .jpg
    parsed = urlparse(url)
    ext = Path(parsed.path).suffix or ".jpg"
    return AVATAR_CACHE_DIR / f"{url_hash}{ext}"


def get_avatar_fail_marker_path(url: str) -> Path:
    """Generate fail marker file path for a given URL."""
    url_hash = hashlib.md5(url.encode()).hexdigest()
    return AVATAR_CACHE_DIR / f"{url_hash}.failed"


def is_avatar_fetch_failed(url: str) -> bool:
    """Check if avatar fetch has failed recently (within TTL)."""
    fail_marker = get_avatar_fail_marker_path(url)
    if not fail_marker.exists():
        return False
    # Check if marker is expired
    marker_age = datetime.now().timestamp() - fail_marker.stat().st_mtime
    if marker_age > AVATAR_FAIL_CACHE_TTL:
        fail_marker.unlink()  # Remove expired marker
        return False
    return True


def mark_avatar_fetch_failed(url: str):
    """Mark avatar fetch as failed."""
    fail_marker = get_avatar_fail_marker_path(url)
    fail_marker.touch()


def get_scholar_photo_url(aminer_id: Optional[str]) -> Optional[str]:
    """
    Get the original photo URL for a scholar.
    Priority: enriched photo_url > AMiner avatar > None
    """
    if not aminer_id:
        return None

    # Check enriched data for photo_url first
    enriched_path = ENRICHED_SCHOLARS_DIR / f"{aminer_id}.json"
    if enriched_path.exists():
        try:
            enriched_data = load_json_file(str(enriched_path))
            if enriched_data.get("photo_url"):
                return enriched_data["photo_url"]
        except Exception:
            pass

    # Fall back to AMiner avatar
    return get_aminer_avatar_url(aminer_id)


def get_scholar_photo(aminer_id: Optional[str]) -> Optional[str]:
    """
    Get scholar photo URL (proxied through our API for caching).
    Returns the proxy URL that will cache and serve the avatar.
    """
    if not aminer_id:
        return None

    # Return proxy URL - frontend will request this, and we'll cache the avatar
    return f"/api/avatar/{aminer_id}"


# ============== Pydantic Models ==============

class ConferenceLocation(BaseModel):
    venue: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None


class ConferenceDates(BaseModel):
    start: Optional[str] = None
    end: Optional[str] = None


class ConferenceUrl(BaseModel):
    url: str
    name: Optional[str] = None
    description: Optional[str] = None


class ConferenceMeta(BaseModel):
    id: str  # directory name as ID
    name: str
    shortName: Optional[str] = None
    edition: Optional[int] = None
    year: Optional[int] = None
    dates: Optional[ConferenceDates] = None
    location: Optional[ConferenceLocation] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    urls: Optional[list[ConferenceUrl]] = None
    timezone: Optional[str] = None
    tags: Optional[list[str]] = None


class ScholarBasic(BaseModel):
    name: str
    affiliation: Optional[str] = None
    roles: list[str] = []
    aminer_id: Optional[str] = None
    photo_url: Optional[str] = None
    description: Optional[str] = None


class AminerValidation(BaseModel):
    status: Optional[str] = None
    is_same_person: Optional[bool] = None
    reason: Optional[str] = None


# Labels related models
class LabelResult(BaseModel):
    name: str
    value: Optional[bool] = None
    confidence: Optional[str] = None
    reason: Optional[str] = None


class ScholarLabels(BaseModel):
    last_updated: Optional[str] = None
    results: list[LabelResult] = []


class LabelDefinition(BaseModel):
    name: str
    description: str


class LabelsConfig(BaseModel):
    version: str
    labels: list[LabelDefinition]


class ScholarDetail(BaseModel):
    # Basic info from scholars.json
    name: str
    aliases: Optional[list[str]] = None
    affiliation: Optional[str] = None
    roles: list[str] = []
    description: Optional[str] = None
    sources: Optional[list[str]] = None
    source_urls: Optional[list[str]] = None
    aminer_id: Optional[str] = None
    aminer_validation: Optional[AminerValidation] = None
    photo_url: Optional[str] = None

    # From AMiner data
    bio: Optional[str] = None
    education: Optional[str] = None
    position: Optional[str] = None
    organizations: Optional[list[str]] = None
    honors: Optional[list[dict]] = None
    research_interests: Optional[list[dict]] = None

    # From enriched data
    homepage: Optional[str] = None
    google_scholar: Optional[str] = None
    dblp: Optional[str] = None
    linkedin: Optional[str] = None
    twitter: Optional[str] = None
    email: Optional[str] = None
    orcid: Optional[str] = None
    semantic_scholar: Optional[str] = None
    additional_info: Optional[str] = None

    # Labels
    labels: Optional[ScholarLabels] = None


class HealthResponse(BaseModel):
    status: str
    timestamp: str


# ============== API Endpoints ==============

@app.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat()
    )


@app.get("/api/conferences", response_model=list[ConferenceMeta])
def get_conferences():
    """
    Get all conferences.
    Scans data directory for subdirectories containing meta.json.
    """
    conferences = []

    if not DATA_DIR.exists():
        raise HTTPException(status_code=500, detail=f"Data directory not found: {DATA_DIR}")

    for item in DATA_DIR.iterdir():
        if item.is_dir():
            meta_path = item / "meta.json"
            if meta_path.exists():
                try:
                    meta_data = load_json_file(str(meta_path))
                    meta_data["id"] = item.name
                    conferences.append(ConferenceMeta(**meta_data))
                except Exception as e:
                    print(f"Error loading {meta_path}: {e}")
                    continue

    return conferences


@app.get("/api/conferences/{conference_id}/scholars", response_model=list[ScholarBasic])
def get_conference_scholars(conference_id: str):
    """
    Get scholars for a specific conference.
    Returns list of scholars with basic info and photo URLs.
    """
    conference_dir = DATA_DIR / conference_id
    scholars_path = conference_dir / "scholars.json"

    if not conference_dir.exists():
        raise HTTPException(status_code=404, detail=f"Conference not found: {conference_id}")

    if not scholars_path.exists():
        raise HTTPException(status_code=404, detail=f"Scholars data not found for conference: {conference_id}")

    try:
        scholars_data = load_json_file(str(scholars_path))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading scholars data: {e}")

    # Handle both formats: { "talents": [...] } or { "metadata": {...}, "talents": [...] }
    talents = scholars_data.get("talents", [])

    scholars = []
    for talent in talents:
        aminer_id = talent.get("aminer_id")
        photo_url = get_scholar_photo(aminer_id)

        scholars.append(ScholarBasic(
            name=talent.get("name", "Unknown"),
            affiliation=talent.get("affiliation"),
            roles=talent.get("roles", []),
            aminer_id=aminer_id,
            photo_url=photo_url,
            description=talent.get("description"),
        ))

    return scholars


@app.get("/api/conferences/{conference_id}/scholars/search", response_model=list[ScholarDetail])
def search_scholars(
    conference_id: str,
    name: Optional[str] = Query(None, description="Scholar name to search"),
    aminer_id: Optional[str] = Query(None, description="AMiner ID to search"),
):
    """
    Search for scholars by name and/or aminer_id (OR logic).
    Returns detailed scholar information.
    """
    if not name and not aminer_id:
        raise HTTPException(status_code=400, detail="At least one of 'name' or 'aminer_id' must be provided")

    conference_dir = DATA_DIR / conference_id
    scholars_path = conference_dir / "scholars.json"

    if not conference_dir.exists():
        raise HTTPException(status_code=404, detail=f"Conference not found: {conference_id}")

    if not scholars_path.exists():
        raise HTTPException(status_code=404, detail=f"Scholars data not found for conference: {conference_id}")

    try:
        scholars_data = load_json_file(str(scholars_path))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading scholars data: {e}")

    talents = scholars_data.get("talents", [])

    # Filter by name OR aminer_id
    matching_talents = []
    for talent in talents:
        match = False
        if name and talent.get("name", "").lower() == name.lower():
            match = True
        if aminer_id and talent.get("aminer_id") == aminer_id:
            match = True
        if match:
            matching_talents.append(talent)

    # Build detailed response
    results = []
    for talent in matching_talents:
        scholar_aminer_id = talent.get("aminer_id")
        detail = build_scholar_detail(talent, scholar_aminer_id)
        results.append(detail)

    return results


def build_scholar_detail(talent: dict, aminer_id: Optional[str]) -> ScholarDetail:
    """Build detailed scholar information from multiple sources."""
    photo_url = get_scholar_photo(aminer_id)

    # Start with basic info
    detail = ScholarDetail(
        name=talent.get("name", "Unknown"),
        aliases=talent.get("aliases"),
        affiliation=talent.get("affiliation"),
        roles=talent.get("roles", []),
        description=talent.get("description"),
        sources=talent.get("sources"),
        source_urls=talent.get("source_urls"),
        aminer_id=aminer_id,
        photo_url=photo_url,
    )

    # Add aminer_validation if present
    if talent.get("aminer_validation"):
        detail.aminer_validation = AminerValidation(**talent["aminer_validation"])

    # Load AMiner data if available
    if aminer_id:
        aminer_path = AMINER_SCHOLARS_DIR / f"{aminer_id}.json"
        if aminer_path.exists():
            try:
                aminer_data = load_json_file(str(aminer_path))
                aminer_detail = aminer_data.get("detail", {})

                detail.bio = aminer_detail.get("bio")
                detail.education = aminer_detail.get("edu")
                detail.position = aminer_detail.get("position")
                detail.organizations = aminer_detail.get("orgs")
                detail.honors = aminer_detail.get("honor")

                # Research interests from figure
                figure = aminer_data.get("figure", {})
                detail.research_interests = figure.get("ai_interests")
            except Exception as e:
                print(f"Error loading AMiner data for {aminer_id}: {e}")

        # Load enriched data if available
        enriched_path = ENRICHED_SCHOLARS_DIR / f"{aminer_id}.json"
        if enriched_path.exists():
            try:
                enriched_data = load_json_file(str(enriched_path))
                detail.homepage = enriched_data.get("homepage")
                detail.google_scholar = enriched_data.get("google_scholar")
                detail.dblp = enriched_data.get("dblp")
                detail.linkedin = enriched_data.get("linkedin")
                detail.twitter = enriched_data.get("twitter")
                detail.email = enriched_data.get("email")
                detail.orcid = enriched_data.get("orcid")
                detail.semantic_scholar = enriched_data.get("semantic_scholar")
                detail.additional_info = enriched_data.get("additional_info")

                # Load labels if available
                if enriched_data.get("labels"):
                    labels_data = enriched_data["labels"]
                    detail.labels = ScholarLabels(
                        last_updated=labels_data.get("last_updated"),
                        results=[LabelResult(**r) for r in labels_data.get("results", [])]
                    )
            except Exception as e:
                print(f"Error loading enriched data for {aminer_id}: {e}")

    return detail


@app.get("/api/avatar/{aminer_id}")
async def get_avatar(aminer_id: str):
    """
    Get avatar image for a scholar.
    Caches the image locally to avoid repeated remote requests.
    Also caches failed fetches to avoid slow repeated timeouts.
    """
    # Get the original photo URL
    photo_url = get_scholar_photo_url(aminer_id)
    if not photo_url:
        raise HTTPException(status_code=404, detail="No photo URL found")

    # Check if we have a cached version
    cache_path = get_avatar_cache_path(photo_url)
    if cache_path.exists():
        # Determine content type from extension
        ext = cache_path.suffix.lower()
        content_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        content_type = content_types.get(ext, "image/jpeg")
        return FileResponse(cache_path, media_type=content_type)

    # Check if this URL has failed recently
    if is_avatar_fetch_failed(photo_url):
        raise HTTPException(status_code=404, detail="Avatar fetch previously failed")

    # Fetch from remote and cache
    try:
        response = await http_client.get(photo_url)
        if response.status_code != 200:
            mark_avatar_fetch_failed(photo_url)
            raise HTTPException(status_code=404, detail="Remote avatar not found")

        # Get content type
        content_type = response.headers.get("content-type", "image/jpeg")

        # Save to cache
        with open(cache_path, "wb") as f:
            f.write(response.content)

        return Response(content=response.content, media_type=content_type)

    except httpx.RequestError as e:
        mark_avatar_fetch_failed(photo_url)
        raise HTTPException(status_code=502, detail=f"Failed to fetch avatar: {str(e)}")


@app.get("/api/labels", response_model=LabelsConfig)
def get_labels_config():
    """
    Get labels configuration.
    Returns all available label definitions from config/labels.json.
    """
    if not LABELS_CONFIG_PATH.exists():
        raise HTTPException(status_code=404, detail="Labels configuration not found")

    try:
        labels_data = load_json_file(str(LABELS_CONFIG_PATH))
        return LabelsConfig(**labels_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading labels config: {e}")


@app.get("/api/conferences/{conference_id}/scholars/filter", response_model=list[ScholarBasic])
def filter_scholars_by_labels(
    conference_id: str,
    labels: Optional[str] = Query(None, description="Label filters in format 'name:value,name:value' (e.g., 'Chinese:true,Student:false')"),
):
    """
    Filter scholars by label values.
    Only returns scholars where labels match with high confidence.
    """
    conference_dir = DATA_DIR / conference_id
    scholars_path = conference_dir / "scholars.json"

    if not conference_dir.exists():
        raise HTTPException(status_code=404, detail=f"Conference not found: {conference_id}")

    if not scholars_path.exists():
        raise HTTPException(status_code=404, detail=f"Scholars data not found for conference: {conference_id}")

    try:
        scholars_data = load_json_file(str(scholars_path))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading scholars data: {e}")

    talents = scholars_data.get("talents", [])

    # Parse label filters
    label_filters: dict[str, bool] = {}
    if labels:
        for filter_item in labels.split(","):
            if ":" in filter_item:
                name, value = filter_item.split(":", 1)
                name = name.strip()
                value = value.strip().lower()
                if value in ("true", "false"):
                    label_filters[name] = value == "true"

    # If no filters, return all scholars
    if not label_filters:
        scholars = []
        for talent in talents:
            aminer_id = talent.get("aminer_id")
            photo_url = get_scholar_photo(aminer_id)
            scholars.append(ScholarBasic(
                name=talent.get("name", "Unknown"),
                affiliation=talent.get("affiliation"),
                roles=talent.get("roles", []),
                aminer_id=aminer_id,
                photo_url=photo_url,
                description=talent.get("description"),
            ))
        return scholars

    # Filter scholars by labels
    filtered_scholars = []
    for talent in talents:
        aminer_id = talent.get("aminer_id")
        if not aminer_id:
            continue

        # Load enriched data to check labels
        enriched_path = ENRICHED_SCHOLARS_DIR / f"{aminer_id}.json"
        if not enriched_path.exists():
            continue

        try:
            enriched_data = load_json_file(str(enriched_path))
            labels_data = enriched_data.get("labels", {})
            results = labels_data.get("results", [])

            # Check if all filter conditions are met with medium or high confidence
            all_match = True
            for label_name, expected_value in label_filters.items():
                found_match = False
                for result in results:
                    if result.get("name") == label_name:
                        if (result.get("value") == expected_value and
                            result.get("confidence") in ("high", "medium")):
                            found_match = True
                        break
                if not found_match:
                    all_match = False
                    break

            if all_match:
                photo_url = get_scholar_photo(aminer_id)
                filtered_scholars.append(ScholarBasic(
                    name=talent.get("name", "Unknown"),
                    affiliation=talent.get("affiliation"),
                    roles=talent.get("roles", []),
                    aminer_id=aminer_id,
                    photo_url=photo_url,
                    description=talent.get("description"),
                ))
        except Exception:
            continue

    return filtered_scholars


@app.post("/api/cache/clear")
def clear_cache():
    """Clear all cached data (JSON cache only, not avatar cache)."""
    _load_json_file.cache_clear()
    _cache_timestamp.clear()
    return {"status": "cache cleared"}


@app.post("/api/avatar/cache/clear")
def clear_avatar_cache():
    """Clear all cached avatar images."""
    count = 0
    for file in AVATAR_CACHE_DIR.iterdir():
        if file.is_file():
            file.unlink()
            count += 1
    return {"status": "avatar cache cleared", "files_deleted": count}


# ============== AMiner Web API Integration ==============

def get_aminer_web_api_cache_path(scholar_id: str) -> Path:
    """Get cache file path for AMiner web API response."""
    return AMINER_WEB_API_CACHE_DIR / f"{scholar_id}.json"


def is_aminer_cache_valid(cache_path: Path) -> bool:
    """Check if AMiner cache file is still valid (within 15 days)."""
    if not cache_path.exists():
        return False

    cache_age = datetime.now().timestamp() - cache_path.stat().st_mtime
    return cache_age < AMINER_WEB_API_CACHE_TTL


async def fetch_aminer_web_api(
    scholar_id: str,
    authorization: str,
    x_signature: str,
    x_timestamp: str
) -> dict:
    """
    Fetch scholar data from AMiner web API.

    Args:
        scholar_id: AMiner scholar ID
        authorization: Authorization token from header
        x_signature: X-Signature from header
        x_timestamp: X-Timestamp from header

    Returns:
        Raw API response from AMiner web API
    """
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

    logger.info(f"[AMiner API] Fetching scholar data for ID: {scholar_id}")
    logger.debug(f"[AMiner API] Request URL: {url}")
    logger.debug(f"[AMiner API] Request payload: {json.dumps(payload, ensure_ascii=False)}")

    try:
        response = await http_client.post(url, json=payload, headers=headers, timeout=30.0)
        response.raise_for_status()

        result = response.json()
        logger.info(f"[AMiner API] Successfully fetched data for scholar {scholar_id}")
        logger.debug(f"[AMiner API] Full response: {json.dumps(result, ensure_ascii=False, indent=2)}")

        return result
    except httpx.HTTPError as e:
        logger.error(f"[AMiner API] Failed to fetch scholar {scholar_id}: {str(e)}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch from AMiner API: {str(e)}")


def convert_web_api_to_official_format(web_response: dict) -> dict:
    """
    Convert AMiner web API response to official API format.

    Args:
        web_response: Raw response from AMiner web API

    Returns:
        Response in official API format
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


@app.get("/api/aminer/scholar/detail")
async def get_aminer_scholar_detail(
    id: str = Query(..., description="AMiner scholar ID"),
    authorization: Optional[str] = Header(None, description="AMiner authorization token"),
    x_signature: Optional[str] = Header(None, alias="X-Signature", description="AMiner API signature"),
    x_timestamp: Optional[str] = Header(None, alias="X-Timestamp", description="AMiner API timestamp"),
    force_refresh: bool = Query(False, description="Force refresh cache"),
):
    """
    Get scholar detail from AMiner web API with caching.

    This endpoint mimics the official AMiner API format while using the web API internally.
    Responses are cached for 15 days by default.

    Headers required:
    - Authorization: AMiner bearer token
    - X-Signature: Request signature
    - X-Timestamp: Request timestamp

    Query parameters:
    - id: Scholar AMiner ID (required)
    - force_refresh: Force refresh cache (optional, default: false)
    """
    logger.info(f"[API Request] GET /api/aminer/scholar/detail - Scholar ID: {id}, Force Refresh: {force_refresh}")

    # Validate required headers
    if not authorization:
        logger.warning(f"[API Request] Missing Authorization header for scholar {id}")
        raise HTTPException(status_code=400, detail="Authorization header is required")
    if not x_signature:
        logger.warning(f"[API Request] Missing X-Signature header for scholar {id}")
        raise HTTPException(status_code=400, detail="X-Signature header is required")
    if not x_timestamp:
        logger.warning(f"[API Request] Missing X-Timestamp header for scholar {id}")
        raise HTTPException(status_code=400, detail="X-Timestamp header is required")

    # Check cache
    cache_path = get_aminer_web_api_cache_path(id)

    if not force_refresh and is_aminer_cache_valid(cache_path):
        # Return cached response
        cache_age_seconds = datetime.now().timestamp() - cache_path.stat().st_mtime
        cache_age_days = cache_age_seconds / (24 * 60 * 60)
        logger.info(f"[Cache] ✓ Cache HIT for scholar {id} - Age: {cache_age_days:.1f} days ({cache_age_seconds/3600:.1f} hours)")
        logger.info(f"[Cache] Returning cached data from: {cache_path}")

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
            logger.debug(f"[Cache] Cached response: {json.dumps(cached_data, ensure_ascii=False, indent=2)}")
            return cached_data
        except Exception as e:
            # If cache read fails, fetch fresh data
            logger.error(f"[Cache] Failed to read cache for {id}: {e}")
            logger.info(f"[Cache] Falling back to fetching fresh data")
    else:
        if force_refresh:
            logger.info(f"[Cache] ⟳ Force refresh requested for scholar {id}")
        elif not cache_path.exists():
            logger.info(f"[Cache] ✗ Cache MISS for scholar {id} - No cache file found")
        else:
            cache_age_seconds = datetime.now().timestamp() - cache_path.stat().st_mtime
            cache_age_days = cache_age_seconds / (24 * 60 * 60)
            logger.info(f"[Cache] ✗ Cache EXPIRED for scholar {id} - Age: {cache_age_days:.1f} days (TTL: 15 days)")

    # Fetch from AMiner web API
    logger.info(f"[Data Source] Fetching fresh data from AMiner web API for scholar {id}")
    web_response = await fetch_aminer_web_api(id, authorization, x_signature, x_timestamp)

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
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(official_response, f, indent=2, ensure_ascii=False)
        logger.info(f"[Cache] ✓ Cached response for scholar {id} to: {cache_path}")
    except Exception as e:
        logger.error(f"[Cache] Failed to cache response for {id}: {e}")

    logger.info(f"[API Response] Successfully processed scholar {id}")
    return official_response


@app.post("/api/aminer/cache/clear")
def clear_aminer_cache():
    """Clear all cached AMiner web API responses."""
    logger.info("[Cache Management] Clearing all AMiner API cache")
    count = 0
    for file in AMINER_WEB_API_CACHE_DIR.iterdir():
        if file.is_file():
            logger.debug(f"[Cache Management] Deleting cache file: {file.name}")
            file.unlink()
            count += 1
    logger.info(f"[Cache Management] ✓ Cleared {count} cached files")
    return {"status": "aminer cache cleared", "files_deleted": count}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=37801,
        reload=True,
        reload_excludes=["aminer_web_api_cache/*", "avatar_cache/*"]
    )
