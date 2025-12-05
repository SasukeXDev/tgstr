from tmdbv3api import TMDb, Movie, TV
import re
import requests

tmdb = TMDb()
tmdb.api_key = "68be78e728be4e86e934df1591d26c5b"
tmdb.language = 'en'

movie_api = Movie()
tv_api = TV()


def extract_title_info(title: str):
    """
    Extract clean title, year, season number, and forced media type
    """
    # YEAR (1990–2099)
    year_match = re.search(r"\b(19|20)\d{2}\b", title)
    year = int(year_match.group()) if year_match else None

    # SEASON NUMBER
    season_match = re.search(r"[Ss]eason\s?(\d+)", title) or re.search(r"[Ss](\d+)", title)
    season_number = int(season_match.group(1)) if season_match else None

    # FORCE TYPE
    mtype = None
    if "(movie)" in title.lower():
        mtype = "movie"
    elif "(tv)" in title.lower() or "(series)" in title.lower() or "(show)" in title.lower():
        mtype = "tv"

    # CLEAN TITLE FOR SEARCH
    cleaned = re.sub(r"\(.*?\)", "", title)              # remove (xxx)
    cleaned = re.sub(r"[Ss]eason\s?\d+", "", cleaned)    # remove Season 2
    cleaned = re.sub(r"[Ss]\d+", "", cleaned)            # remove S02
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", cleaned)    # remove symbols
    cleaned = cleaned.strip()

    return cleaned, year, season_number, mtype


def get_title(obj):
    """
    Safely get title or name
    """
    if hasattr(obj, "title") and obj.title:
        return obj.title
    if hasattr(obj, "name") and obj.name:
        return obj.name
    return ""


def get_year(obj):
    """
    Safely extract year from movie or tv object
    """
    date = None

    if hasattr(obj, "release_date") and obj.release_date:
        date = obj.release_date
    elif hasattr(obj, "first_air_date") and obj.first_air_date:
        date = obj.first_air_date

    if date and len(date) >= 4:
        return int(date[:4])

    return None


def get_best_match(results, search_title, search_year=None):
    """
    Scoring system:
    +40 if year matches
    +50 if title similarity
    +popularity weight
    """
    if not results:
        return None

    search_title = search_title.lower()
    best = None
    best_score = -999

    for r in results:
        title = get_title(r).lower()
        score = 0

        # Title similarity
        if search_title in title:
            score += 50

        # Year match
        item_year = get_year(r)
        if search_year and item_year == search_year:
            score += 40

        # Popularity
        if hasattr(r, "popularity") and r.popularity:
            score += r.popularity

        if score > best_score:
            best_score = score
            best = r

    return best


def fetch_tmdb_season_poster(tv_id, season_number):
    """Fetch season poster safely."""
    try:
        season = tv_api.season(tv_id, season_number)
        if season and hasattr(season, "poster_path") and season.poster_path:
            return f"https://image.tmdb.org/t/p/w500{season.poster_path}"
    except:
        pass
    return None


def fetch_poster(title: str) -> str:
    cleaned_title, year, season_number, forced_type = extract_title_info(title)

    # ---------- 1. Forced movie ----------
    if forced_type == "movie":
        movies = movie_api.search(cleaned_title)
        best = get_best_match(movies, cleaned_title, year)
        if best and hasattr(best, "poster_path") and best.poster_path:
            return f"https://image.tmdb.org/t/p/w500{best.poster_path}"

    # ---------- 2. Forced TV ----------
    if forced_type == "tv":
        shows = tv_api.search(cleaned_title)
        best = get_best_match(shows, cleaned_title, year)

        if best:
            # Season poster if available
            if season_number:
                season_poster = fetch_tmdb_season_poster(best.id, season_number)
                if season_poster:
                    return season_poster

            # Default series poster
            if hasattr(best, "poster_path") and best.poster_path:
                return f"https://image.tmdb.org/t/p/w500{best.poster_path}"

    # ---------- 3. Auto-detect: try movie ----------
    movies = movie_api.search(cleaned_title)
    best_movie = get_best_match(movies, cleaned_title, year)
    if best_movie and hasattr(best_movie, "poster_path") and best_movie.poster_path:
        return f"https://image.tmdb.org/t/p/w500{best_movie.poster_path}"

    # ---------- 4. Auto-detect: try TV ----------
    shows = tv_api.search(cleaned_title)
    best_show = get_best_match(shows, cleaned_title, year)

    if best_show:
        # Season poster
        if season_number:
            season_poster = fetch_tmdb_season_poster(best_show.id, season_number)
            if season_poster:
                return season_poster

        # TV show poster
        if hasattr(best_show, "poster_path") and best_show.poster_path:
            return f"https://image.tmdb.org/t/p/w500{best_show.poster_path}"

    # ---------- 5. FINAL FALLBACK ----------
    return "https://cdn-icons-png.flaticon.com/512/565/565547.png"
