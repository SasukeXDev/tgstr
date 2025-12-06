# bot/helper/tmdb.py
import os
import requests
from difflib import SequenceMatcher
import re

TMDB_API_KEY = os.environ.get("TMDB_API_KEY") or "68be78e728be4e86e934df1591d26c5b"
TMDB_BASE_URL = "https://api.themoviedb.org/3"

def clean_title(title: str):
    """
    Extract clean title, year, season, type from raw string
    Example: 'Stranger Things S04 (2016) (Tv)'
    Returns: dict with keys: title, year, season, type
    """
    info = {"title": title, "year": None, "season": None, "type": None}
    t = title

    # Detect type (tv or movie)
    type_match = re.search(r"\((Tv|Movie|tv|movie)\)", t, re.I)
    if type_match:
        info["type"] = type_match.group(1).lower()
        t = t.replace(type_match.group(0), "")

    # Detect year
    year_match = re.search(r"\((\d{4})\)", t)
    if year_match:
        info["year"] = int(year_match.group(1))
        t = t.replace(year_match.group(0), "")

    # Detect season (Sxx)
    season_match = re.search(r"[sS](\d+)", t)
    if season_match:
        info["season"] = int(season_match.group(1))
        t = t.replace(season_match.group(0), "")

    # Clean extra chars
    t = re.sub(r"[^a-zA-Z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    info["title"] = t
    return info

def tmdb_request(endpoint, params=None):
    if params is None:
        params = {}
    params["api_key"] = TMDB_API_KEY
    try:
        resp = requests.get(f"{TMDB_BASE_URL}{endpoint}", params=params, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {}

def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def fetch_poster(raw_title: str) -> str:
    """
    Fetch poster for Movie or TV show.
    Handles seasons for TV shows.
    """
    info = clean_title(raw_title)
    clean_title_str = info["title"]
    year = info["year"]
    season = info["season"]
    type_ = info["type"]

    # 1️⃣ Movie search
    if type_ == "movie":
        data = tmdb_request("/search/movie", {"query": clean_title_str, "year": year})
        results = data.get("results", [])
        if not results:
            data = tmdb_request("/search/movie", {"query": clean_title_str})
            results = data.get("results", [])
        if results:
            # Best match by similarity and year
            best = max(results, key=lambda x: similarity(clean_title_str, x.get("title", "")))
            poster = best.get("poster_path")
            if poster:
                return f"https://image.tmdb.org/t/p/w500{poster}"
    
    # 2️⃣ TV search
    if type_ == "tv":
        data = tmdb_request("/search/tv", {"query": clean_title_str})
        results = data.get("results", [])
        if results:
            # Best match by similarity and year
            best = max(results, key=lambda x: similarity(clean_title_str, x.get("name", "")))
            tv_id = best.get("id")
            # If season specified, fetch season poster
            if tv_id and season:
                season_data = tmdb_request(f"/tv/{tv_id}/season/{season}")
                poster = season_data.get("poster_path")
                if poster:
                    return f"https://image.tmdb.org/t/p/w500{poster}"
            # fallback: use show poster
            poster = best.get("poster_path")
            if poster:
                return f"https://image.tmdb.org/t/p/w500{poster}"

    # 3️⃣ Default fallback image
    return "https://cdn-icons-png.flaticon.com/512/565/565547.png"
