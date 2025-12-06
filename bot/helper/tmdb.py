import re
import requests
from tmdbv3api import TMDb, Movie, TV

# =========================
# TMDb CONFIG
# =========================
TMDB_API_KEY = "68be78e728be4e86e934df1591d26c5b"

tmdb = TMDb()
tmdb.api_key = TMDB_API_KEY
tmdb.language = "en"

movie_api = Movie()
tv_api = TV()


# =========================
# UTIL FUNCTIONS
# =========================
def extract_info(raw_title: str):
    """
    Extract clean title, year, season, forced type
    """
    year = None
    season = None
    force_type = None

    y = re.search(r"\b(19|20)\d{2}\b", raw_title)
    if y:
        year = int(y.group())

    s = re.search(r"(?:S|Season)\s*(\d+)", raw_title, re.I)
    if s:
        season = int(s.group(1))

    if "(movie)" in raw_title.lower():
        force_type = "movie"
    elif "(tv)" in raw_title.lower():
        force_type = "tv"

    clean = re.sub(r"\(.*?\)|\[.*?\]", "", raw_title)
    clean = re.sub(r"[^a-zA-Z0-9\s]", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()

    return clean, year, season, force_type


def best_match(results, search_title, year):
    """
    Safely select best result from TMDb search
    """
    best = None
    best_score = -1

    for r in results:
        # tmdbv3api sometimes returns garbage
        if not hasattr(r, "__dict__"):
            continue

        title = getattr(r, "title", None) or getattr(r, "name", "")
        if not isinstance(title, str):
            continue

        score = getattr(r, "popularity", 0) or 0

        # Title similarity boost
        if search_title.lower() in title.lower():
            score += 40

        # Year match boost
        r_year = None
        date = getattr(r, "release_date", None) or getattr(r, "first_air_date", None)
        if isinstance(date, str) and len(date) >= 4:
            try:
                r_year = int(date[:4])
            except:
                pass

        if year and r_year == year:
            score += 30

        if score > best_score:
            best_score = score
            best = r

    return best


def fetch_season_poster(tv_id: int, season: int):
    """
    Official TMDb season poster endpoint
    """
    url = f"https://api.themoviedb.org/3/tv/{tv_id}/season/{season}"
    params = {
        "api_key": TMDB_API_KEY,
        "language": "en-US"
    }

    try:
        r = requests.get(url, params=params, timeout=5)
        data = r.json()
        if data.get("poster_path"):
            return f"https://image.tmdb.org/t/p/w500{data['poster_path']}"
    except:
        pass

    return None


# =========================
# MAIN POSTER FUNCTION
# =========================
def fetch_poster(title: str) -> str:
    """
    Fetch best poster using TMDb:
    Movie ➜ TV ➜ TV Season ➜ Fallback
    """
    clean_title, year, season, force_type = extract_info(title)

    # -------- MOVIE --------
    if force_type != "tv":
        try:
            movies = movie_api.search(clean_title)
            best_movie = best_match(movies, clean_title, year)
            if best_movie and best_movie.poster_path:
                return f"https://image.tmdb.org/t/p/w500{best_movie.poster_path}"
        except Exception as e:
            print(f"TMDb movie fetch error for '{title}': {e}")

    # -------- TV --------
    try:
        shows = tv_api.search(clean_title)
        best_tv = best_match(shows, clean_title, year)

        if best_tv:
            # ✅ SEASON POSTER (CORRECT METHOD)
            if season:
                season_poster = fetch_season_poster(best_tv.id, season)
                if season_poster:
                    return season_poster

            # ✅ TV SHOW POSTER
            if best_tv.poster_path:
                return f"https://image.tmdb.org/t/p/w500{best_tv.poster_path}"

    except Exception as e:
        print(f"TMDb TV fetch error for '{title}': {e}")

    # -------- FALLBACK --------
    return "https://cdn-icons-png.flaticon.com/512/565/565547.png"
