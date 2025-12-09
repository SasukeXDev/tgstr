# bot/helper/tmdb.py
"""
Robust TMDb poster fetcher that:
- Cleans noisy filenames (removes ep/part/combined/resolution/uploader noise)
- Extracts: clean title, year, season number, forced type (movie/tv)
- Searches TMDb (REST API) and scores results by similarity + year + popularity
- For TV shows with season number: fetches season poster via /tv/{tv_id}/season/{season}
- Falls back to show poster if season poster missing, or movie poster, or default image
- Safe against various noisy inputs like:
    "Stranger Things S04 Ep1/part1 (2016) (Tv)"
    "Show.Name.S1E02.720p.x265.Part1 [Uploader]"
- Requires only `requests` (add to requirements.txt)
"""

import os
import re
import math
import requests
from difflib import SequenceMatcher
from typing import Optional, Tuple, Dict

TMDB_API_KEY = os.environ.get("TMDB_API_KEY") or "68be78e728be4e86e934df1591d26c5b"
TMDB_BASE_URL = "https://api.themoviedb.org/3"
POSTER_BASE = "https://image.tmdb.org/t/p/w500"
FALLBACK_POSTER = "https://cdn-icons-png.flaticon.com/512/565/565547.png"
HTTP_TIMEOUT = 6.0


