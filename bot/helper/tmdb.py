from tmdbv3api import TMDb, Movie, TV
import requests

tmdb = TMDb()
tmdb.api_key = "68be78e728be4e86e934df1591d26c5b"
tmdb.language = 'en'

# AniList GraphQL API endpoint
ANILIST_API_URL = "https://graphql.anilist.co"

def clean_title(title: str) -> str:
    """
    Clean title for better API search results
    """
    import re
    # Remove extra info like resolution, audio, brackets, etc.
    title = re.sub(r'\[.*?\]', '', title)
    title = re.sub(r'\(.*?\)', '', title)
    title = re.sub(r'\d{3,4}p|HEVC|HDRip|WEB-DL|x264|x265|(720p|1080p|480p|WEB-DL|HDRip|HEVC|x264|x265|Dual Audio|Hindi|English|ORG)', '', title, flags=re.I)
    title = re.sub(r'[^a-zA-Z0-9\s]', ' ', title)
    return title.strip()

def fetch_anilist_poster(title: str):
    """
    Fetch anime poster from AniList API
    """
    query = '''
    query ($search: String) {
      Media(search: $search, type: ANIME) {
        title {
          romaji
          english
          native
        }
        coverImage {
          large
        }
      }
    }
    '''
    variables = {"search": title}
    try:
        response = requests.post(ANILIST_API_URL, json={'query': query, 'variables': variables}, timeout=5)
        response.raise_for_status()
        data = response.json()
        poster = data.get('data', {}).get('Media', {}).get('coverImage', {}).get('large')
        if poster:
            return poster
    except Exception as e:
        return None
    return None

def fetch_tmdb_poster(title: str):
    """
    Fetch movie/TV poster from TMDb
    """
    m = Movie()
    tv = TV()
    try:
        movies = m.search(title)
        if movies:
            poster = movies[0].poster_path
            if poster:
                return f"https://image.tmdb.org/t/p/w500{poster}"
        shows = tv.search(title)
        if shows:
            poster = shows[0].poster_path
            if poster:
                return f"https://image.tmdb.org/t/p/w500{poster}"
    except Exception as e:
        return None
    return None

def fetch_poster(title: str) -> str:
    """
    Fetch poster for movie, TV show, or anime
    """
    clean = clean_title(title)
    
    # 1️⃣ Try TMDb (movie/TV)
    poster = fetch_tmdb_poster(clean)
    if poster:
        return poster

    # 2️⃣ Fallback: AniList (anime)
    poster = fetch_anilist_poster(clean)
    if poster:
        return poster

    # 3️⃣ Fallback: default image
    return "https://cdn-icons-png.flaticon.com/512/565/565547.png"
