
# tmdb_season_poster_fetcher.py
import re
import requests
from difflib import SequenceMatcher
from typing import Optional, List, Dict, Tuple

TMDB_API_KEY = "68be78e728be4e86e934df1591d26c5b"   # <<-- put your TMDb key here
TMDB_BASE = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
FALLBACK_IMAGE = "https://cdn-icons-png.flaticon.com/512/565/565547.png"
REQUEST_TIMEOUT = 7


# -------------------------
# Utilities: cleaning / parsing
# -------------------------
def clean_title(raw: str) -> str:
    s = re.sub(r'\[.*?\]|\(.*?\)', ' ', raw)  # remove bracketed content
    s = re.sub(r'\b(720p|1080p|480p|WEB-DL|HDRip|HEVC|x264|x265|10bit|NF|WEB|BluRay|BRRip)\b', ' ', s, flags=re.I)
    s = re.sub(r'\b(Dual Audio|Hindi|English|ORG|HE-AAC|AAC)\b', ' ', s, flags=re.I)
    s = re.sub(r'[^a-zA-Z0-9\s]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def extract_info(raw_title: str) -> Tuple[str, Optional[int], Optional[int], Optional[str]]:
    """
    Return (clean_title, year, season_number, forced_type)
    forced_type can be "movie" or "tv" or None.
    Handles many season patterns: S05, S05V1, S05V, Season 5, season-05 etc.
    """
    year = None
    season = None
    forced_type = None

    # year
    y = re.search(r'\b(19|20)\d{2}\b', raw_title)
    if y:
        try:
            year = int(y.group())
        except:
            year = None

    # season patterns
    # prefer patterns like S05V1 -> S05, S05V -> S05, also S1 or Season 1
    s = (re.search(r'\b[Ss](\d{1,2})(?:V\d+)?\b', raw_title)  # S05 or S05V1 or S05V
         or re.search(r'[Ss]eason[\s:_-]*(\d{1,2})', raw_title, re.I)
         or re.search(r'\bSeason\s*(\d{1,2})', raw_title, re.I))

    if s:
        try:
            season = int(s.group(1))
        except:
            season = None

    low = raw_title.lower()
    if "(movie)" in low or " (movie)" in low:
        forced_type = "movie"
    elif "(tv)" in low or "(series)" in low or " (tv)" in low:
        forced_type = "tv"

    cleaned = clean_title(raw_title)
    if not cleaned:
        # fallback to raw title sanitized
        cleaned = re.sub(r'[^a-zA-Z0-9\s]', ' ', raw_title).strip()

    return cleaned, year, season, forced_type


# -------------------------
# TMDb HTTP helpers
# -------------------------
def tmdb_search_tv(query: str, year: Optional[int] = None) -> List[Dict]:
    params = {"api_key": TMDB_API_KEY, "query": query, "page": 1}
    if year:
        params["first_air_date_year"] = year
    try:
        r = requests.get(f"{TMDB_BASE}/search/tv", params=params, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        return r.json().get("results", [])
    except Exception as e:
        print(f"[tmdb_search_tv] error for '{query}': {e}")
        return []


def tmdb_search_movie(query: str, year: Optional[int] = None) -> List[Dict]:
    params = {"api_key": TMDB_API_KEY, "query": query, "page": 1, "include_adult": False}
    if year:
        params["year"] = year
    try:
        r = requests.get(f"{TMDB_BASE}/search/movie", params=params, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        return r.json().get("results", [])
    except Exception as e:
        print(f"[tmdb_search_movie] error for '{query}': {e}")
        return []


def tmdb_get_season(tv_id: int, season_number: int) -> Optional[Dict]:
    try:
        r = requests.get(f"{TMDB_BASE}/tv/{tv_id}/season/{season_number}",
                         params={"api_key": TMDB_API_KEY, "language": "en-US"},
                         timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        # Do not spam logs — return None
        print(f"[tmdb_get_season] failed tv_id={tv_id} season={season_number}: {e}")
        return None


# -------------------------
# Scoring & picking best result
# -------------------------
def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def score_result(item: Dict, search_title: str, search_year: Optional[int]) -> float:
    """score a search result (movie or tv) — higher is better"""
    item_title = (item.get("title") or item.get("name") or "").strip()
    if not item_title:
        return -999.0

    sim = similarity(search_title, item_title)  # 0..1
    score = sim * 100.0

    # year match
    rd = item.get("release_date") or item.get("first_air_date")
    item_year = None
    if isinstance(rd, str) and len(rd) >= 4:
        try:
            item_year = int(rd[:4])
        except:
            item_year = None

    if search_year and item_year and search_year == item_year:
        score += 40.0

    pop = item.get("popularity") or 0
    votes = item.get("vote_count") or 0
    score += float(pop) * 0.5
    score += (min(votes, 10000) / 1000.0)

    return score


def pick_best(results: List[Dict], search_title: str, search_year: Optional[int]) -> Optional[Dict]:
    best = None
    best_score = -1.0
    for it in results:
        if not isinstance(it, dict):
            continue
        s = score_result(it, search_title, search_year)
        if s > best_score:
            best_score = s
            best = it
    return best


# -------------------------
# Main function: fetch poster (movie / tv / season)
# -------------------------
def fetch_poster(raw_title: str) -> str:
    """
    Public entry point:
      - Extract clean title, year, season, forced type
      - Search movie/tv accordingly
      - If season requested and best_show found, call /tv/{id}/season/{season}
      - Return season poster if present, otherwise show poster, otherwise movie poster, otherwise fallback
    """
    cleaned, year, season, forced = extract_info(raw_title)
    # debug
    #print(f"[debug] cleaned='{cleaned}', year={year}, season={season}, forced={forced}")

    # if user forced movie
    if forced == "movie":
        movies = tmdb_search_movie(cleaned, year)
        best_movie = pick_best(movies, cleaned, year)
        if best_movie and best_movie.get("poster_path"):
            return IMAGE_BASE + best_movie["poster_path"]
        # else fall through to tv attempt

    # if user forced tv
    if forced == "tv":
        shows = tmdb_search_tv(cleaned, year)
        best_show = pick_best(shows, cleaned, year)
        if best_show:
            tv_id = best_show.get("id")
            # get season poster if requested
            if season and isinstance(tv_id, int):
                season_data = tmdb_get_season(tv_id, season)
                if season_data and season_data.get("poster_path"):
                    return IMAGE_BASE + season_data["poster_path"]
                else:
                    print(f"[info] season poster missing for tv_id={tv_id} season={season} (falling back to show poster)")
            # fallback to show poster
            if best_show.get("poster_path"):
                return IMAGE_BASE + best_show["poster_path"]
        # if forced tv but no show, do not try movie? we still try fallback below

    # Auto: Try movie first
    movies = tmdb_search_movie(cleaned, year)
    best_movie = pick_best(movies, cleaned, year)
    if best_movie and best_movie.get("poster_path"):
        return IMAGE_BASE + best_movie["poster_path"]

    # Auto: Try TV
    shows = tmdb_search_tv(cleaned, year)
    best_show = pick_best(shows, cleaned, year)
    if best_show:
        tv_id = best_show.get("id")
        if season and isinstance(tv_id, int):
            # attempt season poster with debug + retries
            season_data = tmdb_get_season(tv_id, season)
            if season_data and season_data.get("poster_path"):
                return IMAGE_BASE + season_data["poster_path"]
            else:
                print(f"[info] season poster not found for '{raw_title}' -> tv_id={tv_id}, season={season}")
        # fallback to show poster
        if best_show.get("poster_path"):
            return IMAGE_BASE + best_show["poster_path"]

    # final fallback
    return FALLBACK_IMAGE
