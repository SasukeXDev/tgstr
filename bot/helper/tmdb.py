# bot/helper/tmdb.py
import os
import re
import requests
from difflib import SequenceMatcher

TMDB_API_KEY = os.environ.get("TMDB_API_KEY") or "68be78e728be4e86e934df1591d26c5b"
TMDB_BASE_URL = "https://api.themoviedb.org/3"

def clean_title_info(raw_title: str):
    """
    Extract clean title, year, season, type from raw string.
    Example: 'Stranger Things S04 (2016) (Tv)'
    Returns: dict with keys: title, year, season, type
    """
    info = {"title": raw_title, "year": None, "season": None, "type": None}
    t = raw_title

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

def score_match(item, search_title, search_year=None, is_tv=False):
    """
    Score TMDb result for best match.
    +50 for title similarity, +40 for year match, +popularity
    """
    score = 0
    tmdb_title = item.get("name") if is_tv else item.get("title")
    tmdb_year = None
    if is_tv and "first_air_date" in item and item["first_air_date"]:
        tmdb_year = int(item["first_air_date"][:4])
    elif not is_tv and "release_date" in item and item["release_date"]:
        tmdb_year = int(item["release_date"][:4])

    # Title similarity
    if tmdb_title:
        score += 50 * similarity(search_title, tmdb_title)

    # Year match
    if search_year and tmdb_year == search_year:
        score += 40

    # Popularity
    if "popularity" in item and item["popularity"]:
        score += item["popularity"]

    return score

def fetch_poster(raw_title: str) -> str:
    """
    Fetch poster for Movie or TV show.
    Handles seasons for TV shows and best match scoring.
    """
    info = clean_title_info(raw_title)
    title_str = info["title"]
    year = info["year"]
    season = info["season"]
    type_ = info["type"]

    # ---------- Movie ----------
    if type_ == "movie":
        data = tmdb_request("/search/movie", {"query": title_str, "year": year})
        results = data.get("results", [])
        if not results:
            data = tmdb_request("/search/movie", {"query": title_str})
            results = data.get("results", [])

        if results:
            # Best match by score
            best = max(results, key=lambda x: score_match(x, title_str, year, is_tv=False))
            poster = best.get("poster_path")
            if poster:
                return f"https://image.tmdb.org/t/p/w500{poster}"

    # ---------- TV ----------
    if type_ == "tv":
        data = tmdb_request("/search/tv", {"query": title_str})
        results = data.get("results", [])
        if results:
            # Best match by score
            best = max(results, key=lambda x: score_match(x, title_str, year, is_tv=True))
            tv_id = best.get("id")

            # Season poster if available
            if tv_id and season:
                season_data = tmdb_request(f"/tv/{tv_id}/season/{season}")
                poster = season_data.get("poster_path")
                if poster:
                    return f"https://image.tmdb.org/t/p/w500{poster}"

            # Fallback: show poster
            poster = best.get("poster_path")
            if poster:
                return f"https://image.tmdb.org/t/p/w500{poster}"

    # ---------- Auto-detect if type not forced ----------
    # Movie search
    data = tmdb_request("/search/movie", {"query": title_str, "year": year})
    results = data.get("results", [])
    if results:
        best = max(results, key=lambda x: score_match(x, title_str, year, is_tv=False))
        poster = best.get("poster_path")
        if poster:
            return f"https://image.tmdb.org/t/p/w500{poster}"

    # TV search
    data = tmdb_request("/search/tv", {"query": title_str})
    results = data.get("results", [])
    if results:
        best = max(results, key=lambda x: score_match(x, title_str, year, is_tv=True))
        tv_id = best.get("id")

        if tv_id and season:
            season_data = tmdb_request(f"/tv/{tv_id}/season/{season}")
            poster = season_data.get("poster_path")
            if poster:
                return f"https://image.tmdb.org/t/p/w500{poster}"

        poster = best.get("poster_path")
        if poster:
            return f"https://image.tmdb.org/t/p/w500{poster}"

    # ---------- Default fallback ----------
    return "https://cdn-icons-png.flaticon.com/512/565/565547.png"