# -------------------------
# Utility helpers
# -------------------------
def _tmdb_get(endpoint: str, params: Optional[Dict] = None) -> dict:
    if params is None:
        params = {}
    params = params.copy()
    params["api_key"] = TMDB_API_KEY
    try:
        resp = requests.get(f"{TMDB_BASE_URL}{endpoint}", params=params, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        return resp.json() or {}
    except Exception:
        return {}


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _build_poster_url(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    return f"{POSTER_BASE}{path}"


# -------------------------
# Title cleaning & extraction
# -------------------------
def clean_and_extract(raw: str) -> Tuple[str, Optional[int], Optional[int], Optional[str]]:
    """
    Returns: (clean_title, year, season_number, forced_type)
    forced_type: "movie" | "tv" | None
    This aggressively strips episode/part/resolution/uploader noise.
    """
    if not raw:
        return "", None, None, None

    s = raw.strip()

    # Normalize separators to spaces
    s = s.replace('.', ' ').replace('_', ' ').replace('-', ' ')
    s = re.sub(r'\s+/+\s*', ' ', s)  # remove stray slashes groups

    # Forced type: look for explicit (tv) or (movie) or trailing markers
    forced = None
    m = re.search(r"\((tv|movie|series|film)\)", s, flags=re.I)
    if m:
        forced = "tv" if m.group(1).lower().startswith("tv") or m.group(1).lower().startswith("series") else "movie"
        s = s.replace(m.group(0), ' ')

    # Year: first 4-digit 19xx or 20xx in parentheses or standalone
    y = re.search(r"\b(19|20)\d{2}\b", s)
    year = int(y.group()) if y else None
    if y:
        # remove the exact match substring
        s = re.sub(rf"\b{y.group()}\b", " ", s)

    # Season: look for Season 1, S01, S1, series S1, or 'season1'
    season = None
    s_match = re.search(r"(?:season[\s\-]*|s)(\d{1,3})(?!\d)", s, flags=re.I)
    if s_match:
        try:
            season = int(s_match.group(1))
            s = re.sub(re.escape(s_match.group(0)), " ", s, flags=re.I)
        except Exception:
            season = None

    # Remove episode/part markers and ranges: E01, Ep1, Ep01, E01-E05, Ep1/part1, part1, combined
    s = re.sub(r'\b(e(?:p|pisode)?\d{1,3})(?:[-/–]\d{1,3})?\b', ' ', s, flags=re.I)   # ep1, e01, episode01, e01-04
    s = re.sub(r'\b(part|pt)\s*\d{1,3}\b', ' ', s, flags=re.I)                           # part1, pt1
    s = re.sub(r'\b(combined|complete|full|multi)\b', ' ', s, flags=re.I)

    # Remove common noise tokens
    noise_tokens = r'\b(720p|1080p|480p|2160p|4k|hd|webrip|web-dl|webdl|hdrip|bluray|brrip|x264|x265|hevc|10bit|dual audio|dd5 1|aac|h264|nf|remux|proper)\b'
    s = re.sub(noise_tokens, ' ', s, flags=re.I)

    # Remove uploader tags or bracketed groups like [Uploader] or (Group)
    s = re.sub(r'\[.*?\]|\(.*?\)', ' ', s)

    # Remove any leftover non-alphanum (preserve spaces)
    s = re.sub(r'[^A-Za-z0-9\s]', ' ', s)

    # Collapse whitespace
    cleaned = re.sub(r'\s+', ' ', s).strip()

    # If cleaned ends up empty, fallback to raw simplified
    if not cleaned:
        cleaned = re.sub(r'[^A-Za-z0-9\s]', ' ', raw).strip()

    return cleaned, year, season, forced


# -------------------------
# Scoring & matching
# -------------------------
def _score_item(item: dict, search_title: str, search_year: Optional[int], is_tv: bool) -> float:
    """
    Score a TMDb search result item (dict) for relevance.
    Factors:
     - Title similarity (heavily weighted)
     - Year match (bonus)
     - Popularity (small bonus)
     - vote_count (small bonus)
    """
    # Get candidate title (name for TV, title for movie)
    candidate_title = (item.get("name") or item.get("title") or "") or ""
    sim = _similarity(search_title, candidate_title)  # 0..1

    # candidate year
    rdate = item.get("first_air_date") if is_tv else item.get("release_date")
    cand_year = None
    if isinstance(rdate, str) and len(rdate) >= 4:
        try:
            cand_year = int(rdate[:4])
        except Exception:
            cand_year = None

    year_bonus = 0.0
    if search_year and cand_year and search_year == cand_year:
        year_bonus = 0.35  # 35% boost when year matches

    # popularity/vote_count scaled
    pop = float(item.get("popularity") or 0.0)
    vc = float(item.get("vote_count") or 0.0)
    pop_score = math.log1p(pop) / 10.0    # small
    vote_score = math.log1p(vc) / 20.0    # small

    # final score: similarity major + bonuses
    score = (sim * 0.65) + year_bonus + pop_score + vote_score
    return score


def _choose_best(results: list, search_title: str, search_year: Optional[int], is_tv: bool):
    """
    Choose best result dict from TMDb search results using _score_item.
    Returns the best dict or None.
    """
    if not results:
        return None
    best = None
    best_score = -1.0
    for r in results:
        if not isinstance(r, dict):
            # some libraries return objects; try to coerce
            try:
                r = dict(r)
            except Exception:
                continue
        # require candidate title
        if not (r.get("title") or r.get("name")):
            continue
        try:
            sc = _score_item(r, search_title, search_year, is_tv)
        except Exception:
            sc = 0.0
        if sc > best_score:
            best_score = sc
            best = r
    return best


# -------------------------
# TMDb search helpers
# -------------------------
def _search_movie(query: str, year: Optional[int] = None) -> list:
    params = {"query": query, "include_adult": "false", "page": 1}
    if year:
        # movie search supports 'year' query param
        params["year"] = year
    data = _tmdb_get("/search/movie", params)
    return data.get("results", []) if isinstance(data, dict) else []


def _search_tv(query: str) -> list:
    params = {"query": query, "page": 1}
    data = _tmdb_get("/search/tv", params)
    return data.get("results", []) if isinstance(data, dict) else []


def _get_season_poster(tv_id: int, season_number: int) -> Optional[str]:
    if not tv_id or not season_number:
        return None
    data = _tmdb_get(f"/tv/{tv_id}/season/{season_number}", {"language": "en-US"})
    if isinstance(data, dict) and data.get("poster_path"):
        return _build_poster_url(data.get("poster_path"))
    return None


# -------------------------
# Public function
# -------------------------
def fetch_poster(raw_title: str) -> str:
    """
    Main entrypoint.
    Given raw_title (e.g. "Stranger Things S04 Ep1/part1 (2016) (Tv)"),
    returns best poster URL (season poster if available) or fallback.
    """
    try:
        clean_title, year, season, forced_type = clean_and_extract(raw_title)
        if not clean_title:
            return FALLBACK_POSTER

        # If forced movie
        if forced_type == "movie":
            movies = _search_movie(clean_title, year)
            best = _choose_best(movies, clean_title, year, is_tv=False)
            if best and best.get("poster_path"):
                return _build_poster_url(best.get("poster_path"))
            return FALLBACK_POSTER

        # If forced tv
        if forced_type == "tv":
            shows = _search_tv(clean_title)
            best = _choose_best(shows, clean_title, year, is_tv=True)
            if best:
                # season poster preferred
                if season:
                    season_poster = _get_season_poster(best.get("id"), season)
                    if season_poster:
                        return season_poster
                # fallback to show poster
                if best.get("poster_path"):
                    return _build_poster_url(best.get("poster_path"))
            return FALLBACK_POSTER

        # Auto-detect: try movies first
        movies = _search_movie(clean_title, year)
        best_movie = _choose_best(movies, clean_title, year, is_tv=False)
        if best_movie and best_movie.get("poster_path"):
            return _build_poster_url(best_movie.get("poster_path"))

        # Then try TV
        shows = _search_tv(clean_title)
        best_show = _choose_best(shows, clean_title, year, is_tv=True)
        if best_show:
            if season:
                season_poster = _get_season_poster(best_show.get("id"), season)
                if season_poster:
                    return season_poster
            if best_show.get("poster_path"):
                return _build_poster_url(best_show.get("poster_path"))

        return FALLBACK_POSTER

    except Exception:
        return FALLBACK_POSTER
