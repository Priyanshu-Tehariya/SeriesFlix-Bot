import asyncio
import aiohttp
import structlog
from aiogram.types import BufferedInputFile
from bot.config import settings

logger = structlog.get_logger(__name__)

# Create a custom ClientTimeout to prevent 20+ second hangs
TMDB_TIMEOUT = aiohttp.ClientTimeout(total=5, connect=3)

TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
POSTER_BROKEN_SENTINEL = "__broken__"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p"

def get_poster_url(poster_path: str | None) -> str | None:
    if not poster_path or poster_path == POSTER_BROKEN_SENTINEL:
        return None  # Fallback to text card or local placeholder
    if poster_path.startswith("http"):
        return poster_path
    
    clean_path = poster_path if poster_path.startswith("/") else "/" + poster_path
    return f"{TMDB_IMAGE_BASE_URL}{clean_path}"

def generate_fallback_poster_bytes() -> bytes:
    import base64
    # A tiny 1x1 solid dark gray PNG to act as a fallback poster
    b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    return base64.b64decode(b64)


async def _try_download_url(
    session: aiohttp.ClientSession, url: str
) -> bytes | None:
    try:
        async with session.get(url, allow_redirects=True) as resp:
            if resp.status == 200:
                data = await resp.read()
                if data:
                    return data
            else:
                logger.warning(f"TMDB image 404/failed ({resp.status}): {url}")
    except Exception as e:
        logger.warning(f"Error fetching {url}: {e}")
    return None

async def fetch_poster_file(
    poster_path: str | None,
) -> tuple[BufferedInputFile | None, bool]:
    """
    Returns (file, tmdb_404).
    - file: BufferedInputFile of poster bytes (from TMDB or fallback placeholder).
    - tmdb_404: True if the poster_path was provided but TMDB returned 404 for
      all sizes, signalling that the caller should purge this path from the DB.
    """
    # Return local fallback image immediately if no path or marked broken
    if not poster_path or poster_path == POSTER_BROKEN_SENTINEL:
        logger.debug("poster_sentinel_hit_or_none", path=poster_path)
        return BufferedInputFile(
            generate_fallback_poster_bytes(), filename="poster.jpg"
        ), False

    # Extract raw image filename if a full URL was passed
    raw_file = poster_path.split("/")[-1]
    if not raw_file.endswith((".jpg", ".png", ".jpeg")):
        return BufferedInputFile(
            generate_fallback_poster_bytes(), filename="poster.jpg"
        ), False

    sizes = ["w500", "original"]
    urls = [f"{TMDB_IMAGE_BASE}/{size}/{raw_file}" for size in sizes]

    timeout = aiohttp.ClientTimeout(total=8, connect=4)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.themoviedb.org/",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    }

    async with aiohttp.ClientSession(
        timeout=timeout, headers=headers
    ) as session:
        tasks = [_try_download_url(session, url) for url in urls]
        results = await asyncio.gather(*tasks)

        for img_bytes in results:
            if img_bytes:
                return BufferedInputFile(img_bytes, filename="poster.jpg"), False

    # All TMDB sizes returned 404 — mark for DB purge
    logger.warning(f"All TMDB sizes 404 for '{poster_path}'. Marking for DB purge.")
    
    # Return local fallback
    return BufferedInputFile(
        generate_fallback_poster_bytes(), filename="poster.jpg"
    ), True


class TMDBClient:
    """Client for fetching TV Series metadata from TMDB."""
    
    BASE_URL = "https://api.themoviedb.org/3"
    
    _genres_cache: dict[int, str] | None = None
    
    @classmethod
    async def _ensure_genres(cls, session: aiohttp.ClientSession) -> None:
        if cls._genres_cache is not None:
            return
            
        cls._genres_cache = {}
        if not settings.TMDB_API_KEY:
            return
            
        url = f"{cls.BASE_URL}/genre/tv/list"
        params = {"api_key": settings.TMDB_API_KEY}
        try:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for g in data.get("genres", []):
                        cls._genres_cache[g["id"]] = g["name"]
        except Exception as e:
            logger.error("tmdb_genres_failed", error=str(e))

    @classmethod
    async def search_series(cls, title: str) -> dict | None:
        """
        Searches TMDB for a TV series by title and returns a metadata dictionary.
        Returns None if not found or if the API key is missing/invalid.
        """
        if not settings.TMDB_API_KEY:
            logger.debug("tmdb_search_skipped", reason="missing_api_key")
            return None
            
        url = f"{cls.BASE_URL}/search/tv"
        params = {
            "api_key": settings.TMDB_API_KEY,
            "query": title,
            "page": 1,
            "include_adult": "false"
        }
        
        try:
            async with aiohttp.ClientSession(timeout=TMDB_TIMEOUT) as session:
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        logger.warning("tmdb_search_failed", status=resp.status, title=title)
                        return None
                        
                    data = await resp.json()
                    
                    if not data.get("results"):
                        return None
                    # Ensure genres are loaded
                    await cls._ensure_genres(session)
                    
                    # Take the first best match
                    result = data["results"][0]
                    
                    # Store raw relative path exactly as TMDB returns it (e.g. /poster.jpg)
                    poster_path = result.get("poster_path")
                    
                    # Map genres
                    genre_ids = result.get("genre_ids", [])
                    genre_names = [cls._genres_cache[gid] for gid in genre_ids if gid in (cls._genres_cache or {})]
                    genres_str = ", ".join(genre_names)
                    
                    # Format rating
                    raw_rating = result.get("vote_average", 0.0)
                    rating_str = f"{raw_rating:.1f}/10" if raw_rating else ""
                    
                    # Parse year
                    air_date = result.get("first_air_date", "")
                    year = air_date.split("-")[0] if air_date else ""
                    
                    return {
                        "name": result.get("name", ""),
                        "poster_url": poster_path,
                        "rating": rating_str,
                        "summary": result.get("overview", ""),
                        "genres": genres_str,
                        "year": year,
                        "tmdb_id": result.get("id"),
                    }
        except Exception as e:
            logger.error(f"TMDB connection failed: {e}. Falling back to internal DB search.", title=title)
            return None

    @classmethod
    async def get_trending_shows(cls) -> list[dict]:
      """Fetch top trending TV shows for today."""
      url = f"{cls.BASE_URL}/trending/tv/day"
      async with aiohttp.ClientSession() as session:
        async with session.get(
            url, params={"api_key": settings.TMDB_API_KEY}
        ) as resp:
          if resp.status == 200:
            data = await resp.json()
            return data.get("results", [])[:10]
      return []

    @classmethod
    async def get_popular_shows(cls) -> list[dict]:
      """Fetch top popular TV shows."""
      url = f"{cls.BASE_URL}/tv/popular"
      async with aiohttp.ClientSession() as session:
        async with session.get(
            url, params={"api_key": settings.TMDB_API_KEY}
        ) as resp:
          if resp.status == 200:
            data = await resp.json()
            return data.get("results", [])[:10]
      return []
