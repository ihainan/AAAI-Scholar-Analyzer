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
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

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

# Avatar cache directory (writable, separate from read-only data)
AVATAR_CACHE_DIR = Path(os.environ.get("AVATAR_CACHE_DIR", Path(__file__).parent / "avatar_cache"))
AVATAR_CACHE_DIR.mkdir(parents=True, exist_ok=True)

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=37801, reload=True)
